"""Spotify Web API search adapter (§5.6).

The counterpart to ``youtube_adapter`` behind ``/providers/search``, so a
request can be served by either provider without the caller knowing which.

**Authentication is the Client Credentials flow, deliberately.** Search is a
catalogue read: it needs an *application* token, not a user's. Requiring user
OAuth to see a recommendation would make the Spotify mode unusable for guests,
and none of the endpoints used here are user-scoped. The user's own grant is
still what §5.6's taste import and playlist writes will need -- that is a
different concern, and the historical reference implementation in
``aws/lambda_spotify_package/spotify_lambda.py`` makes the same split
(``get_spotify_client`` prefers a user token and falls back to client
credentials).

Where the YouTube adapter has to work hard to decide whether a result is even
music -- filtering reaction videos, hour-long mixes, explainer Shorts -- the
Spotify catalogue contains only real releases, so this adapter is much
simpler. Confidence comes from Spotify's own ``popularity`` rather than
from title heuristics.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any, Optional

from shared_lib.http import make_async_client

logger = logging.getLogger("provider-gateway.spotify")

TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105 - endpoint, not a secret
SEARCH_URL = "https://api.spotify.com/v1/search"

# Mirrors the YouTube adapter so "is this single-length" means the same thing
# regardless of provider.
DEFAULT_MIN_TRACK_SECONDS = 60
DEFAULT_MAX_TRACK_SECONDS = 600

# Refresh slightly early rather than racing the expiry.
_TOKEN_EXPIRY_SAFETY_SECONDS = 60


class ProviderError(Exception):
    """Normalized failure, mapped onto the shared AppError envelope by main.py.

    Same code vocabulary as ``youtube_adapter.ProviderError`` so
    ``/providers/search`` maps either provider's failures identically.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _duration_bounds() -> tuple[int, int]:
    def _int_env(name: str, default: int) -> int:
        try:
            return int(os.getenv(name) or default)
        except ValueError:
            return default

    return (
        _int_env("SPOTIFY_MIN_TRACK_SECONDS", DEFAULT_MIN_TRACK_SECONDS),
        _int_env("SPOTIFY_MAX_TRACK_SECONDS", DEFAULT_MAX_TRACK_SECONDS),
    )


def _market() -> str:
    """Availability is market-specific; an unplayable track is a bad result."""
    return (os.getenv("SPOTIFY_MARKET") or os.getenv("YOUTUBE_REGION") or "IL").strip().upper()


# Cached application token. Client credentials are per-application, not
# per-user, so one token serves every request until it expires.
_token_value: Optional[str] = None
_token_expires_at: float = 0.0


def _reset_token_cache() -> None:
    """Test seam; also used to force a refresh after a 401."""
    global _token_value, _token_expires_at
    _token_value = None
    _token_expires_at = 0.0


async def _get_app_token() -> str:
    global _token_value, _token_expires_at

    if _token_value and time.time() < _token_expires_at:
        return _token_value

    client_id = (os.getenv("SPOTIPY_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("SPOTIPY_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE",
            "Spotify is not configured on this server.",
        )

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
        async with make_async_client() as client:
            response = await client.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                # The secret travels in the Authorization header, never in a
                # query string that could be logged (the same lesson as the
                # YouTube api-key-in-logs leak fixed in §5.1).
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
    except Exception as exc:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Could not reach Spotify."
        ) from exc

    if response.status_code != 200:
        # Never echo the response body: it can repeat the credentials back.
        raise ProviderError(
            "PROVIDER_UNAVAILABLE",
            "Spotify rejected the application credentials.",
        )

    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise ProviderError("PROVIDER_UNAVAILABLE", "Spotify returned no access token.")

    _token_value = token
    _token_expires_at = time.time() + max(
        0, int(payload.get("expires_in") or 3600) - _TOKEN_EXPIRY_SAFETY_SECONDS
    )
    return token


def _raise_for_api_error(response: Any) -> None:
    status = response.status_code
    if status == 200:
        return
    if status == 429:
        raise ProviderError("RATE_LIMITED", "Spotify rate limit reached. Try again shortly.")
    if status in (401, 403):
        # An app token cannot be "insufficiently scoped" for search, so this is
        # a configuration or expiry problem, not something the user can fix.
        _reset_token_cache()
        raise ProviderError("PROVIDER_UNAVAILABLE", "Spotify rejected the request.")
    if status >= 500:
        raise ProviderError("PROVIDER_UNAVAILABLE", "Spotify is unavailable right now.")
    raise ProviderError("PROVIDER_UNAVAILABLE", "Spotify search failed.")


