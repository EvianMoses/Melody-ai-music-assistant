"""One-hop genre-graph expansion backed by ``genre_nodes`` / ``genre_edges`` (RAG-009, §3.5 item 4).

Replaces the hardcoded ``GENRE_GRAPH`` map that ``test_hybrid_retrieval.py``
used as a placeholder. The graph is built by
``rag-service/scripts/build_genre_graph.py`` from the 23 source Markdown files.

Expansion is deliberately **one hop only** and applied to the lexical leg of the
hybrid search, so it broadens keyword recall without diluting the dense vector
query (the §3.5 decision).

Matching an alias to a query is conservative on purpose:

* aliases come from the node names themselves, split on the separators used in
  the corpus (``/``, ``:``, ``,``, ``&``, parentheses);
* very short and generic fragments are dropped, so "EDM / DANCE: HOUSE" is
  reachable by "house" but not by "dance";
* an alias matches only as a whole word.

Usage::

    from genre_graph import load_genre_graph, expand_terms
    graph = load_genre_graph(session)
    matched = expand_terms("rock music", graph)      # {"ROCK ...": [subgenres]}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import text

# Fragments that are real words in the corpus but far too broad to trigger an
# expansion on their own.
STOP_ALIASES = {
    "edm", "dance", "music", "note", "blue", "golden", "age", "new", "uk", "us",
    "contemporary", "modern", "classic", "early", "late", "and", "the", "with",
    "rock n roll", "n", "r", "b", "ii", "i",
}
MIN_ALIAS_LEN = 4
# Caps so one broad word cannot flood the lexical query with OR-terms. Without
# a global budget, "rock music" expanded into 4 families x 12 neighbours = 48
# extra terms and matched ~90% of the corpus, which flattens the lexical
# ranking signal instead of sharpening it.
MAX_EXPANSION_PER_MATCH = 8
MAX_TOTAL_EXPANSION = 14
# Some aliases are legitimately ambiguous across whole families: the corpus has
# no single "ROCK" parent, it has six rock families. Expanding into a few of
# them is more honest than arbitrarily picking the alphabetically first.
MAX_GENRES_PER_ALIAS = 4


def _normalize(value: str) -> str:
    """Fold the corpus's typographic quirks so queries can match plain spellings.

    ``DRUM 'N' BASS`` and ``drum and bass`` must reach the same node.
    """
    out = value.lower().strip()
    out = out.replace("’", "'")
    # "'n'" is not word-bounded (apostrophes are non-word characters), so it has
    # to be replaced literally before the bare-"n" rule.
    out = out.replace("'n'", " and ")
    out = re.sub(r"\bn\b", " and ", out)
    out = re.sub(r"[^\w&/:,()\s'-]", " ", out)
    return re.sub(r"\s+", " ", out).strip()


@dataclass
class GenreGraph:
    """Alias -> canonical genre name(s), plus each genre's one-hop neighbourhood."""

    alias_to_genres: dict[str, list[str]] = field(default_factory=dict)
    neighbours: dict[str, list[str]] = field(default_factory=dict)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.neighbours)


def _aliases_for(name: str) -> set[str]:
    """Searchable aliases derived from a genre name."""
    normalized = _normalize(name)
    aliases = {normalized}
    # Split on the separators actually used in the corpus.
    for part in re.split(r"[/:,&()]+", normalized):
        part = re.sub(r"\s+", " ", part).strip(" -'")
        if part:
            aliases.add(part)
    return {a for a in aliases if len(a) >= MIN_ALIAS_LEN and a not in STOP_ALIASES}


def load_genre_graph(session) -> GenreGraph:
    """Load nodes and one-hop edges from the database.

    Returns an empty graph if the tables have not been populated yet, so the
    caller can fall back rather than fail.
    """
    rows = session.execute(text("SELECT id::text, name, kind FROM genre_nodes")).all()
    if not rows:
        return GenreGraph()

    names = {row[0]: row[1] for row in rows}
    graph = GenreGraph()

    # An alias can be claimed by several nodes ("techno" is in both
    # "EDM / DANCE: TECHNO" and "EDM / DANCE: HARDCORE (TECHNO)"). Score the
    # candidates rather than letting insertion order decide, otherwise the
    # winner is just whichever file sorted first.
    candidates: dict[str, list[tuple[int, int, str]]] = {}
    for _node_id, name, kind in rows:
        graph.neighbours.setdefault(name, [])
        normalized = _normalize(name)
        for alias in _aliases_for(name):
            # Lower sorts first: exact whole-name match, then parent genres.
            candidates.setdefault(alias, []).append(
                (0 if alias == normalized else 1, 0 if kind == "parent" else 1, name)
            )

    for alias, options in candidates.items():
        options.sort(key=lambda o: (o[0], o[1], len(o[2]), o[2]))
        best_tier = (options[0][0], options[0][1])
        # Keep every candidate in the winning tier — that is what lets a broad
        # alias like "rock" reach all the rock families instead of just one.
        graph.alias_to_genres[alias] = [
            name for tier0, tier1, name in options if (tier0, tier1) == best_tier
        ][:MAX_GENRES_PER_ALIAS]

    edges = session.execute(
        text(
            """
            SELECT source_id::text, target_id::text, relation, weight
            FROM genre_edges
            ORDER BY weight DESC NULLS LAST
            """
        )
    ).all()

    for source_id, target_id, relation, _weight in edges:
        src, tgt = names.get(source_id), names.get(target_id)
        if not src or not tgt:
            continue
        # `parent` edges point subgenre -> parent; for expansion we want the
        # reverse (a broad genre should reach its subgenres). `influenced_by`
        # and `related` are useful in both directions.
        if relation == "parent":
            graph.neighbours.setdefault(tgt, []).append(src)
        else:
            graph.neighbours.setdefault(src, []).append(tgt)
            graph.neighbours.setdefault(tgt, []).append(src)

    # De-duplicate while preserving the weight-descending order.
    for genre, related in graph.neighbours.items():
        seen: dict[str, None] = {}
        for item in related:
            if item != genre:
                seen.setdefault(item, None)
        graph.neighbours[genre] = list(seen)

    return graph


def expand_terms(query: str, graph: GenreGraph) -> dict[str, list[str]]:
    """Return {matched genre: one-hop related genres} for genres named in the query."""
    if not graph.alias_to_genres:
        return {}
    normalized = _normalize(query)
    matched: dict[str, list[str]] = {}
    covered: list[str] = []
    # Longest alias first so "hardcore punk" wins over "punk".
    for alias in sorted(graph.alias_to_genres, key=len, reverse=True):
        if not re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
            continue
        # Skip an alias already contained in a longer one we just matched, so
        # "hardcore punk" does not also drag in every "punk" family.
        if any(alias in longer for longer in covered):
            continue
        covered.append(alias)
        genres = graph.alias_to_genres[alias]
        # Share the per-alias budget across an ambiguous alias's families, so
        # "rock" (4 families) does not cost four times as much as "house" (1).
        per_genre = max(2, MAX_EXPANSION_PER_MATCH // max(1, len(genres)))
        for genre in genres:
            if genre in matched:
                continue
            related = graph.neighbours.get(genre, [])[:per_genre]
            if related:
                matched[genre] = related

    # Enforce the global budget, keeping the earliest (longest-alias) matches.
    total = 0
    trimmed: dict[str, list[str]] = {}
    for genre, related in matched.items():
        if total >= MAX_TOTAL_EXPANSION:
            break
        allowed = related[: MAX_TOTAL_EXPANSION - total]
        trimmed[genre] = allowed
        total += len(allowed)
    return trimmed
