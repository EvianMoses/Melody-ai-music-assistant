"""Anthropic adapter for the single heavy-model call in the graph (§4.8/§4.9, ADR-006).

Node 17 (generate_grounded_explanation) is the only call site. Every call records
provider/model/token counts/latency/estimated cost/cache hit/request id/success
per §4.9, via ``AdapterResult``.

``user_safe_caveats`` must already be plain-language, user-appropriate strings --
never pass raw ``state["warnings"]`` (internal/debug text: exception messages,
field names, "retrieval confidence", etc.) through to this module. A prior
version did exactly that and a live run leaked "confidence in the retrieval"
into user-facing Hebrew prose, violating §4.8's "no raw retrieval mechanics in
prose" rule. Translation happens in graph_nodes.py's ``_user_safe_caveats``.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic

DEFAULT_MODEL = "claude-haiku-4-5"
# $1 / $5 per MTok (input/output) -- ADR-006.
INPUT_PRICE_PER_MTOK = 1.0
OUTPUT_PRICE_PER_MTOK = 5.0

SYSTEM_PROMPT = (
    "You are Melody's curator. Write a short, warm explanation of a track "
    "selection using only the supplied evidence and tracks.\n"
    "Rules (do not violate these):\n"
    "- No unsupported biographies or factual claims about artists or tracks.\n"
    "- No raw retrieval mechanics (scores, ranks, 'RRF', 'cross-encoder', chunk ids) in prose.\n"
    "- Never use internal/technical terms like 'retrieval', 'confidence score', "
    "'rewrite', 'query', or similar system jargon, even when translating a caveat "
    "-- write the way a human music curator would talk to a friend, in whatever "
    "language the user wrote in.\n"
    "- One or two sentences per track, grounded in the evidence or the track's own metadata.\n"
    "- 'Known caveats' below are already pre-approved, plain-language phrasing -- "
    "use them as-is or lightly adapt them; do not add technical detail back in.\n"
    "- playlist_title is short and evocative; playlist_description is 1-3 sentences."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "playlist_title": {"type": "string"},
        "playlist_description": {"type": "string"},
        "tracks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "reasoning": {"type": "string"},
                },
                "required": ["index", "reasoning"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["playlist_title", "playlist_description", "tracks"],
    "additionalProperties": False,
}


@dataclass
class AdapterResult:
    success: bool
    provider: str = "anthropic"
    model: str = DEFAULT_MODEL
    latency_ms: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    request_id: Optional[str] = None
    error: Optional[str] = None
    playlist_title: Optional[str] = None
    playlist_description: Optional[str] = None
    track_reasons: dict[int, str] = field(default_factory=dict)


def _build_user_content(
    *,
    sequenced_tracks: list[dict[str, Any]],
    reranked_chunks: list[dict[str, Any]],
    discovery_mode: str,
    user_safe_caveats: list[str],
    normalized_text: str,
) -> str:
    evidence_lines = [
        f"- [{c.get('metadata', {}).get('domain', c.get('domain', 'unknown'))}] "
        f"{(c.get('chunk_text') or c.get('text') or '').strip()[:400]}"
        for c in reranked_chunks[:8]
    ]
    track_lines = [
        f"{i}. \"{t.get('title', '')}\" by {t.get('artist', '')} "
        f"(fit score {t.get('final_score', 0):.2f})"
        for i, t in enumerate(sequenced_tracks)
    ]
    parts = [
        f"User request: {normalized_text or '(no text; audio-only request)'}",
        f"Discovery mode: {discovery_mode}",
        "Evidence:",
        *(evidence_lines or ["(none retrieved)"]),
        "Tracks to explain (reference by index):",
        *track_lines,
    ]
    if user_safe_caveats:
        parts.append("Known caveats: " + "; ".join(user_safe_caveats))
    return "\n".join(parts)


async def generate_curator_explanation(
    *,
    sequenced_tracks: list[dict[str, Any]],
    reranked_chunks: list[dict[str, Any]],
    discovery_mode: str,
    user_safe_caveats: list[str],
    normalized_text: str,
) -> AdapterResult:
    model = os.getenv("HEAVY_MODEL", DEFAULT_MODEL)
    started = time.perf_counter()
    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _build_user_content(
                        sequenced_tracks=sequenced_tracks,
                        reranked_chunks=reranked_chunks,
                        discovery_mode=discovery_mode,
                        user_safe_caveats=user_safe_caveats,
                        normalized_text=normalized_text,
                    ),
                }
            ],
            output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        )
    except Exception as exc:  # anthropic.APIError and friends -- ADR-006: fail, don't fake it
        return AdapterResult(
            success=False,
            model=model,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            error=str(exc),
        )

    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return AdapterResult(
            success=False,
            model=model,
            latency_ms=latency_ms,
            request_id=getattr(response, "_request_id", None),
            error=f"non-JSON structured output: {exc}",
        )

    usage = response.usage
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    cost = None
    if input_tokens is not None and output_tokens is not None:
        cost = round(
            (input_tokens / 1_000_000) * INPUT_PRICE_PER_MTOK
            + (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_MTOK,
            6,
        )

    return AdapterResult(
        success=True,
        model=response.model,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", None),
        estimated_cost_usd=cost,
        request_id=getattr(response, "_request_id", None),
        playlist_title=parsed.get("playlist_title"),
        playlist_description=parsed.get("playlist_description"),
        track_reasons={
            int(t["index"]): t["reasoning"]
            for t in parsed.get("tracks", [])
            if "index" in t and "reasoning" in t
        },
    )
