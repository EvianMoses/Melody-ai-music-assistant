"""Tests for the Google OIDC flow (Phase 5 §5.2, AUTH-001…007).

Fully offline: the Authlib client is stubbed and the database is in-memory
SQLite, so no Google credentials, network, or Postgres are required. Matches the
monkeypatch-the-seam style used across the service test suites.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import auth_google
from contracts import token_crypto
from contracts.db_models import Base, GuestSession, OAuthAccount, User

GOOGLE_SUB = "108000000000000000001"
GOOGLE_EMAIL = "listener@example.com"
ACCESS_TOKEN = "ya29.a0-super-secret-access-token"
REFRESH_TOKEN = "1//0g-super-secret-refresh-token"


class _StubGoogleClient:
    """Stands in for Authlib's registered `oauth.google` remote app."""

    def __init__(self, token: dict):
        self._token = token
        self.authorize_calls: list[dict] = []

    def authorize_redirect(self, redirect_uri, **kwargs):
        self.authorize_calls.append({"redirect_uri": redirect_uri, **kwargs})
        from flask import redirect as flask_redirect

        return flask_redirect("https://accounts.google.com/o/oauth2/v2/auth?stub=1")

    def authorize_access_token(self):
        return self._token


def _default_token(scope: str = "openid email profile") -> dict:
    return {
        "access_token": ACCESS_TOKEN,
        "refresh_token": REFRESH_TOKEN,
        "scope": scope,
        "expires_in": 3599,
        "userinfo": {
            "sub": GOOGLE_SUB,
            "email": GOOGLE_EMAIL,
            "name": "Test Listener",
            "locale": "en",
        },
    }


@pytest.fixture
def db_factory():
    # SQLite lacks JSONB/Uuid-native types; SQLAlchemy maps them for tests.
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            GuestSession.__table__,
            OAuthAccount.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)


@pytest.fixture
def client(monkeypatch, db_factory):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    # Must match the test client's own host ("localhost"). When it doesn't,
    # /auth/google/login deliberately redirects to the callback's origin first
    # so the whole flow shares one cookie scope -- see
    # test_login_realigns_to_the_callback_host below.
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost/auth/google/callback")
    monkeypatch.setenv(token_crypto.ENV_VAR, token_crypto.generate_key())

    app = Flask(__name__)
    app.secret_key = "test-secret-key"
    app.config["TESTING"] = True
    auth_google.init_app(app, lambda: db_factory())
    return app.test_client(), db_factory


def _start_flow(test_client, session_id="11111111-1111-1111-1111-111111111111"):
    """Prime a session id, then hit /login so the binding key is stashed."""
    with test_client.session_transaction() as sess:
        sess["session_id"] = session_id
    return test_client.get("/auth/google/login")


# ---------------------------------------------------------------------------
# AUTH-004: identity scopes first
# ---------------------------------------------------------------------------


