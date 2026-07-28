"""Guardrails service (Section 2.5).

Endpoints (Section 2.4):
- POST /check/input  -> schema/size, language, prompt-injection, off-topic
- POST /check/output -> schema validity plus the §2.5 unsupported-claim rules

Formerly Phase 2 fixtures. The §2.5 P0 checks are implemented as of 2026-07-26
(§8.5 `INT-002`). The *framework* decision (NeMo Guardrails vs. this rule
engine) remains deferred per §2.5 — "deterministic placeholder" described the
depth of the rules, and several checks that section lists as required were
simply missing: off-topic was hardcoded `False`, language handling did not
exist, and the output check verified only that `tracks` was a list.

The output rules are not theoretical. §4.8 records a live leak where the
curator model repeated "confidence in the retrieval" into user-facing Hebrew
prose after an internal warning reached it; that is exactly the class of thing
`internal_leakage` below is here to stop reaching a user, independently of the
node that produced it. Defence in depth: the recommendation service already
sanitizes what it passes the model, and this rail catches what slips through.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from shared_lib import create_app

app = create_app("guardrails-service")

MAX_INPUT_CHARS = 4000

_INJECTION_MARKERS = (
    "ignore previous",
    "disregard instructions",
    "system prompt",
    "reveal your prompt",
    "exfiltrate",
    "ignore all prior",
    "print your instructions",
    "developer message",
)

# Off-topic detection is deliberately built from *positive evidence of another
# domain* rather than from "does this mention music". A music-words allowlist
# would reject legitimate requests phrased in Hebrew, in slang, or by mood
# alone ("something for a rainy night"), which is the majority of real use.
# These markers only fire on requests that are clearly asking for something
# else entirely.
_OFF_TOPIC_MARKERS = (
    "write me code",
    "write a function",
    "debug this",
    "medical advice",
    "legal advice",
    "stock tip",
    "invest in",
    "write my essay",
    "solve this equation",
    "כתוב לי קוד",
    "ייעוץ רפואי",
    "ייעוץ משפטי",
)

_HEBREW_RE = re.compile(r"[֐-׿]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# §2.5 output rules. Each is a (category, pattern) pair so a failure names the
# rule it broke rather than a generic "blocked".
_INTERNAL_LEAKAGE_MARKERS = (
    "system prompt",
    "chain of thought",
    "chain-of-thought",
    "retrieval confidence",
    "confidence in the retrieval",
    "reranked chunk",
    "rag-service",
    "provider-gateway",
    "recommendation-service",
    "embedding vector",
    "sk-",  # API-key prefixes
    "bearer ",
    "access_token",
    "refresh_token",
)

# §PLAY-004: never promise ad-free playback or imply OAuth means Premium.
_AD_FREE_CLAIM_MARKERS = (
    "ad-free",
    "ad free",
    "without ads",
    "no ads",
    "commercial-free",
    "ללא פרסומות",
)

# §2.5: "no fabricated BPM/key when unknown". Nothing upstream supplies audio
# features yet (Phase 6/7), so any BPM/key in user-facing prose is invented.
_FABRICATED_FEATURE_RE = re.compile(
    r"\b(\d{2,3}\s*bpm|beats per minute|in the key of|camelot)\b", re.IGNORECASE
)


class InputCheckRequest(BaseModel):
    text: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class InputCheckResponse(BaseModel):
    allowed: bool
    categories: dict[str, bool]
    reasons: list[str]
    language: str = "unknown"
    # False since 2026-07-26: these are real, tested rules, not a stand-in
    # returning a constant. The framework choice stays open (§2.5).
    placeholder: bool = False


class OutputCheckRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class OutputCheckResponse(BaseModel):
    allowed: bool
    schema_valid: bool
    issues: list[str]
    categories: dict[str, bool] = Field(default_factory=dict)
    placeholder: bool = False


def _detect_language(text: str) -> str:
    """§2.5 'allowed language handling for Hebrew and English'."""
    has_hebrew = bool(_HEBREW_RE.search(text))
    has_latin = bool(_LATIN_RE.search(text))
    if has_hebrew and has_latin:
        return "mixed"
    if has_hebrew:
        return "he"
    if has_latin:
        return "en"
    return "unknown"


@app.post("/check/input", response_model=InputCheckResponse)
async def check_input(request: InputCheckRequest) -> InputCheckResponse:
    text = request.text or ""
    lowered = text.lower()

    prompt_injection = any(marker in lowered for marker in _INJECTION_MARKERS)
    too_long = len(text) > MAX_INPUT_CHARS
    off_topic = any(marker in lowered for marker in _OFF_TOPIC_MARKERS)
    language = _detect_language(text)
    # "mixed" is explicitly fine -- "תמליץ לי על shoegaze" is a normal request
    # here. Only a request with no recognizable script at all is unsupported,
    # and empty text is caught by WF-001's schema validation before this.
    unsupported_language = bool(text.strip()) and language == "unknown"

    reasons: list[str] = []
    if prompt_injection:
        reasons.append("Possible prompt-injection pattern detected.")
    if too_long:
        reasons.append(f"Input exceeds the maximum allowed length ({MAX_INPUT_CHARS} characters).")
    if off_topic:
        reasons.append("This assistant only handles music discovery requests.")
    if unsupported_language:
        reasons.append("Only Hebrew and English requests are supported.")

    return InputCheckResponse(
        allowed=not (prompt_injection or too_long or off_topic or unsupported_language),
        categories={
            "prompt_injection": prompt_injection,
            "too_long": too_long,
            "off_topic": off_topic,
            "unsupported_language": unsupported_language,
        },
        language=language,
        reasons=reasons,
    )


def _user_facing_text(payload: dict[str, Any]) -> str:
    """Everything in the payload a user will actually read.

    Deliberately excludes ids and urls: a video id can contain any substring
    and must not be able to trip a prose rule.
    """
    parts = [str(payload.get("playlist_title") or ""), str(payload.get("playlist_description") or "")]
    tracks = payload.get("tracks")
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                parts.append(str(track.get("reasoning") or ""))
    return "\n".join(parts)


@app.post("/check/output", response_model=OutputCheckResponse)
async def check_output(request: OutputCheckRequest) -> OutputCheckResponse:
    payload = request.payload if isinstance(request.payload, dict) else {}
    issues: list[str] = []

    tracks = payload.get("tracks", [])
    schema_valid = isinstance(tracks, list)
    if not schema_valid:
        issues.append("`tracks` must be a list.")
        tracks = []

    prose = _user_facing_text(payload).lower()

    internal_leakage = any(marker in prose for marker in _INTERNAL_LEAKAGE_MARKERS)
    if internal_leakage:
        issues.append("Response prose contains internal implementation detail.")

    ad_free_claim = any(marker in prose for marker in _AD_FREE_CLAIM_MARKERS)
    if ad_free_claim:
        issues.append("Response claims ad-free playback, which cannot be promised (§PLAY-004).")

    fabricated_features = bool(_FABRICATED_FEATURE_RE.search(prose))
    if fabricated_features:
        issues.append("Response states BPM/key, which no upstream service supplies.")

    # §2.5 "real provider IDs for non-mock tracks". Only enforced when the
    # payload does not declare itself a placeholder -- a fixture is allowed to
    # be a fixture, it just may not masquerade as a resolved track.
    is_placeholder = bool(payload.get("placeholder"))
    missing_ids = (
        not is_placeholder
        and schema_valid
        and any(
            isinstance(t, dict) and not str(t.get("provider_track_id") or "").strip()
            for t in tracks
        )
    )
    if missing_ids:
        issues.append("A non-placeholder track is missing its provider track id.")

    return OutputCheckResponse(
        allowed=schema_valid and not issues,
        schema_valid=schema_valid,
        issues=issues,
        categories={
            "internal_leakage": internal_leakage,
            "ad_free_claim": ad_free_claim,
            "fabricated_features": fabricated_features,
            "missing_provider_ids": missing_ids,
        },
    )
