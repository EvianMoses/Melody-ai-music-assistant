# EXAMPLE GENRE

**This file is synthetic.** It exists to show `ingest_local_data.py` what it
parses — the real genre corpus is not distributed with this repository (see
`data/README.md`). Every word below is filler; do not ingest it as knowledge.

A parent genre opens with an `# H1` heading and one or more paragraphs of prose
describing the genre's origins, instrumentation, and cultural context. The
ingester keeps these paragraphs together as the genre's overview chunk, which is
why `_clean_genre_slug` in `recommendation-service` treats a trailing
`#overview` as the *least* specific thing a query can match.

Instrumentation and mood language matters here more than trivia: this prose is
what a mood query like "warm and acoustic for a rainy afternoon" is embedded
against, so descriptive vocabulary is doing the retrieval work.

## Sub-Genres

### EXAMPLE SUB-GENRE ONE
1968
EXAMPLE GENRE
A sub-genre opens with an `### H3` heading, then a line holding its year of
origin, then a line naming its parent genre, then prose. `parse_genre_file`
reads those two lines positionally, so their order is part of the format rather
than decoration. The year feeds the `year_from` / `year_to` constraints that
`build_retrieval_query` can set and `rewrite_query` can relax.

### EXAMPLE SUB-GENRE TWO
1974
EXAMPLE GENRE
A second sub-genre, present so the sample exercises the multi-sub-genre path.
Each sub-genre becomes its own chunk with a slug of the form
`genre:example_genre#example_sub_genre_two`, which is the identifier that
surfaces in `matched_genres` and in the genre-graph edges built by
`build_genre_graph.py`.
