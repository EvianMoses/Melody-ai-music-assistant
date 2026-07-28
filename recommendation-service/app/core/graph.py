"""LangGraph topology for the recommendation engine (plan §4.2 / §4.3).

Wires the 18 stub nodes into a compiled ``StateGraph``:

    START
      -> validate_context -> normalize_input -> load_or_accept_user_profile
      -> build_retrieval_query
      -> retrieve_genres -> retrieve_reviews -> expand_genre_graph
      -> fuse_results -> rerank_documents
      -> evaluate_retrieval_confidence
           |-- (confidence < threshold AND rewrite_count < 1) --> rewrite_query
           |       rewrite_query -> retrieve_genres   (ONE extra retrieval pass)
           |-- otherwise --------------------------> build_provider_search_intents
      -> search_providers -> deduplicate_and_resolve_tracks -> rank_tracks
      -> sequence_tracks -> generate_grounded_explanation -> validate_output
      -> END

Graph rules enforced by the topology itself (§4.3):
- ``rewrite_count`` can never exceed 1: the router only selects
  ``rewrite_query`` when ``rewrite_count < MAX_REWRITES`` (1), and
  ``rewrite_query`` increments the counter before looping back — so the second
  pass through the confidence gate always proceeds forward. No open-ended
  agent loop is possible (§4.5).
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

    Routes to the single bounded rewrite only when BOTH hold:
    - retrieval confidence is below ``CONFIDENCE_THRESHOLD``;
    - ``rewrite_count`` is still below ``MAX_REWRITES`` (i.e. 0).

    Otherwise the pipeline continues forward — with warnings or an honest
    no-result response, never another loop.
    """
    confidence = float(state.get("retrieval_confidence", 0.0))
    rewrites = int(state.get("rewrite_count", 0))
    if confidence < CONFIDENCE_THRESHOLD and rewrites < MAX_REWRITES:
        return "rewrite_query"
    return "build_provider_search_intents"


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
    graph.add_edge("build_retrieval_query", "retrieve_genres")
    graph.add_edge("retrieve_genres", "retrieve_reviews")
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
    # The rewrite loops back for ONE additional retrieval pass.
    graph.add_edge("rewrite_query", "retrieve_genres")

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
