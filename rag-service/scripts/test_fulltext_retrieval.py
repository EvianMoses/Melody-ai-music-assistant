"""Prove PostgreSQL full-text retrieval over knowledge_chunks (§3.5 item 2).

This is the lexical (BM25-like) leg of the hybrid retrieval pipeline, and the
counterpart to the dense vector search in ``test_retrieval.py``. It needs no
embedding model — it relies entirely on native Postgres full-text search.

How it works:
- The search string is turned into a ``tsquery`` with ``websearch_to_tsquery``
  ('english' config), which accepts natural input (plain words, "quoted
  phrases", OR, -negation).
- Matching uses the ``content_tsv`` column, a GENERATED STORED column
  (``to_tsvector('english', chunk_text)``) that Postgres maintains automatically
  and which is indexed with GIN (``ix_knowledge_chunks_content_tsv``).
- Results are ranked with ``ts_rank_cd`` (cover-density ranking).

`content_tsv` population:
Because ``content_tsv`` is a GENERATED STORED column, it is always in sync with
``chunk_text`` and CANNOT be written to with ``UPDATE`` (Postgres rejects that).
If for any reason the column were unavailable/empty, this script transparently
falls back to computing ``to_tsvector('english', chunk_text)`` on the fly in the
query (use ``--on-the-fly`` to force it). The permanent fix, if the generated
column were ever dropped, is a migration — not a data UPDATE.

Usage (inside the rag-service container — see the run instructions in chat)::

    python scripts/test_fulltext_retrieval.py                 # default query "electronic"
    python scripts/test_fulltext_retrieval.py "drum and bass"
    python scripts/test_fulltext_retrieval.py --top-k 5 "melancholic guitar"
    python scripts/test_fulltext_retrieval.py --on-the-fly "electronic"
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

DEFAULT_QUERY = "electronic"
TS_CONFIG = "english"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*", help=f'Search string (default "{DEFAULT_QUERY}").')
    parser.add_argument("--top-k", type=int, default=3, help="Results to show (default 3).")
    parser.add_argument(
        "--on-the-fly",
        action="store_true",
        help="Compute to_tsvector(chunk_text) in the query instead of using content_tsv.",
    )
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    query = " ".join(args.query) if args.query else DEFAULT_QUERY

    from sqlalchemy import create_engine, text

    engine = create_engine(resolve_database_url(args.database_url), future=True)

    with engine.connect() as conn:
        # Decide which tsvector source to rank against.
        populated = conn.execute(
            text("SELECT count(*) FROM knowledge_chunks WHERE content_tsv IS NOT NULL")
        ).scalar_one()
        total = conn.execute(text("SELECT count(*) FROM knowledge_chunks")).scalar_one()
        use_on_the_fly = args.on_the_fly or populated == 0

        source_expr = (
            f"to_tsvector('{TS_CONFIG}', chunk_text)" if use_on_the_fly else "content_tsv"
        )
        mode = "on-the-fly to_tsvector(chunk_text)" if use_on_the_fly else "stored content_tsv column"
        print(f"content_tsv populated: {populated}/{total} chunks")
        print(f"Ranking source: {mode}")
        print(f'tsquery: websearch_to_tsquery({TS_CONFIG!r}, "{query}")')

        sql = text(
            f"""
            SELECT
                chunk_text,
                metadata->>'doc_id'  AS doc_id,
                metadata->>'domain'  AS domain,
                ts_rank_cd({source_expr}, q) AS rank
            FROM knowledge_chunks, websearch_to_tsquery(:cfg, :q) AS q
            WHERE {source_expr} @@ q
            ORDER BY rank DESC
            LIMIT :k
            """
        )
        rows = conn.execute(
            sql, {"cfg": TS_CONFIG, "q": query, "k": args.top_k}
        ).all()

        print("\n" + "=" * 78)
        print(f"FULL-TEXT QUERY: {query}")
        print("=" * 78)
        if not rows:
            print("\n(no matches)")
        for rank, row in enumerate(rows, start=1):
            snippet = " ".join((row.chunk_text or "").split())[:200]
            print(f"\n#{rank}  ts_rank_cd={float(row.rank):.6f}  [{row.domain}] {row.doc_id}")
            print(f"    {snippet}...")

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
