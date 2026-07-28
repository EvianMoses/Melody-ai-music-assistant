"""Backfill ``knowledge_chunks.embedding`` with local sentence embeddings.

Model: ``intfloat/multilingual-e5-small`` (384-d, bilingual HE/EN, CPU-friendly).
See ``docs/adr/ADR-003-embedding-model.md`` for the decision record.

E5 models expect an instruction prefix: documents are embedded as
``"passage: <text>"`` and search queries as ``"query: <text>"``. This script
only produces *passage* embeddings for stored chunks; the query side lives in
the retrieval path.

Pipeline:
1. Connect via SQLAlchemy (DATABASE_URL env / .env, psycopg v3 dialect).
2. Select ``knowledge_chunks`` rows where ``embedding IS NULL``.
3. Encode in batches (default 64) with L2 normalization (cosine-ready).
4. Write the 384-d vector back to the ``embedding`` column (pgvector).

Usage (run from the repo root, or inside the rag-service container)::

    python rag-service/scripts/generate_embeddings.py            # backfill all NULLs
    python rag-service/scripts/generate_embeddings.py --limit 100
    python rag-service/scripts/generate_embeddings.py --batch-size 32
    python rag-service/scripts/generate_embeddings.py --dry-run   # count only, no model load

Requires ``sentence-transformers`` and ``torch`` (see rag-service/requirements.txt).
On first run the model (~120 MB) is downloaded from the HuggingFace hub.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
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
EMBED_DIM = 384
PASSAGE_PREFIX = "passage: "


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-size", type=int, default=64, help="Chunks encoded per batch (default 64)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max chunks to embed this run (0 = all NULL embeddings).",
    )
    parser.add_argument("--model", default=MODEL_NAME, help="SentenceTransformer model id.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many chunks need embeddings without loading the model.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (otherwise resolved from env / .env).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    database_url = resolve_database_url(args.database_url)

    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session

    from contracts.db_models import EMBEDDING_DIM, KnowledgeChunk

    if EMBEDDING_DIM != EMBED_DIM:
        print(
            f"WARNING: contracts.db_models.EMBEDDING_DIM={EMBEDDING_DIM} but this "
            f"model produces {EMBED_DIM}-d vectors. Run the resize migration first."
        )

    engine = create_engine(database_url, future=True)

    with Session(engine) as session:
        pending = session.scalar(
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(KnowledgeChunk.embedding.is_(None))
        )
        print(f"Chunks needing embeddings: {pending}")

        if args.dry_run:
            print("[dry-run] Not loading the model or writing to the database.")
            engine.dispose()
            return 0

        if not pending:
            print("Nothing to do. All chunks already have embeddings.")
            engine.dispose()
            return 0

        target = pending if args.limit in (0, None) else min(pending, args.limit)
        print(f"Loading model '{args.model}' (first run downloads ~120 MB)...")
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(args.model)
        model_dim = model.get_sentence_embedding_dimension()
        if model_dim != EMBED_DIM:
            raise RuntimeError(
                f"Model '{args.model}' emits {model_dim}-d vectors; expected {EMBED_DIM}. "
                "Update the schema/migration and EMBED_DIM before continuing."
            )
        print(f"Model loaded (dimension={model_dim}). Backfilling {target} chunks...")

        processed = 0
        started = time.time()
        while processed < target:
            batch_size = min(args.batch_size, target - processed)
            chunks = session.scalars(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.embedding.is_(None))
                .order_by(KnowledgeChunk.id)
                .limit(batch_size)
            ).all()
            if not chunks:
                break

            texts = [PASSAGE_PREFIX + (c.chunk_text or "") for c in chunks]
            vectors = model.encode(
                texts,
                batch_size=len(texts),
                normalize_embeddings=True,  # unit vectors → cosine == dot product
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            for chunk, vector in zip(chunks, vectors):
                chunk.embedding = vector.tolist()
            session.commit()

            processed += len(chunks)
            rate = processed / max(time.time() - started, 1e-6)
            print(f"  embedded {processed}/{target} chunks ({rate:.1f}/s)")

    engine.dispose()
    print(f"\nDone. Embedded {processed} chunks with '{args.model}' ({EMBED_DIM}-d).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
