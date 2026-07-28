"""Real implementations of the 18 required graph nodes (plan §4.2).

Every node follows the same contract (§4.3):
- takes the full ``RecommendationState`` as input;
- is idempotent and individually unit-testable;
- returns a *partial* state update (plain dict) — never mutates the input;
- always includes a ``node_metrics`` entry with latency, model name/version,
  and a safe status;
- never raises — failures are captured in state (``status="error"`` +
  a warning) so the graph always completes.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import jsonschema

from . import llm_adapter, provider_client, rag_client, sequencer
from .graph_state import NodeMetric, RecommendationState

logger = logging.getLogger("recommendation-service.graph")


def _metrics(
    name: str,
    started: float,
    *,
    model: Optional[str] = None,
    status: str = "ok",
    detail: str = "stub",
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    estimated_cost_usd: Optional[float] = None,
) -> dict[str, dict[str, NodeMetric]]:
    """Build the §4.3-mandated metrics entry for a single node run."""
    entry: NodeMetric = {
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "model": model,
        "model_version": None,
        "status": status,
        "detail": detail,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    }
    # §4.9: every model call's provider/model/tokens/latency/cost must be
    # recorded. node_metrics lives only in per-request graph state (never
    # persisted -- see the model_usage-table gap noted in the plan doc), so
    # log it too: this is the only place that data survives the request.
    logger.info("node_metrics: %s", json.dumps({name: entry}))
    return {"node_metrics": {name: entry}}


def _triggered(name: str) -> float:
    logger.info("graph node triggered: %s", name)
    return time.perf_counter()


# ---------------------------------------------------------------------------
# 1-4: context validation, normalization, profile, query construction
# (real implementations — Phase 4, July 24, 2026)
# ---------------------------------------------------------------------------

# Hard cap on user text fed to prompts/retrieval: prevents prompt bloating and
# blunts long-form injection payloads. Guardrails-service does semantic checks.
MAX_USER_TEXT_CHARS = 1000

# Audio features at/above this confidence act as constraints; below it they
# become down-weighted soft hints (weight == confidence), never hard filters.
AUDIO_CONFIDENCE_THRESHOLD = 0.6

VALID_DISCOVERY_MODES = ("safe", "balanced", "adventurous")
DEFAULT_DISCOVERY_MODE = "balanced"

# Deterministic per-mode retrieval knobs.
#
# ~~⚠️ `candidate_pool` and `genre_expansion` currently reach NOTHING~~ →
# **`candidate_pool` is wired through as of 2026-07-28 (Phase 3)** and now sets
# how deep each first-stage retriever goes before fusion and reranking. It
# became load-bearing the moment the corpus grew from 325 to 4,249 chunks: a
# fixed pool of 20 was 6% of the old corpus and 0.5% of the new one, and the
# measured consequence was that a 90s-grunge query stopped returning Soundgarden
# — not because the album left the store, but because dense+FTS never handed it
# to the reranker.
#
# `genre_expansion` still reaches nothing and is left in place honestly: §4.4
# intends it as a real lever, but wiring it is a behaviour change that wants
# §3.8's evaluation set behind it. `diversity` is consumed by
# `apply_diversity_constraints`.
#
# ⚠️ The pool values below are the pre-existing ones and are **not yet tuned** —
# they are set by measurement against the golden evaluation set, not by
# intuition. Until that run lands, treat them as a starting point.
DISCOVERY_PARAMS: dict[str, dict[str, Any]] = {
    "safe": {"genre_expansion": False, "diversity": 0.2, "candidate_pool": 20},
    "balanced": {"genre_expansion": True, "diversity": 0.5, "candidate_pool": 20},
    "adventurous": {"genre_expansion": True, "diversity": 0.8, "candidate_pool": 30},
}

# explicit_constraints keys recognized by normalize_input.
_POSITIVE_CONSTRAINT_KEYS = (
    "genre", "genres", "artist", "artists", "era", "year_from", "year_to",
    "mood", "language",
)
_NEGATIVE_CONSTRAINT_KEYS = ("exclude_genres", "exclude_artists", "avoid", "exclude")

# Control characters (except \n and \t, which normalize to spaces anyway).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _as_lowered_list(value: Any) -> list[str]:
    """Coerce a scalar/list constraint value into a clean lowercase list."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    return [str(item).strip().lower() for item in items if str(item).strip()]


# ---------------------------------------------------------------------------
# Free-text negation (§3.8 negative-constraint category)
# ---------------------------------------------------------------------------
#
# `normalize_input` reads negative constraints out of `explicit_constraints`,
# which is the UI's structured payload -- and the UI has no "exclude" control,
# so in practice that dictionary was ALWAYS EMPTY. Negation only ever arrives
# the way people actually express it: in the sentence.
#
# Measured on the §3.8 golden set before this existed: the `negative_constraint`
# category scored **0.00 context precision**. "rock but nothing metal" retrieved
# metal, because a bi-encoder embedding of the whole phrase is dominated by its
# nouns and has no notion of "not".
#
# Deliberately conservative: only explicit negation markers, and only the short
# span that follows one. Over-triggering here silently deletes evidence, which is
# a worse failure than missing an exclusion -- so the patterns require a marker
# and stop at the first conjunction or punctuation.
_NEGATION_MARKERS_EN = r"(?:but\s+(?:not|no|nothing)|without|nothing|no|not|avoid|except|excluding)"
# Hebrew: בלי (without), ללא (without), חוץ מ (except), לא (not).
_NEGATION_MARKERS_HE = r"(?:בלי|ללא|חוץ\s+מ|לא)"

_NEGATION_RE = re.compile(
    rf"\b{_NEGATION_MARKERS_EN}\s+(?P<term>[a-z0-9][a-z0-9'&\- ]{{1,30}}?)"
    r"(?=\s*(?:,|\.|;|!|\?|$|\band\b|\bor\b|\bbut\b|\bwith\b|\bfor\b))",
    re.IGNORECASE,
)
_NEGATION_RE_HE = re.compile(
    rf"{_NEGATION_MARKERS_HE}\s+(?P<term>[֐-׿][֐-׿' \-]{{1,30}}?)"
    r"(?=\s*(?:,|\.|;|!|\?|$|\bו\b))",
)

# Words that are never a musical exclusion, even after a negation marker. Without
# this, "I do not want something too loud" yields the exclusion "want".
_NEGATION_STOPWORDS = {
    "want", "like", "sure", "really", "very", "too", "that", "this", "it",
    "the", "a", "an", "any", "much", "more", "less", "one", "thing", "things",
    "idea", "problem", "matter", "worry", "rush",
}

# Conversational filler that trails an exclusion. "no rap either" is an
# exclusion of *rap*, not of "rap either" -- and the difference matters, because
# the term is matched against doc_ids and chunk text downstream, where a
# two-word term with a filler in it simply never matches anything.
_NEGATION_TRAILING_FILLER = {
    "either", "please", "thanks", "though", "actually", "at", "all", "really",
    "tonight", "today", "stuff", "music", "songs", "tracks",
}


