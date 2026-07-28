"""Google grant resolution and refresh (Phase 5 §5.5).

Google access tokens live about an hour, so refresh is the ordinary path for
export -- not an edge case. These tests pin the three things that matter: a
refreshed token is re-encrypted and persisted, a dead refresh token becomes an
actionable REAUTHORIZATION_REQUIRED, and no token material ever leaves this
module in a log line or a status payload.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from contracts.db_models import Base, OAuthAccount, User
from contracts.token_crypto import decrypt, encrypt, generate_key

from app import google_token
from app.youtube_adapter import ProviderError

YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine, tables=[User.__table__, OAuthAccount.__table__])
    with sessionmaker(bind=engine, future=True)() as s:
        yield s


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    """Stands in for the shared async httpx client."""

    def __init__(self, response):
        self._response = response
        self.posted = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, data=None, **_):
        self.posted.append((url, data))
        return self._response


def _make_account(session, *, expires_in=3600, refresh_token="refresh-original", scopes=None):
    user = User(email=f"{uuid.uuid4().hex}@example.com")
    session.add(user)
    session.flush()

    access_ct, key_id = encrypt("access-original")
    refresh_ct = encrypt(refresh_token)[0] if refresh_token else None
    account = OAuthAccount(
        user_id=user.id,
        provider="google",
        provider_account_id=uuid.uuid4().hex,
        encrypted_access_token=access_ct,
        encrypted_refresh_token=refresh_ct,
        encryption_key_id=key_id,
        scopes=["openid", "email"] + ([YOUTUBE_SCOPE] if scopes is None else scopes),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    )
    session.add(account)
    session.commit()
    return str(user.id), account


@pytest.mark.anyio
async def test_valid_token_is_returned_without_a_refresh(session, monkeypatch):
    user_id, _ = _make_account(session)

    def never():
        raise AssertionError("a live token must not trigger a refresh")

    monkeypatch.setattr(google_token, "make_async_client", never)

    grant = await google_token.get_grant(session, user_id)
    assert grant.access_token == "access-original"
    assert grant.has_youtube_write() is True


@pytest.mark.anyio
async def test_expired_token_is_refreshed_reencrypted_and_persisted(session, monkeypatch):
    user_id, account = _make_account(session, expires_in=-10)
    old_ciphertext = account.encrypted_access_token
    client = _FakeClient(
        _FakeResponse(200, {"access_token": "access-refreshed", "expires_in": 3600})
    )
    monkeypatch.setattr(google_token, "make_async_client", lambda: client)

    grant = await google_token.get_grant(session, user_id)

    assert grant.access_token == "access-refreshed"
    assert client.posted[0][0] == google_token.TOKEN_URL
    assert client.posted[0][1]["grant_type"] == "refresh_token"

    session.refresh(account)
    assert account.encrypted_access_token != old_ciphertext, "not re-encrypted"
    assert decrypt(account.encrypted_access_token) == "access-refreshed"
    assert not google_token._is_expired(account), "expiry was not pushed forward"
    # The refresh token was not rotated by Google, so the old one is kept.
    assert decrypt(account.encrypted_refresh_token) == "refresh-original"


@pytest.mark.anyio
async def test_a_rotated_refresh_token_replaces_the_stored_one(session, monkeypatch):
    user_id, account = _make_account(session, expires_in=-10)
    client = _FakeClient(
        _FakeResponse(
            200,
            {
                "access_token": "access-refreshed",
                "expires_in": 3600,
                "refresh_token": "refresh-rotated",
            },
        )
    )
    monkeypatch.setattr(google_token, "make_async_client", lambda: client)

    await google_token.get_grant(session, user_id)

    session.refresh(account)
    assert decrypt(account.encrypted_refresh_token) == "refresh-rotated"


@pytest.mark.anyio
async def test_invalid_grant_becomes_reauthorization_required(session, monkeypatch):
    """The 7-day Testing-mode expiry must be actionable, not an opaque 502."""
    user_id, _ = _make_account(session, expires_in=-10)
    client = _FakeClient(_FakeResponse(400, {"error": "invalid_grant"}))
    monkeypatch.setattr(google_token, "make_async_client", lambda: client)

    with pytest.raises(ProviderError) as excinfo:
        await google_token.get_grant(session, user_id)
    assert excinfo.value.code == "REAUTHORIZATION_REQUIRED"


@pytest.mark.anyio
async def test_missing_refresh_token_requires_reauthorization(session, monkeypatch):
    user_id, _ = _make_account(session, expires_in=-10, refresh_token=None)
    with pytest.raises(ProviderError) as excinfo:
        await google_token.get_grant(session, user_id)
    assert excinfo.value.code == "REAUTHORIZATION_REQUIRED"


@pytest.mark.anyio
async def test_missing_scope_is_rejected_before_any_network_call(session, monkeypatch):
    user_id, _ = _make_account(session, scopes=[])

    def never():
        raise AssertionError("scope must be checked before any provider call")

    monkeypatch.setattr(google_token, "make_async_client", never)

    with pytest.raises(ProviderError) as excinfo:
        await google_token.get_grant(session, user_id, require_youtube_write=True)
    assert excinfo.value.code == "INSUFFICIENT_SCOPE"


@pytest.mark.anyio
async def test_unknown_user_is_authorization_required(session):
    with pytest.raises(ProviderError) as excinfo:
        await google_token.get_grant(session, str(uuid.uuid4()))
    assert excinfo.value.code == "AUTHORIZATION_REQUIRED"


@pytest.mark.anyio
async def test_a_revoked_connection_fails_closed(session):
    """The §5.2 disconnect path: a revoked grant must not still export."""
    user_id, account = _make_account(session)
    account.revoked_at = datetime.now(timezone.utc)
    session.commit()

    with pytest.raises(ProviderError) as excinfo:
        await google_token.get_grant(session, user_id)
    assert excinfo.value.code == "REAUTHORIZATION_REQUIRED"


@pytest.mark.anyio
async def test_grant_repr_does_not_leak_the_token(session):
    user_id, _ = _make_account(session)
    grant = await google_token.get_grant(session, user_id)
    assert "access-original" not in repr(grant)


def test_connection_status_excludes_token_material(session):
    user_id, _ = _make_account(session)
    status = google_token.connection_status(session, user_id)

    assert status["connected"] is True
    assert status["youtube_write_authorized"] is True
    assert status["reauthorization_required"] is False
    serialized = str(status)
    assert "access-original" not in serialized
    assert "refresh-original" not in serialized


def test_connection_status_flags_a_revoked_connection(session):
    user_id, account = _make_account(session)
    account.revoked_at = datetime.now(timezone.utc)
    session.commit()

    status = google_token.connection_status(session, user_id)
    assert status["connected"] is False
    assert status["reauthorization_required"] is True
