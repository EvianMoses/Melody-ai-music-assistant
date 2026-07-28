"""ACRCloud recognition adapter (§6.4, REC-ID-004/005).

Implements ACRCloud's Audio & Video Recognition `/v1/identify` call: an
HMAC-SHA1 signed multipart POST. The signature is over a fixed six-line string,
and getting any line wrong produces the same `3001 Missing/Invalid Access Key`
as a wrong key would — which is why `describe_configuration()` exists and why
the probe result is reported rather than guessed at.

**Three states, kept distinct**, because collapsing them is how a user ends up
told "no match" for a feature that never ran:

* `configured: False` — no credentials or no host. Not a failure, a gap.
* `matched: False` — the service ran and genuinely recognized nothing.
* `matched: True` — with a score, mapped through the thresholds below.

Nothing here fabricates. If the call fails, that is reported as a failure.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("melody.audio.acrcloud")

# REC-ID-005 — confidence thresholds, fixed before any measurement.
#
# ACRCloud returns `score` 0-100, which is a fingerprint-match strength, not a
# probability. Two bands rather than one, because the middle band is real: a
# noisy phone recording of a genuine match often lands in the 60s, and throwing
# it away is as wrong as presenting it as certain.
MATCH_SCORE = 80.0        # confident enough to state as fact
LOW_CONFIDENCE_SCORE = 60.0  # show, but say it is uncertain

# ⚠️ The melody index scores on a completely different scale: **0–1, not 0–100**.
# Measured against six real hums with known answers (2026-07-28): the one clearly
# correct match scored 0.80, and everything else fell between 0.30 and 0.67.
# Applying the fingerprint thresholds above to those numbers rejects every
# melody result no matter how good it is -- which is why recognition still
# reported "no match" after the `metadata.humming` bug was fixed.
#
# 0.75 is deliberately strict. On that test set it yields **one match, correct,
# and no false positives**; dropping it to 0.6 would surface three wrong answers
# (a Japanese city-pop track for "Something", "Heaven" by the wrong artist, an
# unrelated "Wannabe"). A confidently wrong answer is the failure the user
# cannot detect, and this index produces them readily.
HUMMING_MATCH_SCORE = 0.75

# No low-confidence band for melody matches. On the fingerprint index the 60–80
# band holds genuinely correct noisy captures; here the equivalent band is
# almost entirely wrong answers, so showing it would trade a clean miss for a
# plausible lie.
HUMMING_LOW_CONFIDENCE_SCORE = 0.75

# ACRCloud's own status codes, mapped to something a caller can act on.
_NO_RESULT_CODES = {1001}
_AUTH_CODES = {3001, 3002}
_LIMIT_CODES = {3003, 3015}

DEFAULT_TIMEOUT_SECONDS = 15.0

# The identification host is issued per project and per region, so there is no
# usable default. Listed here only so an operator can see the shapes that exist.
KNOWN_HOSTS = (
    "identify-eu-west-1.acrcloud.com",
    "identify-us-west-2.acrcloud.com",
    "identify-ap-southeast-1.acrcloud.com",
    "identify-ap-northeast-1.acrcloud.com",
    "identify-cn-north-1.acrcloud.cn",
)


def _env(*names: str) -> str:
    """First non-empty value among several spellings of the same setting.

    The repository's `.env` uses `acrcloud_api_key`; ACRCloud's own docs and
    every other service here use SCREAMING_SNAKE. Accepting both avoids a
    silent misconfiguration that looks exactly like a rejected key.
    """
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


# How many ranked alternatives to hand back. ACRCloud returns up to five; more
# than four on screen stops being a choice and becomes a list to read.
MAX_CANDIDATES = 4


@dataclass(frozen=True)
class Recognition:
    configured: bool
    matched: bool
    confidence: float
    track: dict[str, Any] = field(default_factory=dict)
    low_confidence: bool = False
    reason: Optional[str] = None
    provider: str = "acrcloud"
    # Every plausible candidate the provider ranked, best first, each with its
    # own confidence.
    #
    # This is not a nicety. Melody matching returns a *ranked* list and its
    # top-1 accuracy is poor: measured on six real hums, the correct answer for
    # "Heaven" was returned at **rank 2** while a wrong track held rank 1, so
    # collapsing the list to its head turned a findable answer into "no match".
    # Handing the user the list is what Google's hum-to-search does when it is
    # unsure, and it is the honest response to a ranking we do not trust.
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "matched": self.matched,
            "confidence": self.confidence,
            "track": self.track,
            "low_confidence": self.low_confidence,
            "reason": self.reason,
            "provider": self.provider,
            "candidates": self.candidates,
        }


def _credentials() -> tuple[str, str, str]:
    host = _env("ACRCLOUD_HOST", "acrcloud_host")
    key = _env("ACRCLOUD_ACCESS_KEY", "acrcloud_api_key", "acrcloud_access_key")
    secret = _env("ACRCLOUD_ACCESS_SECRET", "acrcloud_api_secret", "acrcloud_access_secret")
    return host, key, secret


def is_configured() -> bool:
    host, key, secret = _credentials()
    return bool(host and key and secret)


def describe_configuration() -> dict[str, Any]:
    """What is present, without revealing any of it.

    Lengths only: ACRCloud issues a 32-character access key and a 40-character
    secret for Audio & Video Recognition projects, so a length mismatch is a
    strong hint that the credentials came from a different product section --
    a diagnosis that is otherwise indistinguishable from a wrong key, because
    both answer `3001`.
    """
    host, key, secret = _credentials()
    return {
        "host_set": bool(host),
        "access_key_set": bool(key),
        "access_secret_set": bool(secret),
        "access_key_length": len(key),
        "access_secret_length": len(secret),
        "expected_access_key_length": 32,
        "expected_access_secret_length": 40,
        "configured": bool(host and key and secret),
    }


def _signature(secret: str, key: str, timestamp: str, data_type: str = "audio") -> str:
    # The signed string is positional and newline-separated; every field must
    # match the request exactly -- including the literal path AND the data_type.
    # Signing "audio" while sending "humming" fails with the same 3001 as a bad
    # key, which is the confusion this whole module is arranged to avoid.
    string_to_sign = "\n".join(["POST", "/v1/identify", key, data_type, "1", timestamp])
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(digest.digest()).decode("ascii")


# Catalogue junk. ACRCloud's index contains placeholder entries, and they are
# the single biggest source of *wrong* answers -- worse than a miss, because the
# user cannot tell a confident wrong answer from a right one.
#
# Two real observations drove this list, and both matter:
#   * a field report of `'Remix' — 'DJ' — album 'Remix'` returned at score 64
#     for Ariana Grande's "Problem";
#   * `'Fingerprint Less' — 'Kanroc Xpitaf'` returned at **score 100** for a
#     GTZAN rock clip whose real identity is "Killing In The Name".
#
# The second is why this check cannot be limited to low scores: a junk entry
# fingerprints just as strongly as a real one. Score measures *fingerprint
# agreement*, not whether the catalogue row is worth showing anybody.
_JUNK_TITLES = frozenset({
    "fingerprint less", "fingerprintless", "unknown", "unknown title",
    "untitled", "no title", "n/a", "null", "none",
})

# On their own these are plausible (plenty of real tracks are called "Intro"),
# so they only disqualify an entry when the *artist* is equally generic.
_GENERIC_TITLES = frozenset({
    "remix", "track", "audio", "song", "music", "intro", "outro", "mix",
})

_GENERIC_ARTISTS = frozenset({
    "dj", "unknown", "unknown artist", "various", "various artists",
    "artist", "n/a", "null", "none", "no artist", "karaoke", "cover",
})


def _normalize_text(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def is_plausible_release(title: Optional[str], artist: Optional[str]) -> bool:
    """Whether a catalogue entry looks like a real release worth showing.

    Deliberately conservative: it rejects entries that are *definitively*
    placeholders, and entries where title and artist are **both** generic. A
    single generic field is not enough — "Intro" by a named artist is a real
    track, and "Remix" by a named artist may well be too.
    """
    title_text, artist_text = _normalize_text(title), _normalize_text(artist)
    if not title_text or not artist_text:
        return False
    if title_text in _JUNK_TITLES or artist_text in _JUNK_TITLES:
        return False
    # Both generic together is the signature of a placeholder row. Either one
    # alone is left alone: plenty of DJs are credited as "DJ <something>", and
    # "Intro" by a named artist is a real track.
    return not (title_text in _GENERIC_TITLES and artist_text in _GENERIC_ARTISTS)


def _duration_seconds(value: Any) -> Optional[int]:
    try:
        return round(float(value) / 1000) if value else None
    except (TypeError, ValueError):
        return None


def _normalize_track(music: dict[str, Any]) -> dict[str, Any]:
    """ACRCloud's metadata shape → Melody's.

    REC-ID-004: the external IDs are the point. `isrc` and the Spotify/YouTube
    IDs are what let a recognized track be handed to Provider Adapter without a
    second text search, which is both faster and far more accurate than
    re-searching by title.
    """
    artists = music.get("artists") or []
    external = music.get("external_metadata") or {}

    ids: dict[str, Any] = {}
    if music.get("external_ids"):
        ids.update({k: v for k, v in music["external_ids"].items() if v})
    for provider in ("spotify", "youtube", "deezer", "apple_music"):
        entry = external.get(provider) or {}
        track_id = (entry.get("track") or {}).get("id") or entry.get("vid") or entry.get("id")
        if track_id:
            ids[provider] = track_id

    return {
        "title": music.get("title"),
        "artist": ", ".join(a.get("name", "") for a in artists if a.get("name")) or None,
        "album": (music.get("album") or {}).get("name"),
        "release_date": music.get("release_date"),
        "label": music.get("label"),
        # The melody index returns `duration_ms` as a **string** ("375040")
        # where the fingerprint index returns an int -- so this crashed with a
        # TypeError the moment humming results were finally being read, and
        # only ever on the humming path.
        "duration_seconds": _duration_seconds(music.get("duration_ms")),
        "genres": [g.get("name") for g in (music.get("genres") or []) if g.get("name")],
        "external_ids": ids,
    }


# ACRCloud searches a different index depending on `data_type`. A hum shares no
# spectral fingerprint with the recording it is a hum of, so the two are
# genuinely different searches over different data -- not one search with a flag.
DATA_TYPE_AUDIO = "audio"
DATA_TYPE_HUMMING = "humming"


async def identify(
    audio_path: Path,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    data_type: str = DATA_TYPE_AUDIO,
) -> Recognition:
    """Send a clip to ACRCloud and interpret the answer.

    **This module previously hardcoded `data_type="audio"`**, so the humming
    index was never queried once. When the synthetic humming probes came back
    empty, that was wrongly written up as the account lacking the capability --
    the account had it; the code never asked for it. Corrected 2026-07-28.
    """
    host, key, secret = _credentials()
    if not (host and key and secret):
        missing = [
            name
            for name, value in (("host", host), ("access_key", key), ("access_secret", secret))
            if not value
        ]
        return Recognition(
            configured=False,
            matched=False,
            confidence=0.0,
            reason="not_configured:" + ",".join(missing),
        )

    sample = audio_path.read_bytes()
    timestamp = str(int(time.time()))
    form = {
        "access_key": key,
        "data_type": data_type,
        "signature_version": "1",
        "signature": _signature(secret, key, timestamp, data_type),
        "sample_bytes": str(len(sample)),
        "timestamp": timestamp,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"https://{host}/v1/identify",
                data=form,
                files={"sample": ("sample.wav", sample, "audio/wav")},
            )
        payload = response.json()
    except httpx.TimeoutException:
        # Configured by definition -- the unconfigured case returned above.
        return Recognition(True, False, 0.0, reason="timeout")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("acrcloud_request_failed", extra={"error": type(exc).__name__})
        return Recognition(True, False, 0.0, reason="provider_error")

    status = payload.get("status") or {}
    code = status.get("code")

    if code in _NO_RESULT_CODES:
        # The service ran and recognized nothing. This is a real answer.
        return Recognition(True, False, 0.0, reason="no_match")
    if code in _AUTH_CODES:
        # Reported as a configuration problem rather than "no match", because
        # telling a user their song is unrecognizable when the key is wrong is
        # the exact failure this module is structured to prevent.
        logger.error("acrcloud_auth_rejected", extra={"code": code})
        return Recognition(False, False, 0.0, reason="auth_rejected")
    if code in _LIMIT_CODES:
        return Recognition(True, False, 0.0, reason="quota_exceeded")
    if code != 0:
        logger.warning("acrcloud_unexpected_status", extra={"code": code})
        return Recognition(True, False, 0.0, reason=f"provider_status_{code}")

    metadata = payload.get("metadata") or {}
    # ⚠️ ACRCloud returns melody/cover-song matches under `humming`, NOT `music`.
    # Reading only `music` meant every hum the service *did* recognize was
    # discarded here and reported to the user as "no match" -- which then got
    # written up twice as a provider limitation. The engine was working and
    # answering; this function was throwing the answer away.
    #
    # `music` is checked first because a spectral fingerprint match is a far
    # stronger claim than a melodic one: if the actual recording was
    # identified, that is the answer, and the melody index is a fallback.
    music_list = metadata.get("music") or []
    matched_index = "music"
    if not music_list:
        music_list = metadata.get("humming") or []
        matched_index = "humming"
    if not music_list:
        return Recognition(True, False, 0.0, reason="no_match")

    # Walk the candidates by score rather than taking the top one outright: when
    # the best-scoring row is catalogue junk, the *real* track is often sitting
    # right behind it. Observed live -- a placeholder entry scored 100 while the
    # correct answer was the runner-up.
    # Thresholds follow whichever index answered -- see HUMMING_MATCH_SCORE.
    match_at = MATCH_SCORE if matched_index == "music" else HUMMING_MATCH_SCORE
    floor_at = (
        LOW_CONFIDENCE_SCORE if matched_index == "music" else HUMMING_LOW_CONFIDENCE_SCORE
    )
    # Reported on a common 0-1 scale so a caller never has to know which index
    # produced the number.
    scale = 100.0 if matched_index == "music" else 1.0

    ranked = sorted(music_list, key=lambda m: float(m.get("score") or 0), reverse=True)
    best_score = float(ranked[0].get("score") or 0)
    rejected_junk = 0

    # Built from the whole ranked list, *before* any threshold is applied --
    # the alternatives are most useful in exactly the case where nothing
    # cleared the bar.
    candidates: list[dict[str, Any]] = []
    for entry in ranked[: MAX_CANDIDATES * 2]:
        entry_track = _normalize_track(entry)
        if not is_plausible_release(entry_track.get("title"), entry_track.get("artist")):
            continue
        candidates.append(
            {**entry_track, "confidence": round(float(entry.get("score") or 0) / scale, 4)}
        )
        if len(candidates) >= MAX_CANDIDATES:
            break

    for candidate in ranked:
        score = float(candidate.get("score") or 0)
        if score < floor_at:
            break  # sorted, so nothing below here qualifies either

        track = _normalize_track(candidate)
        if not is_plausible_release(track.get("title"), track.get("artist")):
            rejected_junk += 1
            logger.info(
                "acrcloud_junk_entry_skipped",
                extra={"score": score, "title": track.get("title")},
            )
            continue

        return Recognition(
            configured=True,
            matched=True,
            confidence=round(score / scale, 4),
            track=track,
            low_confidence=score < match_at,
            reason=None if score >= match_at else "low_confidence",
            candidates=candidates,
            # Which index answered. A melody match is a weaker claim than a
            # fingerprint match and the UI should be able to say so rather
            # than presenting both with the same certainty.
            provider="acrcloud:humming" if matched_index == "humming" else "acrcloud",
        )

    if rejected_junk:
        # We *did* recognize something; it just was not worth showing anyone.
        # Distinguished from a plain miss so the logs can tell them apart.
        return Recognition(
            True, False, round(best_score / scale, 4),
            reason="junk_metadata_only", candidates=candidates,
        )
    # Below the floor we do not name a track at all. A wrong confident answer is
    # worse than no answer -- the user cannot tell it is wrong.
    # Below the bar for a confident answer -- but the alternatives go back
    # anyway, so the user can recognise what we could not.
    return Recognition(
        True, False, round(best_score / scale, 4),
        reason="below_threshold", candidates=candidates,
    )