def extract_negations(text: str) -> list[str]:
    """Pull explicit exclusions out of free text. Returns lowercase terms.

    Bilingual, because the product is. Returns ``[]`` for text with no negation
    marker, which is the overwhelming majority of requests.
    """
    if not text:
        return []

    found: list[str] = []
    for pattern in (_NEGATION_RE, _NEGATION_RE_HE):
        for match in pattern.finditer(text):
            term = " ".join((match.group("term") or "").split()).strip(" -'")
            if not term:
                continue
            # A bare stopword is noise; a phrase whose FIRST word is a stopword
            # ("too loud") is usually noise too, but the tail may be real.
            words = term.lower().split()
            while words and words[0] in _NEGATION_STOPWORDS:
                words = words[1:]
            while words and words[-1] in _NEGATION_TRAILING_FILLER:
                words = words[:-1]
            term = " ".join(words)
            if not term or term in _NEGATION_STOPWORDS or len(term) < 2:
                continue
            if term not in found:
                found.append(term)
    return found


def validate_context(state: RecommendationState) -> dict[str, Any]:
    """1. Validate the incoming RecommendationContext envelope.

    The request is workable only if it carries at least one usable input
    signal: non-blank ``user_text`` OR a non-empty ``audio_features`` dict.
    On failure the state is captured (``context_valid=False``,
    ``output_valid=False`` + warning) so a future error edge can exit early.
    """
    started = _triggered("validate_context")

    has_text = bool((state.get("user_text") or "").strip())
    audio = state.get("audio_features")
    has_audio = isinstance(audio, dict) and len(audio) > 0

    update: dict[str, Any] = {
        "context_valid": has_text or has_audio,
        "rewrite_count": int(state.get("rewrite_count", 0)),
    }
    if not (has_text or has_audio):
        update["output_valid"] = False
        update["warnings"] = [
            "validation failure: request carries neither user_text nor "
            "audio_features — nothing to recommend from"
        ]
        return {**update, **_metrics("validate_context", started, status="error",
                                     detail="no usable input signal")}
    return {**update, **_metrics("validate_context", started)}


def normalize_input(state: RecommendationState) -> dict[str, Any]:
    """2. Sanitize user text and extract explicit constraints.

    Text hygiene: strip control characters, collapse all whitespace runs to
    single spaces, and truncate to ``MAX_USER_TEXT_CHARS`` (with a warning) so
    downstream prompts cannot be bloated or smuggled multi-line payloads.

    Explicit UI constraints (§4.3: never overridden by the agent) are split
    into ``normalized_constraints = {"positive": ..., "negative": ...}``.
    """
    started = _triggered("normalize_input")

    raw_text = state.get("user_text") or ""
    text = _CONTROL_CHARS_RE.sub(" ", raw_text)
    text = " ".join(text.split())

    update: dict[str, Any] = {}
    if len(text) > MAX_USER_TEXT_CHARS:
        text = text[:MAX_USER_TEXT_CHARS].rstrip()
        update["warnings"] = [
            f"user_text truncated to {MAX_USER_TEXT_CHARS} characters"
        ]

    explicit = state.get("explicit_constraints") or {}
    positive: dict[str, Any] = {}
    negative: dict[str, Any] = {}
    for key in _POSITIVE_CONSTRAINT_KEYS:
        if key not in explicit:
            continue
        if key in ("year_from", "year_to"):
            try:
                positive[key] = int(explicit[key])
            except (TypeError, ValueError):
                update.setdefault("warnings", []).append(
                    f"ignored non-numeric constraint {key}={explicit[key]!r}"
                )
        else:
            values = _as_lowered_list(explicit[key])
            if values:
                # Singular and plural forms merge into the plural bucket.
                bucket = {"genre": "genres", "artist": "artists"}.get(key, key)
                positive.setdefault(bucket, [])
                positive[bucket] = list(dict.fromkeys(positive[bucket] + values)) \
                    if isinstance(positive[bucket], list) else values
    for key in _NEGATIVE_CONSTRAINT_KEYS:
        if key in explicit:
            values = _as_lowered_list(explicit[key])
            if values:
                negative[key] = values

    # Negation as the user actually expressed it, in the sentence. The
    # `explicit_constraints` route above only ever fires for a UI that has an
    # exclude control, and this one does not -- so before this, negative
    # constraints were empty on every real request.
    text_negations = extract_negations(text)
    if text_negations:
        existing = list(negative.get("exclude", []) or [])
        negative["exclude"] = existing + [t for t in text_negations if t not in existing]

    # era/language may arrive as single strings — keep scalars readable.
    for scalar_key in ("era", "mood", "language"):
        if isinstance(positive.get(scalar_key), list) and len(positive[scalar_key]) == 1:
            positive[scalar_key] = positive[scalar_key][0]

    update.update(
        {
            "normalized_text": text,
            "normalized_constraints": {"positive": positive, "negative": negative},
        }
    )
    return {**update, **_metrics("normalize_input", started)}


# Fallback profile injected for guests / missing profiles: neutral genre
# weights (empty dict = no prior taste bias) and balanced discovery.
GUEST_PROFILE: dict[str, Any] = {
    "profile_type": "guest",
    "version": 0,
    "discovery_mode": DEFAULT_DISCOVERY_MODE,
    "weights": {
        "genres": {},          # neutral: no genre gets a prior boost
        "text_relevance": 1.0, # text is the only trusted signal for guests
        "personal_taste": 0.0,
        "provider_taste": 0.0,
    },
}


def load_or_accept_user_profile(state: RecommendationState) -> dict[str, Any]:
    """3. Accept the provided profile or inject the default Guest profile.

    Also resolves ``discovery_mode`` explicitly, in priority order:
    request-level value > profile value > ``"balanced"``. Invalid values fall
    back to ``"balanced"`` with a warning rather than failing the run.
    """
    started = _triggered("load_or_accept_user_profile")

    profile = state.get("user_profile")
    injected_guest = not (isinstance(profile, dict) and profile)
    if injected_guest:
        profile = dict(GUEST_PROFILE)

    update: dict[str, Any] = {}
    requested_mode = state.get("discovery_mode") or profile.get("discovery_mode")
    if requested_mode not in VALID_DISCOVERY_MODES:
        if requested_mode:
            update["warnings"] = [
                f"invalid discovery_mode {requested_mode!r}; fell back to "
                f"'{DEFAULT_DISCOVERY_MODE}'"
            ]
        requested_mode = DEFAULT_DISCOVERY_MODE

    update.update({"user_profile": profile, "discovery_mode": requested_mode})
    return {
        **update,
        **_metrics(
            "load_or_accept_user_profile",
            started,
            detail="guest profile injected" if injected_guest else "profile accepted",
        ),
    }


# Keys the audio service returns that describe the *analysis*, not the audio.
# Treating them as features produced entries like `source: "librosa-dsp"` with a
# confidence and a weight, which then reached the retrieval query as nonsense.
_AUDIO_METADATA_KEYS = frozenset(
    {
        "confidence",
        "source",
        "model_version",
        "field_confidence",
        "analyzed_seconds",
        "genre_model",
        "placeholder",
    }
)

# audio-service names its per-field confidences after the *measurement*
# ("tempo", "key"); the feature fields are named after the musical quantity
# ("bpm", "musical_key"). This is the join between the two.
_AUDIO_CONFIDENCE_FIELD = {
    "bpm": "tempo",
    "musical_key": "key",
    "camelot": "key",
    "energy": "energy",
    "genre": "genre",
}


