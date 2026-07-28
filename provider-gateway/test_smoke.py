from fastapi.testclient import TestClient

from app import spotify_adapter, youtube_adapter
from main import app

client = TestClient(app)


async def _fake_youtube_search_ok(query, limit):
    return [
        {
            "provider": "youtube",
            "provider_track_id": "fixture-1",
            "title": "Holocene",
            "artist": "Bon Iver",
            "url": "https://www.youtube.com/watch?v=fixture-1",
            "confidence": 0.9,
        }
    ]


async def _fake_youtube_search_quota_exceeded(query, limit):
    raise youtube_adapter.ProviderError("QUOTA_EXCEEDED", "YouTube search quota exceeded.")


def test_health_live():
    assert client.get("/health/live").json() == {"status": "ok"}


def test_search_youtube_real_path(monkeypatch):
    monkeypatch.setattr(youtube_adapter, "search", _fake_youtube_search_ok)
    response = client.post("/providers/search", json={"query": "bon iver holocene unique-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "youtube"
    assert body["placeholder"] is False
    assert len(body["results"]) == 1
    assert body["results"][0]["title"] == "Holocene"


def test_search_rejects_unknown_provider():
    response = client.post(
        "/providers/search", json={"query": "x unique-2", "provider": "soundcloud"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_PROVIDER"


def test_search_spotify_returns_normalized_tracks(monkeypatch):
    """§5.6: Spotify search is implemented as of 2026-07-26.

    Replaces the former test_search_spotify_not_implemented, which asserted a
    501 PROVIDER_NOT_IMPLEMENTED. The endpoint now dispatches to the Spotify
    adapter and returns the same NormalizedTrack shape as YouTube, so the
    caller does not branch on provider.
    """

    async def _fake_spotify_search(query, limit):
        return [
            {
                "provider": "spotify",
                "provider_track_id": "4cOdK2wGLETKBW3PvgPWqT",
                "title": "Never Gonna Give You Up",
                "artist": "Rick Astley",
                "url": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
                "confidence": 0.9,
                "duration_seconds": 213,
                "embeddable": True,
                "duration_in_track_range": True,
                "field_sources": {},
            }
        ]

    monkeypatch.setattr(spotify_adapter, "search", _fake_spotify_search)
    response = client.post(
        "/providers/search", json={"query": "x unique-3", "provider": "spotify"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "spotify"
    assert body["results"][0]["provider"] == "spotify"
    assert body["results"][0]["provider_track_id"] == "4cOdK2wGLETKBW3PvgPWqT"


def test_search_spotify_errors_map_like_youtube_errors(monkeypatch):
    """One error vocabulary across providers, so callers handle one set."""

    async def _rate_limited(query, limit):
        raise spotify_adapter.ProviderError("RATE_LIMITED", "Slow down.")

    monkeypatch.setattr(spotify_adapter, "search", _rate_limited)
    response = client.post(
        "/providers/search", json={"query": "x unique-3b", "provider": "spotify"}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_search_quota_exceeded_maps_to_403(monkeypatch):
    monkeypatch.setattr(youtube_adapter, "search", _fake_youtube_search_quota_exceeded)
    response = client.post("/providers/search", json={"query": "x unique-4"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_playlists_disabled(monkeypatch):
    # Pin the flag rather than inherit it: docker-compose sets
    # ENABLE_PLAYLIST_EXPORT=true, so without this the test read the ambient
    # environment and failed with 401 AUTHORIZATION_REQUIRED -- the correct
    # response for an *enabled* export with no signed-in user, and nothing to
    # do with the behaviour this test is about.
    monkeypatch.setenv("ENABLE_PLAYLIST_EXPORT", "false")
    response = client.post("/providers/playlists", json={"provider": "youtube"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "FEATURE_DISABLED"
