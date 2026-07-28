"""Phase 3 local knowledge ingestion pipeline (text-only, no embeddings yet).

Reads the two local knowledge domains that already live in ``data/`` and loads
them into the ``knowledge_documents`` / ``knowledge_chunks`` tables:

1. Genre knowledge -- 23 Markdown files in ``data/genres_knowledge/``.
   Split by Markdown headers (H1 genre overview, ``### SUBGENRE`` sections) so
   every chunk maps to one semantic section (RAG-006).
2. Album reviews -- ``data/cleaned_large_dataset_t.csv``.
   Each unique review becomes one coherent passage that keeps the song / artist
   / score context around the review text (RAG-007).

Every chunk gets a stable source-document id (``genre:{slug}`` /
``review:{source}:{id}`` -- RAG-004) and domain/source/genre/artist/era/version
metadata (RAG-008).

Embeddings are intentionally left ``NULL`` here; a later step wires the real
embedding model. The generated ``content_tsv`` column is populated by Postgres,
so we never write it from Python.

Usage (from the repo root, using the project venv)::

    python rag-service/scripts/ingest_local_data.py --all
    python rag-service/scripts/ingest_local_data.py --genres
    python rag-service/scripts/ingest_local_data.py --reviews --reviews-limit 500
    python rag-service/scripts/ingest_local_data.py --all --dry-run   # parse only

The database URL is resolved from ``DATABASE_URL`` (env var first, then ``.env``),
exactly like ``migrations/env.py``. Re-running is idempotent: a document with the
same ``(source, uri, version)`` is deleted (cascading its chunks) and re-inserted.
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

# --- Make the repo root importable so ``contracts`` / ``.env`` resolve -------
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DATA_DIR = REPO_ROOT / "data"
GENRE_DIR = DATA_DIR / "genres_knowledge"
REVIEWS_CSV = DATA_DIR / "cleaned_large_dataset_t.csv"

INGESTION_VERSION = "v0-text-2026-07"

# RAG-010. `--stage` writes a NEW version alongside the live one instead of
# replacing it in place, so a bad chunking change is never live before WF-007's
# smoke queries have judged it. The live corpus keeps serving throughout.
_STAGED_VERSION: Optional[str] = None


def active_ingestion_version() -> str:
    """The version this run writes to: the staged one if staging, else v0."""
    return _STAGED_VERSION or INGESTION_VERSION


def active_doc_version() -> str:
    """Document-level version for this run.

    Must move with the ingestion version while staging. `knowledge_documents` is
    unique on (source, uri, version), and staging deliberately does NOT delete
    the live document -- so reusing "v0" makes the staged document collide with
    the one still serving traffic. Found by running it: the first staged run
    failed on that constraint, which is the safe direction to fail in (the live
    corpus was untouched) but is still a failure.
    """
    return _STAGED_VERSION or DOC_VERSION


DOC_VERSION = "v0"

# Large CSV fields (long review descriptions) can exceed the default limit.
csv.field_size_limit(10_000_000)


# ---------------------------------------------------------------------------
# Small parsed representations (decoupled from the ORM so --dry-run needs no DB)
# ---------------------------------------------------------------------------
@dataclass
class ParsedChunk:
    chunk_index: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    source: str
    title: str
    uri: str
    doc_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[ParsedChunk] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase, collapse non-alphanumeric runs to single underscores."""
    return _SLUG_RE.sub("_", value.strip().lower()).strip("_")


_YEAR_RE = re.compile(r"^\s*(1[89]\d{2}|20\d{2})\s*$")
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*#*\s*$")


# ---------------------------------------------------------------------------
# Genre Markdown chunking (regex-based Markdown header splitter)
# ---------------------------------------------------------------------------
def split_markdown_by_headers(text: str) -> list[dict[str, Any]]:
    """Split Markdown into leaf sections keyed by their H1/H2/H3 header path.

    Returns a list of ``{"headers": {1:.., 2:.., 3:..}, "body": str}`` entries,
    one per header section (content before the first header is dropped).
    """
    sections: list[dict[str, Any]] = []
    headers: dict[int, Optional[str]] = {}
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if headers and body:
            sections.append({"headers": dict(headers), "body": body})
        buffer.clear()

    for line in text.splitlines():
        match = _HEADER_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            headers[level] = title
            # Clear deeper levels so a new H2 resets the stale H3, etc.
            for deeper in [lvl for lvl in headers if lvl > level]:
                headers[deeper] = None
        else:
            buffer.append(line)
    flush()
    return sections


