"""Playlist export tests (Phase 5 §5.5, EXPORT-001…003).

Covers the six cases §5.5 calls for: success, partial failure, expired
authorization, insufficient scope, quota exhaustion, and the repeated click.
No network: the YouTube write calls are stubbed, and the database is an
in-memory SQLite built from the canonical ORM so the idempotency constraint
under test is the real one.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("OAUTH_TOKEN_ENCRYPTION_KEY", "")

from contracts.db_models import Base, OAuthAccount, PlaylistExport, User  # noqa: E402
from contracts.token_crypto import encrypt, generate_key  # noqa: E402

import main  # noqa: E402
from app import db, youtube_playlist  # noqa: E402
from app.youtube_adapter import ProviderError  # noqa: E402

YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
IDENTITY_SCOPES = ["openid", "email", "profile"]


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setenv("OAUTH_TOKEN_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("ENABLE_PLAYLIST_EXPORT", "true")
    yield


@pytest.fixture
def session_factory():
    # StaticPool so every connection sees the same in-memory database (without
    # it the tables created here are invisible to the handler), and
    # check_same_thread=False because TestClient runs the app in a worker thread.
    engine = create_engine(
        "sqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            OAuthAccount.__table__,
            PlaylistExport.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, future=True)
    db.reset_for_tests(factory)
    yield factory
    db.reset_for_tests(None)


@pytest.fixture
def client():
    return TestClient(main.app, raise_server_exceptions=False)


def _make_user(factory, *, scopes=None, expires_in=3600, refresh_token="refresh-abc"):
    """Create a user with a connected Google account and return its id."""
    scopes = IDENTITY_SCOPES + [YOUTUBE_SCOPE] if scopes is None else scopes
    with factory() as session:
        user = User(email=f"{uuid.uuid4().hex}@example.com")
        session.add(user)
        session.flush()

        access_ct, key_id = encrypt("access-token-xyz")
        refresh_ct, _ = encrypt(refresh_token) if refresh_token else (None, None)
        session.add(
            OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_account_id=uuid.uuid4().hex,
                encrypted_access_token=access_ct,
                encrypted_refresh_token=refresh_ct,
                encryption_key_id=key_id,
                scopes=scopes,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            )
        )
        session.commit()
        return str(user.id)


def _post(client, user_id, key, tracks=("yt:vid1", "vid2")):
    return client.post(
        "/providers/playlists",
        json={
            "provider": "youtube",
            "user_id": user_id,
            "idempotency_key": key,
            "track_ids": list(tracks),
            "name": "Melody Test Export",
        },
    )


# --------------------------------------------------------------------------
# Success and partial failure
# --------------------------------------------------------------------------


def test_export_success_records_playlist(client, session_factory, monkeypatch):
    user_id = _make_user(session_factory)
    calls = {}

    async def fake_export(*, access_token, name, track_ids, description=""):
        calls["track_ids"] = track_ids
        calls["name"] = name
        return {
            "playlist_id": "PL123",
            "url": "https://www.youtube.com/playlist?list=PL123",
            "added": list(track_ids),
            "failed": [],
            "status": "completed",
        }

    monkeypatch.setattr(main.youtube_playlist, "export_playlist", fake_export)

    response = _post(client, user_id, "key-success")
    assert response.status_code == 200
    body = response.json()
    assert body["playlist_id"] == "PL123"
    assert body["status"] == "completed"
    assert body["replayed"] is False
    # The "yt:" prefix the smoke test sends is normalized before the provider.
    assert calls["track_ids"] == ["yt:vid1", "vid2"]

    with session_factory() as session:
        row = session.execute(select(PlaylistExport)).scalar_one()
        assert row.provider_playlist_id == "PL123"
        assert row.url.endswith("PL123")
        assert row.status == "completed"
        assert str(row.user_id) == user_id


def test_export_partial_failure_is_recorded_not_fatal(client, session_factory, monkeypatch):
    """A deleted or region-locked video must not sink the whole export."""
    user_id = _make_user(session_factory)

    async def fake_export(*, access_token, name, track_ids, description=""):
        return {
            "playlist_id": "PL456",
            "url": "https://www.youtube.com/playlist?list=PL456",
            "added": ["vid1"],
            "failed": [{"video_id": "vid2", "reason": "MISSING_ITEM"}],
            "status": "partial",
        }

    monkeypatch.setattr(main.youtube_playlist, "export_playlist", fake_export)

    response = _post(client, user_id, "key-partial")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["added"] == ["vid1"]
    assert body["failed"][0]["reason"] == "MISSING_ITEM"

    with session_factory() as session:
        row = session.execute(select(PlaylistExport)).scalar_one()
        assert row.status == "partial"
        assert row.partial_failure["failed"][0]["video_id"] == "vid2"


# --------------------------------------------------------------------------
# Authorization failures
# --------------------------------------------------------------------------


def test_export_without_youtube_scope_returns_insufficient_scope(
    client, session_factory, monkeypatch
):
    """Fail before spending quota, so the UI can send the user to /upgrade."""
    user_id = _make_user(session_factory, scopes=IDENTITY_SCOPES)

    async def never(**_):
        raise AssertionError("provider must not be called without the scope")

    monkeypatch.setattr(main.youtube_playlist, "export_playlist", never)

    response = _post(client, user_id, "key-scope")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


def test_export_with_dead_refresh_token_asks_for_reauthorization(
    client, session_factory, monkeypatch
):
    """Expired access token + refused refresh = reconnect, not a 500."""
    user_id = _make_user(session_factory, expires_in=-10)

    async def fake_refresh(_db, _account):
        raise ProviderError(
            "REAUTHORIZATION_REQUIRED", "The Google authorization has expired."
        )

    monkeypatch.setattr(main.google_token, "_refresh", fake_refresh)

    response = _post(client, user_id, "key-reauth")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REAUTHORIZATION_REQUIRED"

    with session_factory() as session:
        row = session.execute(select(PlaylistExport)).scalar_one()
        assert row.status == "failed"
        assert row.provider_playlist_id is None


def test_export_requires_a_signed_in_user(client, session_factory):
    response = client.post(
        "/providers/playlists",
        json={"provider": "youtube", "idempotency_key": "k", "track_ids": ["v"]},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHORIZATION_REQUIRED"


def test_export_is_gated_by_the_feature_flag(client, session_factory, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAYLIST_EXPORT", "false")
    response = _post(client, str(uuid.uuid4()), "key-flag")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "FEATURE_DISABLED"


# --------------------------------------------------------------------------
# Quota and idempotency
# --------------------------------------------------------------------------


def test_export_quota_error_surfaces_as_403(client, session_factory, monkeypatch):
    user_id = _make_user(session_factory)

    async def fake_export(**_):
        raise ProviderError("QUOTA_EXCEEDED", "YouTube playlist creation quota exceeded.")

    monkeypatch.setattr(main.youtube_playlist, "export_playlist", fake_export)

    response = _post(client, user_id, "key-quota")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_repeated_click_returns_stored_result_without_calling_provider(
    client, session_factory, monkeypatch
):
    """EXPORT-002: the same key must never create a second real playlist."""
    user_id = _make_user(session_factory)
    provider_calls = []

    async def fake_export(*, access_token, name, track_ids, description=""):
        provider_calls.append(name)
        return {
            "playlist_id": "PL789",
            "url": "https://www.youtube.com/playlist?list=PL789",
            "added": list(track_ids),
            "failed": [],
            "status": "completed",
        }

    monkeypatch.setattr(main.youtube_playlist, "export_playlist", fake_export)

    first = _post(client, user_id, "key-idem")
    second = _post(client, user_id, "key-idem")

    assert first.status_code == second.status_code == 200
    assert first.json()["playlist_id"] == second.json()["playlist_id"] == "PL789"
    assert first.json()["replayed"] is False
    assert second.json()["replayed"] is True
    assert len(provider_calls) == 1, "the provider was called twice for one key"

    with session_factory() as session:
        rows = session.execute(select(PlaylistExport)).scalars().all()
        assert len(rows) == 1


def test_export_requires_an_idempotency_key(client, session_factory):
    response = client.post(
        "/providers/playlists",
        json={"provider": "youtube", "user_id": str(uuid.uuid4()), "track_ids": ["v"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# The adapter itself (no HTTP client involved beyond a stub)
# --------------------------------------------------------------------------


def test_normalize_video_id_accepts_both_shapes():
    assert youtube_playlist.normalize_video_id("yt:dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert youtube_playlist.normalize_video_id("youtube:abc") == "abc"
    assert youtube_playlist.normalize_video_id(" dQw4w9WgXcQ ") == "dQw4w9WgXcQ"


@pytest.mark.anyio
async def test_export_playlist_rejects_an_empty_track_list():
    with pytest.raises(ProviderError) as excinfo:
        await youtube_playlist.export_playlist(
            access_token="t", name="n", track_ids=["", "  "]
        )
    assert excinfo.value.code == "MISSING_ITEM"


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --------------------------------------------------------------------------
# Connection status (WF-009)
# --------------------------------------------------------------------------


def test_connection_status_reports_scopes_and_never_tokens(client, session_factory):
    user_id = _make_user(session_factory)
    response = client.post(
        "/providers/connection/status", json={"user_id": user_id, "provider": "google"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["youtube_write_authorized"] is True
    assert "access-token-xyz" not in response.text
    assert not any("token" in k for k in body if k != "reauthorization_required")


def test_connection_status_for_an_unconnected_user(client, session_factory):
    response = client.post(
        "/providers/connection/status", json={"user_id": str(uuid.uuid4())}
    )
    assert response.json()["connected"] is False
