# ADR-003: Retrieval embedding model

- **Status:** Accepted
- **Date:** 2026-07-24
- **Phase / tasks:** Phase 3 — §3.4 Embedding-model decision (`RAG-EMB-003`)
- **Supersedes:** the provisional 768-d Gemini-style default in `contracts/db_models.py`

## Context

The RAG pipeline stores text chunks in `knowledge_chunks` and needs dense
vectors for semantic retrieval over two local knowledge domains (genre
descriptions and album reviews). Melody must serve **both Hebrew and English**
users, and the initial deployment target is **local/CPU inference** (no managed
embedding API, no GPU guaranteed). The plan (§3.4) calls for a bilingual model
with a modest CPU/RAM footprint that can run under local HuggingFace inference.

## Decision

Use **`intfloat/multilingual-e5-small`** as the retrieval embedding model.

- **Dimension:** 384 (down from the placeholder 768). `knowledge_chunks.embedding`
  is resized to `vector(384)` via migration `f1a2b3c4d5e6_resize_embedding_to_384`,
  and `EMBEDDING_DIM` in `contracts/db_models.py` is set to `384`.
- **Instruction prefixes (required by E5):** documents are embedded as
  `"passage: <text>"` and search queries as `"query: <text>"`.
- **Normalization:** embeddings are L2-normalized so cosine similarity equals the
  dot product, matching the HNSW `vector_cosine_ops` index already defined on the
  column.
- **Runtime:** `sentence-transformers` + `torch` (CPU), executed locally / inside
  the `rag-service` container (Python 3.12).

## Rationale

1. **Bilingual (Hebrew + English) support.** The `multilingual-e5` family is
   trained across ~100 languages including Hebrew, giving usable cross-lingual and
   Hebrew-native retrieval out of the box — a hard requirement for Melody.
2. **Low CPU/RAM footprint.** The `-small` variant (~118 MB, 384-d) embeds
   quickly on CPU and keeps memory modest, so ingestion backfill and online query
   embedding run without a GPU.
3. **Local HuggingFace inference.** Loads directly via `sentence-transformers`
   with no external API dependency, keeping data local and inference cost-free.
4. **Retrieval quality per size.** E5-small is a strong performer on MTEB
   retrieval benchmarks for its size, an efficient default before any heavier
   upgrade.

## Alternatives considered

- **`intfloat/multilingual-e5-base` / `-large`** — higher quality but larger and
  slower on CPU; kept as a future upgrade path if retrieval quality proves
  insufficient.
- **`BAAI/bge-m3`** — strong multilingual retriever with hybrid dense/sparse
  output, but heavier (1024-d, larger model) than needed for the first pass.
- **Managed embedding APIs (e.g. Gemini/OpenAI, 768/1536-d)** — rejected for the
  local-first deployment: adds cost, latency, and a data-egress dependency.

## Consequences

- The formal two-model benchmark (`RAG-EMB-001`, `RAG-EMB-002`) is superseded by
  this pragmatic first choice; a benchmark can still be run later to justify an
  upgrade, and swapping models means re-embedding all chunks and resizing the
  column again.
- Any change of model dimension requires a new migration on
  `knowledge_chunks.embedding` plus a full re-embed.
- The embedding backfill pipeline lives in
  `rag-service/scripts/generate_embeddings.py`.