# ---------------------------------------------------------------------------
# Token-bounded splitting (RAG-003 / embedding correctness)
# ---------------------------------------------------------------------------
#
# The embedding model is `intfloat/multilingual-e5-small`, whose hard limit is
# **512 tokens**. Anything longer is silently truncated at encode time -- the
# tokenizer even warns `877 > 512 ... will result in indexing errors` -- so the
# tail of a long section simply never reaches the vector.
#
# Measured before this fix: 30 of 300 genre chunks (10%) exceeded the limit, the
# worst at 877 tokens, meaning ~42% of that section's text was invisible to
# dense retrieval while still appearing in full-text search. That asymmetry is
# the nastiest part -- a chunk could be found lexically and then score terribly
# on the reranker, because the reranker was reading text the embedder never saw.
#
# 420 rather than 512: `passage: ` prefixes the text at embed time, headers are
# prepended for self-describing chunks, and tokenizer estimates drift by a few
# percent across languages. The margin costs nothing and removes a class of
# silent failure.
MAX_CHUNK_TOKENS = 420

# Conservative chars-per-token for this tokenizer on English prose. Measured
# against the real tokenizer: 1,700 chars -> 343 tokens, 4,371 -> 877, i.e.
# ~4.96 chars/token. 4.0 keeps the estimate on the safe side without shredding
# paragraphs unnecessarily.
_CHARS_PER_TOKEN = 4.0
MAX_CHUNK_CHARS = int(MAX_CHUNK_TOKENS * _CHARS_PER_TOKEN)


