# RAG evaluation — neg_ragas_pooldefault

- Run (UTC): 2026-07-28T21:23:09.737682+00:00
- Golden set: melody-golden-retrieval-v1 (25 queries, 23 retrieval-scored)
- Settings: top_k=5, candidate_pool=None

## Retrieval

| Metric | Value |
| --- | --- |
| Recall@5 | 0.4891 |
| Recall@10 | 0.4891 |
| MRR | 0.5109 |
| nDCG@10 | 0.4753 |
| Latency median (both domains) | 4.503s |
| Latency max | 4.877s |

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
| faithfulness | 0.8513 |
| response_relevancy | 0.7397 |
| context_precision | 0.4127 |
| context_recall | 0.24 |

## Per query

| id | category | lang | R@5 | MRR | latency |
| --- | --- | --- | --- | --- | --- |
| mood-01 | mood | en | 0.0 | 0.0 | 4.59s |
| mood-02 | mood | en | 0.75 | 0.5 | 4.321s |
| mood-03 | mood | en | 0.0 | 0.0 | 4.293s |
| mood-04 | mood | en | 0.5 | 0.3333 | 4.795s |
| mood-05 | mood | en | 0.25 | 0.3333 | 4.377s |
| blend-01 | blended_genres | en | 0.6667 | 1.0 | 4.122s |
| blend-02 | blended_genres | en | 0.0 | 0.0 | 4.81s |
| blend-03 | blended_genres | en | 0.25 | 0.25 | 4.877s |
| blend-04 | blended_genres | en | 0.3333 | 0.3333 | 4.322s |
| genre-01 | exact_genre | en | 1.0 | 1.0 | 4.167s |
| genre-02 | exact_genre | en | 1.0 | 1.0 | 4.537s |
| genre-03 | exact_genre | en | 1.0 | 1.0 | 4.557s |
| genre-04 | exact_genre | en | 1.0 | 1.0 | 4.209s |
| genre-05 | exact_genre | en | 0.5 | 1.0 | 4.532s |
| artist-01 | exact_artist | en | 1.0 | 1.0 | 4.385s |
| artist-02 | exact_artist | en | 1.0 | 1.0 | 4.375s |
| he-01 | hebrew | he | 1.0 | 1.0 | 4.506s |
| he-02 | hebrew | he | 0.0 | 0.0 | 4.709s |
| he-03 | hebrew | he | 1.0 | 1.0 | 4.412s |
| he-04 | hebrew | he | 0.0 | 0.0 | 4.573s |
| anti-01 | anti_echo_chamber | en | — | — | 4.399s |
| anti-02 | anti_echo_chamber | en | — | — | 4.629s |
| neg-01 | negative_constraint | en | 0.0 | 0.0 | 4.503s |
| neg-02 | negative_constraint | en | 0.0 | 0.0 | 4.608s |
| neg-03 | negative_constraint | en | 0.0 | 0.0 | 4.377s |
