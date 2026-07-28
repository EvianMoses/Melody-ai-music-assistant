"""RAG service (Section 2.4 skeleton -> Phase 4 real retrieval, §4.2 nodes 5-9).

Endpoints:
- POST /rag/retrieve -> real hybrid retrieval (dense + lexical -> RRF -> genre-graph
  expansion -> cross-encoder rerank), lifted from scripts/test_hybrid_retrieval.py and
  scripts/genre_graph.py rather than reimplemented. Models/engine/graph are loaded once
  at import time so a live service doesn't pay per-request load cost.
- POST /rag/ingest   -> disabled except for authenticated internal ingestion
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import Header
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared_lib import AppError, create_app

SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _db import resolve_database_url  # noqa: E402
from genre_graph import GenreGraph, load_genre_graph  # noqa: E402
from test_hybrid_retrieval import (  # noqa: E402
    build_lexical_or_query,
    build_metadata_filters,
    dense_search,
    fulltext_search,
    reciprocal_rank_fusion,
)

app = create_app("rag-service")

MODEL_NAME = "intfloat/multilingual-e5-small"
# Reranker, selectable at runtime so RAG-RERANK-001/002/003 stayed measured
# rather than argued about.
#
# ⚠️ DEFAULT CHANGED 2026-07-28 (RAG-RERANK-001), on measurement against the
# §3.8 golden set (25 queries). ~~cross-encoder/ms-marco-MiniLM-L-6-v2~~ is
# English-only, and the corpus is English while a fifth of real queries are not:
#
#   | reranker            | Recall@5 | MRR   | nDCG@10 | HE Recall@5 | median |
#   | ------------------- | -------- | ----- | ------- | ----------- | ------ |
#   | ms-marco (English)  | 0.409    | 0.458 | 0.410   | 0.125       | 2.29 s |
#   | none (RRF order)    | 0.424    | 0.480 | 0.426   | 0.125       | 0.13 s |
#   | mmarco (multiling.) | 0.489    | 0.511 | 0.475   | 0.500       | 2.79 s |
#
# Two findings, both worth keeping. First, the English reranker was **worse than
# no reranker at all** on every metric while costing 17x the latency -- it was
# actively destroying rankings that RRF had got right. Second, dense retrieval
# was never the Hebrew problem: multilingual-e5 returns the correct chunk top-1
# for a Hebrew query, and the English cross-encoder then demoted it. Swapping
# the reranker quadruples Hebrew Recall@5 for +0.5 s.
#
#   RERANKER_MODEL=<hf id>   swap the cross-encoder
#   RERANKER_ENABLED=false   skip reranking entirely (RRF order survives) -- the
#                            no-reranker baseline RAG-RERANK-002 requires
CE_MODEL_NAME = os.getenv(
    "RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
)
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").strip().lower() not in {
    "false",
    "0",
    "no",
}
QUERY_PREFIX = "query: "
DEFAULT_POOL = 20
DEFAULT_K_RRF = 60

_engine = None
_embedding_model = None
_cross_encoder = None
_genre_graph: Optional[GenreGraph] = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(resolve_database_url(), future=True)
    return _engine


def _get_embedding_model():
    """Lazy singleton: loaded once, reused across requests (not per-request like the CLI script)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(MODEL_NAME)
    return _embedding_model


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(CE_MODEL_NAME)
    return _cross_encoder


def _get_genre_graph() -> GenreGraph:
    global _genre_graph
    if _genre_graph is None:
        with Session(_get_engine()) as session:
            _genre_graph = load_genre_graph(session)
    return _genre_graph


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: dict[str, Any] = Field(default_factory=dict)
    # How deep each first-stage retriever goes before fusion and reranking.
    #
    # This is the recall ceiling of the whole pipeline and it was previously a
    # hardcoded 20, which was 6% of a 325-chunk corpus and became 0.5% of a
    # 4,249-chunk one. Measured consequence: a query for 90s grunge stopped
    # returning Soundgarden after the corpus grew, not because the album left
    # the store but because dense+FTS never handed it to the reranker.
    #
    # Exposed per-request so `candidate_pool` in the recommendation service's
    # DISCOVERY_PARAMS finally reaches something -- it had no consumer at all
    # until now (see graph_nodes.plan_query_relaxation).
    candidate_pool: Optional[int] = Field(default=None, ge=1, le=500)


