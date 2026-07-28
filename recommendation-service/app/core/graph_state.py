"""LangGraph state for the Phase 4 recommendation engine (plan §4.1).

``RecommendationState`` is the single mutable object that flows through all 18
graph nodes (§4.2). Nodes return *partial* updates (plain dicts); LangGraph
merges them into the state using the per-field reducers declared below:

- Most fields use the default last-write-wins semantics.
- ``warnings`` accumulates across nodes (``operator.add`` on lists).
- ``node_metrics`` accumulates one entry per node run (dict merge), satisfying
  the §4.3 rule that *every* node returns latency, model name/version, and
  safe status metadata.

Only types live here — no business logic — so the schema stays importable by
unit tests without pulling in retrieval/provider dependencies.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict


def merge_dicts(
    left: Optional[dict[str, Any]], right: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """Reducer for dict-valued state fields: shallow merge, right wins."""
    return {**(left or {}), **(right or {})}


class NodeMetric(TypedDict, total=False):
    """Safe per-node metadata (§4.3): latency, model identity, status.

    ``input_tokens``/``output_tokens``/``estimated_cost_usd`` are populated
    only by nodes that actually call a paid model (currently just node 17,
    generate_grounded_explanation) -- structured per §4.9 rather than packed
    into ``detail`` text, so log consumers (e.g. eval/rec_leg_comparison.py)
    can parse them without regexing a sentence.
    """

    latency_ms: float
    model: Optional[str]
    model_version: Optional[str]
    status: str  # "ok" | "skipped" | "error"
    detail: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost_usd: Optional[float]


class RecommendationState(TypedDict, total=False):
    """Full pipeline state across the 18 nodes (§4.1).

    ``total=False``: every field is optional so nodes can return sparse
    updates; defaults are established by ``validate_context``/entry input.
    """

    # ------------------------------------------------------------------
    # Original request context (from the RecommendationContext envelope)
    # ------------------------------------------------------------------
    request_id: str
    user_id: Optional[str]
    user_text: str
    discovery_mode: str  # "safe" | "balanced" | "adventurous" (§4.4)
    # The provider mode selected in the UI ("youtube" | "spotify"). A default,
    # not a constraint: naming a provider in `user_text` overrides it. See
    # graph_nodes.resolve_provider.
    provider: Optional[str]
    language: Optional[str]
    region: Optional[str]
    audio_features: Optional[dict[str, Any]]  # BPM/key/energy + confidence
    user_profile: Optional[dict[str, Any]]  # weights, taste signals
    explicit_constraints: dict[str, Any]  # UI intent — never overridden (§4.3)

    # ------------------------------------------------------------------
    # Normalization and structured query construction (§4.4)
    # ------------------------------------------------------------------
    context_valid: bool
    normalized_text: str
    # {"positive": {...}, "negative": {...}} — extracted from explicit_constraints
    normalized_constraints: dict[str, Any]
    retrieval_query: dict[str, Any]

    # ------------------------------------------------------------------
    # Retrieval (reuses the Phase 3 hybrid pipeline server-side)
    # ------------------------------------------------------------------
    retrieved_genres: list[dict[str, Any]]
    retrieved_reviews: list[dict[str, Any]]
    expanded_genre_terms: list[str]
    fused_chunks: list[dict[str, Any]]  # post-RRF
    reranked_chunks: list[dict[str, Any]]  # post cross-encoder, top 5-8

    # ------------------------------------------------------------------
    # Confidence gate and bounded retry (§4.3 / §4.5)
    # ------------------------------------------------------------------
    retrieval_confidence: float  # 0.0 - 1.0
    rewrite_count: int  # MUST never exceed 1 (§4.3)
    rewrite_reason: Optional[str]  # which constraint was relaxed/clarified

    # ------------------------------------------------------------------
    # Provider stage (reads only inside LangGraph — §4.3)
    # ------------------------------------------------------------------
    provider_search_intents: list[dict[str, Any]]  # LLM output = intents (§4.6)
    candidate_tracks: list[dict[str, Any]]  # raw provider results / fixtures
    resolved_tracks: list[dict[str, Any]]  # deduplicated, provider-resolved
    ranked_tracks: list[dict[str, Any]]  # Track Reranker v1 output (§4.7)
    sequenced_tracks: list[dict[str, Any]]  # final playback order
    # Smart Sequencer v1 output (§7.5). Declared here rather than left as loose
    # keys on the node's return: LangGraph builds its state from this TypedDict,
    # so anything undeclared is dropped on the way through -- silently, and only
    # in the compiled graph, which is exactly where a unit test would not see it.
    sequence_confidence: float          # share of comparisons with real data
    sequence_transitions: list[dict[str, Any]]  # per-step cost, parts, reason

    # ------------------------------------------------------------------
    # Output (§4.8)
    # ------------------------------------------------------------------
    curator_explanation: Optional[str]
    playlist_title: Optional[str]
    output_valid: bool

    # ------------------------------------------------------------------
    # Internal carrier (not part of the public contract): per-domain
    # {matched_genres, confidence} from nodes 5/6, consumed by nodes 7
    # (genre expansion) and 10 (confidence gate).
    #
    # ~~Last-write-wins is fine -- a rewrite pass fully recomputes it via
    # nodes 5/6 on the loop-back.~~ → **NO LONGER TRUE, and it now carries a
    # reducer.** That reasoning held only while nodes 5 and 6 ran in sequence,
    # each reading the other's committed value and adding its own key. Now that
    # they run CONCURRENTLY (§4.6 latency work), both read the same base state
    # and both return a `_retrieval_debug`, so last-write-wins would silently
    # discard one domain's entry -- and node 10 computes retrieval confidence
    # from both. The failure would have been invisible: a plausible confidence
    # number computed from half the evidence.
    # ------------------------------------------------------------------
    _retrieval_debug: Annotated[dict[str, Any], merge_dicts]

    # ------------------------------------------------------------------
    # Cross-cutting bookkeeping (§4.3): accumulate, never overwrite
    # ------------------------------------------------------------------
    warnings: Annotated[list[str], operator.add]
    node_metrics: Annotated[dict[str, NodeMetric], merge_dicts]
