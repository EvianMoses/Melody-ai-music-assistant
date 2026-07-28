"""YouTube Data API v3 search adapter (Phase 5 §5.1/§5.3).

Real, direct-mode search behind provider-gateway/main.py's /providers/search --
lifts the query straight to the REST API via httpx (no SDK, matching the
project's pattern in rag_client.py/provider_client.py) rather than the heavy
google-api-python-client package.

Two calls per search:

1. ``search.list``  (100 quota units) -- candidate discovery.
2. ``videos.list``  (1 quota unit, one batched call for all candidates) --
   enrichment: duration, region restrictions, embeddability. This is what lets
   the adapter drop hour-long DJ mixes and region-blocked/deleted videos, tell
   the caller whether the IFrame player will work (§PLAY-005), and dedupe
   alternate uploads of the *same recording* without merging genuinely
   distinct ones (§YT-004).

Enrichment is an improvement, not a hard dependency: if ``videos.list`` fails,
the search still returns unenriched results rather than failing outright.
"""

from __future__ import annotations

import difflib
import html
import json
import logging
import os
import re
from typing import Any, Optional

from shared_lib.http import make_async_client

logger = logging.getLogger("provider-gateway.youtube")

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
MUSIC_CATEGORY_ID = "10"
SEARCH_LIST_QUOTA_UNITS = 100
VIDEOS_LIST_QUOTA_UNITS = 1
# videos.list accepts at most 50 ids per call; search never returns more than 25.
VIDEOS_LIST_MAX_IDS = 50

# A "track" is roughly single-length. Below the floor is clips/shorts/intros;
# above the ceiling is DJ mixes, "1 Hour of ...", full-album uploads, and
# radio-style compilations -- the dominant noise in mood/vibe queries.
DEFAULT_MIN_TRACK_SECONDS = 60
DEFAULT_MAX_TRACK_SECONDS = 600  # 10 minutes
# Out-of-range candidates are penalized this hard before any soft-keep.
OUT_OF_RANGE_CONFIDENCE_FACTOR = 0.25
NOT_EMBEDDABLE_CONFIDENCE_FACTOR = 0.85
# Two uploads of the same recording rarely differ by more than a second or two.
SAME_RECORDING_DURATION_TOLERANCE_S = 2
SAME_RECORDING_TITLE_SIMILARITY = 0.82

# Bracketed release/format qualifiers. Deliberately tolerant of the quality
# token appearing *inside* the phrase ("Official HD Video", "Official 4K
# Audio"), which the previous pattern did not match -- so a title kept a
# trailing "(Official HD Video)" and it was shown to the user as part of the
# song name.
_QUALITY_TOKENS = r"(?:hd|hq|4k|8k|1080p|720p|remastered)"
_SUFFIX_RE = re.compile(
    r"[\(\[]\s*(?:"
    rf"official\s*(?:music\s*)?{_QUALITY_TOKENS}?\s*(?:video|audio|lyric\s*video)?"
    r"|lyrics?(?:\s*video)?"
    rf"|{_QUALITY_TOKENS}"
    r"|audio(?:\s*only)?"
    r"|visuali[sz]er"
    r"|full\s*album\s*stream"
    r")\s*[\)\]]",
    re.IGNORECASE,
)

# The same qualifiers appearing *bare* after a separator -- "Alison - HD",
# "Song (Official Audio) - HD". Without this the tail was treated as the song
# title: "Some Song (Official Audio) - HD" parsed to title="HD". Anchored to
# the end so a real title containing these words is untouched.
_TRAILING_QUALIFIER_RE = re.compile(
    rf"(?:\s*[-–—|]\s*(?:{_QUALITY_TOKENS}|audio(?:\s*only)?|lyrics?|visuali[sz]er))+\s*$",
    re.IGNORECASE,
)

