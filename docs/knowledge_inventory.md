# Melody — Knowledge Inventory (Phase 3, Sections 3.1 & 3.2)

> Status: **In progress** — scaffold created July 24, 2026. Datasets are **not yet downloaded**.
> This document is the working register for Phase 3 tasks **RAG-001 … RAG-005**. It defines the
> canonical knowledge domains (Section 3.1) and the per-dataset inventory / legal metadata
> (Section 3.2) so ingestion (Section 3.3) can begin as soon as source material lands in `data/raw/`.

Related plan sections: `MELODY_AI_ORDERED_EXECUTION_PLAN.md` → §3.1 Canonical knowledge domains, §3.2 Dataset inventory and legal/source metadata.

---

## 1. Canonical knowledge domains (Section 3.1)

The four domains are kept **logically separate** so retrieval can be measured and filtered per domain.
Domains 1–3 are ingestible source material; domain 4 is live structured state (not ordinary RAG prose).

### Domain 1 — Genre knowledge
- **Scope:** 23 parent genres and 278 subgenres.
- **Per-item fields:** descriptions, mood, texture, instrumentation, production style, era.
- **Relations:** parent, related, influenced-by, and influence relations.
- **Ingestion target:** vectorized into `knowledge_documents` / `knowledge_chunks` (domain = `genre`),
  and the graph structure populated into `genre_nodes` / `genre_edges` (RAG-009).
- **Raw location:** `data/raw/genre_knowledge/` (new drop zone) **plus existing curated corpus in
  `data/genres_knowledge/`** — 23 parent-genre markdown files are **already present** (matches the
  "23 parent genres" figure); subgenre coverage still to be verified against the 278 target.
- **Retrieval domain tag:** `genre`

### Domain 2 — Reviews and music context
- **Scope:** reviews and descriptive excerpts.
- **Vocabulary captured:** artist, album, track, scene, period, production, and aesthetic vocabulary.
- **Ingestion target:** chunked by coherent passages (RAG-007) into `knowledge_documents` / `knowledge_chunks`
  (domain = `reviews`).
- **Raw location:** `data/raw/reviews_context/`
- **Retrieval domain tag:** `reviews`

### Domain 3 — Structured track metadata
- **Scope:** canonical IDs, provider IDs, ISRC where available; versioned BPM, key, energy, source, and confidence.
- **Ingestion target:** relational tables `tracks`, `track_provider_ids`, `track_audio_features`
  (NOT the vector store — this is exact/metadata retrieval, not semantic prose).
- **Raw location:** `data/raw/track_metadata/`
- **Retrieval domain tag:** `track_metadata`

### Domain 4 — User preference state
- **Scope:** materialized, versioned preference profile per user.
- **Storage:** structured state in `user_preferences` — **not** ordinary RAG prose.
- **Use:** injected into query construction and Track Reranking (not embedded/retrieved as documents).
- **Raw location:** _none_ (runtime-generated state; no scraped source).
- **Retrieval domain tag:** `n/a (structured state)`

---

## 2. Directory layout

```
data/
  genres_knowledge/        # EXISTING curated Domain 1 corpus (23 parent-genre .md files)
  raw/                     # immutable source drops, one subfolder per ingestible domain
    genre_knowledge/       # Domain 1 new/scraped source files (markdown, json, csv)
    reviews_context/       # Domain 2 review corpora / excerpts
    track_metadata/        # Domain 3 track + provider + audio-feature exports
  processed/               # cleaned, chunked, deduplicated, embedding-ready artifacts (RAG-003..008)
```

Rules:
- `data/raw/` is treated as append-only source-of-truth; cleaning writes to `data/processed/` (RAG-003).
- Large/binary corpora should be git-ignored; keep only manifests and small samples in the repo.
- Every processed artifact must trace back to a stable source-document ID and ingestion version (RAG-004, RAG-005).

---

## 3. Dataset inventory (Section 3.2 — RAG-001, RAG-002)

Fill one row per dataset / scraper output / genre document / review collection / current AWS source.
Columns follow RAG-002 (source, license/usage status, retrieval domain, allowed runtime use).

| Dataset ID | Description | Domain | Source / Origin | License / Usage status | Allowed runtime use | Source-doc ID scheme (RAG-004) | Ingestion version | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `genre-md-v0` | 23 parent-genre markdown files (present); 278 subgenres pending | genre | `data/genres_knowledge/*.md` (in-repo, curated) | owned (project-authored) — confirm | retrieval+grounding | `genre:{slug}` | `v0` | Available (raw) — needs cleaning/chunking |
| _(tbd)_ | Music reviews / descriptive excerpts | reviews | _tbd_ | _tbd_ | _tbd_ | `review:{source}:{id}` | `v0` | Not started |
| _(tbd)_ | Track + provider + ISRC metadata | track_metadata | _tbd (Spotify/YouTube exports)_ | _tbd_ | _tbd_ | `track:{isrc\|uuid}` | `v0` | Not started |
| _(tbd)_ | Current AWS Bedrock knowledge source | reviews/genre | existing AWS RAG source | _tbd (migration audit)_ | _tbd_ | _tbd_ | `v0` | Needs audit |

> Legend — **License / Usage status:** owned / open-license / permissioned / restricted / unknown.
> **Allowed runtime use:** retrieval+grounding / retrieval-only / training-excluded / internal-only.

---

## 4. Phase 3.2 task checklist (mirror of plan RAG-001 … RAG-005)

- [ ] **RAG-001** Inventory every dataset, scraper output, genre document, review collection, and current AWS source (fill §3 table).
- [ ] **RAG-002** Record source, license/usage status, retrieval domain, and allowed runtime use for each row.
- [ ] **RAG-003** Remove empty text, exact duplicates, near duplicates, and malformed metadata (writes to `data/processed/`).
- [ ] **RAG-004** Define stable source-document IDs and ingestion versions (see ID schemes above).
- [ ] **RAG-005** Preserve the original source reference for evaluation and internal grounding.

_When these are complete, proceed to Section 3.3 (Chunking and ingestion) and Section 3.4 (Embedding-model decision)._
