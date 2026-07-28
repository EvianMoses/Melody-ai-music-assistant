"""Last.fm music-knowledge adapter (agent tool: artist info and music history).

Reactivates and expands `aws/info_lambda_package/extra_tools_lambda.py`, the
Bedrock action-group Lambda that fetched artist biographies. Three things
changed on the way across:

1. **It lives in provider-gateway**, not in the agent. ADR-001 puts "normalized
   provider data" in the Provider Adapter Layer, and Last.fm is a provider like
   any other -- so quota, error vocabulary and timeouts are handled the same way
   as YouTube and Spotify rather than reinvented inside a prompt.
2. **It returns structured data, not a preformatted string.** The Lambda built
   `"Artist: X\\nBio: Y\\n..."` because Bedrock action groups pass strings. An
   agent tool result is JSON, and prose assembled here would fight the system
   prompt's own voice and language rules.
3. **It answers more than "who is this artist".** The developer asked for band
   histories and major historical music events, so the adapter exposes a
   timeline built from real Last.fm data rather than a single bio blob.

⚠️ **The honest boundary of what Last.fm can support.** Last.fm has no
"historical events" endpoint. What it genuinely has is artist biographies (which
contain formation dates and career narrative), tags, similar artists, top
albums/tracks, and tag-level charts. `get_music_history` therefore composes
those into a timeline and **says where each part came from**. It does not invent
a chronology, and when the data will not support one it says so -- an invented
music history is exactly the failure mode §2.5 exists to prevent.
"""

from __future__ import annotations

import html
import logging
import os
import re
from typing import Any, Optional

from shared_lib.http import make_async_client

from .youtube_adapter import ProviderError

logger = logging.getLogger("melody.provider.lastfm")

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
DEFAULT_TIMEOUT = 10.0

# Last.fm bios end with a "Read more on Last.fm" CC-BY link. Useful legally,
# noise in a prompt -- and the model would otherwise repeat it to the user as if
# it were part of the artist's story.
_BIO_FOOTER = re.compile(r"<a href=.*?</a>\s*$", re.IGNORECASE | re.DOTALL)
_HTML_TAG = re.compile(r"<[^>]+>")

# Years that plausibly belong to recorded music history. Guards against picking
# up a track duration or a chart position and presenting it as a date.
_YEAR = re.compile(r"\b(1[89]\d{2}|20[0-2]\d)\b")


def _api_key() -> str:
    key = (os.getenv("LASTFM_API_KEY") or "").strip()
    if not key:
        raise ProviderError("PROVIDER_UNAVAILABLE", "Music history is unavailable: LASTFM_API_KEY is not configured.")
    return key


def _clean_text(value: str) -> str:
    """Strip Last.fm's HTML and its trailing attribution link."""
    text = _BIO_FOOTER.sub("", value or "")
    text = _HTML_TAG.sub("", text)
    return html.unescape(text).strip()