# Album types, best first. A track from a proper album or single release is a
# stronger recommendation than one lifted from a compilation, which on Spotify
# is disproportionately karaoke, covers and "50 Relaxing Songs" filler.
_ALBUM_TYPE_WEIGHT = {"album": 1.0, "single": 0.95, "compilation": 0.7}


def _confidence_for(track: dict[str, Any], in_range: bool) -> float:
    """Result-quality signal built from what ``/v1/search`` actually returns.

    Spotify's own ``popularity`` (0-100) would be the natural signal, but
    search returns *simplified* track objects that omit it, and the obvious
    fix -- a batched ``/v1/tracks`` enrichment call mirroring the YouTube
    adapter's ``videos.list`` -- **is rejected by Spotify with 403 for
    client-credentials tokens** (verified live, 2026-07-26). Rather than spend
    a request per search on a call that always fails, confidence is derived
    from fields that are present.

    This matters because of §4.7's lesson: a constant confidence collapses
    ranking onto fuzzy text match. The saving grace is that the failure mode
    is far milder here -- every Spotify hit is a real released recording, so
    confidence separates good from better, not real from fake, which is
    exactly what it had to do for YouTube.
    """
    album = track.get("album") or {}
    base = 0.72 * _ALBUM_TYPE_WEIGHT.get(str(album.get("album_type") or "").lower(), 0.85)

    # A single-artist release is a marginally safer "this is the recording you
    # meant" signal than a many-artist compilation entry.
    if len(track.get("artists") or []) == 1:
        base += 0.08
    # Market-aware: the caller asked for a playable track, not a greyed-out one.
    if track.get("is_playable") is False:
        base *= 0.4
    if not in_range:
        base *= 0.25
    return round(min(1.0, max(0.05, base)), 3)


def _normalize(track: dict[str, Any], min_seconds: int, max_seconds: int) -> Optional[dict[str, Any]]:
    track_id = track.get("id")
    name = (track.get("name") or "").strip()
    if not track_id or not name:
        return None

    artists = [a.get("name", "").strip() for a in (track.get("artists") or []) if a.get("name")]
    artist = ", ".join(artists) if artists else "Unknown artist"

    duration_ms = track.get("duration_ms")
    duration_seconds = int(duration_ms / 1000) if isinstance(duration_ms, (int, float)) else None
    in_range = (
        duration_seconds is not None and min_seconds <= duration_seconds <= max_seconds
    )

    url = (track.get("external_urls") or {}).get("spotify") or f"https://open.spotify.com/track/{track_id}"

    return {
        "provider": "spotify",
        "provider_track_id": track_id,
        "title": name,
        "artist": artist,
        "url": url,
        "confidence": _confidence_for(track, in_range),
        "duration_seconds": duration_seconds,
        # Spotify's embed player accepts any catalogue track, so unlike YouTube
        # there is no per-track embedding permission to respect.
        "embeddable": True,
        "duration_in_track_range": in_range if duration_seconds is not None else None,
        "field_sources": {
            "title": "search:tracks.items[].name",
            "artist": "search:tracks.items[].artists[].name",
            "duration_seconds": "search:tracks.items[].duration_ms",
            "confidence": "search:tracks.items[].popularity",
        },
    }


async def search(query: str, limit: int) -> list[dict[str, Any]]:
    """Search the Spotify catalogue and return NormalizedTrack-shaped dicts."""
    query = (query or "").strip()
    if not query:
        return []

    token = await _get_app_token()
    min_seconds, max_seconds = _duration_bounds()

    try:
        async with make_async_client() as client:
            response = await client.get(
                SEARCH_URL,
                params={
                    "q": query,
                    "type": "track",
                    # Over-fetch a little so the length filter below has room
                    # to drop intros/interludes without starving the caller.
                    "limit": min(50, max(limit * 2, limit)),
                    "market": _market(),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError("PROVIDER_UNAVAILABLE", "Could not reach Spotify.") from exc

    _raise_for_api_error(response)

    items = [i for i in (((response.json() or {}).get("tracks") or {}).get("items") or []) if i]
    tracks = [t for t in (_normalize(i, min_seconds, max_seconds) for i in items) if t]
    tracks.sort(key=lambda t: t["confidence"], reverse=True)

    # Same "prefer real track lengths, but never return nothing" rule the
    # YouTube adapter applies, so the two providers behave consistently.
    in_range = [t for t in tracks if t.get("duration_in_track_range") is not False]
    selected = in_range if len(in_range) >= min(limit, 3) else tracks
    return selected[:limit]
