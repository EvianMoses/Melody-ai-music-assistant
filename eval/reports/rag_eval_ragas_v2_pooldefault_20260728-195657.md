# RAG evaluation — ragas_v2_pooldefault

- Run (UTC): 2026-07-28T19:56:57.429667+00:00
- Golden set: melody-golden-retrieval-v1 (25 queries, 23 retrieval-scored)
- Settings: top_k=5, candidate_pool=None

## Retrieval

| Metric | Value |
| --- | --- |
| Recall@5 | 0.4891 |
| Recall@10 | 0.4891 |
| MRR | 0.5109 |
| nDCG@10 | 0.4753 |
| Latency median (both domains) | 4.61s |
| Latency max | 9.426s |

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
| faithfulness | 0.7863 |
| response_relevancy | 0.6119 |
| context_precision | 0.3873 |
| context_recall | 0.28 |

## Per query

| id | category | lang | R@5 | MRR | latency |
| --- | --- | --- | --- | --- | --- |
| mood-01 | mood | en | 0.0 | 0.0 | 4.706s |
| mood-02 | mood | en | 0.75 | 0.5 | 4.626s |
| mood-03 | mood | en | 0.0 | 0.0 | 4.66s |
| mood-04 | mood | en | 0.5 | 0.3333 | 4.505s |
| mood-05 | mood | en | 0.25 | 0.3333 | 4.502s |
| blend-01 | blended_genres | en | 0.6667 | 1.0 | 4.324s |
| blend-02 | blended_genres | en | 0.0 | 0.0 | 4.797s |
| blend-03 | blended_genres | en | 0.25 | 0.25 | 4.775s |
| blend-04 | blended_genres | en | 0.3333 | 0.3333 | 4.403s |
| genre-01 | exact_genre | en | 1.0 | 1.0 | 4.118s |
| genre-02 | exact_genre | en | 1.0 | 1.0 | 4.604s |
| genre-03 | exact_genre | en | 1.0 | 1.0 | 4.58s |
| genre-04 | exact_genre | en | 1.0 | 1.0 | 4.407s |
| genre-05 | exact_genre | en | 0.5 | 1.0 | 4.596s |
| artist-01 | exact_artist | en | 1.0 | 1.0 | 4.498s |
| artist-02 | exact_artist | en | 1.0 | 1.0 | 4.41s |
| he-01 | hebrew | he | 1.0 | 1.0 | 4.512s |
| he-02 | hebrew | he | 0.0 | 0.0 | 4.61s |
| he-03 | hebrew | he | 1.0 | 1.0 | 4.7s |
| he-04 | hebrew | he | 0.0 | 0.0 | 8.37s |
| anti-01 | anti_echo_chamber | en | — | — | 9.292s |
| anti-02 | anti_echo_chamber | en | — | — | 9.426s |
| neg-01 | negative_constraint | en | 0.0 | 0.0 | 9.382s |
| neg-02 | negative_constraint | en | 0.0 | 0.0 | 9.123s |
| neg-03 | negative_constraint | en | 0.0 | 0.0 | 8.979s |
