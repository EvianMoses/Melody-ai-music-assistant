"""Phase 3 genre-graph builder — populates ``genre_nodes`` and ``genre_edges`` (RAG-009).

Reads the 23 Markdown files in ``data/genres_knowledge/`` and derives a real
genre graph instead of the hardcoded map that §3.5 item 4 used as a placeholder.

Source structure (verified across all 23 files)::

    # PARENT GENRE NAME              <- one per file, 23 total
    ...prose...
    ## Sub-Genres
    ### SUBGENRE NAME                <- 277 total
    1910                             <- year of emergence
    BLUESGOLDEN AGE(r & b)           <- lineage marker
    ...prose...

The lineage marker is a concatenation of tokens from a closed 22-token
vocabulary of super-genres, optionally followed by a lowercase parenthetical
secondary influence. ``BLUESGOLDEN AGE`` means "influenced by BLUES and by
GOLDEN AGE"; ``JUMP BLUES -> BLUES(r & b)`` means "primarily BLUES, secondarily
R & B".

What is written:

* ``genre_nodes`` — 23 ``kind='parent'`` rows and 277 ``kind='subgenre'`` rows.
  Each subgenre's ``parent_id`` points at the parent genre whose file it is in.
  ``metadata`` carries the year, decade, source file, and stable document id.
* ``genre_edges`` — three relations:
  ``parent``       subgenre -> containing parent genre (weight 1.0)
  ``influenced_by``subgenre -> super-genre from the lineage marker
                   (weight 1.0 primary, 0.6 secondary, 0.3 parenthetical)
  ``related``      parent <-> parent, when a lineage marker links two families

Nothing is invented: an edge exists only where the source document states a
lineage. Genres with no parseable marker simply get no influence edge.

Usage (from the repo root)::

    python rag-service/scripts/build_genre_graph.py --dry-run   # parse + report only
    python rag-service/scripts/build_genre_graph.py             # write to the database

Re-running is idempotent: nodes are matched by unique ``name`` and edges by the
``(source_id, target_id, relation)`` unique constraint.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --- Make the repo root importable so ``contracts`` / ``.env`` resolve -------
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _db import resolve_database_url  # noqa: E402

GENRE_DIR = REPO_ROOT / "data" / "genres_knowledge"
INGESTION_VERSION = "v0-genre-graph-2026-07"

# Closed vocabulary of lineage tokens -> the parent genre (H1) each one names.
# Derived by enumerating every distinct marker in the corpus, not guessed.
TOKEN_TO_PARENT: dict[str, str] = {
    "BLUES": "BLUE NOTE: BLUES",
    "GOSPEL": "BLUE NOTE: GOSPEL & PIONEERS",
    "JAZZ": "BLUE NOTE: JAZZ",
    "COUNTRY": "COUNTRY",
    "DOWNTEMPO": "DOWNTEMPO / AMBIENT",
    "BREAKBEAT": "EDM / DANCE: BREAKBEAT",
    "DRUM 'N' BASS": "EDM / DANCE: DRUM 'N' BASS / JUNGLE",
    "HOUSE": "EDM / DANCE: HOUSE",
    "TECHNO": "EDM / DANCE: TECHNO",
    "TRANCE": "EDM / DANCE: TRANCE",
    "METAL": "HEAVY METAL",
    "INDUSTRIAL": "INDUSTRIAL & GOTHIC",
    "JAMAICAN": "JAMAICAN MUSIC / REGGAE",
    "POP": "POP MUSIC",
    "RAP": "RAP / HIP-HOP MUSIC",
    "R & B": "RHYTHM 'N' BLUES (R&B)",
    "ALTERNATIVE": "Rock, ALTERNATIVE ROCK / INDIE",
    "CONTEMPORARY": "CONTEMPORARY ROCK",
    "GOLDEN AGE": "ROCK, GOLDEN AGE, CLASSIC ROCK",
    "PUNK/WAVE": "PUNK ROCK / NEW WAVE",
    "ROCK 'N' ROLL": "ROCK, ROCK 'N' ROLL (R'N'R) (ROCK & ROLL)",
}

# "HARDCORE" is genuinely ambiguous in the corpus: it names both the EDM genre
# (EDM / DANCE: HARDCORE (TECHNO)) and hardcore punk (ROCK, HARDCORE PUNK).
# Resolved by company rather than by guess — if the marker also names an EDM
# genre, it is the EDM one; otherwise it is hardcore punk. Solo "HARDCORE"
# falls back to the family of the file the subgenre lives in.
AMBIGUOUS_TOKEN = "HARDCORE"
HARDCORE_EDM = "EDM / DANCE: HARDCORE (TECHNO)"
HARDCORE_PUNK = "ROCK, HARDCORE PUNK"
EDM_TOKENS = {"TECHNO", "TRANCE", "HOUSE", "BREAKBEAT", "DRUM 'N' BASS", "DOWNTEMPO"}

# Longest-first so "DRUM 'N' BASS" wins over a shorter prefix during the split.
LINEAGE_TOKENS = sorted(
    list(TOKEN_TO_PARENT) + [AMBIGUOUS_TOKEN], key=len, reverse=True
)

SUBGENRE_RE = re.compile(r"^### ([^\n]+)\n(.*?)(?=^### |\Z)", re.M | re.S)
H1_RE = re.compile(r"^# ([^\n]+)$", re.M)
YEAR_RE = re.compile(r"^(\d{4})$")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


@dataclass
class Subgenre:
    name: str
    parent: str
    source_file: str
    year: Optional[int] = None
    lineage_raw: str = ""
    primary: list[str] = field(default_factory=list)
    secondary: list[str] = field(default_factory=list)


def split_lineage(marker: str) -> tuple[list[str], list[str]]:
    """Split a lineage marker into (primary tokens, parenthetical tokens).

    ``BLUESGOLDEN AGE(r & b)`` -> (["BLUES", "GOLDEN AGE"], ["R & B"])
    An unrecognised remainder is dropped rather than guessed at.
    """
    paren_tokens: list[str] = []
    m = re.search(r"\(([^)]*)\)\s*$", marker)
    if m:
        inner = m.group(1).strip().upper()
        marker = marker[: m.start()]
        for tok in LINEAGE_TOKENS:
            if inner == tok:
                paren_tokens.append(tok)
                break

    rest = marker.strip().upper()
    primary: list[str] = []
    # Greedy longest-prefix split against the closed vocabulary.
    while rest:
        for tok in LINEAGE_TOKENS:
            if rest.startswith(tok):
                primary.append(tok)
                rest = rest[len(tok):].strip()
                break
        else:
            break  # unrecognised remainder — stop rather than invent
    return primary, paren_tokens


def resolve_token(token: str, companions: list[str], source_parent: str) -> Optional[str]:
    """Map a lineage token to a parent genre name, resolving HARDCORE by context."""
    if token != AMBIGUOUS_TOKEN:
        return TOKEN_TO_PARENT.get(token)
    if any(c in EDM_TOKENS for c in companions):
        return HARDCORE_EDM
    if source_parent.startswith("EDM"):
        return HARDCORE_EDM
    return HARDCORE_PUNK


def parse_corpus() -> tuple[list[str], list[Subgenre], list[str]]:
    """Return (parent genre names, subgenres, warnings)."""
    parents: list[str] = []
    subgenres: list[Subgenre] = []
    warnings: list[str] = []

    for path in sorted(GENRE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        h1 = H1_RE.findall(text)
        if not h1:
            warnings.append(f"{path.name}: no H1 heading, skipped")
            continue
        parent = h1[0].strip()
        parents.append(parent)

        for m in SUBGENRE_RE.finditer(text):
            name = m.group(1).strip()
            lines = [ln.strip() for ln in m.group(2).split("\n") if ln.strip()]
            sub = Subgenre(name=name, parent=parent, source_file=path.name)

            # A few headings carry the year inline ("POST-ROCK 1995") instead of
            # on the following line; then line 0 is already the lineage marker.
            heading_year = re.search(r"\s(\d{4})$", name)
            if heading_year:
                sub.year = int(heading_year.group(1))
                sub.name = name[: heading_year.start()].strip()
                if lines:
                    sub.lineage_raw = lines[0]
            elif len(lines) >= 1 and YEAR_RE.fullmatch(lines[0]):
                sub.year = int(lines[0])
                if len(lines) >= 2:
                    sub.lineage_raw = lines[1]
            elif lines:
                warnings.append(
                    f"{path.name}: '{name[:40]}' has no year line "
                    f"(first line: {lines[0][:30]!r})"
                )
            else:
                warnings.append(f"{path.name}: '{name[:40]}' has an empty body")

            if sub.lineage_raw:
                prim, sec = split_lineage(sub.lineage_raw)
                if not prim:
                    warnings.append(
                        f"{path.name}: '{name[:40]}' unparsed lineage "
                        f"{sub.lineage_raw[:30]!r}"
                    )
                sub.primary, sub.secondary = prim, sec
            subgenres.append(sub)

    return parents, subgenres, warnings


def build_graph(parents: list[str], subgenres: list[Subgenre]):
    """Return (nodes, edges) as plain dicts, ready to persist."""
    nodes: list[dict] = [
        {
            "name": p,
            "kind": "parent",
            "parent": None,
            "metadata": {
                "doc_id": f"genre:{slugify(p)}",
                "version": INGESTION_VERSION,
                "domain": "genre_knowledge",
            },
        }
        for p in parents
    ]

    edges: list[tuple[str, str, str, float]] = []  # (source, target, relation, weight)
    family_links: set[tuple[str, str]] = set()

    # 39 subgenre names are cross-listed under two (or three) parent families —
    # e.g. TRIP HOP under both DOWNTEMPO / AMBIENT and EDM / DANCE: BREAKBEAT.
    # `genre_nodes.name` is UNIQUE and one node per genre is the correct model,
    # so merge the occurrences explicitly instead of letting the last one
    # silently overwrite the others: the first parent becomes `parent_id`, and
    # every family is kept both in metadata and as its own `parent` edge.
    merged: dict[str, dict] = {}
    for sub in subgenres:
        spec = merged.get(sub.name)
        if spec is None:
            spec = {
                "name": sub.name,
                "kind": "subgenre",
                "parent": sub.parent,  # first occurrence wins -> deterministic
                "metadata": {
                    "doc_id": f"genre:{slugify(sub.parent)}#{slugify(sub.name)}",
                    "version": INGESTION_VERSION,
                    "domain": "genre_knowledge",
                    "year": sub.year,
                    "decade": (sub.year // 10 * 10) if sub.year else None,
                    "parents": [],
                    "source_files": [],
                    "lineage_raw": [],
                },
            }
            merged[sub.name] = spec
        meta = spec["metadata"]
        if sub.parent not in meta["parents"]:
            meta["parents"].append(sub.parent)
        if sub.source_file not in meta["source_files"]:
            meta["source_files"].append(sub.source_file)
        if sub.lineage_raw and sub.lineage_raw not in meta["lineage_raw"]:
            meta["lineage_raw"].append(sub.lineage_raw)
        # Keep the earliest attested year across cross-listings.
        if sub.year and (meta["year"] is None or sub.year < meta["year"]):
            meta["year"] = sub.year
            meta["decade"] = sub.year // 10 * 10

        edges.append((sub.name, sub.parent, "parent", 1.0))

    nodes.extend(merged.values())

    for sub in subgenres:
        for idx, tok in enumerate(sub.primary):
            target = resolve_token(tok, sub.primary, sub.parent)
            if not target:
                continue
            edges.append((sub.name, target, "influenced_by", 1.0 if idx == 0 else 0.6))
            if target != sub.parent:
                family_links.add(tuple(sorted((sub.parent, target))))

        for tok in sub.secondary:
            target = resolve_token(tok, sub.primary, sub.parent)
            if target:
                edges.append((sub.name, target, "influenced_by", 0.3))
                if target != sub.parent:
                    family_links.add(tuple(sorted((sub.parent, target))))

    # Parent-level `related` edges, derived only from observed lineage links.
    for a, b in sorted(family_links):
        edges.append((a, b, "related", 0.5))
        edges.append((b, a, "related", 0.5))

    return nodes, edges


def persist(nodes: list[dict], edges: list[tuple[str, str, str, float]], url: str) -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from contracts.db_models import GenreEdge, GenreNode

    engine = create_engine(url, future=True)
    with Session(engine) as session:
        # --- nodes: upsert by unique name ---------------------------------
        existing = {n.name: n for n in session.scalars(select(GenreNode))}
        for spec in nodes:
            node = existing.get(spec["name"])
            if node is None:
                node = GenreNode(name=spec["name"])
                session.add(node)
                existing[spec["name"]] = node
            node.kind = spec["kind"]
            node.node_metadata = spec["metadata"]
        session.flush()

        # Parent links need the ids, so they are set on a second pass.
        for spec in nodes:
            if spec["parent"]:
                child = existing[spec["name"]]
                parent = existing.get(spec["parent"])
                child.parent_id = parent.id if parent else None
        session.flush()

        # --- edges: upsert by (source, target, relation) -------------------
        by_identity = {
            (e.source_id, e.target_id, e.relation): e
            for e in session.scalars(select(GenreEdge))
        }
        added = 0
        for src_name, tgt_name, relation, weight in edges:
            src, tgt = existing.get(src_name), existing.get(tgt_name)
            if not src or not tgt or src.id == tgt.id:
                continue
            key = (src.id, tgt.id, relation)
            edge = by_identity.get(key)
            if edge is None:
                edge = GenreEdge(
                    source_id=src.id, target_id=tgt.id, relation=relation, weight=weight
                )
                session.add(edge)
                by_identity[key] = edge
                added += 1
            else:
                edge.weight = weight
        session.commit()

        parents = sum(1 for s in nodes if s["kind"] == "parent")
        print(
            f"\nwrote {len(nodes)} nodes ({parents} parent / "
            f"{len(nodes) - parents} subgenre), {added} new edges"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Parse and report; write nothing.")
    ap.add_argument("--database-url", default=None, help="Override the resolved DATABASE_URL.")
    args = ap.parse_args()

    if not GENRE_DIR.is_dir():
        print(f"error: {GENRE_DIR} not found", file=sys.stderr)
        return 1

    parents, subgenres, warnings = parse_corpus()
    nodes, edges = build_graph(parents, subgenres)

    by_relation: dict[str, int] = {}
    for _, _, rel, _ in edges:
        by_relation[rel] = by_relation.get(rel, 0) + 1

    distinct_subs = len(nodes) - len(parents)
    cross_listed = len(subgenres) - distinct_subs
    print(f"parsed {len(parents)} parent genres, {len(subgenres)} subgenre entries")
    print(
        f"nodes: {len(nodes)} ({len(parents)} parent + {distinct_subs} distinct subgenre; "
        f"{cross_listed} cross-listed entries merged by name)"
    )
    print(f"edges: {len(edges)} built  {by_relation}")
    unlinked = [s.name for s in subgenres if not s.primary]
    print(f"subgenres with no influence edge: {len(unlinked)}")
    for name in unlinked[:10]:
        print(f"   - {name[:60]}")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings[:10]:
            print(f"   ! {w}")

    if args.dry_run:
        print("\n(dry run — nothing written)")
        return 0

    persist(nodes, edges, resolve_database_url(args.database_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