async def _call(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """One Last.fm call, with this project's normalized error vocabulary.

    The API key travels as a query parameter because Last.fm supports no other
    scheme -- unlike the YouTube fix, where moving it to a header removed it from
    logs entirely. So it is kept out of any logged URL by never logging one: the
    error paths below report the method and status, never the request.
    """
    query = {**params, "method": method, "api_key": _api_key(), "format": "json"}
    try:
        async with make_async_client() as client:
            response = await client.get(LASTFM_API_URL, params=query, timeout=DEFAULT_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("lastfm_unreachable method=%s: %s", method, type(exc).__name__)
        raise ProviderError("PROVIDER_UNAVAILABLE", "The music knowledge service is temporarily unreachable.") from exc

    if response.status_code == 429:
        raise ProviderError("RATE_LIMITED", "The music knowledge service is rate limited; try again shortly.")
    if response.status_code >= 500:
        raise ProviderError("PROVIDER_UNAVAILABLE", "The music knowledge service is temporarily unavailable.")

    try:
        data = response.json()
    except ValueError as exc:
        raise ProviderError("PROVIDER_UNAVAILABLE", "The music knowledge service returned an unreadable response.") from exc

    # Last.fm reports its own errors with HTTP 200 and an `error` code -- 6 is
    # "not found", which is a normal answer to a misspelt artist rather than a
    # failure of the system.
    if isinstance(data, dict) and "error" in data:
        if int(data.get("error", 0)) == 6:
            return {}
        logger.warning("lastfm_api_error method=%s code=%s", method, data.get("error"))
        raise ProviderError("PROVIDER_UNAVAILABLE", "The music knowledge service rejected that request.")
    return data if isinstance(data, dict) else {}


async def get_artist_info(artist_name: str) -> dict[str, Any]:
    """Biography, tags and similar artists for one artist.

    Returns ``{"found": False, ...}`` rather than raising when the artist is
    unknown: "I could not find that artist" is an answer the agent should be
    able to give in the user's own language, not an error it has to interpret.
    """
    name = (artist_name or "").strip()
    if not name:
        return {"found": False, "reason": "no artist name supplied"}

    data = await _call("artist.getinfo", {"artist": name, "autocorrect": "1"})
    artist = data.get("artist") if isinstance(data, dict) else None
    if not artist:
        return {"found": False, "query": name, "reason": "no matching artist"}

    stats = artist.get("stats") or {}
    return {
        "found": True,
        "name": artist.get("name") or name,
        # `autocorrect=1` fixes "shakiraa" -> "Shakira", which the original
        # system prompt asked the MODEL to do. Better done by the API: it has the
        # catalogue, and a model correcting spellings invents plausible ones.
        "corrected_from": name if (artist.get("name") or name) != name else None,
        "biography": _clean_text((artist.get("bio") or {}).get("summary", "")),
        "biography_full": _clean_text((artist.get("bio") or {}).get("content", "")),
        "formed_year": _first_year(_clean_text((artist.get("bio") or {}).get("content", ""))),
        "tags": [t.get("name") for t in (artist.get("tags") or {}).get("tag", []) if t.get("name")][:6],
        "similar_artists": [
            a.get("name") for a in (artist.get("similar") or {}).get("artist", []) if a.get("name")
        ][:6],
        "listeners": _as_int(stats.get("listeners")),
        "playcount": _as_int(stats.get("playcount")),
        "url": artist.get("url"),
        # True when several acts share this name and Last.fm returned a
        # disambiguation page. The agent must say so rather than picking one.
        "ambiguous_name": _is_disambiguation(
            _clean_text((artist.get("bio") or {}).get("content", ""))
        ),
        "source": "last.fm",
    }


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# Last.fm has no formation-year field, so a year has to come out of prose. Only
# a year sitting next to an explicit formation phrase is trusted.
_FORMED_NEAR_YEAR = re.compile(
    r"\b(?:formed|founded|form(?:ed)?\s+in|established|began|started|born)\b"
    r"[^.]{0,40}?\b(1[89]\d{2}|20[0-2]\d)\b",
    re.IGNORECASE,
)

# Last.fm returns a DISAMBIGUATION bio when several acts share a name, e.g.
# "There are multiple artists tracked as \"Nirvana\"... six, listed in order of
# prominence". Any year mined from that text may belong to a different band.
_DISAMBIGUATION = re.compile(
    r"there (?:are|is) (?:multiple|several|\d+) artists?", re.IGNORECASE
)


def _first_year(text: str) -> Optional[int]:
    """Formation year, or None -- and None is a perfectly good answer.

    ⚠️ MEASURED FAILURE that produced this version: the first implementation
    took the *earliest* year anywhere in the biography, on the theory that bios
    open with a recent album before recounting history. Asked about **Nirvana**
    it returned **1967** -- because Last.fm's Nirvana bio is a disambiguation
    page covering six different acts, one of them a 1960s British band. A
    confidently wrong date is worse than no date, because the user cannot tell.

    Two guards now: refuse outright on a disambiguation bio, and otherwise only
    accept a year that sits next to an explicit formation phrase.
    """
    text = text or ""
    if _DISAMBIGUATION.search(text):
        return None
    match = _FORMED_NEAR_YEAR.search(text)
    return int(match.group(1)) if match else None


def _is_disambiguation(text: str) -> bool:
    """Whether this biography describes several different acts sharing a name."""
    return bool(_DISAMBIGUATION.search(text or ""))


async def get_music_history(subject: str) -> dict[str, Any]:
    """A grounded timeline for an artist, band or musical movement.

    Composed from three real Last.fm sources rather than one, because no single
    endpoint answers "tell me the history of X":

      * `artist.getinfo`  -- narrative biography and formation year
      * `artist.gettopalbums` -- the discography spine a timeline hangs on
      * `tag.getinfo`     -- when the subject is a genre or movement, not an act

    ⚠️ **Every element carries its source, and nothing is inferred.** Last.fm has
    no events endpoint; a chronology invented to look complete would be exactly
    the fabrication §2.5 forbids. When the data cannot support a timeline, this
    says so and lets the agent tell the user plainly.
    """
    name = (subject or "").strip()
    if not name:
        return {"found": False, "reason": "no subject supplied"}

    # Ask BOTH, then decide -- artist-first was wrong.
    #
    # ⚠️ MEASURED FAILURE: `artist.getinfo` with autocorrect happily matched an
    # obscure act literally named "shoegaze", so asking for the history of
    # shoegaze returned "shoegaze is a singer; songwriter based in the UK". The
    # genre branch was unreachable for exactly the subjects most likely to need
    # it, because any well-known genre name is also somebody's stage name.
    info = await get_artist_info(name)
    tag = await _call("tag.getinfo", {"tag": name})
    tag_data = (tag or {}).get("tag") or {}
    tag_reach = _as_int(tag_data.get("reach")) or 0
    artist_listeners = info.get("listeners") or 0

    # A genre wins when it is widely used AND the artist match is comparatively
    # obscure. Both halves matter: "Nirvana" is also a tag, but the band dwarfs
    # it; "shoegaze" is a tag used by hundreds of thousands and an artist almost
    # nobody listens to.
    prefer_tag = bool(tag_data.get("name")) and tag_reach > 1000 and artist_listeners < tag_reach

    if info.get("found") and not prefer_tag:
        albums = await _call("artist.gettopalbums", {"artist": info["name"], "limit": 10})
        album_list = ((albums.get("topalbums") or {}).get("album") or []) if albums else []
        discography = [
            {
                "album": a.get("name"),
                "playcount": _as_int(a.get("playcount")),
                "url": a.get("url"),
            }
            for a in album_list
            if a.get("name") and a.get("name") != "(null)"
        ][:8]

        return {
            "found": True,
            "subject": info["name"],
            "subject_type": "artist",
            "formed_year": info.get("formed_year"),
            "narrative": info.get("biography_full") or info.get("biography"),
            "genres": info.get("tags"),
            "contemporaries": info.get("similar_artists"),
            "notable_releases": discography,
            "listeners": info.get("listeners"),
            "url": info.get("url"),
            "source": "last.fm",
            "ambiguous_name": info.get("ambiguous_name", False),
            "coverage_note": (
                "Biography and discography from Last.fm. Album entries are ordered by "
                "listening popularity, not release date -- Last.fm does not expose "
                "release years here, so do not present them as a chronology."
                + (
                    " WARNING: several different acts share this name and Last.fm "
                    "returned a disambiguation page. Say so rather than presenting "
                    "one of them as definitive."
                    if info.get("ambiguous_name")
                    else ""
                )
            ),
        }

    # Genre / movement branch: either the artist lookup failed, or the tag is
    # so much better known that treating the name as an act would mislead.
    if tag_data.get("name"):
        return {
            "found": True,
            "subject": tag_data.get("name"),
            "subject_type": "genre_or_movement",
            "narrative": _clean_text((tag_data.get("wiki") or {}).get("summary", "")),
            "reach": tag_reach,
            "also_matches_an_artist": bool(info.get("found")),
            "total_uses": _as_int(tag_data.get("total")),
            "source": "last.fm",
            "coverage_note": (
                "This is a genre/movement description, not an artist biography. "
                "For a chronology of the movement, the project's own genre corpus "
                "(search_knowledge) is richer than Last.fm."
            ),
        }

    return {
        "found": False,
        "subject": name,
        "reason": "no matching artist, band, genre or movement",
    }


async def get_similar_artists(artist_name: str, limit: int = 8) -> dict[str, Any]:
    """Artists Last.fm considers similar -- real listening data, not a guess.

    Useful to the agent for two distinct jobs: answering "who sounds like X?"
    directly, and turning a vague taste statement into concrete artist names that
    provider search can actually find, which §5.3 identified as the highest-
    leverage fix for recommendation quality.
    """
    name = (artist_name or "").strip()
    if not name:
        return {"found": False, "reason": "no artist name supplied"}

    data = await _call(
        "artist.getsimilar", {"artist": name, "autocorrect": "1", "limit": max(1, min(limit, 20))}
    )
    similar = ((data.get("similarartists") or {}).get("artist") or []) if data else []
    if not similar:
        return {"found": False, "query": name, "reason": "no similar artists found"}

    return {
        "found": True,
        "query": name,
        "similar": [
            {"name": a.get("name"), "match": _as_float(a.get("match")), "url": a.get("url")}
            for a in similar
            if a.get("name")
        ],
        "source": "last.fm",
    }


def _as_float(value: Any) -> Optional[float]:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None
