"""LangGraph topology for the recommendation engine (plan §4.2 / §4.3).

Wires the 18 stub nodes into a compiled ``StateGraph``:

    START
      -> validate_context -> normalize_input -> load_or_accept_user_profile
      -> build_retrieval_query
      -> [ retrieve_genres || retrieve_reviews ]   (CONCURRENT — §4.6)
      -> expand_genre_graph
      -> fuse_results -> rerank_documents
      -> evaluate_retrieval_confidence
           |-- (confidence < threshold AND rewrite_count < 1
           |     AND a relaxation exists) ---------> rewrite_query
           |       rewrite_query -> [ retrieve_genres || retrieve_reviews ]
           |                                        (ONE extra retrieval pass)
           |-- otherwise --------------------------> build_provider_search_intents
      -> search_providers -> deduplicate_and_resolve_tracks -> rank_tracks
      -> sequence_tracks -> generate_grounded_explanation -> validate_output
      -> END

Graph rules enforced by the topology itself (§4.3):
- ``rewrite_count`` can never exceed 1: the router only selects
  ``rewrite_query`` when ``rewrite_count < MAX_REWRITES`` (1), and
  ``rewrite_query`` increments the counter before looping back — so the second
  pass through the confidence gate always proceeds forward. No open-ended
  agent loop is possible (§4.5). The 2026-07-28 relaxation check makes the
  router *stricter*, never looser, so this guarantee is unaffected.
- The two retrieval nodes run in the same superstep and must therefore not
  depend on each other's output. They do not: both read only
  ``retrieval_query``. Any future node added to that fan-out must keep that
  property, and any state key two parallel nodes both write needs a reducer in
  ``graph_state.py`` — otherwise one write is silently discarded.
- Provider access is read-only: only ``search_providers`` touches the Provider
  Adapter; no write node exists in the graph.
"""

from __future__ import annotations

import os
from typing import Literal

from langgraph.graph import END, START, StateGraph

from . import graph_nodes as nodes
from .graph_state import RecommendationState

# §4.3: rewrite_count must never exceed 1.
MAX_REWRITES = 1
# Retrieval confidence below this triggers the single bounded rewrite (§4.5).
CONFIDENCE_THRESHOLD = float(os.getenv("RETRIEVAL_CONFIDENCE_THRESHOLD", "0.5"))

# (name, callable) in the exact §4.2 order.
NODE_SEQUENCE = [
    ("validate_context", nodes.validate_context),
    ("normalize_input", nodes.normalize_input),
    ("load_or_accept_user_profile", nodes.load_or_accept_user_profile),
    ("build_retrieval_query", nodes.build_retrieval_query),
    ("retrieve_genres", nodes.retrieve_genres),
    ("retrieve_reviews", nodes.retrieve_reviews),
    ("expand_genre_graph", nodes.expand_genre_graph),
    ("fuse_results", nodes.fuse_results),
    ("rerank_documents", nodes.rerank_documents),
    ("evaluate_retrieval_confidence", nodes.evaluate_retrieval_confidence),
    ("rewrite_query", nodes.rewrite_query),
    ("build_provider_search_intents", nodes.build_provider_search_intents),
    ("search_providers", nodes.search_providers),
    ("deduplicate_and_resolve_tracks", nodes.deduplicate_and_resolve_tracks),
    ("rank_tracks", nodes.rank_tracks),
    ("sequence_tracks", nodes.sequence_tracks),
    ("generate_grounded_explanation", nodes.generate_grounded_explanation),
    ("validate_output", nodes.validate_output),
]


def route_after_confidence(
    state: RecommendationState,
) -> Literal["rewrite_query", "build_provider_search_intents"]:
    """Conditional edge out of ``evaluate_retrieval_confidence`` (§4.5).

    Routes to the single bounded rewrite only when ALL THREE hold:
    - retrieval confidence is below ``CONFIDENCE_THRESHOLD``;
    - ``rewrite_count`` is still below ``MAX_REWRITES`` (i.e. 0);
    - **a relaxation actually exists** for this query.

    Otherwise the pipeline continues forward — with warnings or an honest
    no-result response, never another loop.

    ⚠️ The third condition was added on 2026-07-28 and is a latency fix, not a
    behaviour change. Measured: the rewrite fired on 100% of observed requests,
    because retrieval confidence is near zero for ordinary phrasing ("warm indie
    folk for a rainy afternoon" scores 0.0012 while returning five good chunks)
    and near one only when the query contains a literal genre name. So the
    "exceptional" path was the default path.

    Without this check, a request whose query has nothing left to relax still
    looped back and re-ran the whole retrieval pipeline with **identical
    inputs** — guaranteed to produce identical results, for roughly 8 seconds
    of an 18-second request. Asking ``plan_query_relaxation`` first is what
    makes the loop-back conditional on it being able to accomplish something.

    Note this does NOT weaken §4.3's guarantee: ``rewrite_count`` can still
    only ever reach 1, and the condition here is strictly narrower than before.
    """
    confidence = float(state.get("retrieval_confidence", 0.0))
    rewrites = int(state.get("rewrite_count", 0))
    if confidence >= CONFIDENCE_THRESHOLD or rewrites >= MAX_REWRITES:
        return "build_provider_search_intents"

    if nodes.plan_query_relaxation(state.get("retrieval_query") or {}) is None:
        return "build_provider_search_intents"

    return "rewrite_query"


