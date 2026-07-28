"""Resolve a usable Google access token for a user (Phase 5 §5.5).

Reads the encrypted grant written by the Flask OAuth flow (§5.2), decrypts it,
refreshes it when expired, and re-encrypts the refreshed value back into
``oauth_accounts``. Playlist export is the first consumer.

Refresh is not an edge case here: Google access tokens live about an hour, so
any export outside that window meets an expired token. The refresh token itself
also expires -- after 7 days while the OAuth app is in Testing mode -- which
surfaces as ``REAUTHORIZATION_REQUIRED`` rather than an opaque provider error,
so the UI can send the user back through consent.

Nothing here ever logs or returns token material.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select

from contracts.db_models import OAuthAccount
from contracts.token_crypto import TokenCryptoError, decrypt, encrypt
from shared_lib.http import make_async_client

from .youtube_adapter import ProviderError

logger = logging.getLogger("provider-gateway.google_token")

PROVIDER = "google"
TOKEN_URL = "https://oauth2.googleapis.com/token"
# The scope §5.2's /auth/google/upgrade requests; either grants playlist writes.
YOUTUBE_WRITE_SCOPES = (
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
)
# Refresh a little early so a token cannot expire mid-export.
EXPIRY_SKEW = timedelta(seconds=60)


class GoogleGrant:
    """A decrypted, currently-valid access token plus its granted scopes."""

    def __init__(self, access_token: str, scopes: list[str], account_id: uuid.UUID):
        self.access_token = access_token
        self.scopes = scopes
        self.account_id = account_id

    def has_youtube_write(self) -> bool:
        return any(s in self.scopes for s in YOUTUBE_WRITE_SCOPES)

    def __repr__(self) -> str:  # never leak the token, even in a traceback
        return f"<GoogleGrant account={self.account_id} scopes={len(self.scopes)}>"


def _load_account(db, user_id: str) -> OAuthAccount:
    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError) as exc:
        raise ProviderError(
            "AUTHORIZATION_REQUIRED", "No Google connection for this user."
        ) from exc

    account = db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user_uuid, OAuthAccount.provider == PROVIDER
        )
    ).scalar_one_or_none()

    if account is None:
        raise ProviderError(
            "AUTHORIZATION_REQUIRED", "This user has not connected a Google account."
        )
    if account.revoked_at is not None:
        raise ProviderError(
            "REAUTHORIZATION_REQUIRED", "The Google connection was disconnected."
        )
    return account


def _is_expired(account: OAuthAccount) -> bool:
    if account.expires_at is None:
        return False
    expires_at = account.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) + EXPIRY_SKEW >= expires_at


async def _refresh(db, account: OAuthAccount) -> str:
    """Exchange the refresh token for a new access token and persist it."""
    if not account.encrypted_refresh_token:
        raise ProviderError(
            "REAUTHORIZATION_REQUIRED",
            "The stored Google connection has no refresh token; please reconnect.",
        )

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not (client_id and client_secret):
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Google client credentials are not configured."
        )

    refresh_token = decrypt(account.encrypted_refresh_token)

    async with make_async_client() as client:
        try:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
        except Exception as exc:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE", f"Google token endpoint unreachable: {exc}"
            ) from exc

    if response.status_code != 200:
        # invalid_grant = revoked, or expired (7 days in Testing mode).
        reason = ""
        try:
            reason = response.json().get("error", "")
        except ValueError:
            pass
        if reason == "invalid_grant":
            raise ProviderError(
                "REAUTHORIZATION_REQUIRED",
                "The Google authorization has expired or been revoked; please reconnect.",
            )
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", f"Google token refresh returned {response.status_code}."
        )

    payload = response.json()
    new_access = payload.get("access_token")
    if not new_access:
        raise ProviderError("PROVIDER_UNAVAILABLE", "Google returned no access token.")

    ciphertext, key_id = encrypt(new_access)
    account.encrypted_access_token = ciphertext
    account.encryption_key_id = key_id
    if payload.get("expires_in"):
        account.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(payload["expires_in"])
        )
    # Google may rotate the refresh token; keep the old one when it doesn't.
    if payload.get("refresh_token"):
        rotated, _ = encrypt(payload["refresh_token"])
        account.encrypted_refresh_token = rotated
    db.commit()

    logger.info("google_token_refreshed", extra={"account_id": str(account.id)})
    return new_access


async def get_grant(db, user_id: str, *, require_youtube_write: bool = False) -> GoogleGrant:
    """Return a usable grant, refreshing the access token if needed.

    ``require_youtube_write`` is checked *before* any provider call so an
    unscoped user gets an actionable INSUFFICIENT_SCOPE (the UI's cue to send
    them to /auth/google/upgrade) instead of a raw Google 403.
    """
    account = _load_account(db, user_id)
    scopes = list(account.scopes or [])

    if require_youtube_write and not any(s in scopes for s in YOUTUBE_WRITE_SCOPES):
        raise ProviderError(
            "INSUFFICIENT_SCOPE",
            "This connection does not grant YouTube playlist access. "
            "Reconnect and approve playlist permissions to export.",
        )

    try:
        if _is_expired(account):
            access_token = await _refresh(db, account)
        else:
            access_token = decrypt(account.encrypted_access_token)
    except TokenCryptoError as exc:
        # Key rotated away or lost -- actionable, and never echo ciphertext.
        logger.error("google_token_decrypt_failed: %s", exc)
        raise ProviderError(
            "REAUTHORIZATION_REQUIRED",
            "Stored credentials could not be read; please reconnect your account.",
        ) from exc

    return GoogleGrant(access_token=access_token, scopes=scopes, account_id=account.id)


def connection_status(db, user_id: str) -> dict[str, Any]:
    """Metadata for WF-009. Never includes token material."""
    try:
        account = _load_account(db, user_id)
    except ProviderError as exc:
        return {
            "connected": False,
            "provider": PROVIDER,
            "reauthorization_required": exc.code == "REAUTHORIZATION_REQUIRED",
            "reason": exc.code,
        }

    scopes = list(account.scopes or [])
    return {
        "connected": True,
        "provider": PROVIDER,
        "scopes": scopes,
        "expires_at": account.expires_at.isoformat() if account.expires_at else None,
        "expired": _is_expired(account),
        "youtube_write_authorized": any(s in scopes for s in YOUTUBE_WRITE_SCOPES),
        # An expired access token alone is recoverable via refresh; only a
        # missing refresh token actually forces the user back through consent.
        "reauthorization_required": account.encrypted_refresh_token is None,
    }