_SEPARATORS = (" - ", " – ", " — ", " | ")
# A pipe is often typed without surrounding spaces ("שלמים| Idan Rafael Haviv"),
# which the fixed-string separator above misses -- the whole raw title then
# reached the UI as the song name. Safe to be lenient here specifically,
# because the pipe branch takes the artist from the channel rather than
# guessing which side is which.
_PIPE_SPLIT_RE = re.compile(r"\s*\|\s*")
_TOPIC_SUFFIX_RE = re.compile(r"\s*-\s*topic\s*$", re.IGNORECASE)
_OFFICIAL_MARKERS = ("official video", "official audio", "official music video", "official lyric video")

# Commentary / listicle / educational content that YouTube files under the
# Music category but which is *about* music rather than being a track. Duration
# filtering cannot catch these -- a video essay is 5-10 minutes, squarely
# inside track range. Live-observed for genre-shaped queries: "How Grunge
# Ended Hair Metal", "Top 5 Grunge Songs of All Time", "Grunge Vs Post Grunge
# Guitar Riffs". Matched as whole words/phrases against the raw title.
_NON_TRACK_TITLE_PATTERNS = (
    r"\btop\s*\d+\b",
    r"\bbest\s+(of|\d+)\b",
    r"\bgreatest\s+\d*\s*(songs|hits|tracks)\b",
    r"\b(vs\.?|versus)\b",
    r"\breact(ing|ion)\b",
    r"\bexplained\b",
    r"\bdocumentar(y|ies)\b",
    r"\binterview\b",
    r"\b(guitar|bass|drum|piano)\s+(lesson|tutorial|riffs?|cover)\b",
    r"\bhow\s+\w+\s+(ended|changed|created|invented|started|killed)\b",
    r"\bthe\s+(different\s+)?(styles|history|story|rise|fall)\s+of\b",
    r"\b(playlist|compilation|megamix|mixtape)\b",
    r"#shorts?\b",
)
_NON_TRACK_RE = re.compile("|".join(_NON_TRACK_TITLE_PATTERNS), re.IGNORECASE)
# Same "deprioritize, never hard-drop" philosophy as the duration rule: a
# false positive should cost a result its ranking, not its existence.
NON_TRACK_CONFIDENCE_FACTOR = 0.2
_ISO8601_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