def build_graph() -> StateGraph:
    """Assemble the (uncompiled) StateGraph with all 18 nodes and edges."""
    graph = StateGraph(RecommendationState)

    for name, fn in NODE_SEQUENCE:
        graph.add_node(name, fn)

    # Linear spine up to the confidence gate.
    graph.add_edge(START, "validate_context")
    graph.add_edge("validate_context", "normalize_input")
    graph.add_edge("normalize_input", "load_or_accept_user_profile")
    graph.add_edge("load_or_accept_user_profile", "build_retrieval_query")
    # §4.6 latency: nodes 5 and 6 run CONCURRENTLY, not one after the other.
    #
    # They are genuinely independent -- both read only `retrieval_query`, and
    # neither looks at the other's output -- so the sequential edge between them
    # was costing the full duration of the slower call for nothing. Measured:
    # genre retrieval ~7.0 s, reviews ~1.4 s; run in parallel the pair costs
    # what the genre call alone costs.
    #
    # Fanning out required one supporting change: `_retrieval_debug` gained a
    # merge reducer in graph_state.py. Both nodes write that key, and without a
    # reducer LangGraph's last-write-wins would have dropped one domain's entry
    # -- leaving node 10 to compute retrieval confidence from half the evidence
    # and report a perfectly plausible number for it.
    #
    # `expand_genre_graph` has an incoming edge from each, so LangGraph waits
    # for both to finish before running it.
    graph.add_edge("build_retrieval_query", "retrieve_genres")
    graph.add_edge("build_retrieval_query", "retrieve_reviews")
    graph.add_edge("retrieve_genres", "expand_genre_graph")
    graph.add_edge("retrieve_reviews", "expand_genre_graph")
    graph.add_edge("expand_genre_graph", "fuse_results")
    graph.add_edge("fuse_results", "rerank_documents")
    graph.add_edge("rerank_documents", "evaluate_retrieval_confidence")

    # Confidence gate: one bounded rewrite OR continue forward (§4.5).
    graph.add_conditional_edges(
        "evaluate_retrieval_confidence",
        route_after_confidence,
        {
            "rewrite_query": "rewrite_query",
            "build_provider_search_intents": "build_provider_search_intents",
        },
    )
    # The rewrite loops back for ONE additional retrieval pass -- into both
    # retrieval nodes, matching the parallel fan-out above.
    graph.add_edge("rewrite_query", "retrieve_genres")
    graph.add_edge("rewrite_query", "retrieve_reviews")

    # Linear spine from provider intents to the end.
    graph.add_edge("build_provider_search_intents", "search_providers")
    graph.add_edge("search_providers", "deduplicate_and_resolve_tracks")
    graph.add_edge("deduplicate_and_resolve_tracks", "rank_tracks")
    graph.add_edge("rank_tracks", "sequence_tracks")
    graph.add_edge("sequence_tracks", "generate_grounded_explanation")
    graph.add_edge("generate_grounded_explanation", "validate_output")
    graph.add_edge("validate_output", END)

    return graph


# Compiled singleton used by the service (and by `python -m app.core.graph`).
recommendation_graph = build_graph().compile()


def describe_graph() -> str:
    """Human-readable summary of the compiled topology + routing rules."""
    lines = [
        "Compiled LangGraph: 18 nodes (§4.2 order)",
        "",
        "Nodes:",
    ]
    for i, (name, _fn) in enumerate(NODE_SEQUENCE, start=1):
        lines.append(f"  {i:2d}. {name}")
    lines += [
        "",
        "Conditional routing (evaluate_retrieval_confidence):",
        f"  if retrieval_confidence < {CONFIDENCE_THRESHOLD} and rewrite_count < {MAX_REWRITES}:",
        "      -> rewrite_query  (increments rewrite_count, loops to retrieve_genres",
        "                         for exactly ONE additional retrieval pass)",
        "  else:",
        "      -> build_provider_search_intents  (continue forward)",
        "",
        "Mermaid diagram:",
        recommendation_graph.get_graph().draw_mermaid(),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe_graph())
