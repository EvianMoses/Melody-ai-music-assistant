"""Prove the pgvector index works: dense semantic search over knowledge_chunks.

Embeds a query with the same model used for ingestion
(``intfloat/multilingual-e5-small``, with the required ``"query: "`` prefix,
L2-normalized) and runs a cosine-similarity search against
``knowledge_chunks.embedding`` using pgvector.

Usage (run inside the rag-service container, or locally with the deps)::

    # Built-in demo queries (English + Hebrew):
    python rag-service/scripts/test_retrieval.py

    # Custom query / options:
    python rag-service/scripts/test_retrieval.py "fast-paced electronic music"
    python rag-service/scripts/test_retrieval.py --top-k 5 "quiet pop music"

Cosine similarity = 1 - cosine_distance (embeddings are unit vectors).
"""

from __future__ import annotations

import argparse
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
QUERY_PREFIX = "query: "

# Default demo queries (kept in-file so non-ASCII queries don't depend on the
# shell encoding): one English, one Hebrew ("quiet pop music").
DEFAULT_QUERIES = [
    "fast-paced electronic music",
    "מוזיקת פופ שקטה",
]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", nargs="*", help="Query string(s). Defaults to a demo set.")
    parser.add_argument("--top-k", type=int, default=3, help="Results per query (default 3).")
    parser.add_argument("--model", default=MODEL_NAME, help="SentenceTransformer model id.")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    queries = args.queries or DEFAULT_QUERIES

    database_url = resolve_database_url(args.database_url)

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from contracts.db_models import KnowledgeChunk

    print(f"Loading model '{args.model}'...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(args.model)

    engine = create_engine(database_url, future=True)
    with Session(engine) as session:
        for query in queries:
            vector = model.encode(
                QUERY_PREFIX + query,
                normalize_embeddings=True,
                convert_to_numpy=True,
            ).tolist()

            distance = KnowledgeChunk.embedding.cosine_distance(vector).label("distance")
            rows = session.execute(
                select(KnowledgeChunk, distance)
                .where(KnowledgeChunk.embedding.is_not(None))
                .order_by(distance)
                .limit(args.top_k)
            ).all()

            print("\n" + "=" * 78)
            print(f"QUERY: {query}")
            print("=" * 78)
            for rank, (chunk, dist) in enumerate(rows, start=1):
                similarity = 1.0 - float(dist)
                meta = chunk.chunk_metadata or {}
                label = meta.get("doc_id", chunk.id)
                domain = meta.get("domain", "?")
                extra = meta.get("subgenre") or meta.get("album") or meta.get("genre") or ""
                snippet = " ".join((chunk.chunk_text or "").split())[:200]
                print(f"\n#{rank}  similarity={similarity:.4f}  [{domain}] {label}")
                if extra:
                    print(f"    {extra}")
                print(f"    {snippet}...")

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
