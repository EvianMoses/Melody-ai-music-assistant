# `data/` — not distributed with this repository

**The datasets themselves are deliberately not in Git.** This directory keeps its
structure and a format sample so the ingestion scripts are readable and testable,
but the corpora are supplied locally.

Two reasons, and the first is the one that decided it:

1. **The tailored genre corpus is a project asset.** `data/genres_knowledge/`
   holds the curated genre and sub-genre mappings the whole retrieval layer is
   built on — the part of this project that is not reproducible from a library.
   It is not published.
2. **The review datasets are third-party text.** Redistributing them from a
   public repository is a different act from reading them locally, and it is
   avoidable, so it is avoided.

Removing them also took the repository from ~76 MB to ~27 MB, which is a real
convenience for cloning.

## What belongs here

| Path | What it is | Used by |
| ---- | ---------- | ------- |
| `genres_knowledge/` | 23 Markdown files, one per parent genre, each with a `## Sub-Genres` section. **The primary RAG corpus.** | `rag-service/scripts/ingest_local_data.py` → `knowledge_documents` / `knowledge_chunks` (domain `genre`) |
| `cleaned_large_dataset_t.csv` | Album ratings and short review descriptions (Metacritic-derived), ~39 MB | same script, domain `reviews` |
| `18,393 Pitchfork Reviews/` | Pitchfork review database (SQLite). Present from v1; **not currently ingested.** | — |
| `Contemporary album ratings and reviews/`, `all_songs_rating_review/` | Additional rating/review CSVs. **Not currently ingested.** | — |
| `raw/`, `processed/` | Working directories for ingestion staging | ingestion scripts |
| `gtzan/` | GTZAN audio dataset (~1.2 GB), downloaded on demand — never in Git | `audio-service/ml/dataset.py` |

## Format samples

`samples/` contains **synthetic** files that illustrate the expected shape.
They carry no real corpus content: their only job is to let someone read the
ingestion code and know what it parses. Do not ingest them as knowledge — the
prose is filler.

## Restoring the data on a new machine

1. Place `genres_knowledge/` and the review datasets under `data/` as laid out
   above (the genre corpus is kept outside this repository — ask the author).
2. Run the ingestion, from the repository root with the stack up:

   ```bash
   python rag-service/scripts/ingest_local_data.py
   python rag-service/scripts/generate_embeddings.py
   python rag-service/scripts/build_genre_graph.py
   ```

3. Confirm with `WF-007 — Knowledge Ingestion` in n8n, or directly:

   ```bash
   curl -X POST localhost:8002/rag/retrieve \
     -H 'Content-Type: application/json' \
     -d '{"query":"warm indie folk with acoustic instrumentation","filters":{"domain":"genre"}}'
   ```

   A healthy corpus is **24 documents / 325 chunks**, all embedded.

## Provenance and licence status (`RAG-002`)

⚠️ **Still open, and not resolved by removing the data from Git.** Taking the
corpora out of the repository settles the *redistribution* question; it does not
record where they came from, which the submission still needs (`DOC-010`).
`docs/knowledge_inventory.md` is where that goes, and only the author can fill
it in. `WF-007` reports the gap on every run rather than letting it be forgotten.