def _normalize_audio_features(audio: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Per-feature confidence weighting (§4.4): low confidence -> soft hint.

    Accepts either flat values (``{"bpm": 124}``), per-feature dicts
    (``{"bpm": {"value": 124, "confidence": 0.4}}``), or a flat dict with a
    global ``confidence`` key applying to all sibling features.

    §6.2 added a `field_confidence` map, and it takes precedence over the
    global number where it covers a field. That matters because the headline
    `confidence` is deliberately the *weakest* field: without this, one
    ambiguous key would demote a rock-solid tempo reading to a soft hint.
    """
    if not audio:
        return {}
    global_conf = audio.get("confidence")
    global_conf = float(global_conf) if isinstance(global_conf, (int, float)) else 1.0
    per_field = audio.get("field_confidence")
    per_field = per_field if isinstance(per_field, dict) else {}

    normalized: dict[str, Any] = {}
    for name, raw in audio.items():
        if name in _AUDIO_METADATA_KEYS:
            continue
        if raw is None:
            # An absent measurement (no genre model, undetectable key) is not a
            # feature with low confidence -- it is not a feature at all.
            continue
        default_conf = per_field.get(_AUDIO_CONFIDENCE_FIELD.get(name, name), global_conf)
        if isinstance(raw, dict):
            value = raw.get("value")
            confidence = raw.get("confidence", default_conf)
        else:
            value, confidence = raw, default_conf
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0
        is_trusted = confidence >= AUDIO_CONFIDENCE_THRESHOLD
        normalized[name] = {
            "value": value,
            "confidence": round(confidence, 3),
            # Down-weight, never fabricate: untrusted features keep their
            # confidence as the weight and are marked as soft hints.
            "weight": 1.0 if is_trusted else round(confidence, 3),
            "treat_as": "constraint" if is_trusted else "soft_hint",
        }
    return normalized


# §6.5 AUD-RAG-001 — the vocabulary that turns measured audio into something
# retrieval can match on. Retrieval is text-and-embedding based, so a BPM number
# is invisible to it; the words below are what the corpus actually contains.
#
# The boundaries are musical, not arithmetic: 90 BPM separates a ballad from a
# groove, 128 is club four-on-the-floor, and past 160 you are in drum'n'bass and
# thrash territory. Each band is deliberately described the way a *listener*
# would, because that is how the reviews corpus is written.
_TEMPO_BANDS: tuple[tuple[float, str], ...] = (
    (70.0, "very slow, spacious, ballad tempo"),
    (90.0, "slow, downtempo, unhurried"),
    (110.0, "mid-tempo, relaxed groove"),
    (130.0, "steady danceable pulse, four on the floor"),
    (160.0, "fast, driving, propulsive"),
    (float("inf"), "very fast, frenetic, high tempo"),
)

_ENERGY_BANDS: tuple[tuple[float, str], ...] = (
    (0.25, "quiet, sparse, ambient, low energy"),
    (0.45, "gentle, restrained, mellow"),
    (0.65, "warm, moderate energy"),
    (0.85, "energetic, bold, punchy"),
    (1.01, "intense, loud, aggressive, high energy"),
)


def _band(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    for ceiling, description in bands:
        if value < ceiling:
            return description
    return bands[-1][1]


def describe_audio_features(audio: dict[str, Any]) -> dict[str, Any]:
    """Turn normalized audio features into retrieval terms (AUD-RAG-001).

    `audio` is the output of `_normalize_audio_features`, so every feature
    already carries a confidence and a `treat_as` of `constraint` or
    `soft_hint`. That distinction is honoured here rather than re-derived:

    * **constraints** (confident) become part of the retrieval *text*, so they
      influence the embedding and the lexical match;
    * **soft hints** (uncertain) are returned separately and never enter the
      query text. A tempo the analyser is 20% sure of must not be allowed to
      steer the search — that is exactly the "down-weight uncertain features"
      requirement (AUD-RAG-002), and dropping them from the text is the only
      down-weighting that has any effect on a text query.

    Returns `{"text": str, "terms": [...], "soft_hints": [...], "used": {...}}`.
    """
    if not audio:
        return {"text": "", "terms": [], "soft_hints": [], "used": {}}

    terms: list[str] = []
    soft_hints: list[str] = []
    used: dict[str, Any] = {}

    def _add(feature: str, description: str, entry: dict[str, Any]) -> None:
        if entry.get("treat_as") == "constraint":
            terms.append(description)
            used[feature] = {"value": entry.get("value"), "confidence": entry.get("confidence")}
        else:
            soft_hints.append(description)

    genre = audio.get("genre")
    if genre and isinstance(genre, dict) and genre.get("value"):
        # The single strongest signal available: a genre name matches the corpus
        # vocabulary directly, where tempo and energy only match descriptions
        # of it. Listed first so it leads the query.
        _add("genre", str(genre["value"]), genre)

    bpm = audio.get("bpm")
    if bpm and isinstance(bpm, dict) and isinstance(bpm.get("value"), (int, float)):
        _add("bpm", _band(float(bpm["value"]), _TEMPO_BANDS), bpm)

    energy = audio.get("energy")
    if energy and isinstance(energy, dict) and isinstance(energy.get("value"), (int, float)):
        _add("energy", _band(float(energy["value"]), _ENERGY_BANDS), energy)

    key = audio.get("musical_key")
    if key and isinstance(key, dict) and isinstance(key.get("value"), str):
        # Only the mode, never the tonic. "A minor" as a search term matches
        # documents that happen to mention the words; the *mood* of a minor key
        # is the part that generalizes, and it is what people write about.
        mode_word = "minor" if "minor" in key["value"].lower() else "major"
        _add(
            "musical_key",
            "melancholy, wistful, minor key" if mode_word == "minor"
            else "bright, uplifting, major key",
            key,
        )

    return {
        "text": ", ".join(terms),
        "terms": terms,
        "soft_hints": soft_hints,
        "used": used,
        # Surfaced separately because a genre is the one audio feature that is
        # also a *constraint* -- it belongs in `positive_constraints.genres`,
        # where ranking and the curator both already read it, not only in the
        # retrieval text.
        "genre": (used.get("genre") or {}).get("value"),
    }


def negative_terms(retrieval_query: dict[str, Any]) -> list[str]:
    """Flatten `negative_constraints` into the flat term list rag-service takes.

    The dict is keyed by origin (`exclude_genres` from a UI control,
    `exclude` from free-text negation), and retrieval does not care which door a
    term came through -- only that the user does not want it.
    """
    negatives = (retrieval_query or {}).get("negative_constraints") or {}
    terms: list[str] = []
    for value in negatives.values():
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            term = str(item).strip().lower()
            if term and term not in terms:
                terms.append(term)
    return terms


def build_retrieval_query(state: RecommendationState) -> dict[str, Any]:
    """4. Structured query construction (§4.4) — deterministic, rules-based.

    Combines normalized text, positive/negative constraints, profile weights,
    confidence-weighted audio features, discovery mode (with its per-mode
    retrieval knobs), and language/region into the payload the dense/lexical
    retrieval nodes will consume.

    §6.5 changed what `text` means here. It used to be the user's words alone,
    which made an audio-only request retrieve *nothing*: nodes 5 and 6 skip on
    empty text, so the whole pipeline ran on no evidence and the audio was
    inert. Confident audio features are now described in words and appended, so
    "recommend something like this clip" is a real query. The user's own words
    still lead — audio informs the search, it does not replace what was asked.
    """
    started = _triggered("build_retrieval_query")

    constraints = state.get("normalized_constraints") or {"positive": {}, "negative": {}}
    profile = state.get("user_profile") or {}
    mode = state.get("discovery_mode", DEFAULT_DISCOVERY_MODE)
    audio = _normalize_audio_features(state.get("audio_features"))
    audio_description = describe_audio_features(audio)

    user_text = state.get("normalized_text", "")
    query_text = ", ".join(part for part in (user_text, audio_description["text"]) if part)

    # AUD-RAG-001 -- "map audio features to normalized query constraints", and
    # the genre is the one that is genuinely a constraint rather than a
    # description. Merged rather than assigned: if the user *said* "something
    # like this, but jazzier", their word stays and the classifier's is added.
    # Only a confident prediction gets here; `describe_audio_features` puts an
    # uncertain one in `soft_hints`, which never reaches this branch.
    positive = dict(constraints.get("positive", {}))
    audio_genre = audio_description.get("genre")
    if audio_genre:
        existing = list(positive.get("genres", []) or [])
        if audio_genre not in existing:
            positive["genres"] = existing + [audio_genre]

    retrieval_query = {
        "text": query_text,
        "user_text": user_text,
        "audio_query": audio_description,
        "positive_constraints": positive,
        "negative_constraints": constraints.get("negative", {}),
        "profile_weights": profile.get("weights", {}),
        "audio_features": audio,  # each entry: value/confidence/weight/treat_as
        "discovery_mode": mode,
        "discovery_params": dict(
            DISCOVERY_PARAMS.get(mode, DISCOVERY_PARAMS[DEFAULT_DISCOVERY_MODE])
        ),
        "language": state.get("language") or constraints.get("positive", {}).get("language"),
        "region": state.get("region"),
    }
    return {"retrieval_query": retrieval_query, **_metrics("build_retrieval_query", started)}


# ---------------------------------------------------------------------------
# 5-9: retrieval legs, expansion, fusion, reranking (Phase 3 pipeline reuse,
# via rag-service's real /rag/retrieve — see rag-service/main.py). No
# embedding/rerank model work happens in this service (Section 2.2).
# ---------------------------------------------------------------------------

RAG_TOP_K_BY_MODE: dict[str, int] = {"safe": 5, "balanced": 6, "adventurous": 8}


async def retrieve_genres(state: RecommendationState) -> dict[str, Any]:
    """5. Real dense+lexical retrieval over the genre domain (via rag-service)."""
    started = _triggered("retrieve_genres")
    query = state.get("retrieval_query") or {}
    text = query.get("text", "")
    positive = query.get("positive_constraints", {})
    mode = query.get("discovery_mode", DEFAULT_DISCOVERY_MODE)
    top_k = RAG_TOP_K_BY_MODE.get(mode, 5)
    debug = dict(state.get("_retrieval_debug") or {})

    if not text:
        debug["genre"] = {"matched_genres": {}, "confidence": 0.0}
        return {
            "retrieved_genres": [],
            "_retrieval_debug": debug,
            **_metrics("retrieve_genres", started, status="skipped", detail="no query text"),
        }
    try:
        response = await rag_client.retrieve(
            text,
            domain="genre",
            top_k=top_k,
            year_from=positive.get("year_from"),
            year_to=positive.get("year_to"),
            candidate_pool=(query.get("discovery_params") or {}).get("candidate_pool"),
            exclude_terms=negative_terms(query),
        )
    except httpx.HTTPError as exc:
        debug["genre"] = {"matched_genres": {}, "confidence": 0.0}
        return {
            "retrieved_genres": [],
            "_retrieval_debug": debug,
            "warnings": [f"retrieve_genres: rag-service unreachable ({exc})"],
            **_metrics(
                "retrieve_genres", started, status="error", detail="rag-service unreachable"
            ),
        }

    debug["genre"] = {
        "matched_genres": response.get("matched_genres", {}),
        "confidence": response.get("retrieval_confidence", 0.0),
    }
    chunks = response.get("chunks", [])
    return {
        "retrieved_genres": chunks,
        "_retrieval_debug": debug,
        **_metrics("retrieve_genres", started, detail=f"{len(chunks)} chunks"),
    }


async def retrieve_reviews(state: RecommendationState) -> dict[str, Any]:
    """6. Real dense+lexical retrieval over the reviews/context domain."""
    started = _triggered("retrieve_reviews")
    query = state.get("retrieval_query") or {}
    text = query.get("text", "")
    positive = query.get("positive_constraints", {})
    mode = query.get("discovery_mode", DEFAULT_DISCOVERY_MODE)
    top_k = RAG_TOP_K_BY_MODE.get(mode, 5)
    debug = dict(state.get("_retrieval_debug") or {})

    if not text:
        debug["reviews"] = {"matched_genres": {}, "confidence": 0.0}
        return {
            "retrieved_reviews": [],
            "_retrieval_debug": debug,
            **_metrics("retrieve_reviews", started, status="skipped", detail="no query text"),
        }
    try:
        response = await rag_client.retrieve(
            text,
            domain="reviews",
            top_k=top_k,
            candidate_pool=(query.get("discovery_params") or {}).get("candidate_pool"),
            exclude_terms=negative_terms(query),
            year_from=positive.get("year_from"),
            year_to=positive.get("year_to"),
        )
    except httpx.HTTPError as exc:
        debug["reviews"] = {"matched_genres": {}, "confidence": 0.0}
        return {
            "retrieved_reviews": [],
            "_retrieval_debug": debug,
            "warnings": [f"retrieve_reviews: rag-service unreachable ({exc})"],
            **_metrics(
                "retrieve_reviews", started, status="error", detail="rag-service unreachable"
            ),
        }

    debug["reviews"] = {
        "matched_genres": response.get("matched_genres", {}),
        "confidence": response.get("retrieval_confidence", 0.0),
    }
    chunks = response.get("chunks", [])
    return {
        "retrieved_reviews": chunks,
        "_retrieval_debug": debug,
        **_metrics("retrieve_reviews", started, detail=f"{len(chunks)} chunks"),
    }


def expand_genre_graph(state: RecommendationState) -> dict[str, Any]:
    """7. Surface the one-hop genre-graph expansion already computed by
    rag-service (nodes 5/6) — no second HTTP call, pure transformation."""
    started = _triggered("expand_genre_graph")
    debug = state.get("_retrieval_debug") or {}
    terms: list[str] = []
    for entry in debug.values():
        for related in (entry.get("matched_genres") or {}).values():
            terms.extend(related)
    deduped = list(dict.fromkeys(terms))
    return {
        "expanded_genre_terms": deduped,
        **_metrics("expand_genre_graph", started, detail=f"{len(deduped)} related terms"),
    }


def fuse_results(state: RecommendationState) -> dict[str, Any]:
    """8. Cross-domain fusion: combine genre-domain + reviews-domain chunks.

    RRF fusion *within* each domain already happened inside rag-service; this
    is a second, cheap fusion step across the two domain-specific result sets.
    """
    started = _triggered("fuse_results")
    combined = list(state.get("retrieved_genres") or []) + list(
        state.get("retrieved_reviews") or []
    )
    best: dict[str, dict[str, Any]] = {}
    for chunk in combined:
        doc_id = chunk.get("document_id")
        if doc_id is None:
            continue
        if doc_id not in best or chunk.get("score", 0) > best[doc_id].get("score", 0):
            best[doc_id] = chunk
    fused = sorted(best.values(), key=lambda c: c.get("score", 0), reverse=True)
    return {"fused_chunks": fused, **_metrics("fuse_results", started, detail=f"{len(fused)} unique chunks")}


def rerank_documents(state: RecommendationState) -> dict[str, Any]:
    """9. Select the top 5-8 fused chunks by rag-service's cross-encoder score.

    No new model call here — the score is reused, not recomputed (Section 2.2:
    embedding/rerank math belongs to rag-service, not this service).
    """
    started = _triggered("rerank_documents")
    fused = state.get("fused_chunks") or []
    top = sorted(fused, key=lambda c: c.get("score", 0), reverse=True)[:8]
    return {
        "reranked_chunks": top,
        **_metrics(
            "rerank_documents",
            started,
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
            detail="reused rag-service scores, no re-embedding",
        ),
    }


# ---------------------------------------------------------------------------
# 10-11: confidence gate and bounded rewrite (§4.5)
# ---------------------------------------------------------------------------


def evaluate_retrieval_confidence(state: RecommendationState) -> dict[str, Any]:
    """10. Average the per-domain rag-service confidences; the conditional
    edge in graph.py routes on this. Forced to 0 when nothing was retrieved."""
    started = _triggered("evaluate_retrieval_confidence")
    debug = state.get("_retrieval_debug") or {}
    confidences = [entry.get("confidence", 0.0) for entry in debug.values()]
    confidence = sum(confidences) / len(confidences) if confidences else 0.0
    if not state.get("reranked_chunks"):
        confidence = 0.0
    return {
        "retrieval_confidence": round(confidence, 4),
        **_metrics("evaluate_retrieval_confidence", started),
    }


def plan_query_relaxation(
    retrieval_query: dict[str, Any]
) -> Optional[tuple[dict[str, Any], str]]:
    """Work out what a rewrite would change, WITHOUT applying it (§4.5).

    Returns ``(new_retrieval_query, reason)``, or **None** when nothing can be
    relaxed. Pulled out of ``rewrite_query`` so the router in graph.py can ask
    the question before committing to a second retrieval pass.

    ⚠️ **Only one relaxation remains, and removing the other two is the actual
    latency fix (2026-07-28).**

    The original three were: drop the year range -> widen the candidate pool ->
    enable genre expansion. Measured, the rewrite fired on 100% of requests and
    took the "widened candidate pool" branch every time. Chasing that revealed
    why it was harmless-looking and expensive:

        `rag_client.retrieve` sends only {query, top_k, filters}. Neither
        `candidate_pool` nor `genre_expansion` is sent, and neither has any
        consumer in this repository. Widening the pool changed a number that
        nothing reads.

    So the second retrieval pass was issuing a **byte-identical request** to
    rag-service and, by construction, could not produce a different result. That
    is ~8 seconds of an ~18 second request spent guaranteeing the same answer.

    Dropping the year range is different in kind: `year_from`/`year_to` really
    are sent, inside `filters`, so relaxing them really does widen what
    retrieval can return. It is also the only one of the three that is a genuine
    *semantic* relaxation -- it changes what the user asked for -- which is what
    §4.5's "constraint relaxation" means and why it is worth a second pass.

    The inert knobs are not deleted (§4.4 intends them as real discovery-mode
    levers) but they no longer count as relaxations, so they can no longer buy a
    retrieval pass with a promise they do not keep. Wiring them through for real
    is a behaviour change and wants §3.8's evaluation set behind it.
    """
    retrieval_query = dict(retrieval_query or {})
    positive = dict(retrieval_query.get("positive_constraints") or {})

    if "year_from" in positive or "year_to" in positive:
        positive.pop("year_from", None)
        positive.pop("year_to", None)
        retrieval_query["positive_constraints"] = positive
        return retrieval_query, "relaxed year range constraint"

    return None


def rewrite_query(state: RecommendationState) -> dict[str, Any]:
    """11. ONE deterministic, rule-based constraint relaxation (§4.5).

    Deliberately rule-based rather than an LLM call, so node 17 remains the
    only heavy-model call site for this phase of work (confirmed decision —
    a documented narrowing of ADR-006's literal text, flagged for later ADR
    reconciliation). Priority order lives in ``plan_query_relaxation``, which
    the router consults first so this node is only reached when a relaxation
    genuinely exists. Increments ``rewrite_count``; the router in graph.py
    guarantees this node runs at most once per request.
    """
    started = _triggered("rewrite_query")
    plan = plan_query_relaxation(state.get("retrieval_query") or {})

    if plan is None:
        # Defensive: the router should not route here at all in this case. If
        # it ever does, do NOT increment rewrite_count into a second retrieval
        # pass that cannot change anything -- report and continue.
        return {
            "rewrite_reason": "no further constraint available to relax",
            **_metrics(
                "rewrite_query",
                started,
                status="skipped",
                detail="no further constraint available to relax",
            ),
        }

    retrieval_query, reason = plan
    return {
        "rewrite_count": int(state.get("rewrite_count", 0)) + 1,
        "rewrite_reason": reason,
        "retrieval_query": retrieval_query,
        "warnings": [f"retrieval confidence was low; one bounded rewrite executed ({reason})"],
        **_metrics("rewrite_query", started, detail=reason),
    }


# ---------------------------------------------------------------------------
# 12-15: provider search intents, provider reads, dedup, ranking
# ---------------------------------------------------------------------------


def _clean_genre_slug(doc_id: str) -> str:
    """Turn a genre corpus doc_id (e.g. ``genre:edm_dance_house#deep_house``)
    into human-readable search words (``"deep house"``). Prefers the more
    specific sub-genre part after ``#``; falls back to the parent when the
    child is just a generic section name like ``"overview"``."""
    slug = str(doc_id).removeprefix("genre:")
    parent, _, child = slug.partition("#")
    chosen = child if child and child != "overview" else parent
    return chosen.replace("_", " ").replace("-", " ").strip()


# Each intent costs 100 YouTube quota units for search.list plus 1 for the
# batched videos.list enrichment, against a 10,000/day budget -- so this is a
# spend decision, not just a tuning knob. Three keeps a request at ~301 units.
MAX_SEARCH_INTENTS = 3

DEFAULT_PROVIDER = "youtube"
SUPPORTED_PROVIDERS = ("youtube", "spotify")

# Words that mean "I want this from Spotify", in the two locales WF-001 accepts.
# Deliberately specific: a request that merely *mentions* a Spotify playlist in
# passing should not silently switch providers, so these match the provider
# name itself rather than any music-service vocabulary.
_PROVIDER_MENTIONS = {
    "spotify": ("spotify", "ספוטיפיי", "ספוטיפי"),
    "youtube": ("youtube", "yt music", "יוטיוב", "יוטויב"),
}


def detect_requested_provider(text: str) -> Optional[str]:
    """Return a provider the user named outright, or None.

    An explicit ask outranks the UI toggle: if someone types "find me
    something on Spotify" while the toggle sits on YouTube, they meant
    Spotify. The toggle expresses a default, not a constraint.
    """
    lowered = (text or "").lower()
    for provider, mentions in _PROVIDER_MENTIONS.items():
        if any(mention in lowered for mention in mentions):
            return provider
    return None


def resolve_provider(state: RecommendationState) -> str:
    """Explicit request in the text > the caller's selected mode > default."""
    requested = detect_requested_provider(state.get("user_text") or "")
    if requested:
        return requested
    selected = (state.get("provider") or "").strip().lower()
    if selected in SUPPORTED_PROVIDERS:
        return selected
    return DEFAULT_PROVIDER


def build_provider_search_intents(state: RecommendationState) -> dict[str, Any]:
    """12. Deterministic search-intent construction (§4.6).

    One intent per distinct signal, not one query concatenating all of them:
    joining two unrelated genre chunks into a single compound query (e.g.
    "trance" + "hardcore punk" in one string) starves the search of any
    coherent match rather than broadening it. Confirmed live via REC-LEG
    re-run: 7/12 recommendations came back with zero YouTube results because
    of exactly this, before real search existed to expose it. No LLM call —
    LLM output would be search INTENTS, not final recommendations either way
    (§4.6); this phase keeps it rule-based.
    """
    started = _triggered("build_provider_search_intents")
    retrieval_query = state.get("retrieval_query") or {}
    positive = retrieval_query.get("positive_constraints", {})
    text = retrieval_query.get("text", "")

    provider = resolve_provider(state)

    intents: list[dict[str, Any]] = []
    seen_queries: set[str] = set()

    def _add_intent(query_text: str) -> None:
        query_text = " ".join(query_text.split()).strip()
        if query_text and query_text.lower() not in seen_queries:
            seen_queries.add(query_text.lower())
            intents.append({"query": query_text, "provider": provider, "limit": 5})

    constraint_words: list[str] = []
    constraint_words.extend(positive.get("artists", []))
    constraint_words.extend(positive.get("genres", []))
    for key in ("mood", "era"):
        value = positive.get(key)
        if isinstance(value, str) and value:
            constraint_words.append(value)
    if constraint_words:
        _add_intent(" ".join(dict.fromkeys(constraint_words)))

    for chunk in (state.get("reranked_chunks") or [])[:2]:
        domain = (chunk.get("metadata") or {}).get("domain")
        doc_id = chunk.get("document_id")
        if domain == "genre" and doc_id:
            _add_intent(_clean_genre_slug(doc_id))

    # The user's own words are always searched, not only as a last resort.
    # They were previously a fallback (`if not intents`), so a request that
    # produced any constraint at all never searched what the user actually
    # typed. Live evidence (2026-07-26): "dreamy shoegaze for a rainy night"
    # collapsed to the single intent "dream pop shoegaze", whose five results
    # were all hour-long compilations and a 52-second explainer -- while
    # searching the user's phrase directly returns real tracks. One
    # derived-constraint query plus the literal request is a much better
    # spread than two derived queries.
    _add_intent(text)
    if not intents:
        _add_intent("recommended music")

    intents = intents[:MAX_SEARCH_INTENTS]
    return {
        "provider_search_intents": intents,
        **_metrics(
            "build_provider_search_intents",
            started,
            detail="; ".join(f'"{i["query"]}"' for i in intents),
        ),
    }


async def search_providers(state: RecommendationState) -> dict[str, Any]:
    """13. Provider Adapter READS only (§4.3). Real YouTube search as of Phase 5
    §5.1/§5.3 (provider-gateway); playlist writes remain out of reach from here
    regardless, by construction -- this node only ever calls /providers/search."""
    started = _triggered("search_providers")
    intents = state.get("provider_search_intents") or []
    candidates: list[dict[str, Any]] = []

    # Run the intents concurrently. They are independent read-only searches, so
    # issuing them one after another simply added their latencies together --
    # with three intents that was most of a ~22s request, and WF-002's HTTP
    # node gives up at 25s, which is how a perfectly good Hebrew request came
    # back to the browser as "the recommendation orchestrator timed out".
    results = await asyncio.gather(
        *(
            provider_client.search(
                intent.get("query", ""),
                provider=intent.get("provider", DEFAULT_PROVIDER),
                limit=intent.get("limit", 5),
            )
            for intent in intents[:MAX_SEARCH_INTENTS]
        ),
        return_exceptions=True,
    )

    failures: list[str] = []
    for i, response in enumerate(results):
        # One failing intent must not lose the others' results -- that is the
        # whole point of gathering rather than aborting on the first error.
        if isinstance(response, BaseException):
            failures.append(type(response).__name__)
            continue
        for track in response.get("results", []):
            candidates.append({**track, "source_intent": i})

    if failures and not candidates:
        return {
            "candidate_tracks": [],
            "warnings": [f"search_providers: every provider search failed ({', '.join(failures)})"],
            **_metrics(
                "search_providers",
                started,
                status="error",
                detail="all provider searches failed",
            ),
        }

    detail = f"{len(candidates)} candidates from {len(intents[:MAX_SEARCH_INTENTS])} intent(s)"
    return {
        "candidate_tracks": candidates,
        **(
            {"warnings": [f"search_providers: {len(failures)} intent(s) failed ({', '.join(failures)})"]}
            if failures
            else {}
        ),
        **_metrics("search_providers", started, detail=detail),
    }


# Below this many track-length candidates, keep everything rather than hand
# the ranker too little to work with. Three is the same floor provider-gateway
# uses for the same reason.
MIN_TRACK_LENGTH_RESULTS = 3


# A track-length result is one provider-gateway measured as inside the
# configured bounds (60-600s). `False` means it measured *outside* them --
# a 52-second Short or a 90-minute compilation -- and `None` means unknown,
# which must not be treated as a failure.
def _is_track_length(track: dict[str, Any]) -> bool:
    return track.get("duration_in_track_range") is not False


def deduplicate_and_resolve_tracks(state: RecommendationState) -> dict[str, Any]:
    """14. Deduplicate candidates and keep only provider-resolved tracks.

    Also drops known non-track-length results when enough real tracks remain.
    provider-gateway already deprioritizes them, but its "don't return an empty
    list" fallback is evaluated *per search query* -- so a single intent that
    finds only hour-long mixes still emits them, and they arrive here mixed in
    with good results from the other intents. This node is the first place that
    sees the union across every intent, so it is the first place the fallback
    can be applied with the full picture. Live evidence (2026-07-26): a query
    for "dreamy shoegaze for a rainy night" rendered a 52-second explainer
    Short at position 1, plus three compilations of 76, 49 and 91 minutes,
    each presented as a track with a Play button.
    """
    started = _triggered("deduplicate_and_resolve_tracks")
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for track in state.get("candidate_tracks") or []:
        title = str(track.get("title", "")).strip().lower()
        artist = str(track.get("artist", "")).strip().lower()
        if not title or not artist or not track.get("provider_track_id"):
            continue
        key = (title, artist)
        existing = seen.get(key)
        if existing is None or track.get("confidence", 0) > existing.get("confidence", 0):
            seen[key] = track
    resolved = list(seen.values())

    track_length = [t for t in resolved if _is_track_length(t)]
    # Same principle as the adapter's fallback: never return nothing just
    # because every candidate was the wrong length. Keep the full set only
    # when filtering would leave too little to recommend.
    dropped = 0
    if len(track_length) >= MIN_TRACK_LENGTH_RESULTS:
        dropped = len(resolved) - len(track_length)
        resolved = track_length

    detail = f"{len(resolved)} resolved"
    if dropped:
        detail += f"; dropped {dropped} non-track-length"
    return {
        "resolved_tracks": resolved,
        **_metrics("deduplicate_and_resolve_tracks", started, detail=detail),
    }


def _text_relevance_score(track: dict[str, Any], normalized_text: str, positive: dict[str, Any]) -> float:
    """Cheap, dependency-free fuzzy overlap between a track and the query (§4.7)."""
    haystack = f"{track.get('title', '')} {track.get('artist', '')}".strip().lower()
    needle_parts = [normalized_text] + list(positive.get("genres", [])) + list(positive.get("artists", []))
    needle = " ".join(p for p in needle_parts if p).strip().lower()
    if not haystack or not needle:
        return 0.0
    return difflib.SequenceMatcher(None, haystack, needle).ratio()


# The provider's own confidence is a *result-quality* signal (is this a real
# track, from an authoritative upload, actually playable) -- NOT a taste
# signal. It must therefore carry weight even for a guest with no taste
# profile at all, which is why it is a constant here rather than a profile
# weight. Live evidence for why this matters: with provider confidence mapped
# onto the guest profile's `provider_taste` weight of 0.0, it was multiplied
# away entirely, and ranking collapsed to pure fuzzy text match -- which
# actively *rewards* titles that repeat the genre word, so "Top 5 Grunge
# Songs of All Time" (a video essay) outranked Nirvana's actual recording.
PROVIDER_CONFIDENCE_WEIGHT = 1.0



# §7.4 RANK-003/004 -----------------------------------------------------------

# At most this many tracks by the same artist in one result. §7.3 requires
# "artist repetition caps" for a specific reason: the ranker's own logic pushes
# towards repetition, because if one track by an artist scores well on taste and
# text relevance, so will their next four. Left alone, a "shoegaze for a rainy
# night" request returns five Slowdive tracks -- each individually the best
# available answer, and collectively a worse result than a varied five.
MAX_TRACKS_PER_ARTIST = 2


def _personal_taste_score(track: dict[str, Any], profile: dict[str, Any]) -> float:
    """How well a track matches the stored preference profile (§7.2 -> §7.4).

    Previously hardcoded to `1.0`, which made the whole component inert: a
    constant score multiplied by any weight contributes an identical amount to
    every candidate, so the profile could not change the order of anything. The
    profile was loaded, versioned, decayed and explained -- and then had no
    effect on a single recommendation.

    Returns 0.0-1.0 centred on 0.5, so a track the profile knows nothing about
    is neither rewarded nor punished. Artists count for more than genres: an
    artist match is an exact statement about this recording, while a genre match
    is inferred from words in a title.
    """
    if not profile:
        return 0.5

    artist = " ".join(str(track.get("artist", "")).strip().lower().split())
    haystack = f"{track.get('title', '')} {track.get('artist', '')}".lower()

    score = 0.5
    preferred_artists = {
        " ".join(str(a).strip().lower().split()) for a in profile.get("preferred_artists") or []
    }
    if artist and artist in preferred_artists:
        score += 0.4

    for genre in profile.get("preferred_genres") or []:
        if genre and str(genre).lower() in haystack:
            score += 0.2
            break

    # Avoided genres subtract more than preferred ones add. Someone who has
    # rejected a genre has made a sharper statement than someone who liked a
    # neighbouring one, and getting served the thing you rejected is the more
    # visible failure.
    for genre in profile.get("avoided_genres") or []:
        if genre and str(genre).lower() in haystack:
            score -= 0.45
            break

    return round(max(0.0, min(1.0, score)), 4)


def apply_diversity_constraints(
    ranked: list[dict[str, Any]], *, max_per_artist: int = MAX_TRACKS_PER_ARTIST
) -> tuple[list[dict[str, Any]], int]:
    """RANK-004: cap artist repetition without discarding anything.

    Over-cap tracks are **moved to the end, not dropped**. Dropping them would
    mean a request that legitimately has only one relevant artist returns fewer
    tracks than asked for -- or none -- and "we found nothing" is a far worse
    answer than "we found several by the same artist". The cap shapes the head
    of the list, which is all any caller reads.

    Returns the reordered list and how many tracks were demoted.
    """
    kept: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for track in ranked:
        artist = " ".join(str(track.get("artist", "")).strip().lower().split())
        if not artist:
            kept.append(track)
            continue
        seen[artist] = seen.get(artist, 0) + 1
        if seen[artist] <= max_per_artist:
            kept.append(track)
        else:
            track = {**track, "diversity_demoted": True}
            overflow.append(track)
    return kept + overflow, len(overflow)


def rank_tracks(state: RecommendationState) -> dict[str, Any]:
    """15. Track Reranker v1 — transparent component scores (§4.7).

    Components: ``provider_confidence`` (the adapter's result-quality score —
    official-upload heuristics, duration sanity, availability), plus
    ``text_relevance`` (fuzzy title/artist match against the query +
    constraints), ``personal_taste`` and ``provider_taste`` (profile-weighted
    taste signals, both legitimately 0 for a guest). ``audio_fit`` is
    intentionally omitted, not fabricated: provider-gateway carries no
    per-track audio features yet (Phase 6/7 wires that); its weight share is
    redistributed across the present components rather than invented, per
    §4.7's explicit instruction.
    """
    started = _triggered("rank_tracks")
    profile = state.get("user_profile") or {}
    weights = profile.get("weights", {})
    retrieval_query = state.get("retrieval_query") or {}
    positive = retrieval_query.get("positive_constraints", {})
    normalized_text = state.get("normalized_text", "")

    ranked: list[dict[str, Any]] = []
    for track in state.get("resolved_tracks") or []:
        components = {
            "provider_confidence": {
                "weight": PROVIDER_CONFIDENCE_WEIGHT,
                "score": float(track.get("confidence", 0.0)),
            },
            "text_relevance": {
                "weight": float(weights.get("text_relevance", 1.0)),
                "score": _text_relevance_score(track, normalized_text, positive),
            },
            "personal_taste": {
                "weight": float(weights.get("personal_taste", 0.0)),
                "score": _personal_taste_score(track, profile),
            },
            "provider_taste": {
                "weight": float(weights.get("provider_taste", 0.0)),
                "score": float(track.get("confidence", 0.0)),
            },
        }
        total_weight = sum(c["weight"] for c in components.values())
        if total_weight <= 0:
            final_score = components["text_relevance"]["score"]
        else:
            final_score = sum(c["weight"] * c["score"] for c in components.values()) / total_weight
        ranked.append(
            {**track, "score_components": components, "final_score": round(final_score, 4)}
        )

    ranked.sort(key=lambda t: (-t["final_score"], t.get("title", "")))
    ranked, demoted = apply_diversity_constraints(ranked)

    detail = f"{len(ranked)} tracks scored"
    if demoted:
        detail += f"; {demoted} demoted by artist cap"
    return {"ranked_tracks": ranked, **_metrics("rank_tracks", started, detail=detail)}


# ---------------------------------------------------------------------------
# 16-18: sequencing, grounded explanation, output validation
# ---------------------------------------------------------------------------

# Superseded by `sequencer.SEQUENCER_VERSION` in Phase 7. Kept as the name of
# what ran before, so an old stored recommendation's version string still
# resolves to something meaningful.
LEGACY_SEQUENCER_VERSION = "relevance-order-baseline-v1"

# How many tracks a single request answers with.
#
# §SEQ-003 sizes a sequence at 8-12 tracks, but that is the *Smart Sequencer's*
# target (Phase 7), where the deliverable is an ordered set with transitions.
# For conversational discovery the product decision (2026-07-26) is **one
# recommendation per request**: a reply that rendered five embedded players at
# once was wasteful to load and gave the user five things to evaluate instead
# of one. The follow-up recommendation comes from the next turn, informed by
# the like/dislike on this one.
#
# The cap is also what stops the curator being asked to explain a long list
# inside one bounded completion -- the failure that returned tracks with an
# empty `reasoning`. Raise this when Phase 7's sequencer needs a real set.
FINAL_TRACK_LIMIT = 1


def _track_limit() -> int:
    try:
        return max(1, int(os.getenv("RECOMMENDATION_TRACK_LIMIT") or FINAL_TRACK_LIMIT))
    except ValueError:
        return FINAL_TRACK_LIMIT


def sequence_tracks(state: RecommendationState) -> dict[str, Any]:
    """16. Smart Sequencer v1 (§7.5) — ordered set with transition reasons.

    Replaces the relevance-order baseline. The shortlist is trimmed *first* and
    then sequenced, not the other way round: ordering the whole candidate pool
    and taking the head would give the sequencer no say over which tracks are
    kept while costing it work on tracks nobody will see.

    A single-track result (the current conversational default, see
    `FINAL_TRACK_LIMIT`) has nothing to sequence, so the sequencer is skipped
    rather than run for a no-op — but the node still reports which version
    *would* have ordered it, so the metric does not silently change meaning
    when the limit is raised for a playlist request.
    """
    started = _triggered("sequence_tracks")
    shortlist = (state.get("ranked_tracks") or [])[: _track_limit()]

    if len(shortlist) < 2:
        sequenced = [{**t, "position": i + 1} for i, t in enumerate(shortlist)]
        return {
            "sequenced_tracks": sequenced,
            "sequence_confidence": 0.0,
            **_metrics(
                "sequence_tracks",
                started,
                detail=f"{sequencer.SEQUENCER_VERSION}; {len(sequenced)} track, nothing to order",
            ),
        }

    result = sequencer.sequence_tracks(shortlist)
    return {
        "sequenced_tracks": result["tracks"],
        "sequence_confidence": result["confidence"],
        "sequence_transitions": result["transitions"],
        **_metrics(
            "sequence_tracks",
            started,
            detail=(
                f"{result['sequencer_version']}; {len(result['tracks'])} of "
                f"{len(state.get('ranked_tracks') or [])} ordered; "
                f"confidence {result['confidence']}"
            ),
        ),
    }


def _user_safe_caveats(state: RecommendationState) -> list[str]:
    """Translate internal signals into short, user-safe caveat phrases (§4.8:
    "no raw retrieval mechanics ... in normal user prose").

    ``state["warnings"]`` is internal/debug text -- exception messages, field
    names, "retrieval confidence was low", etc. -- written for logs, not
    users. Never hand it to the model directly: a live run did exactly that
    and Haiku faithfully repeated "confidence in the retrieval" in
    user-facing Hebrew prose. Translate only specific, known-safe signals.
    """
    caveats: list[str] = []
    if int(state.get("rewrite_count", 0)) > 0:
        caveats.append("we weren't fully sure about this pick, so we broadened the search a little")
    return caveats


async def generate_grounded_explanation(state: RecommendationState) -> dict[str, Any]:
    """17. Curator explanation grounded in selected tracks + chunks (§4.8).

    The first (and, for this phase, only) call to the heavy model —
    claude-haiku-4-5 via the direct Anthropic API, behind ``llm_adapter``
    (ADR-006, §4.9). If there is nothing to explain, skip the call rather
    than invent an explanation.
    """
    started = _triggered("generate_grounded_explanation")
    sequenced = state.get("sequenced_tracks") or []
    if not sequenced:
        return {
            "curator_explanation": "No playable tracks were found for this request.",
            **_metrics(
                "generate_grounded_explanation",
                started,
                status="skipped",
                detail="no sequenced tracks; nothing to explain",
            ),
        }

    result = await llm_adapter.generate_curator_explanation(
        sequenced_tracks=sequenced,
        reranked_chunks=state.get("reranked_chunks") or [],
        discovery_mode=state.get("discovery_mode", DEFAULT_DISCOVERY_MODE),
        user_safe_caveats=_user_safe_caveats(state),
        normalized_text=state.get("normalized_text", ""),
    )

    metrics_entry = _metrics(
        "generate_grounded_explanation",
        started,
        model=result.model,
        status="ok" if result.success else "error",
        detail=(f"request_id={result.request_id}" if result.success else f"adapter failure: {result.error}"),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
    )

    if not result.success:
        # ADR-006: "if the API is unreachable at request time, the
        # recommendation path fails" — never synthesize a fake explanation.
        return {
            "output_valid": False,
            "warnings": [f"generate_grounded_explanation failed: {result.error}"],
            **metrics_entry,
        }

    # §4.8 requires "a concise reason per track", and ADR-006 forbids
    # synthesizing one. A track the curator declined to explain therefore
    # cannot be presented as a curated pick -- so it is dropped rather than
    # shipped with an empty `reasoning`. In practice the model declines
    # exactly the candidates that are not tracks at all (reaction videos,
    # visualizers, genre explainers that survived ranking), which makes this
    # a useful last line of defence as well as a contract requirement.
    explained: list[dict[str, Any]] = []
    for i, track in enumerate(sequenced):
        reason = (result.track_reasons.get(i) or "").strip()
        if not reason:
            continue
        # Renumber, so positions stay contiguous after a drop.
        explained.append({**track, "reasoning": reason, "position": len(explained) + 1})
    dropped = len(sequenced) - len(explained)

    if not explained:
        # Dropping everything is not a silent empty playlist -- it means the
        # curator explained nothing, which is an invalid run, handled the same
        # way as an adapter failure above.
        return {
            "output_valid": False,
            "warnings": ["generate_grounded_explanation: no track received an explanation"],
            **metrics_entry,
        }

    return {
        "sequenced_tracks": explained,
        "curator_explanation": result.playlist_description,
        "playlist_title": result.playlist_title,
        **(
            {"warnings": [f"generate_grounded_explanation: dropped {dropped} unexplained track(s)"]}
            if dropped
            else {}
        ),
        **metrics_entry,
    }


# Candidate paths for the frozen response schema — repo layout locally,
# Docker layout in the container (mirrors _db.py's multi-candidate pattern).
_SCHEMA_CANDIDATES = [
    Path(__file__).resolve().parents[3] / "contracts" / "ai_recommendation_schema.json",
    Path("/app/contracts/ai_recommendation_schema.json"),
    Path.cwd() / "contracts" / "ai_recommendation_schema.json",
]
_response_schema: Optional[dict[str, Any]] = None


def _load_response_schema() -> dict[str, Any]:
    global _response_schema
    if _response_schema is None:
        for candidate in _SCHEMA_CANDIDATES:
            if candidate.is_file():
                with open(candidate, encoding="utf-8") as f:
                    _response_schema = json.load(f)
                break
        else:
            raise FileNotFoundError(
                "ai_recommendation_schema.json not found in any candidate path: "
                f"{_SCHEMA_CANDIDATES}"
            )
    return _response_schema


def validate_output(state: RecommendationState) -> dict[str, Any]:
    """18. Validate the final payload against the frozen response contract."""
    started = _triggered("validate_output")
    if state.get("output_valid") is False:
        # An earlier node (validate_context, or node 17's failure path)
        # already declared this run invalid — don't overwrite with a pass.
        return {**_metrics("validate_output", started, status="skipped", detail="already invalid")}

    payload = {
        "playlist_title": state.get("playlist_title") or "",
        "playlist_description": state.get("curator_explanation") or "",
        "tracks": [
            {
                "title": t.get("title", ""),
                "artist": t.get("artist", ""),
                "reasoning": t.get("reasoning", ""),
            }
            for t in state.get("sequenced_tracks") or []
        ],
    }
    try:
        jsonschema.validate(payload, _load_response_schema())
    except jsonschema.ValidationError as exc:
        return {
            "output_valid": False,
            "warnings": [f"validate_output: response failed contract validation: {exc.message}"],
            **_metrics("validate_output", started, status="error", detail=exc.message),
        }
    return {"output_valid": True, **_metrics("validate_output", started)}
