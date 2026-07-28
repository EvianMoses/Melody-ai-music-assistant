"""YouTube playlist creation and population (Phase 5 §5.5, EXPORT-001…003).

The first code in the project that *writes* to an external provider. Everything
before this was read-only, which is why §4.3 could state "search-provider writes
are forbidden; only reads occur inside LangGraph" -- writes live here, reached
only through n8n's WF-006.

⚠️ Quota dominates the design. ``playlists.insert`` costs **50** units and
``playlistItems.insert`` costs **50 per track**, against a 10,000/day project
quota shared with search (100/query). A 10-track export is 550 units, i.e. only
~18 exports/day. Consequences: the track list is capped
(``YOUTUBE_MAX_EXPORT_TRACKS``), a quota error aborts immediately rather than
retrying, and every call is recorded through the shared quota logger.

Partial failure is expected and non-fatal: an individual video can be deleted or
region-locked, so a failing item is recorded and the export continues -- the
playlist still exists and still holds the tracks that worked (EXPORT-002).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from shared_lib.http import make_async_client

from .youtube_adapter import ProviderError, _raise_for_api_error, _record_quota_usage

logger = logging.getLogger("provider-gateway.youtube_playlist")

PLAYLISTS_URL = "https://www.googleapis.com/youtube/v3/playlists"
PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
PLAYLISTS_INSERT_QUOTA_UNITS = 50
PLAYLIST_ITEMS_INSERT_QUOTA_UNITS = 50

DEFAULT_MAX_EXPORT_TRACKS = 25
DEFAULT_PRIVACY_STATUS = "private"

# Track ids arrive either bare ("dQw4w9WgXcQ") or provider-prefixed
# ("yt:dQw4w9WgXcQ" -- the shape the e2e smoke test sends). Accept both rather
# than making callers guess which one this endpoint wants.
_PREFIX_RE = re.compile(r"^(?:yt|youtube):", re.IGNORECASE)


def normalize_video_id(raw: str) -> str:
    return _PREFIX_RE.sub("", str(raw).strip())


def _max_tracks() -> int:
    try:
        return max(1, int(os.getenv("YOUTUBE_MAX_EXPORT_TRACKS") or DEFAULT_MAX_EXPORT_TRACKS))
    except ValueError:
        return DEFAULT_MAX_EXPORT_TRACKS


def _privacy_status() -> str:
    value = (os.getenv("YOUTUBE_PLAYLIST_PRIVACY") or DEFAULT_PRIVACY_STATUS).strip().lower()
    return value if value in ("private", "unlisted", "public") else DEFAULT_PRIVACY_STATUS


def _auth_headers(access_token: str) -> dict[str, str]:
    # OAuth bearer, not the X-Goog-Api-Key used for search: playlist writes are
    # performed as the user, not as the project.
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def _raise_for_write_error(response: Any, what: str) -> None:
    """Map write-specific failures before falling back to the shared mapping.

    Reads can't produce these: an expired user token or a missing scope only
    exist once calls are made *as a user*.
    """
    if response.status_code == 401:
        raise ProviderError(
            "REAUTHORIZATION_REQUIRED",
            "The Google authorization is no longer valid; please reconnect.",
        )
    if response.status_code == 403:
        reason = ""
        try:
            errors = response.json().get("error", {}).get("errors", [])
            reason = errors[0].get("reason", "") if errors else ""
        except (ValueError, KeyError, IndexError):
            pass
        if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
            raise ProviderError("QUOTA_EXCEEDED", f"YouTube {what} quota exceeded.")
        if reason in ("insufficientPermissions", "forbidden"):
            raise ProviderError(
                "INSUFFICIENT_SCOPE",
                "This connection does not grant YouTube playlist access.",
            )
    _raise_for_api_error(response, what)


async def create_playlist(
    client: Any, *, access_token: str, title: str, description: str
) -> dict[str, str]:
    body = {
        "snippet": {"title": title[:150], "description": (description or "")[:5000]},
        "status": {"privacyStatus": _privacy_status()},
    }
    try:
        response = await client.post(
            PLAYLISTS_URL,
            params={"part": "snippet,status"},
            json=body,
            headers=_auth_headers(access_token),
        )
    except Exception as exc:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", f"YouTube playlist creation unreachable: {exc}"
        ) from exc

    _record_quota_usage("playlists.insert", PLAYLISTS_INSERT_QUOTA_UNITS)
    _raise_for_write_error(response, "playlist creation")

    payload = response.json()
    playlist_id = payload.get("id")
    if not playlist_id:
        raise ProviderError("PROVIDER_UNAVAILABLE", "YouTube returned no playlist id.")
    return {
        "playlist_id": playlist_id,
        "url": f"https://www.youtube.com/playlist?list={playlist_id}",
    }


async def add_track(client: Any, *, access_token: str, playlist_id: str, video_id: str) -> None:
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    try:
        response = await client.post(
            PLAYLIST_ITEMS_URL,
            params={"part": "snippet"},
            json=body,
            headers=_auth_headers(access_token),
        )
    except Exception as exc:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", f"YouTube playlist item insert unreachable: {exc}"
        ) from exc

    _record_quota_usage("playlistItems.insert", PLAYLIST_ITEMS_INSERT_QUOTA_UNITS)
    _raise_for_write_error(response, "playlist item insert")


async def export_playlist(
    *,
    access_token: str,
    name: str,
    track_ids: list[str],
    description: str = "",
) -> dict[str, Any]:
    """Create a playlist and add the tracks.

    Returns ``{playlist_id, url, added, failed, status}``. ``status`` is
    ``completed`` or ``partial``; a quota error mid-run aborts the remaining
    inserts (retrying would only burn more of a budget that is already spent)
    but still returns the playlist that was created, with the rest recorded as
    failures.
    """
    ids = [normalize_video_id(t) for t in track_ids if str(t).strip()]
    ids = [i for i in ids if i]
    if not ids:
        raise ProviderError("MISSING_ITEM", "No track ids were supplied to export.")

    capped = ids[: _max_tracks()]
    failed: list[dict[str, str]] = []
    if len(ids) > len(capped):
        dropped = ids[len(capped):]
        logger.warning(
            "export_track_cap_applied",
            extra={"requested": len(ids), "exported": len(capped)},
        )
        failed.extend(
            {"video_id": v, "reason": "TRACK_CAP_EXCEEDED"} for v in dropped
        )

    async with make_async_client() as client:
        created = await create_playlist(
            client, access_token=access_token, title=name, description=description
        )

        added: list[str] = []
        for video_id in capped:
            try:
                await add_track(
                    client,
                    access_token=access_token,
                    playlist_id=created["playlist_id"],
                    video_id=video_id,
                )
                added.append(video_id)
            except ProviderError as exc:
                # Quota is terminal for this run; a single bad video is not.
                failed.append({"video_id": video_id, "reason": exc.code})
                if exc.code == "QUOTA_EXCEEDED":
                    failed.extend(
                        {"video_id": v, "reason": "SKIPPED_AFTER_QUOTA_EXCEEDED"}
                        for v in capped[len(added) + 1:]
                    )
                    break

    return {
        "playlist_id": created["playlist_id"],
        "url": created["url"],
        "added": added,
        "failed": failed,
        "status": "completed" if not failed else "partial",
    }