class ProviderError(Exception):
    """A normalized, safe-to-surface provider failure (§PROV-002)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _target_region() -> str:
    return (os.getenv("YOUTUBE_REGION") or "IL").strip().upper()


def _duration_bounds() -> tuple[int, int]:
    def _int_env(name: str, default: int) -> int:
        try:
            return int(os.getenv(name) or default)
        except ValueError:
            return default

    return (
        _int_env("YOUTUBE_MIN_TRACK_SECONDS", DEFAULT_MIN_TRACK_SECONDS),
        _int_env("YOUTUBE_MAX_TRACK_SECONDS", DEFAULT_MAX_TRACK_SECONDS),
    )


def _record_quota_usage(method: str, units: int, provider: str = "youtube") -> None:
    """§YT-005 / N8N-REAL-004: record quota cost for every API method.

    Logged **and** persisted to `provider_quota_usage`. The log line stays --
    it is what makes a single request debuggable in `docker logs` -- but the row
    is what WF-008 reads, and quota is the hard operational limit in this system
    (10,000 units/day, `search.list` at 100 a call).

    Persistence is best-effort by construction: a monitoring write must never be
    able to fail a user's search. A database outage costs a row in a report, and
    turning that into a failed recommendation would be a strictly worse trade.
    """
    logger.info("youtube_quota_usage: %s", json.dumps({"method": method, "units": units}))

    try:
        from sqlalchemy import text as sql_text

        from . import db

        with db.session() as session:
            session.execute(
                sql_text(
                    "INSERT INTO provider_quota_usage (provider, method, units) "
                    "VALUES (:provider, :method, :units)"
                ),
                {"provider": provider, "method": method, "units": units},
            )
            session.commit()
    except Exception:  # noqa: BLE001 - deliberate: see docstring
        logger.warning("quota_usage_persist_failed", exc_info=True)


_WRAPPING_QUOTE_PAIRS = ('""', "''", "“”", "‘’")


def _strip_wrapping_quotes(text: str) -> str:
    """Titles are sometimes wrapped in quotes to set off the song name (live-
    observed: `&quot;Holocene&quot;` -> unescapes to `"Holocene"`). Strip one
    matching pair, not arbitrary quote characters anywhere in the string."""
    if len(text) >= 2:
        for open_q, close_q in _WRAPPING_QUOTE_PAIRS:
            if text[0] == open_q and text[-1] == close_q:
                return text[1:-1].strip()
    return text


def _strip_suffixes(title: str) -> str:
    cleaned = _SUFFIX_RE.sub("", title)
    # After bracketed qualifiers go, bare trailing ones may be exposed
    # ("X (Official Audio) - HD" -> "X - HD"), so strip those too.
    cleaned = _TRAILING_QUALIFIER_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split()).strip(" -|")
    return _strip_wrapping_quotes(cleaned)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"[^\w\s]", "", (text or "").lower()).strip()


def _sides_match_channel(left: str, right: str, channel_title: str) -> Optional[str]:
    """Return "left" or "right" if that side names the channel, else None.

    The "Artist - Title" convention is a guess, and it is wrong often enough to
    matter: `"שלמים | Idan Rafael Haviv"` on the channel `"עידן רפאל חביב"` is
    Title-then-Artist, and assuming the convention returned the *artist* as the
    song name and the song name as the artist. The channel is a much stronger
    signal than word order -- an official or artist channel is usually named
    after the artist -- so when one side matches it, that side is the artist.
    """
    channel = _normalize_for_match(_TOPIC_SUFFIX_RE.sub("", channel_title))
    if not channel:
        return None
    left_n, right_n = _normalize_for_match(left), _normalize_for_match(right)
    left_hit = bool(left_n) and (left_n in channel or channel in left_n)
    right_hit = bool(right_n) and (right_n in channel or channel in right_n)
    # Only decisive when exactly one side matches.
    if left_hit and not right_hit:
        return "left"
    if right_hit and not left_hit:
        return "right"
    return None


def _parse_title_artist(video_title: str, channel_title: str) -> tuple[str, str, float, str]:
    """Best-effort split of a noisy YouTube video title into
    (title, artist, parse_confidence, artist_source). Never drops a result --
    falls back to the channel name, and says so via ``artist_source`` (§PROV-005)."""
    cleaned = _strip_suffixes(video_title)

    lowered = cleaned.lower()
    if " by " in lowered:
        idx = lowered.rindex(" by ")
        title, artist = cleaned[:idx].strip(), cleaned[idx + 4:].strip()
        if title and artist:
            return title, artist, 1.0, "snippet.title"

    for sep in _SEPARATORS:
        if sep in cleaned:
            left, right = cleaned.split(sep, 1)
            left, right = left.strip(), right.strip()
            if left and right:
                # Prefer hard evidence over the convention: if one side names
                # the channel, that side is the artist regardless of order.
                match = _sides_match_channel(left, right, channel_title)
                if match == "right":
                    return left, right, 1.0, "snippet.title+channelTitle"
                if match == "left":
                    return right, left, 1.0, "snippet.title+channelTitle"

                # No channel evidence. "Artist - Title" is a real convention
                # for dash separators, but "|" is not an artist/title
                # separator at all -- it is a general-purpose divider, and
                # live evidence shows it carrying the opposite order:
                # "שלמים | Idan Rafael Haviv" on channel "עידן רפאל חביב" is
                # Title|Artist, and applying the dash convention returned the
                # artist as the song name. The two sides there are the same
                # name in different scripts, so no string match can rescue it.
                # For "|" the channel is simply the better artist source.
                if sep == " | ":
                    artist = _TOPIC_SUFFIX_RE.sub("", channel_title).strip() or channel_title.strip()
                    if artist:
                        return left, artist, 0.7, "snippet.title+channelTitle"

                # Dash separators: apply the convention, at reduced confidence
                # because it is still a guess.
                return right, left, 0.9, "snippet.title"

    # A pipe written without surrounding spaces, handled the same way as " | ".
    if "|" in cleaned:
        parts = [p for p in _PIPE_SPLIT_RE.split(cleaned) if p.strip()]
        if len(parts) >= 2:
            artist = _TOPIC_SUFFIX_RE.sub("", channel_title).strip() or channel_title.strip()
            match = _sides_match_channel(parts[0], parts[-1], channel_title)
            if match == "right":
                return parts[0].strip(), parts[-1].strip(), 1.0, "snippet.title+channelTitle"
            if match == "left":
                return parts[-1].strip(), parts[0].strip(), 1.0, "snippet.title+channelTitle"
            if artist:
                return parts[0].strip(), artist, 0.7, "snippet.title+channelTitle"

    # No separator found -- fall back to the channel as the artist.
    artist = _TOPIC_SUFFIX_RE.sub("", channel_title).strip() or channel_title.strip()
    return cleaned or video_title.strip(), artist, 0.6, "snippet.channelTitle"


def _looks_like_non_track(video_title_raw: str) -> bool:
    """True for commentary/listicle/lesson content -- *about* music, not music."""
    return bool(_NON_TRACK_RE.search(video_title_raw or ""))


def _confidence_for(channel_title: str, video_title_raw: str, parse_confidence: float) -> float:
    """§YT-002: transparent official-content heuristic, not an allow/deny
    filter -- everything gets a usable, never-zero score."""
    is_topic_channel = bool(_TOPIC_SUFFIX_RE.search(channel_title or ""))
    has_official_marker = any(marker in video_title_raw.lower() for marker in _OFFICIAL_MARKERS)

    if is_topic_channel:
        base = 0.95
    elif has_official_marker:
        base = 0.8
    else:
        base = 0.5

    if _looks_like_non_track(video_title_raw):
        # A Topic-channel upload is a real release even if its title happens to
        # trip a pattern, so the penalty is multiplicative rather than absolute.
        base *= NON_TRACK_CONFIDENCE_FACTOR

    return round(min(1.0, max(0.05, base * parse_confidence)), 3)


def _parse_iso8601_duration(value: str) -> Optional[int]:
    """`PT4M13S` -> 253 seconds. Returns None on anything unparseable rather
    than guessing -- a wrong duration would silently mis-filter a real track."""
    if not value:
        return None
    match = _ISO8601_DURATION_RE.match(value.strip())
    if not match:
        return None
    parts = {k: int(v) for k, v in match.groupdict(default="0").items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def _is_region_blocked(content_details: dict[str, Any], region: str) -> bool:
    """§PROV-002 unavailable-item / Phase 5 gate "playable in the target region"."""
    restriction = content_details.get("regionRestriction") or {}
    allowed = restriction.get("allowed")
    blocked = restriction.get("blocked")
    if allowed is not None:
        return region not in allowed
    if blocked:
        return region in blocked
    return False


def _apply_enrichment(
    track: dict[str, Any],
    details: dict[str, Any],
    region: str,
    min_seconds: int,
    max_seconds: int,
) -> Optional[dict[str, Any]]:
    """Fold one videos.list item into a normalized track.

    Returns None when the video is genuinely unusable (region-blocked), which
    the caller treats as "drop". Non-embeddable videos are NOT dropped --
    §PLAY-005 wants a plain provider link in that case, so the flag is carried
    through and the confidence is only nudged down.
    """
    content_details = details.get("contentDetails") or {}
    status = details.get("status") or {}

    if _is_region_blocked(content_details, region):
        return None

    duration_seconds = _parse_iso8601_duration(content_details.get("duration", ""))
    embeddable = status.get("embeddable")

    enriched = dict(track)
    enriched["duration_seconds"] = duration_seconds
    enriched["embeddable"] = bool(embeddable) if embeddable is not None else None
    enriched["field_sources"] = {
        **track.get("field_sources", {}),
        "duration_seconds": "videos.list:contentDetails.duration",
        "embeddable": "videos.list:status.embeddable",
        "region_checked": f"videos.list:contentDetails.regionRestriction({region})",
    }

    confidence = enriched["confidence"]
    in_range = duration_seconds is not None and min_seconds <= duration_seconds <= max_seconds
    enriched["duration_in_track_range"] = in_range if duration_seconds is not None else None
    if duration_seconds is not None and not in_range:
        confidence *= OUT_OF_RANGE_CONFIDENCE_FACTOR
    if enriched["embeddable"] is False:
        confidence *= NOT_EMBEDDABLE_CONFIDENCE_FACTOR
    enriched["confidence"] = round(max(0.05, confidence), 3)
    return enriched


def _dedupe(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """§YT-004. Two passes, both keeping the highest-confidence entry:

    1. Exact normalized (artist, title) -- catches straightforward re-uploads.
    2. Duration-aware: same artist, near-identical duration, and a
       fuzzy-similar title. This is the pass that catches the same recording
       uploaded under a cosmetically different title, and it is deliberately
       gated on duration -- a live version, remix, or extended edit has a
       different runtime, so it survives as a distinct recording. Entries
       without a known duration are never fuzzy-merged (unenriched results
       fall back to pass-1 behavior only), because merging on title alone is
       exactly the "incorrectly merging distinct recordings" failure the plan
       warns against.
    """
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for track in tracks:
        key = (track["artist"].strip().lower(), track["title"].strip().lower())
        existing = best.get(key)
        if existing is None or track["confidence"] > existing["confidence"]:
            best[key] = track

    survivors: list[dict[str, Any]] = []
    for candidate in sorted(best.values(), key=lambda t: t["confidence"], reverse=True):
        duration = candidate.get("duration_seconds")
        merged_into_existing = False
        if duration is not None:
            for kept in survivors:
                kept_duration = kept.get("duration_seconds")
                if kept_duration is None:
                    continue
                if kept["artist"].strip().lower() != candidate["artist"].strip().lower():
                    continue
                if abs(kept_duration - duration) > SAME_RECORDING_DURATION_TOLERANCE_S:
                    continue
                similarity = difflib.SequenceMatcher(
                    None, kept["title"].strip().lower(), candidate["title"].strip().lower()
                ).ratio()
                if similarity >= SAME_RECORDING_TITLE_SIMILARITY:
                    # Survivors are iterated highest-confidence-first, so the
                    # kept entry already wins; just drop the duplicate.
                    merged_into_existing = True
                    break
        if not merged_into_existing:
            survivors.append(candidate)
    return survivors


def _raise_for_api_error(response: Any, what: str) -> None:
    """Map a YouTube HTTP failure onto the normalized §PROV-002 codes."""
    if response.status_code == 200:
        return
    if response.status_code == 429:
        raise ProviderError("RATE_LIMITED", f"YouTube {what} is rate-limited.")
    if response.status_code == 403:
        reason = ""
        try:
            errors = response.json().get("error", {}).get("errors", [])
            reason = errors[0].get("reason", "") if errors else ""
        except (ValueError, KeyError, IndexError):
            pass
        if reason in ("quotaExceeded", "dailyLimitExceeded"):
            raise ProviderError("QUOTA_EXCEEDED", f"YouTube {what} quota exceeded.")
        raise ProviderError("PROVIDER_UNAVAILABLE", f"YouTube {what} request was forbidden.")
    raise ProviderError("PROVIDER_UNAVAILABLE", f"YouTube {what} returned {response.status_code}.")


async def _fetch_video_details(
    client: Any, video_ids: list[str], api_key: str
) -> dict[str, dict[str, Any]]:
    """One batched videos.list call (1 quota unit) -> {video_id: item}.

    IDs absent from the response are deleted/private/otherwise gone -- the
    caller treats a missing id as an unavailable item (§PROV-002).
    """
    if not video_ids:
        return {}
    response = await client.get(
        VIDEOS_URL,
        params={"part": "contentDetails,status", "id": ",".join(video_ids[:VIDEOS_LIST_MAX_IDS])},
        headers={"X-Goog-Api-Key": api_key},
    )
    _record_quota_usage("videos.list", VIDEOS_LIST_QUOTA_UNITS)
    _raise_for_api_error(response, "video details")
    return {item["id"]: item for item in response.json().get("items", []) if item.get("id")}


async def search(query: str, limit: int) -> list[dict[str, Any]]:
    """§PROV-001/§YT-001: real YouTube search + videos.list enrichment.

    Raises ProviderError on quota/rate-limit/outage -- caller (main.py) maps
    it to an HTTP response.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ProviderError("PROVIDER_UNAVAILABLE", "YOUTUBE_API_KEY is not configured.")

    region = _target_region()
    min_seconds, max_seconds = _duration_bounds()

    params = {
        "part": "snippet",
        "type": "video",
        "videoCategoryId": MUSIC_CATEGORY_ID,
        "q": query,
        "maxResults": min(max(limit * 2, 10), 25),
        "regionCode": region,
    }

    async with make_async_client() as client:
        try:
            # Key goes in a header, not the "key" query param -- httpx's own
            # request logger logs the full URL (observed live: the key showed
            # up in plaintext in container logs), and query params also leak
            # via proxies/referrers/access logs in general. Google's API
            # infrastructure accepts X-Goog-Api-Key for simple API-key auth
            # on any REST endpoint, same mechanism as the query param.
            response = await client.get(
                SEARCH_URL, params=params, headers={"X-Goog-Api-Key": api_key}
            )
        except Exception as exc:  # httpx.TimeoutException, httpx.ConnectError, etc.
            raise ProviderError("PROVIDER_UNAVAILABLE", f"YouTube search unreachable: {exc}") from exc

        _record_quota_usage("search.list", SEARCH_LIST_QUOTA_UNITS)
        _raise_for_api_error(response, "search")

        items = response.json().get("items", [])
        tracks: list[dict[str, Any]] = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            # The API returns HTML-escaped snippet text (e.g. "&quot;", "&amp;") --
            # unescape before parsing/displaying, or titles render with entities
            # (seen live: `&quot;Holocene&quot;` instead of `"Holocene"`).
            raw_title = html.unescape(snippet.get("title", ""))
            channel_title = html.unescape(snippet.get("channelTitle", ""))
            if not video_id or not raw_title:
                continue

            title, artist, parse_confidence, artist_source = _parse_title_artist(
                raw_title, channel_title
            )
            tracks.append(
                {
                    "provider": "youtube",
                    "provider_track_id": video_id,
                    "title": title,
                    "artist": artist,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "confidence": _confidence_for(channel_title, raw_title, parse_confidence),
                    # Enrichment keys are always present (None until videos.list
                    # fills them) so consumers never need an existence check --
                    # the shape is identical enriched or not.
                    "duration_seconds": None,
                    "embeddable": None,
                    "duration_in_track_range": None,
                    # §PROV-005: per-field provenance, plus the parse confidence
                    # that title/artist specifically depend on.
                    "field_sources": {
                        "title": "search.list:snippet.title(parsed)",
                        "artist": f"search.list:{artist_source}",
                        "parse_confidence": parse_confidence,
                    },
                }
            )

        # Enrichment: 1 quota unit for the whole batch, vs 100 for the search.
        # Never fail the search because enrichment failed -- degrade to
        # unenriched results, which are still usable, just unfiltered.
        try:
            details = await _fetch_video_details(
                client, [t["provider_track_id"] for t in tracks], api_key
            )
        except ProviderError as exc:
            logger.warning("videos.list enrichment failed, returning unenriched results: %s", exc.message)
            details = None

    if details is not None:
        enriched: list[dict[str, Any]] = []
        for track in tracks:
            detail = details.get(track["provider_track_id"])
            if detail is None:
                # Present in search but absent from videos.list => deleted,
                # private, or otherwise unavailable (§PROV-002 missing item).
                continue
            result = _apply_enrichment(track, detail, region, min_seconds, max_seconds)
            if result is not None:  # None => region-blocked, genuinely unusable
                enriched.append(result)
        tracks = enriched

    deduped = _dedupe(tracks)
    deduped.sort(key=lambda t: t["confidence"], reverse=True)

    # Prefer real single-length tracks, but never return an empty list just
    # because everything was a long mix -- that recreates the zero-results
    # failure this adapter was fixed for. Out-of-range entries stay available
    # as a clearly-deprioritized fallback (their confidence is already cut).
    in_range = [t for t in deduped if t.get("duration_in_track_range") is not False]
    selected = in_range if len(in_range) >= min(limit, 3) else deduped
    return selected[:limit]