def split_long_body(body: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split an over-long section into pieces that survive embedding intact.

    Splits on paragraph boundaries first and only falls back to sentence
    boundaries when a single paragraph is itself too long, so a piece stays a
    coherent unit of prose rather than an arbitrary character window. Returns
    ``[body]`` unchanged when it already fits, which is the common case.
    """
    body = body.strip()
    if len(body) <= max_chars:
        return [body]

    # Paragraphs, preserving their internal structure.
    units: list[str] = []
    for para in re.split(r"\n\s*\n", body):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            units.append(para)
            continue
        # A single oversized paragraph: fall back to sentence boundaries.
        sentence = ""
        for piece in re.split(r"(?<=[.!?])\s+", para):
            if len(sentence) + len(piece) + 1 <= max_chars:
                sentence = f"{sentence} {piece}".strip()
            else:
                if sentence:
                    units.append(sentence)
                # A single sentence longer than the window is pathological;
                # hard-split it rather than emit something that will truncate.
                while len(piece) > max_chars:
                    units.append(piece[:max_chars])
                    piece = piece[max_chars:]
                sentence = piece
        if sentence:
            units.append(sentence)

    # Recombine adjacent units up to the limit, so we emit as few pieces as
    # possible -- fewer, larger chunks retrieve better than many small ones.
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}".strip() if current else unit
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = unit
    if current:
        chunks.append(current)

    return chunks or [body[:max_chars]]


def parse_genre_file(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8")
    sections = split_markdown_by_headers(text)

    genre_name = sections[0]["headers"].get(1, path.stem) if sections else path.stem
    slug = slugify(genre_name)
    doc_id = f"genre:{slug}"

    doc = ParsedDocument(
        source="genre_knowledge",
        title=genre_name,
        uri=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        doc_id=doc_id,
        metadata={
            "domain": "genre",
            "source": "genre_knowledge",
            "genre": genre_name,
            "language": "en",
            "version": DOC_VERSION,
            "doc_id": doc_id,
        },
    )

    for index, section in enumerate(sections):
        headers = section["headers"]
        body = section["body"]
        subgenre = headers.get(3)
        section_label = headers.get(2)

        # Detect a leading "year" line (e.g. "1949") in subgenre sections.
        era: Optional[str] = None
        body_lines = body.splitlines()
        if body_lines and _YEAR_RE.match(body_lines[0]):
            era = body_lines[0].strip()

        if subgenre:
            title_for_chunk = subgenre
            chunk_slug = slugify(subgenre)
        elif section_label:
            title_for_chunk = section_label
            chunk_slug = slugify(section_label)
        else:
            title_for_chunk = genre_name
            chunk_slug = "overview"

        # Prepend a context header so a retrieved chunk is self-describing.
        context_path = " > ".join(
            v for v in (headers.get(1), headers.get(2), headers.get(3)) if v
        )

        # Keep every emitted chunk inside the embedding model's window. The
        # header is repeated on each piece so a part-2 chunk is still
        # self-describing when retrieved on its own -- without it, the second
        # half of a long sub-genre section arrives as anonymous prose.
        header_cost = len(context_path) + 2
        pieces = split_long_body(body, max_chars=MAX_CHUNK_CHARS - header_cost)

        for part, piece in enumerate(pieces):
            chunk_text = f"{context_path}\n\n{piece}".strip()

            chunk_meta = {
                "domain": "genre",
                "source": "genre_knowledge",
                "genre": genre_name,
                "section": section_label,
                "subgenre": subgenre,
                "title": title_for_chunk,
                "era": era,
                "language": "en",
                "version": DOC_VERSION,
                # RAG-005: the doc_id stays stable for the section; a split
                # section carries an explicit part suffix so a citation can name
                # exactly which piece of the source it came from.
                "doc_id": f"{doc_id}#{chunk_slug}" + (f"~{part + 1}" if len(pieces) > 1 else ""),
                "source_uri": doc.uri,
                "section_part": (part + 1) if len(pieces) > 1 else None,
                "section_parts": len(pieces) if len(pieces) > 1 else None,
            }
            # Drop empty metadata keys to keep JSONB tidy.
            chunk_meta = {k: v for k, v in chunk_meta.items() if v is not None}

            doc.chunks.append(
                ParsedChunk(
                    chunk_index=len(doc.chunks), text=chunk_text, metadata=chunk_meta
                )
            )

    return doc


def parse_all_genres() -> list[ParsedDocument]:
    if not GENRE_DIR.is_dir():
        raise FileNotFoundError(f"Genre directory not found: {GENRE_DIR}")
    docs: list[ParsedDocument] = []
    for path in sorted(GENRE_DIR.glob("*.md")):
        doc = parse_genre_file(path)
        if doc.chunks:
            docs.append(doc)
    return docs


# ---------------------------------------------------------------------------
# Reviews CSV chunking (one coherent passage per unique review)
# ---------------------------------------------------------------------------
REVIEW_SOURCE = "metacritic"


def _clean_artist(raw: str) -> str:
    raw = (raw or "").strip()
    return re.sub(r"^by\s+", "", raw, flags=re.IGNORECASE).strip()


def parse_reviews(limit: Optional[int]) -> Optional[ParsedDocument]:
    if not REVIEWS_CSV.is_file():
        print(f"  ! Reviews dataset not found at {REVIEWS_CSV}; skipping.")
        return None

    doc_id = f"review:{REVIEW_SOURCE}"
    doc = ParsedDocument(
        source="reviews_context",
        title="Contemporary album ratings and reviews (Metacritic)",
        uri=str(REVIEWS_CSV.relative_to(REPO_ROOT)).replace("\\", "/"),
        doc_id=doc_id,
        metadata={
            "domain": "reviews",
            "source": REVIEW_SOURCE,
            "language": "en",
            "version": DOC_VERSION,
            "doc_id": doc_id,
        },
    )

    seen: set[str] = set()
    chunk_index = 0
    with REVIEWS_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            description = (row.get("Description") or "").strip()
            song = (row.get("Name of the Song") or "").strip()
            artist = _clean_artist(row.get("Artist", ""))
            if not description:
                continue

            # De-duplicate the many exact-duplicate rows (RAG-003).
            dedup_key = f"{song}\u241f{artist}\u241f{description}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            row_id = (row.get("Unnamed: 0") or str(chunk_index)).strip()
            release = (row.get("Date of Release") or "").strip()
            metascore = (row.get("Metascore") or "").strip()
            user_score = (row.get("User Score") or "").strip()
            era = None
            year_match = re.search(r"(1[89]\d{2}|20\d{2})", release)
            if year_match:
                era = year_match.group(1)

            header_bits = []
            if song:
                header_bits.append(song)
            if artist:
                header_bits.append(f"by {artist}")
            if release:
                header_bits.append(f"({release})")
            score_bits = []
            if metascore:
                score_bits.append(f"Metascore {metascore}")
            if user_score:
                score_bits.append(f"User score {user_score}")
            header = " ".join(header_bits)
            if score_bits:
                header = f"{header} — {', '.join(score_bits)}".strip(" —")

            chunk_text = f"{header}\n\n{description}".strip()

            chunk_meta = {
                "domain": "reviews",
                "source": REVIEW_SOURCE,
                "artist": artist or None,
                "album": song or None,
                "release_date": release or None,
                "era": era,
                "metascore": metascore or None,
                "user_score": user_score or None,
                "language": "en",
                "version": DOC_VERSION,
                "doc_id": f"review:{REVIEW_SOURCE}:{row_id}",
                # RAG-005: every chunk names the file it came from, so an
                # answer can be traced back to its source without joining
                # through knowledge_documents. Added to the genre parser first
                # and missed here, which an audit caught -- 3,836 review chunks
                # had no source reference at all.
                "source_uri": doc.uri,
                "source_row": row_id or None,
            }
            chunk_meta = {k: v for k, v in chunk_meta.items() if v is not None}

            doc.chunks.append(
                ParsedChunk(chunk_index=chunk_index, text=chunk_text, metadata=chunk_meta)
            )
            chunk_index += 1
            if limit is not None and chunk_index >= limit:
                break

    return doc if doc.chunks else None


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------
def resolve_database_url(override: Optional[str] = None) -> str:
    """Resolve DATABASE_URL (env > .env) and force the psycopg (v3) dialect."""
    import os

    url = override or os.getenv("DATABASE_URL")
    if not url:
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)
            url = os.getenv("DATABASE_URL")
        except ImportError:
            url = None
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Define it in the environment or .env "
            "(e.g. postgresql+psycopg://user:pass@localhost:5432/melody)."
        )
    for prefix, repl in (
        ("postgresql+psycopg2://", "postgresql+psycopg://"),
        ("postgresql://", "postgresql+psycopg://"),
        ("postgres://", "postgresql+psycopg://"),
    ):
        if url.startswith(prefix):
            return repl + url[len(prefix):]
    return url


def persist_documents(docs: Iterable[ParsedDocument], database_url: str) -> tuple[int, int]:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from contracts.db_models import KnowledgeChunk, KnowledgeDocument

    engine = create_engine(database_url, future=True)
    doc_count = 0
    chunk_count = 0

    with Session(engine) as session:
        for parsed in docs:
            # Idempotent re-run: drop any prior version of this document first.
            existing = session.scalars(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source == parsed.source,
                    KnowledgeDocument.uri == parsed.uri,
                    KnowledgeDocument.version == active_doc_version(),
                )
            ).all()
            for old in existing:
                # Replace-in-place is correct for a normal run and WRONG
                # while staging: deleting the live document would take the
                # active corpus down before the new one has been validated.
                # Staged rows are a separate version and coexist with it.
                if _STAGED_VERSION:
                    continue
                session.delete(old)
            session.flush()

            document = KnowledgeDocument(
                source=parsed.source,
                title=parsed.title,
                uri=parsed.uri,
                version=active_doc_version(),
                doc_metadata=parsed.metadata,
            )
            for parsed_chunk in parsed.chunks:
                document.chunks.append(
                    KnowledgeChunk(
                        chunk_index=parsed_chunk.chunk_index,
                        chunk_text=parsed_chunk.text,
                        embedding=None,  # real embeddings handled in the next step
                        ingestion_version=active_ingestion_version(),
                        chunk_metadata=parsed_chunk.metadata,
                    )
                )
            session.add(document)
            doc_count += 1
            chunk_count += len(parsed.chunks)
            print(
                f"  + {parsed.doc_id}: {len(parsed.chunks)} chunks "
                f"({parsed.source})"
            )

        session.commit()

    engine.dispose()
    return doc_count, chunk_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--genres", action="store_true", help="Ingest genre Markdown files.")
    parser.add_argument("--reviews", action="store_true", help="Ingest the reviews CSV.")
    parser.add_argument("--all", action="store_true", help="Ingest both domains.")
    parser.add_argument(
        "--stage",
        action="store_true",
        help=(
            "RAG-010: write a NEW ingestion version alongside the live corpus "
            "instead of replacing it. The staged version is invisible to "
            "retrieval until POST /rag/ingest publishes it."
        ),
    )
    parser.add_argument(
        "--stage-version",
        default=None,
        help="Explicit staged version id (default: v<timestamp>-text).",
    )
    parser.add_argument(
        "--reviews-limit",
        type=int,
        default=500,
        help="Max unique reviews to ingest (default 500; use 0 for no limit).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report chunk counts without touching the database.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (otherwise resolved from env / .env).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    do_genres = args.genres or args.all
    do_reviews = args.reviews or args.all
    if not (do_genres or do_reviews):
        do_genres = do_reviews = True  # default to everything

    global _STAGED_VERSION
    if args.stage:
        _STAGED_VERSION = args.stage_version or (
            "v" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-text"
        )
        print(f"STAGING as ingestion version: {_STAGED_VERSION}")
        print("  (the live corpus keeps serving until this version is published)")

    reviews_limit = None if args.reviews_limit == 0 else args.reviews_limit

    parsed_docs: list[ParsedDocument] = []

    if do_genres:
        print("Parsing genre Markdown files...")
        genre_docs = parse_all_genres()
        genre_chunks = sum(len(d.chunks) for d in genre_docs)
        print(f"  parsed {len(genre_docs)} genre documents, {genre_chunks} chunks")
        parsed_docs.extend(genre_docs)

    if do_reviews:
        limit_label = "no limit" if reviews_limit is None else f"limit {reviews_limit}"
        print(f"Parsing reviews CSV ({limit_label})...")
        reviews_doc = parse_reviews(reviews_limit)
        if reviews_doc:
            print(f"  parsed {len(reviews_doc.chunks)} unique review chunks")
            parsed_docs.append(reviews_doc)

    total_chunks = sum(len(d.chunks) for d in parsed_docs)
    print(f"\nTotal: {len(parsed_docs)} documents, {total_chunks} chunks")

    if args.dry_run:
        print("\n[dry-run] Skipping database insertion. Sample chunks:")
        for doc in parsed_docs:
            if doc.chunks:
                sample = doc.chunks[0]
                preview = sample.text[:160].replace("\n", " ")
                print(f"\n  [{doc.doc_id}] {sample.metadata.get('doc_id')}")
                print(f"    {preview}...")
        return 0

    database_url = resolve_database_url(args.database_url)
    safe_url = re.sub(r"//[^@]+@", "//***:***@", database_url)
    print(f"\nInserting into database: {safe_url}")
    doc_count, chunk_count = persist_documents(parsed_docs, database_url)
    print(f"\nDone. Inserted/updated {doc_count} documents and {chunk_count} chunks.")
    print("Embeddings left NULL; content_tsv generated by Postgres.")

    if _STAGED_VERSION:
        # Register the version so /rag/ingest can publish or roll it back, and
        # so it is visible in `status` rather than being an orphan set of rows.
        from sqlalchemy import create_engine as _ce, text as _sql_text

        with _ce(database_url, future=True).begin() as conn:
            conn.execute(
                _sql_text(
                    "INSERT INTO ingestion_versions (version, status, stats, notes) "
                    "VALUES (:v, 'staged', jsonb_build_object('documents', :d, 'chunks', :c), :n) "
                    "ON CONFLICT (version) DO UPDATE SET "
                    "status = 'staged', stats = EXCLUDED.stats, updated_at = now()"
                ),
                {
                    "v": _STAGED_VERSION,
                    "d": doc_count,
                    "c": chunk_count,
                    "n": "Staged by ingest_local_data.py --stage",
                },
            )
        print()
        print(f"Staged version {_STAGED_VERSION} registered (status=staged).")
        print("  Next: generate embeddings, then let WF-007 validate and publish it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
