# RAG evaluation — negation_pooldefault

- Run (UTC): 2026-07-28T20:30:46.476217+00:00
- Golden set: melody-golden-retrieval-v1 (25 queries, 23 retrieval-scored)
- Settings: top_k=5, candidate_pool=None

## Retrieval

| Metric | Value |
| --- | --- |
| Recall@5 | 0.4891 |
| Recall@10 | 0.4891 |
| MRR | 0.5109 |
| nDCG@10 | 0.4753 |
| Latency median (both domains) | 5.13s |
| Latency max | 5.577s |

### By category

| Category | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| blended_genres | 4 | 0.3125 | 0.3958 |
| exact_artist | 2 | 1.0 | 1.0 |
| exact_genre | 5 | 0.9 | 1.0 |
| hebrew | 4 | 0.5 | 0.5 |
| mood | 5 | 0.3 | 0.2333 |
| negative_constraint | 3 | 0.0 | 0.0 |

### By language

| Language | n | Recall@5 | MRR |
| --- | --- | --- | --- |
| en | 19 | 0.4868 | 0.5132 |
| he | 4 | 0.5 | 0.5 |

## Per query

| id | category | lang | R@5 | MRR | latency |
| --- | --- | --- | --- | --- | --- |
| mood-01 | mood | en | 0.0 | 0.0 | 5.577s |
| mood-02 | mood | en | 0.75 | 0.5 | 5.208s |
| mood-03 | mood | en | 0.0 | 0.0 | 5.217s |
| mood-04 | mood | en | 0.5 | 0.3333 | 5.572s |
| mood-05 | mood | en | 0.25 | 0.3333 | 4.926s |
| blend-01 | blended_genres | en | 0.6667 | 1.0 | 4.963s |
| blend-02 | blended_genres | en | 0.0 | 0.0 | 5.427s |
| blend-03 | blended_genres | en | 0.25 | 0.25 | 5.089s |
| blend-04 | blended_genres | en | 0.3333 | 0.3333 | 5.117s |
| genre-01 | exact_genre | en | 1.0 | 1.0 | 4.791s |
| genre-02 | exact_genre | en | 1.0 | 1.0 | 5.393s |
| genre-03 | exact_genre | en | 1.0 | 1.0 | 4.888s |
| genre-04 | exact_genre | en | 1.0 | 1.0 | 4.908s |
| genre-05 | exact_genre | en | 0.5 | 1.0 | 5.29s |
| artist-01 | exact_artist | en | 1.0 | 1.0 | 5.206s |
| artist-02 | exact_artist | en | 1.0 | 1.0 | 4.789s |
| he-01 | hebrew | he | 1.0 | 1.0 | 5.13s |
| he-02 | hebrew | he | 0.0 | 0.0 | 5.406s |
| he-03 | hebrew | he | 1.0 | 1.0 | 5.099s |
| he-04 | hebrew | he | 0.0 | 0.0 | 5.065s |
| anti-01 | anti_echo_chamber | en | — | — | 5.212s |
| anti-02 | anti_echo_chamber | en | — | — | 5.391s |
| neg-01 | negative_constraint | en | 0.0 | 0.0 | 5.309s |
| neg-02 | negative_constraint | en | 0.0 | 0.0 | 5.111s |
| neg-03 | negative_constraint | en | 0.0 | 0.0 | 5.111s |