class EvidenceChunk(BaseModel):
    document_id: str
    chunk_text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    query: str
    chunks: list[EvidenceChunk]
    retrieval_confidence: float
    matched_genres: dict[str, list[str]] = Field(default_factory=dict)
    placeholder: bool = False


class IngestRequest(BaseModel):
    source: str
    documents: list[dict[str, Any]] = Field(default_factory=list)


def _rerank(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cross-encoder rerank using the cached model instance (no per-call reload)."""
    if not candidates:
        return candidates
    if not RERANKER_ENABLED:
        # RAG-RERANK-002's baseline. Candidates arrive in RRF order, so keeping
        # that order IS the no-reranker condition. `ce_score` is still populated
        # -- from the fusion score -- because every downstream consumer reads it,
        # and returning None there would measure a crash rather than a baseline.
        for rank, candidate in enumerate(candidates):
            candidate["ce_score"] = float(candidate.get("rrf") or 0.0)
        return candidates
    model = _get_cross_encoder()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)
    for candidate, score in zip(candidates, scores):
        candidate["ce_score"] = float(score)
    return sorted(candidates, key=lambda c: c["ce_score"], reverse=True)


@app.post("/rag/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    query = request.query.strip()
    if not query:
        return RetrieveResponse(query=request.query, chunks=[], retrieval_confidence=0.0)

    filters = build_metadata_filters(
        year_from=request.filters.get("year_from"),
        year_to=request.filters.get("year_to"),
        source=request.filters.get("source"),
        domain=request.filters.get("domain"),
    )

    graph = _get_genre_graph()
    or_query, matched_genres = build_lexical_or_query(query, graph)

    model = _get_embedding_model()
    query_vector = model.encode(
        QUERY_PREFIX + query, normalize_embeddings=True, convert_to_numpy=True
    ).tolist()

    pool = request.candidate_pool or DEFAULT_POOL

    with Session(_get_engine()) as session:
        dense = dense_search(session, query_vector, pool, filters)
        fulltext = fulltext_search(session, or_query, pool, filters)

    info = {cid: (txt, doc_id, domain) for cid, txt, doc_id, domain in fulltext}
    info.update({cid: (txt, doc_id, domain) for cid, txt, doc_id, domain in dense})

    fused = reciprocal_rank_fusion(dense, fulltext, DEFAULT_K_RRF)
    fused_ranked = sorted(
        fused.items(),
        key=lambda kv: (-kv[1]["rrf"], kv[1]["vec_rank"] or 1e9, kv[1]["ft_rank"] or 1e9),
    )

    # Cross-encoder over a wider pool than top_k, so reranking has room to
    # reorder. Bounded by what fusion actually produced -- reranking cannot
    # invent candidates the first stage never returned, which is exactly the
    # ceiling `pool` above controls.
    candidate_pool = max(request.top_k, pool)
    candidates = []
    for chunk_id, entry in fused_ranked[:candidate_pool]:
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

    reranked = _rerank(query, candidates)[: request.top_k]

    top_score = reranked[0]["ce_score"] if reranked else None
    retrieval_confidence = (1.0 / (1.0 + math.exp(-top_score))) if top_score is not None else 0.0

    chunks = [
        EvidenceChunk(
            document_id=str(c.get("doc_id") or c["id"]),
            chunk_text=c["text"],
            score=c["ce_score"],
            metadata={
                "domain": c.get("domain"),
                "rrf": c["rrf"],
                "vec_rank": c["vec_rank"],
                "ft_rank": c["ft_rank"],
                "chunk_id": c["id"],
            },
        )
        for c in reranked
    ]

    return RetrieveResponse(
        query=request.query,
        chunks=chunks,
        retrieval_confidence=round(retrieval_confidence, 4),
        matched_genres=matched_genres,
    )


@app.post("/rag/ingest")
async def ingest(
    _: IngestRequest,
    x_internal_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    # Disabled except for authenticated internal ingestion tests (Section 2.4).
    expected = os.getenv("INTERNAL_INGESTION_TOKEN")
    if not expected or x_internal_token != expected:
        raise AppError(
            "Ingestion is disabled outside authenticated internal use.",
            code="INGESTION_DISABLED",
            status_code=403,
        )
    return {"ok": True, "status": "accepted", "placeholder": True}
