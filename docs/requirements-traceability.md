# Requirements traceability matrix

> Phase 0 §0.5 deliverables `ACA-001` (create this file), `ACA-002` (map each
> graded technology to specific Melody components), and `ACA-004` (document the
> approved adaptation from the reference real-estate scenario to the music
> domain).
>
> **Status column is honest, not aspirational.** `Done` means the evidence path
> exists and the behaviour was demonstrated. `Partial` means real code exists but
> the requirement is not fully satisfied. `Planned` means the phase has not
> started. Section 19 of the execution plan governs: a checkbox alone is not
> evidence.
>
> Last reconciled with the repository: **2026-07-24**.

## 1. Graded technology mapping (ACA-002)

| # | Course/reference area | Melody component | Evidence path | Status |
| - | --------------------- | ---------------- | ------------- | ------ |
| 1 | Python — basic and advanced | Flask app, five FastAPI services, ingestion scripts, SQLAlchemy models, dataclass contracts | `app.py`, `*/main.py`, `shared_lib/`, `contracts/models.py`, `contracts/db_models.py`, `rag-service/scripts/` | Done |
| 2 | Web development | Flask UI plus the versioned API boundary (`POST /api/v1/requests`) and OAuth UX | `app.py`, `templates/`, `static/` | Partial — versioned route exists; §8.2 UI modes are Phase 8 |
| 3 | AWS basics / AWS AI | Bedrock Agent + Knowledge Base + OpenSearch Serverless + S3 + Lambda, retained as the rollback and latency/quality benchmark | `aws/`, `README.md`, Phase 0 baseline record | Done (as benchmark) — see §3 for why it is not the target |
| 4 | n8n workflows | WF-000 through WF-010 as the visible main orchestrator | `workflows/n8n/` (WF-000…WF-006 exported) | Partial — 7 of 11 exported; WF-007/008/009/010 outstanding |
| 5 | n8n Information Extractor | `Extract Music Constraints` node in WF-002 — structured mood/genre/era/energy extraction with no invented values | `workflows/n8n/WF-002 — Text Recommendation.json`, prompt surface PE-1 | Partial — node present, prompt log not started |
| 6 | n8n AI Agent | `Recommendation Planning Agent` in WF-002 — read-only planning surface with no external write tools | `workflows/n8n/WF-002 — Text Recommendation.json`, prompt surface PE-2 | Partial — same |
| 7 | RAG / LangChain | Hybrid retrieval: pgvector dense + PostgreSQL full-text + metadata filters + genre expansion + RRF | `rag-service/scripts/test_hybrid_retrieval.py`, `rag-service/main.py`, migration `f1a2b3c4d5e6` | Done (pipeline) — metrics outstanding (§3.8) |
| 8 | LangGraph | Bounded stateful recommendation graph; `rewrite_count <= 1` enforced by graph topology | `recommendation-service/app/core/graph.py`, `graph_state.py`, `graph_nodes.py` | Partial — 4 of 18 nodes carry real logic |
| 9 | Machine-learning classifier | Audio genre/tag or energy classifier (Melody's domain adaptation of the reference image classifier — see §2) | Phase 6 `ML-AUD-001`…`ML-AUD-007` | Planned |
| 10 | PyTorch / Transformers | Audio inference and training; embedding + cross-encoder inference already run on PyTorch | `rag-service/scripts/generate_embeddings.py` (e5-small), `test_hybrid_retrieval.py` (ms-marco cross-encoder) | Partial — inference done, audio training is Phase 6 |
| 11 | Local model runtime (Ollama / HF / llama.cpp) | Ollama `llama3.1` owning the local RAG answer baseline | `rag-service/scripts/test_generation.py`, `docker-compose.yml` (`ollama` service), ADR pending for LOCAL-002/003 | Partial — task owned and working; measurements are `LOCAL-003` |
| 12 | Guardrails | Separate Guardrails Service with input and output rails, called from WF-001 | `guardrails-service/main.py`, WF-001 `Input Guardrails` / `Output Guardrails` nodes | Partial — deterministic placeholder rails; framework decision deferred to Phase 3/4 |
| 13 | MCP / external tools | Provider and service tools behind normalized contracts | `provider-gateway/main.py`, `contracts/`, ADR-001 | Partial — contract exists, real adapter is Phase 5 |
| 14 | External LLM | Final curator explanation and the single bounded rewrite | Phase 4 §4.8, `model_usage` table | Planned |
| 15 | Feedback / active learning | Immutable `feedback_events`, materialized Preference Profile v1, later ranker path | `contracts/db_models.py`, WF-005, `recommendation-service` `/profiles/update` | Partial — tables + wiring done, update logic is Phase 7 |
| 16 | Monitoring | WF-008 metrics, quota, error rate, and budget summary | Phase 1 §1.11, `model_usage` / `audit_events` tables | Planned — WF-008 not yet built |
| 17 | Prompt engineering | Five surfaces × five versions on a shared test set | `docs/prompt-engineering-log.md` | Partial — structure defined, Version 1 outstanding |
| 18 | Docker / EC2 deployment | Separate containers on a private bridge network with health checks and resource limits | `docker-compose.yml`, `*/Dockerfile`, `shared_lib/shared_lib/health.py` | Done (dev) — production hardening is Phase 9 §9.7 |
| 19 | WebUI | Text discovery, audio, playback, feedback, export | `templates/`, `static/`, Phase 8 §8.2 | Partial — text path only |
| 20 | Database / vector store | PostgreSQL 16 + pgvector, 18 tables, HNSW + GIN indexes, Alembic migrations | `migrations/versions/`, `contracts/db_models.py` | Done — `oauth_accounts` deferred to Phase 5 |

### Supporting decision records

| Decision | Record | Status |
| -------- | ------ | ------ |
| Architecture boundaries (n8n / LangGraph / adapters) | `docs/adr/ADR-001-architecture-boundaries.md` | Accepted |
| Music provider mode | ADR-002 — decision closed in the plan (§0.4), **standalone file not yet written** | Decided, unrecorded |
| Retrieval embedding model | `docs/adr/ADR-003-embedding-model.md` | Accepted |
| Recognition provider | ADR-004 | Pending (Phase 6) |
| Service timeouts / retries / idempotency | `docs/service-call-policies.md` | Defined (`ARC-002`, `ARC-003`) |
| Feature flags | `docs/feature-flags.md` | Defined (`ARC-004`) |
| Knowledge domains and sources | `docs/knowledge_inventory.md` | In progress |

## 2. Domain adaptation from the reference scenario (ACA-004)

The course reference project is an AI property-triage system (real estate). Melody
implements the same graded capability set in the music-discovery domain. Each
adaptation below preserves the technical requirement and changes only the subject
matter.

| Reference capability | Reference form (real estate) | Melody form (music) | Why the adaptation is equivalent |
| -------------------- | ---------------------------- | ------------------- | -------------------------------- |
| Domain knowledge base for RAG | Property listings, neighbourhood and regulation documents | Genre knowledge (23 parent genres, subgenres) and album/track reviews | Same retrieval problem: bilingual descriptive prose, chunked semantically, filtered by structured metadata |
| Structured entity extraction | Budget, rooms, location, property type | Mood, genre, era, instrumentation, energy, novelty | Same Information Extractor requirement — structured constraints from free text, with missing-field honesty |
| Supervised classifier (PyTorch) | **Image** classifier over property photos | **Audio** genre/tag or energy classifier over uploaded clips | Same requirement: labelled dataset, leakage-free split, pretrained backbone, accuracy/F1 + confusion matrix, confidence-aware `uncertain` output. The input modality changes; the ML deliverable does not. **Requires evaluator confirmation — see ACA-005 below.** |
| Multimodal input | Photo upload | Audio upload or in-browser recording | Same upload/validation/temporary-storage/cleanup pipeline, with the same "never trust the filename extension" rule |
| Ranking and personalization | Property fit scoring | Track Reranker v1 with transparent component scores and Preference Profile v1 | Same interpretable-scoring requirement plus an explicit anti-echo-chamber constraint |
| External write integration | CRM or listing action | YouTube playlist creation and item insertion | Same OAuth + idempotency + partial-failure surface |
| Domain guardrails | Real-estate policy rules | Music-domain rails: no fabricated BPM/key, no fabricated provider IDs, no ad-free playback claims, no prompt/credential exposure | Same input/output rail requirement, with rules that are actually falsifiable in this domain |

Two adaptations are **additions**, not substitutions, and are declared as such:
bounded LangGraph control flow with a hard rewrite limit, and the Smart Sequencer
(Camelot/BPM-aware ordering) as a music-specific deterministic algorithm.

### Open confirmation

- **`ACA-005` P0 — not confirmable by implementation.** Two questions require the
  evaluator's answer: (a) whether the audio classifier may replace the reference
  image classifier, and (b) whether RAG and LangGraph may share a deployable
  service. Until answered, Melody keeps RAG and LangGraph separable at the API
  boundary (enforced by ADR-001) and documents the classifier adaptation above
  rather than assuming approval. This item stays open in the plan.

## 3. Why the AWS/Bedrock baseline appears as evidence but not as the target

Row 3 credits the existing AWS implementation because it is real, deployed, and
demonstrable. It is retained for three purposes only — rollback while development
is incomplete, a quality and latency benchmark for `REC-LEG-001`/`REC-LEG-002`,
and an optional emergency fallback behind `ENABLE_LEGACY_BEDROCK_FALLBACK`.

It does not define the new request schema, personalization logic, audio path,
provider layer, or workflow structure. Any request served by it records
`engine_used` so the two engines are never confused in evaluation results.

## 4. Maintenance rule

This matrix is re-reconciled at every phase gate. A row may only move to `Done`
when the evidence path exists in the repository and the corresponding gate
criterion has passed — not when the code is written.
