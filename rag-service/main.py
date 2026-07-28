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
CE_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
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

    with Session(_get_engine()) as session:
        dense = dense_search(session, query_vector, DEFAULT_POOL, filters)
        fulltext = fulltext_search(session, or_query, DEFAULT_POOL, filters)

    info = {cid: (txt, doc_id, domain) for cid, txt, doc_id, domain in fulltext}
    info.update({cid: (txt, doc_id, domain) for cid, txt, doc_id, domain in dense})

    fused = reciprocal_rank_fusion(dense, fulltext, DEFAULT_K_RRF)
    fused_ranked = sorted(
        fused.items(),
        key=lambda kv: (-kv[1]["rrf"], kv[1]["vec_rank"] or 1e9, kv[1]["ft_rank"] or 1e9),
    )

    # Cross-encoder over a slightly wider pool than top_k, so reranking has room to reorder.
    candidate_pool = max(request.top_k, 20)
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
