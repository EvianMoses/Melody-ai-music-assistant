# RAG evaluation — ragas_final_pooldefault

- Run (UTC): 2026-07-28T19:10:56.115017+00:00
- Golden set: melody-golden-retrieval-v1 (25 queries, 23 retrieval-scored)
- Settings: top_k=5, candidate_pool=None

## Retrieval

| Metric | Value |
| --- | --- |
| Recall@5 | 0.4891 |
| Recall@10 | 0.4891 |
| MRR | 0.5109 |
| nDCG@10 | 0.4753 |
| Latency median (both domains) | 4.6s |
| Latency max | 4.98s |

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

## Ragas

| Metric | Value |
| --- | --- |
| faithfulness | 0.6185 |
| response_relevancy | 0.6104 |
| context_precision | 0.466 |
| context_recall | 0.24 |

## Per query

| id | category | lang | R@5 | MRR | latency |
| --- | --- | --- | --- | --- | --- |
| mood-01 | mood | en | 0.0 | 0.0 | 4.81s |
| mood-02 | mood | en | 0.75 | 0.5 | 4.887s |
| mood-03 | mood | en | 0.0 | 0.0 | 4.671s |
| mood-04 | mood | en | 0.5 | 0.3333 | 4.639s |
| mood-05 | mood | en | 0.25 | 0.3333 | 4.599s |
| blend-01 | blended_genres | en | 0.6667 | 1.0 | 4.375s |
| blend-02 | blended_genres | en | 0.0 | 0.0 | 4.627s |
| blend-03 | blended_genres | en | 0.25 | 0.25 | 4.795s |
| blend-04 | blended_genres | en | 0.3333 | 0.3333 | 4.564s |
| genre-01 | exact_genre | en | 1.0 | 1.0 | 4.319s |
| genre-02 | exact_genre | en | 1.0 | 1.0 | 4.582s |
| genre-03 | exact_genre | en | 1.0 | 1.0 | 4.6s |
| genre-04 | exact_genre | en | 1.0 | 1.0 | 4.499s |
| genre-05 | exact_genre | en | 0.5 | 1.0 | 4.532s |
| artist-01 | exact_artist | en | 1.0 | 1.0 | 4.675s |
| artist-02 | exact_artist | en | 1.0 | 1.0 | 4.6s |
| he-01 | hebrew | he | 1.0 | 1.0 | 4.525s |
| he-02 | hebrew | he | 0.0 | 0.0 | 4.98s |
| he-03 | hebrew | he | 1.0 | 1.0 | 4.592s |
| he-04 | hebrew | he | 0.0 | 0.0 | 4.601s |
| anti-01 | anti_echo_chamber | en | — | — | 4.694s |
| anti-02 | anti_echo_chamber | en | — | — | 4.898s |
| neg-01 | negative_constraint | en | 0.0 | 0.0 | 4.602s |
| neg-02 | negative_constraint | en | 0.0 | 0.0 | 4.535s |
| neg-03 | negative_constraint | en | 0.0 | 0.0 | 4.564s |
