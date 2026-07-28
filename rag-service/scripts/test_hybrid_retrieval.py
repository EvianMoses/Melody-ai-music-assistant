"""Hybrid retrieval + rerank: the full §3.5 pipeline (items 1–7) and §3.6.

Combines the two retrieval legs already proven individually:
- Dense: pgvector cosine search over ``knowledge_chunks.embedding`` using
  ``intfloat/multilingual-e5-small`` (``"query: "`` prefix, L2-normalized).
- Lexical: Postgres full-text over ``content_tsv`` with
  ``websearch_to_tsquery('english', …)`` ranked by ``ts_rank_cd``.

Fusion: Reciprocal Rank Fusion (RRF). Each result list contributes
``1 / (k + rank)`` (rank is 1-based, ``k`` defaults to 60). A chunk's final
score is the sum of its contributions across both lists.

Rerank (items 6–7 / §3.6): the top ~20 fused candidates are re-scored by a local
cross-encoder (``cross-encoder/ms-marco-MiniLM-L-6-v2``) that reads the full
(query, chunk) pair, then the list is sorted by that score and sliced to the top
5 chunks for downstream generation. Reranking is on by default (``--no-rerank``
to skip). Unlike the bi-encoder retrievers, a cross-encoder attends over the
query and passage jointly, so it is far more precise for the final ordering —
but too expensive to run over the whole corpus, hence "retrieve-then-rerank".

This module also implements §3.5 items 3 and 4:

* Item 3 — Exact-name and metadata filters. Optional ``year_from`` / ``year_to``
  / ``source`` / ``domain`` filters are applied to BOTH legs *before* fusion, as
  predicates on the JSONB ``knowledge_chunks.metadata`` column (e.g.
  ``metadata->>'source' = :source``, numeric year via ``metadata->>'era'``). A
  real LLM query-parser that fills these kwargs is deferred to §3.8.
* Item 4 — One-hop genre-graph expansion (mocked). If a broad genre is detected
  in the query, its subgenres are OR-appended to the lexical query string only
  (e.g. ``"rock"`` → ``"rock OR indie rock OR post-punk …"``). The dense leg
  keeps the original phrasing.

Usage (inside the rag-service container)::

    python scripts/test_hybrid_retrieval.py "fast-paced electronic music"
    python scripts/test_hybrid_retrieval.py --domain genre "rock music"
    python scripts/test_hybrid_retrieval.py --source metacritic --year-from 2015 "indie"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_PATH.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PATH.parent))

from _db import resolve_database_url  # noqa: E402

MODEL_NAME = "intfloat/multilingual-e5-small"
CE_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
QUERY_PREFIX = "query: "
TS_CONFIG = "english"
DEFAULT_QUERY = "fast-paced electronic music"
DEFAULT_FINAL_K = 5

# One-hop genre expansion (item 4) now reads the real `genre_nodes` /
# `genre_edges` graph built by `build_genre_graph.py` (RAG-009).
# ~~A hardcoded mock map used to live here.~~
FALLBACK_GENRE_GRAPH: dict[str, list[str]] = {
    # Used only when the genre tables are empty, so the script still runs on a
    # database where `build_genre_graph.py` has not been executed yet.
    "rock": ["indie rock", "post-punk", "classic rock", "hardcore punk"],
    "electronic": ["techno", "house", "trance", "breakbeat"],
    "pop": ["dream pop", "synthpop", "power pop"],
    "jazz": ["nu jazz", "bebop", "electro jazz"],
    "metal": ["heavy metal", "thrash metal", "doom metal"],
    "reggae": ["dub", "dancehall", "ska"],
    "hip hop": ["rap", "trap", "electro"],
}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*", help=f'Query (default "{DEFAULT_QUERY}").')
    parser.add_argument(
        "--pool", type=int, default=20, help="Candidates retrieved per method (default 20)."
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=20,
        help="Top fused candidates sent to the cross-encoder (default 20).",
    )
    parser.add_argument(
        "--final-k",
        type=int,
        default=DEFAULT_FINAL_K,
        help=f"Final chunks selected for generation (default {DEFAULT_FINAL_K}).",
    )
    parser.add_argument(
        "--rerank",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Cross-encoder rerank the fused candidates (default on; --no-rerank to skip).",
    )
    parser.add_argument("--k-rrf", type=int, default=60, help="RRF constant k (default 60).")
    parser.add_argument("--model", default=MODEL_NAME, help="Bi-encoder (retrieval) model id.")
    parser.add_argument("--ce-model", default=CE_MODEL_NAME, help="Cross-encoder (rerank) model id.")
    # Metadata pre-filters (item 3).
    parser.add_argument("--year-from", type=int, default=None, help="Min era/year (inclusive).")
    parser.add_argument("--year-to", type=int, default=None, help="Max era/year (inclusive).")
    parser.add_argument("--source", default=None, help='Filter metadata.source (e.g. "metacritic").')
    parser.add_argument("--domain", default=None, help='Filter metadata.domain ("genre"|"reviews").')
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    return parser


def build_metadata_filters(
    *,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    source: Optional[str] = None,
    domain: Optional[str] = None,
) -> list:
    """SQLAlchemy predicates on the JSONB ``metadata`` column (item 3).

    Applied identically to the dense and lexical queries so both legs see the
    same pre-filtered candidate set before RRF.
    """
    from sqlalchemy import Integer, cast, func

    from contracts.db_models import KnowledgeChunk

    md = KnowledgeChunk.chunk_metadata
    conditions: list = []
    if source:
        conditions.append(md["source"].astext == source)
    if domain:
        conditions.append(md["domain"].astext == domain)
    if year_from is not None or year_to is not None:
        # era holds a 4-digit year (or is absent). Strip any non-digits and cast;
        # regexp_replace + NULLIF keeps non-numeric/empty values NULL (never errors).
        year_val = cast(
            func.nullif(func.regexp_replace(md["era"].astext, r"\D", "", "g"), ""),
            Integer,
        )
        if year_from is not None:
            conditions.append(year_val >= year_from)
        if year_to is not None:
            conditions.append(year_val <= year_to)
    return conditions


def expand_query_with_genres(query: str, graph=None) -> tuple[list[str], dict[str, list[str]]]:
    """Detect genres in the query and return (base_tokens, {genre: related}).

    Uses the real graph when one is supplied; otherwise falls back to the small
    static map so the script still works against an unpopulated database.
    """
    base_tokens = [t for t in re.split(r"\W+", query, flags=re.UNICODE) if t]
    if graph is not None and len(graph):
        from genre_graph import expand_terms

        return base_tokens, expand_terms(query, graph)

    lowered = query.lower()
    matched: dict[str, list[str]] = {}
    for broad, subs in FALLBACK_GENRE_GRAPH.items():
        if re.search(rf"\b{re.escape(broad)}\b", lowered):
            matched[broad] = subs
    return base_tokens, matched


def build_lexical_or_query(query: str, graph=None) -> tuple[str, dict[str, list[str]]]:
    """OR-join base tokens plus any one-hop genre expansions (items 4 + recall)."""
    base_tokens, matched = expand_query_with_genres(query, graph)
    terms = list(base_tokens)
    for subs in matched.values():
        terms.extend(subs)
    # De-duplicate while preserving order.
    seen: dict[str, None] = {}
    for term in terms:
        seen.setdefault(term, None)
    or_query = " OR ".join(seen.keys()) if seen else query
    return or_query, matched


def dense_search(session, query_vector, pool, filters):
    """Ordered list of (chunk_id, chunk_text, doc_id, domain) from vector search."""
    from sqlalchemy import select

    from contracts.db_models import KnowledgeChunk

    distance = KnowledgeChunk.embedding.cosine_distance(query_vector).label("distance")
    stmt = select(KnowledgeChunk, distance).where(KnowledgeChunk.embedding.is_not(None))
    for condition in filters:
        stmt = stmt.where(condition)
    rows = session.execute(stmt.order_by(distance).limit(pool)).all()

    results = []
    for chunk, _dist in rows:
        meta = chunk.chunk_metadata or {}
        results.append(
            (str(chunk.id), chunk.chunk_text or "", meta.get("doc_id"), meta.get("domain"))
        )
    return results


def fulltext_search(session, or_query, pool, filters):
    """Ordered list of (chunk_id, chunk_text, doc_id, domain) from full-text search."""
    from sqlalchemy import func, select

    from contracts.db_models import KnowledgeChunk

    tsquery = func.websearch_to_tsquery(TS_CONFIG, or_query)
    rank = func.ts_rank_cd(KnowledgeChunk.content_tsv, tsquery).label("rank")
    stmt = select(KnowledgeChunk, rank).where(KnowledgeChunk.content_tsv.op("@@")(tsquery))
    for condition in filters:
        stmt = stmt.where(condition)
    rows = session.execute(stmt.order_by(rank.desc()).limit(pool)).all()

    results = []
    for chunk, _rank in rows:
        meta = chunk.chunk_metadata or {}
        results.append(
            (str(chunk.id), chunk.chunk_text or "", meta.get("doc_id"), meta.get("domain"))
        )
    return results


def reciprocal_rank_fusion(dense, fulltext, k):
    """Fuse two ranked id lists. Returns dict id -> {rrf, vec_rank, ft_rank}."""
    fused: dict[str, dict] = {}

    def ingest(results, key):
        for rank, (chunk_id, *_rest) in enumerate(results, start=1):
            entry = fused.setdefault(chunk_id, {"rrf": 0.0, "vec_rank": None, "ft_rank": None})
            entry["rrf"] += 1.0 / (k + rank)
            entry[key] = rank

    ingest(dense, "vec_rank")
    ingest(fulltext, "ft_rank")
    return fused


def cross_encoder_rerank(query, candidates, model_name):
    """Re-score (query, chunk_text) pairs with a local cross-encoder.

    Mutates each candidate dict with a ``ce_score`` and returns the list sorted
    by that score (descending). The cross-encoder reads the query and passage
    jointly, so it is much more precise than the bi-encoder retrieval scores.
    """
    from sentence_transformers import CrossEncoder

    model = CrossEncoder(model_name)
    pairs = [(query, candidate["text"]) for candidate in candidates]
    scores = model.predict(pairs)
    for candidate, score in zip(candidates, scores):
        candidate["ce_score"] = float(score)
    return sorted(candidates, key=lambda c: c["ce_score"], reverse=True)


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    query = " ".join(args.query) if args.query else DEFAULT_QUERY

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    filters = build_metadata_filters(
        year_from=args.year_from,
        year_to=args.year_to,
        source=args.source,
        domain=args.domain,
    )
    # Load the real genre graph (RAG-009) before building the lexical query.
    from genre_graph import load_genre_graph

    graph_engine = create_engine(resolve_database_url(args.database_url), future=True)
    with Session(graph_engine) as graph_session:
        genre_graph = load_genre_graph(graph_session)
    if len(genre_graph):
        print(f"genre graph: {len(genre_graph)} genres, {len(genre_graph.alias_to_genres)} aliases")
    else:
        print("genre graph: EMPTY — falling back to the static map "
              "(run build_genre_graph.py to populate genre_nodes/genre_edges)")

    or_query, matched_genres = build_lexical_or_query(query, genre_graph)

    print(f"Loading model '{args.model}'...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(args.model)
    query_vector = model.encode(
        QUERY_PREFIX + query, normalize_embeddings=True, convert_to_numpy=True
    ).tolist()

    engine = create_engine(resolve_database_url(args.database_url), future=True)
    with Session(engine) as session:
        dense = dense_search(session, query_vector, args.pool, filters)
        fulltext = fulltext_search(session, or_query, args.pool, filters)

    info = {cid: (txt, doc_id, domain) for cid, txt, doc_id, domain in fulltext}
    info.update({cid: (txt, doc_id, domain) for cid, txt, doc_id, domain in dense})

    fused = reciprocal_rank_fusion(dense, fulltext, args.k_rrf)
    fused_ranked = sorted(
        fused.items(),
        key=lambda kv: (-kv[1]["rrf"], kv[1]["vec_rank"] or 1e9, kv[1]["ft_rank"] or 1e9),
    )

    # Top fused candidates that will be handed to the cross-encoder (item 6).
    candidates = []
    for chunk_id, entry in fused_ranked[: args.candidates]:
        text_val, doc_id, domain = info.get(chunk_id, ("", None, None))
        candidates.append(
            {
                "id": chunk_id,
                "text": text_val,
                "doc_id": doc_id,
                "domain": domain,
                "rrf": entry["rrf"],
                "vec_rank": entry["vec_rank"],
                "ft_rank": entry["ft_rank"],
            }
        )

    active_filters = []
    if args.domain:
        active_filters.append(f"domain={args.domain}")
    if args.source:
        active_filters.append(f"source={args.source}")
    if args.year_from is not None:
        active_filters.append(f"year>={args.year_from}")
    if args.year_to is not None:
        active_filters.append(f"year<={args.year_to}")

    do_rerank = args.rerank and bool(candidates)
    if do_rerank:
        print(f"Reranking {len(candidates)} candidates with cross-encoder '{args.ce_model}'...")
        final = cross_encoder_rerank(query, candidates, args.ce_model)[: args.final_k]
    else:
        final = candidates[: args.final_k]

    stage = "HYBRID + CROSS-ENCODER RERANK" if do_rerank else "HYBRID (RRF, no rerank)"
    print("\n" + "=" * 78)
    print(f"{stage} — QUERY: {query}")
    print(f"metadata filters: {', '.join(active_filters) if active_filters else 'none'}")
    if matched_genres:
        expansion = "; ".join(f"{g} -> {', '.join(s)}" for g, s in matched_genres.items())
        print(f"genre-graph expansion: {expansion}")
    print(f"lexical tsquery (OR): {or_query}")
    print(
        f"dense: {len(dense)} | full-text: {len(fulltext)} | fused: {len(fused_ranked)} "
        f"| reranked: {len(candidates) if do_rerank else 0} -> top {len(final)}"
    )
    print("=" * 78)

    for position, candidate in enumerate(final, start=1):
        vec_label = f"#{candidate['vec_rank']}" if candidate["vec_rank"] else "—"
        ft_label = f"#{candidate['ft_rank']}" if candidate["ft_rank"] else "—"
        snippet = " ".join((candidate["text"] or "").split())[:200]
        score_bits = f"RRF={candidate['rrf']:.6f}   vector={vec_label}  full-text={ft_label}"
        if do_rerank:
            score_bits = f"CE={candidate['ce_score']:+.4f}   " + score_bits
        print(f"\n{position}.  {score_bits}")
        print(f"    [{candidate['domain']}] {candidate['doc_id']}")
        print(f"    {snippet}...")

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
