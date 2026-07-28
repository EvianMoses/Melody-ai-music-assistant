"""Google OpenID Connect sign-in and YouTube authorization (Phase 5 §5.2).

Implements AUTH-001…006 plus the disconnect/revoke half of AUTH-007:

- **AUTH-001** Google OpenID Connect for basic application identity.
- **AUTH-002** Authorization Code Flow, executed server-side.
- **AUTH-003** `state`, `nonce`, callback origin, and session binding validated.
- **AUTH-004** Basic identity scopes (`openid email profile`) requested first.
- **AUTH-005** YouTube write scope requested *incrementally*, only on demand.
- **AUTH-006** Tokens encrypted at rest (`contracts.token_crypto`), never in the
  session cookie.

Section 2.2 puts "OAuth start/callback UX" in the Flask app and explicitly
forbids OAuth in the Recommendation and RAG services, so the whole flow lives
here.

**Authlib is used deliberately**, departing from the raw-httpx pattern used for
the YouTube and RAG clients, for the same reason the project uses the official
`anthropic` SDK: OIDC requires ID-token validation against Google's rotating
JWKS plus state/nonce correlation, and hand-rolling that is a well-known source
of authentication vulnerabilities.

Tokens never appear in a response body or a log line: the status endpoint
returns only connection metadata, mirroring §1.12's rule that "raw tokens must
never pass through client-visible n8n output".
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for
from sqlalchemy import select
from sqlalchemy.orm import Session

from contracts.db_models import GuestSession, OAuthAccount, User
from contracts.token_crypto import TokenCryptoError, encrypt, encrypt_optional

logger = logging.getLogger("melody.auth.google")

PROVIDER = "google"
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# AUTH-004: identity scopes only at first contact.
IDENTITY_SCOPES = ["openid", "email", "profile"]
# AUTH-005: requested incrementally, only when the user opts into export.
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube"]

# AUTH-003: the session key holding the id the flow was started under, so a
# state token replayed into a different browser session is rejected.
_FLOW_SESSION_BINDING_KEY = "google_oauth_bound_session"

bp = Blueprint("auth_google", __name__)
oauth = OAuth()
_session_factory = None


def init_app(app, session_factory) -> None:
    """Register the Google client and the DB session factory on the app."""
    global _session_factory
    _session_factory = session_factory

    oauth.init_app(app)
    oauth.register(
        name=PROVIDER,
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={"scope": " ".join(IDENTITY_SCOPES)},
    )
    app.register_blueprint(bp)


def is_configured() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


def _redirect_uri() -> str:
    """AUTH-003 (callback origin): pinned by configuration rather than derived
    from the incoming request, so a spoofed Host header cannot redirect the
    code elsewhere. Google independently enforces it against the registered URI."""
    configured = (os.getenv("GOOGLE_REDIRECT_URI") or "").strip()
    return configured or url_for("auth_google.callback", _external=True)


def _not_configured_response():
    return (
        jsonify(
            {
                "ok": False,
                "error": {
                    "code": "FEATURE_DISABLED",
                    "message": "Google sign-in is not configured on this server.",
                },
            }
        ),
        503,
    )


def _canonical_host_redirect(endpoint: str):
    """Send the browser to the callback's own origin before starting the flow.

    Cookies are scoped by host, and `localhost` and `127.0.0.1` are *different*
    hosts even though they are the same machine. So when the app is browsed at
    one and GOOGLE_REDIRECT_URI points at the other, the session cookie set
    while starting the flow is simply never sent to the callback: the flow
    binding key is missing and sign-in fails with INVALID_OAUTH_STATE, having
    done everything else correctly. Observed live on 2026-07-26 with the app on
    http://localhost:5000 and the redirect URI on http://127.0.0.1:5000.

    Rather than require the two to be configured identically, start the flow on
    whichever origin the callback will land on, so the entire exchange happens
    within one cookie scope. Returns None when the host already matches.
    """
    configured = (os.getenv("GOOGLE_REDIRECT_URI") or "").strip()
    if not configured:
        return None
    target = urlparse(configured)
    if not target.netloc or target.netloc == request.host:
        return None
    logger.info(
        "google_oauth_host_realign: starting the flow on %s so the session "
        "cookie is set on the callback's own origin",
        target.netloc,
    )
    return redirect(f"{target.scheme}://{target.netloc}{url_for(endpoint)}")


@bp.route("/auth/google/login")
def login():
    """AUTH-001/002/004: start the Authorization Code Flow, identity scopes only."""
    if not is_configured():
        return _not_configured_response()

    realign = _canonical_host_redirect("auth_google.login")
    if realign is not None:
        return realign

    session[_FLOW_SESSION_BINDING_KEY] = session.get("session_id")
    return oauth.google.authorize_redirect(
        _redirect_uri(),
        # Required to receive a refresh token at all; without prompt=consent
        # Google omits it on repeat authorizations.
        access_type="offline",
        prompt="consent",
    )


@bp.route("/auth/google/upgrade")
def upgrade():
    """AUTH-005: request the YouTube scope incrementally.

    ``include_granted_scopes`` makes Google *add* to the existing grant rather
    than replace it, so the identity scopes survive the upgrade.
    """
    if not is_configured():
        return _not_configured_response()

    realign = _canonical_host_redirect("auth_google.upgrade")
    if realign is not None:
        return realign

    session[_FLOW_SESSION_BINDING_KEY] = session.get("session_id")
    return oauth.google.authorize_redirect(
        _redirect_uri(),
        scope=" ".join(IDENTITY_SCOPES + YOUTUBE_SCOPES),
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )


@bp.route("/auth/google/callback")
def callback():
    """AUTH-002/003/006: complete the exchange and persist encrypted tokens."""
    if not is_configured():
        return _not_configured_response()

    # AUTH-003 (session binding). Authlib already validates `state` and `nonce`;
    # this additionally ties the flow to the browser session that began it, so a
    # state token lifted into another session cannot complete the exchange.
    bound = session.pop(_FLOW_SESSION_BINDING_KEY, None)
    if bound is None or bound != session.get("session_id"):
        # Distinguish the two causes: "no session at all" almost always means
        # the cookie never arrived (a host/scheme mismatch between the page and
        # this callback), whereas a *changed* id means the session was replaced
        # mid-flow. They need different fixes, so don't report them identically.
        no_session_at_all = bound is None
        logger.warning(
            "google_oauth_session_binding_mismatch: %s (host=%s, secure_cookie=%s)",
            "no flow binding in session -- the session cookie did not reach the callback"
            if no_session_at_all
            else "session id changed during the flow",
            request.host,
            current_app.config.get("SESSION_COOKIE_SECURE"),
        )
        return (
            jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "INVALID_OAUTH_STATE",
                        "message": (
                            "Sign-in could not be completed because the browser did not send "
                            "its session to this address. Open the app at "
                            f"{request.host_url.rstrip('/')} and sign in from there — "
                            "GOOGLE_REDIRECT_URI must use the same host you browse the app on."
                            if no_session_at_all
                            else "Sign-in session did not match. Please try again."
                        ),
                    },
                }
            ),
            400,
        )

    try:
        # Validates `state` and the ID token (signature via Google's JWKS,
        # issuer, audience, expiry, and `nonce`).
        token = oauth.google.authorize_access_token()
    except Exception as exc:  # authlib raises several distinct error types
        logger.warning("google_oauth_exchange_failed: %s", type(exc).__name__)
        return (
            jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "OAUTH_EXCHANGE_FAILED",
                        "message": "Could not complete Google sign-in. Please try again.",
                    },
                }
            ),
            400,
        )

    claims = token.get("userinfo") or {}
    subject = claims.get("sub")
    email = claims.get("email")
    if not subject:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "OAUTH_EXCHANGE_FAILED",
                        "message": "Google did not return an account identifier.",
                    },
                }
            ),
            400,
        )

    try:
        with _session_factory() as db:
            user = _upsert_user(db, subject=subject, email=email, claims=claims)
            _link_guest_session(db, user)
            _upsert_oauth_account(db, user=user, subject=subject, token=token)
            db.commit()
            user_id = str(user.id)
    except TokenCryptoError as exc:
        # Misconfiguration, not user error -- and never store a plaintext token.
        logger.error("google_oauth_token_encryption_failed: %s", exc)
        return (
            jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "SERVER_MISCONFIGURED",
                        "message": "Server is not configured to store credentials securely.",
                    },
                }
            ),
            500,
        )

    session["user_id"] = user_id
    logger.info("google_oauth_connected", extra={"user_id": user_id})
    return redirect("/")


def _upsert_user(db: Session, *, subject: str, email: Optional[str], claims: dict) -> User:
    """Find-or-create the application user.

    Matched on the provider's stable ``sub`` via ``oauth_accounts`` first, and
    only then on email -- a user can change their Google email address, so
    ``sub`` is the durable key.
    """
    existing = db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == PROVIDER,
            OAuthAccount.provider_account_id == subject,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return db.get(User, existing.user_id)

    if email:
        by_email = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if by_email is not None:
            return by_email

    user = User(
        email=email,
        display_name=claims.get("name"),
        locale=(claims.get("locale") or "en")[:16],
        account_state="active",
    )
    db.add(user)
    db.flush()  # assign the PK before it is referenced
    return user


def _link_guest_session(db: Session, user: User) -> None:
    """Attach the current guest session to the now-identified user.

    ``guest_sessions.migrated_user_id`` exists in the schema for exactly this
    transition; without it a signing-in visitor's guest history is orphaned.
    """
    guest_id = session.get("session_id")
    if not guest_id:
        return
    try:
        guest_uuid = uuid.UUID(str(guest_id))
    except ValueError:
        return
    guest = db.get(GuestSession, guest_uuid)
    if guest is not None and guest.migrated_user_id is None:
        guest.migrated_user_id = user.id


def _upsert_oauth_account(db: Session, *, user: User, subject: str, token: dict) -> None:
    """AUTH-006: persist the grant with both tokens encrypted at rest."""
    access_ciphertext, key_id = encrypt(token["access_token"])
    refresh_ciphertext, _ = encrypt_optional(token.get("refresh_token"))

    expires_at = None
    if token.get("expires_at"):
        expires_at = datetime.fromtimestamp(int(token["expires_at"]), tz=timezone.utc)
    elif token.get("expires_in"):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token["expires_in"]))

    granted = (token.get("scope") or "").split()

    account = db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == PROVIDER,
            OAuthAccount.provider_account_id == subject,
        )
    ).scalar_one_or_none()

    if account is None:
        account = OAuthAccount(
            user_id=user.id, provider=PROVIDER, provider_account_id=subject
        )
        db.add(account)

    account.encrypted_access_token = access_ciphertext
    account.encryption_key_id = key_id
    # Google omits the refresh token when one was already issued and still
    # valid; keep the stored one rather than nulling a working credential.
    if refresh_ciphertext is not None:
        account.encrypted_refresh_token = refresh_ciphertext
    account.scopes = granted or list(account.scopes or [])
    account.expires_at = expires_at
    account.revoked_at = None


def _current_account(db: Session) -> Optional[OAuthAccount]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        return None
    return db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user_uuid, OAuthAccount.provider == PROVIDER
        )
    ).scalar_one_or_none()


def connection_status() -> dict:
    """Connection metadata only, as a plain dict.

    Deliberately returns no token material of any kind, mirroring §1.12's rule
    that raw tokens never reach client-visible output. Factored out of the
    route below so the §8.1 aggregate `/api/v1/auth/status` can reuse it
    instead of re-querying `oauth_accounts` with its own copy of these rules.
    """
    if _session_factory is None:
        return {"connected": False, "configured": is_configured()}

    with _session_factory() as db:
        account = _current_account(db)
        if account is None or account.revoked_at is not None:
            return {"connected": False, "configured": is_configured()}
        user = db.get(User, account.user_id)
        return {
            "connected": True,
            "configured": True,
            "provider": account.provider,
            "email": user.email if user else None,
            "scopes": list(account.scopes or []),
            "expires_at": account.expires_at.isoformat() if account.expires_at else None,
            "youtube_authorized": any(s in (account.scopes or []) for s in YOUTUBE_SCOPES),
        }


@bp.route("/api/auth/google/status")
def status() -> Any:
    return jsonify(connection_status())


@bp.route("/auth/google/disconnect", methods=["POST"])
def disconnect() -> Any:
    """AUTH-007 (partial): revoke at Google, mark revoked, clear the session."""
    if _session_factory is None:
        return _not_configured_response()

    revoked_upstream = False
    with _session_factory() as db:
        account = _current_account(db)
        if account is not None:
            try:
                # Revoke at the provider, not just locally -- a local-only
                # delete would leave a live grant in the user's Google account.
                plaintext = _decrypt_for_revocation(account)
                if plaintext:
                    response = requests.post(
                        GOOGLE_REVOKE_URL, data={"token": plaintext}, timeout=10
                    )
                    revoked_upstream = response.status_code == 200
            except Exception as exc:
                # Local revocation still proceeds; the user asked to disconnect.
                logger.warning("google_oauth_revoke_failed: %s", type(exc).__name__)
            account.revoked_at = datetime.now(timezone.utc)
            db.commit()

    session.pop("user_id", None)
    session.modified = True
    return jsonify({"ok": True, "revoked_at_provider": revoked_upstream})


def _decrypt_for_revocation(account: OAuthAccount) -> Optional[str]:
    """Prefer the refresh token: revoking it invalidates the whole grant."""
    from contracts.token_crypto import decrypt

    if account.encrypted_refresh_token:
        return decrypt(account.encrypted_refresh_token)
    if account.encrypted_access_token:
        return decrypt(account.encrypted_access_token)
    return None