# Regression test for a live sign-in failure (2026-07-26): the app was browsed
# at http://localhost:5000 while GOOGLE_REDIRECT_URI pointed at
# http://127.0.0.1:5000. Those are different cookie hosts, so the session
# cookie set when starting the flow was never sent to the callback, the flow
# binding was missing, and sign-in died on INVALID_OAUTH_STATE having done
# everything else right. The flow must begin on the callback's own origin.
def test_login_realigns_to_the_callback_host(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5000/auth/google/callback")
    stub = _StubGoogleClient(_default_token())
    monkeypatch.setattr(auth_google.oauth, "google", stub, raising=False)

    response = _start_flow(test_client)
    assert response.status_code == 302
    assert response.headers["Location"] == "http://127.0.0.1:5000/auth/google/login"
    # Crucially, the flow has NOT started yet -- no state is burned on an
    # origin that could not have completed it.
    assert stub.authorize_calls == []


def test_upgrade_realigns_to_the_callback_host(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5000/auth/google/callback")
    stub = _StubGoogleClient(_default_token())
    monkeypatch.setattr(auth_google.oauth, "google", stub, raising=False)

    response = test_client.get("/auth/google/upgrade")
    assert response.status_code == 302
    assert response.headers["Location"] == "http://127.0.0.1:5000/auth/google/upgrade"
    assert stub.authorize_calls == []


def test_callback_without_any_session_explains_the_host_mismatch(client, monkeypatch):
    """The unrecoverable case must say what to do, not just 'did not match'."""
    test_client, _ = client
    stub = _StubGoogleClient(_default_token())
    monkeypatch.setattr(auth_google.oauth, "google", stub, raising=False)

    # No /login first => no binding key in the session, exactly as when the
    # cookie is dropped because the callback is on a different host.
    response = test_client.get("/auth/google/callback?state=x&code=y")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "INVALID_OAUTH_STATE"
    assert "GOOGLE_REDIRECT_URI" in body["error"]["message"]


def test_login_requests_identity_scopes_only(client, monkeypatch):
    test_client, _ = client
    stub = _StubGoogleClient(_default_token())
    monkeypatch.setattr(auth_google.oauth, "google", stub, raising=False)

    response = _start_flow(test_client)
    assert response.status_code == 302
    # No YouTube scope at first contact.
    call = stub.authorize_calls[0]
    assert "youtube" not in str(call).lower()
    # A refresh token is only issued with these two set.
    assert call["access_type"] == "offline"
    assert call["prompt"] == "consent"


# ---------------------------------------------------------------------------
# AUTH-005: incremental YouTube scope
# ---------------------------------------------------------------------------


def test_upgrade_requests_youtube_incrementally_keeping_identity_scopes(client, monkeypatch):
    test_client, _ = client
    stub = _StubGoogleClient(_default_token())
    monkeypatch.setattr(auth_google.oauth, "google", stub, raising=False)

    with test_client.session_transaction() as sess:
        sess["session_id"] = "11111111-1111-1111-1111-111111111111"
    response = test_client.get("/auth/google/upgrade")
    assert response.status_code == 302

    call = stub.authorize_calls[0]
    assert "https://www.googleapis.com/auth/youtube" in call["scope"]
    # Identity scopes retained, not replaced.
    assert "openid" in call["scope"] and "email" in call["scope"]
    # This is what makes Google add to the grant rather than replace it.
    assert call["include_granted_scopes"] == "true"


# ---------------------------------------------------------------------------
# AUTH-002/006: callback persists an encrypted grant + first real user
# ---------------------------------------------------------------------------


def test_callback_creates_user_and_encrypted_account(client, monkeypatch):
    test_client, db_factory = client
    stub = _StubGoogleClient(_default_token())
    monkeypatch.setattr(auth_google.oauth, "google", stub, raising=False)

    _start_flow(test_client)
    response = test_client.get("/auth/google/callback")
    assert response.status_code == 302  # redirected home on success

    with db_factory() as db:
        user = db.execute(select(User)).scalar_one()
        assert user.email == GOOGLE_EMAIL

        account = db.execute(select(OAuthAccount)).scalar_one()
        assert account.provider == "google"
        assert account.provider_account_id == GOOGLE_SUB
        assert account.user_id == user.id
        assert account.scopes == ["openid", "email", "profile"]
        assert account.revoked_at is None
        assert account.encryption_key_id

        # The security assertion: ciphertext, not the token.
        assert ACCESS_TOKEN not in account.encrypted_access_token
        assert REFRESH_TOKEN not in (account.encrypted_refresh_token or "")
        assert token_crypto.decrypt(account.encrypted_access_token) == ACCESS_TOKEN
        assert token_crypto.decrypt(account.encrypted_refresh_token) == REFRESH_TOKEN


def test_callback_is_idempotent_for_the_same_google_account(client, monkeypatch):
    """Signing in twice must not create a second user or a duplicate grant."""
    test_client, db_factory = client
    stub = _StubGoogleClient(_default_token())
    monkeypatch.setattr(auth_google.oauth, "google", stub, raising=False)

    _start_flow(test_client)
    test_client.get("/auth/google/callback")
    _start_flow(test_client)
    test_client.get("/auth/google/callback")

    with db_factory() as db:
        assert len(db.execute(select(User)).scalars().all()) == 1
        assert len(db.execute(select(OAuthAccount)).scalars().all()) == 1


def test_callback_links_guest_session_to_new_user(client, monkeypatch, db_factory):
    """guest_sessions.migrated_user_id exists for exactly this transition."""
    test_client, db_factory_ = client
    guest_id = uuid.uuid4()
    with db_factory_() as db:
        db.add(
            GuestSession(
                id=guest_id, expires_at=datetime.now(timezone.utc) + timedelta(days=1)
            )
        )
        db.commit()

    stub = _StubGoogleClient(_default_token())
    monkeypatch.setattr(auth_google.oauth, "google", stub, raising=False)

    _start_flow(test_client, session_id=str(guest_id))
    test_client.get("/auth/google/callback")

    with db_factory_() as db:
        guest = db.get(GuestSession, guest_id)
        user = db.execute(select(User)).scalar_one()
        assert guest.migrated_user_id == user.id


def test_upgrade_then_callback_widens_stored_scopes(client, monkeypatch):
    test_client, db_factory = client
    monkeypatch.setattr(
        auth_google.oauth, "google", _StubGoogleClient(_default_token()), raising=False
    )
    _start_flow(test_client)
    test_client.get("/auth/google/callback")

    upgraded = _default_token(
        scope="openid email profile https://www.googleapis.com/auth/youtube"
    )
    monkeypatch.setattr(auth_google.oauth, "google", _StubGoogleClient(upgraded), raising=False)
    _start_flow(test_client)
    test_client.get("/auth/google/callback")

    with db_factory() as db:
        account = db.execute(select(OAuthAccount)).scalar_one()
        assert "https://www.googleapis.com/auth/youtube" in account.scopes
        assert "openid" in account.scopes  # identity scopes retained


# ---------------------------------------------------------------------------
# AUTH-003: state / session binding
# ---------------------------------------------------------------------------


def test_callback_rejects_when_flow_was_never_started(client, monkeypatch):
    """No binding in the session => a replayed callback URL, not our flow."""
    test_client, db_factory = client
    monkeypatch.setattr(
        auth_google.oauth, "google", _StubGoogleClient(_default_token()), raising=False
    )

    response = test_client.get("/auth/google/callback")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_OAUTH_STATE"
    with db_factory() as db:
        assert db.execute(select(OAuthAccount)).scalars().all() == []


def test_callback_rejects_when_session_changed_mid_flow(client, monkeypatch):
    """Session binding: a state token lifted into another session must fail."""
    test_client, _ = client
    monkeypatch.setattr(
        auth_google.oauth, "google", _StubGoogleClient(_default_token()), raising=False
    )

    _start_flow(test_client, session_id="11111111-1111-1111-1111-111111111111")
    with test_client.session_transaction() as sess:
        sess["session_id"] = "22222222-2222-2222-2222-222222222222"  # different browser

    response = test_client.get("/auth/google/callback")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_OAUTH_STATE"


def test_callback_reports_exchange_failure_safely(client, monkeypatch):
    class _Failing(_StubGoogleClient):
        def authorize_access_token(self):
            raise ValueError("mismatching_state: CSRF Warning!")

    test_client, _ = client
    monkeypatch.setattr(auth_google.oauth, "google", _Failing({}), raising=False)

    _start_flow(test_client)
    response = test_client.get("/auth/google/callback")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "OAUTH_EXCHANGE_FAILED"
    # Internal detail must not leak to the client.
    assert "CSRF Warning" not in body["error"]["message"]


# ---------------------------------------------------------------------------
# AUTH-006: no token ever reaches client-visible output (§1.12 rule)
# ---------------------------------------------------------------------------


def test_status_never_returns_token_material(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(
        auth_google.oauth, "google", _StubGoogleClient(_default_token()), raising=False
    )
    _start_flow(test_client)
    test_client.get("/auth/google/callback")

    response = test_client.get("/api/auth/google/status")
    body = response.get_json()
    assert body["connected"] is True
    assert body["email"] == GOOGLE_EMAIL
    assert body["youtube_authorized"] is False

    serialized = response.get_data(as_text=True)
    assert ACCESS_TOKEN not in serialized
    assert REFRESH_TOKEN not in serialized
    for forbidden in ("access_token", "refresh_token", "encrypted_access_token"):
        assert forbidden not in body


def test_status_reports_disconnected_before_sign_in(client):
    test_client, _ = client
    body = test_client.get("/api/auth/google/status").get_json()
    assert body["connected"] is False


# ---------------------------------------------------------------------------
# AUTH-007 (partial): disconnect + provider-side revocation
# ---------------------------------------------------------------------------


def test_disconnect_revokes_upstream_and_clears_session(client, monkeypatch):
    test_client, db_factory = client
    monkeypatch.setattr(
        auth_google.oauth, "google", _StubGoogleClient(_default_token()), raising=False
    )
    _start_flow(test_client)
    test_client.get("/auth/google/callback")

    revoke_calls: list[dict] = []

    class _Resp:
        status_code = 200

    def _fake_post(url, data=None, timeout=None):
        revoke_calls.append({"url": url, "data": data})
        return _Resp()

    monkeypatch.setattr(auth_google.requests, "post", _fake_post)

    response = test_client.post("/auth/google/disconnect")
    assert response.status_code == 200
    assert response.get_json()["revoked_at_provider"] is True

    # Revokes the refresh token: that invalidates the entire grant.
    assert revoke_calls[0]["url"] == auth_google.GOOGLE_REVOKE_URL
    assert revoke_calls[0]["data"]["token"] == REFRESH_TOKEN

    with db_factory() as db:
        assert db.execute(select(OAuthAccount)).scalar_one().revoked_at is not None
    assert test_client.get("/api/auth/google/status").get_json()["connected"] is False


def test_disconnect_still_revokes_locally_when_google_is_unreachable(client, monkeypatch):
    """The user asked to disconnect; a provider outage must not block that."""
    test_client, db_factory = client
    monkeypatch.setattr(
        auth_google.oauth, "google", _StubGoogleClient(_default_token()), raising=False
    )
    _start_flow(test_client)
    test_client.get("/auth/google/callback")

    def _boom(*_a, **_k):
        raise ConnectionError("google unreachable")

    monkeypatch.setattr(auth_google.requests, "post", _boom)

    response = test_client.post("/auth/google/disconnect")
    assert response.status_code == 200
    assert response.get_json()["revoked_at_provider"] is False
    with db_factory() as db:
        assert db.execute(select(OAuthAccount)).scalar_one().revoked_at is not None


# ---------------------------------------------------------------------------
# Configuration guards
# ---------------------------------------------------------------------------


def test_routes_report_feature_disabled_without_google_credentials(client, monkeypatch):
    test_client, _ = client
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    for path in ("/auth/google/login", "/auth/google/upgrade", "/auth/google/callback"):
        response = test_client.get(path)
        assert response.status_code == 503
        assert response.get_json()["error"]["code"] == "FEATURE_DISABLED"


def test_callback_fails_closed_when_encryption_key_is_missing(client, monkeypatch):
    """Never fall back to storing a plaintext token."""
    test_client, db_factory = client
    monkeypatch.setattr(
        auth_google.oauth, "google", _StubGoogleClient(_default_token()), raising=False
    )
    monkeypatch.delenv(token_crypto.ENV_VAR, raising=False)

    _start_flow(test_client)
    response = test_client.get("/auth/google/callback")
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "SERVER_MISCONFIGURED"
    with db_factory() as db:
        assert db.execute(select(OAuthAccount)).scalars().all() == []
