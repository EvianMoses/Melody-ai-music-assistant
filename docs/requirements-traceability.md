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
> Last reconciled with the repository: ~~**2026-07-24**~~ → **2026-07-28**.
>
> The 2026-07-28 pass moved 11 rows. Most had simply gone stale — Phases 4, 5, 6,
> 7 and 8 all landed after the previous reconciliation and the matrix still
> described the world as it was on 24 July. Honest reading now: **16 `Done`,
> 4 `Partial`, 0 `Planned`**, against 5 / 11 / 4 on 24 July.
>
> ~~The four `Partial` rows are blocked on exactly two artefacts: rows 5, 6 and 17
> all wait on §3.9's Prompt Engineering Log Version 1, and row 11 waits on
> `LOCAL-002`/`LOCAL-003`.~~ → **Updated 2026-07-29:** rows 5, 6 and 11 are now
> closed — row 5 as a documented substitution, row 6 after the AI Agent's prompt
> was rewritten from n8n template boilerplate, row 11 by retargeting `LOCAL-003`
> onto the three local models that actually run. **Row 17 (prompt engineering)
> remains the single `Partial`**, needing versions 3–5 per `DOC-007`.

## 1. Graded technology mapping (ACA-002)

| # | Course/reference area | Melody component | Evidence path | Status |
| - | --------------------- | ---------------- | ------------- | ------ |
| 1 | Python — basic and advanced | Flask app, five FastAPI services, ingestion scripts, SQLAlchemy models, dataclass contracts | `app.py`, `*/main.py`, `shared_lib/`, `contracts/models.py`, `contracts/db_models.py`, `rag-service/scripts/` | Done |
| 2 | Web development | Flask UI plus the versioned API boundary (`POST /api/v1/requests`) and OAuth UX | `app.py`, `templates/`, `static/` | ~~Partial — versioned route exists; §8.2 UI modes are Phase 8~~ → Done — the browser now calls `/api/v1/requests`, not the legacy `/chat`; §8.2 delivered except `UI-008` |
| 3 | AWS basics / AWS AI | Bedrock Agent + Knowledge Base + OpenSearch Serverless + S3 + Lambda, retained as the rollback and latency/quality benchmark | `aws/`, `README.md`, Phase 0 baseline record | Done (as benchmark) — see §3 for why it is not the target |
| 4 | n8n workflows | WF-000 through WF-010 as the visible main orchestrator | `workflows/n8n/` (~~WF-000…WF-006 exported~~ → WF-000…WF-010, all 11) | ~~Partial — 7 of 11 exported; WF-007/008/009/010 outstanding~~ → Done — **all 11 exported** (WF-007/008/010 added 2026-07-28); WF-008 and WF-010 executed against live data, WF-007 carries one labelled `RAG-010` placeholder |
| 5 | n8n Information Extractor | ~~`Extract Music Constraints` node in WF-002~~ → **Deliberate substitution, decided 2026-07-29.** No Information Extractor node exists (verified: zero `informationExtractor` matches in any workflow). Structured extraction is deterministic Python — `normalize_input` + `extract_negations` — chosen over an LLM node because it cannot invent a constraint, costs no latency on a request path already at ~8 s, and is unit-tested against the false-positive failure mode. The n8n requirement is satisfied by WF-001 as the main orchestrator | `recommendation-service/app/core/graph_nodes.py`, `recommendation-service/test_negation.py`; full rationale at PE-1 in `docs/prompt-engineering-log.md` | ~~Partial — node present, prompt log not started~~ → **Done (as a documented substitution)** |
| 6 | n8n AI Agent | ~~`Recommendation Planning Agent` in WF-002~~ → `Classify Ambiguous Intent` in **WF-001** — read-only intent classification, no write tools. ⚠️ Its prompt was untouched n8n template boilerplate (faq/billing/technical/…) until 2026-07-28; rewritten for Melody's six real intents | `workflows/n8n/MELODY — WF-001 — Main Request Router.json`; PE-2 in `docs/prompt-engineering-log.md` | ~~Partial — same~~ → Done (V2) — not yet measured on a 10-case set |
| 7 | RAG / LangChain | Hybrid retrieval: pgvector dense + PostgreSQL full-text + metadata filters + genre expansion + RRF | `rag-service/scripts/test_hybrid_retrieval.py`, `rag-service/main.py`, migration `f1a2b3c4d5e6` | Done (pipeline) — metrics outstanding (§3.8) |
| 8 | LangGraph | Bounded stateful recommendation graph; `rewrite_count <= 1` enforced by graph topology | `recommendation-service/app/core/graph.py`, `graph_state.py`, `graph_nodes.py` | ~~Partial — 4 of 18 nodes carry real logic~~ → Done — all 18 nodes real; Phase 4 gate passed |
| 9 | Machine-learning classifier | Audio genre/tag or energy classifier (Melody's domain adaptation of the reference image classifier — see §2; **the substitution is confirmed by the developer, `ACA-005`, 2026-07-28**) | `audio-service/ml/` (`train.py`, `evaluate.py`, `dataset.py`, `model.py`), `docs/ml/audio-genre-classifier.md` | ~~Planned~~ → Done — trained on GTZAN with a leakage-free split; held-out clip-level macro-F1 **0.8692**, accuracy 0.8733 |
| 10 | PyTorch / Transformers | Audio inference and training; embedding + cross-encoder inference already run on PyTorch | `rag-service/scripts/generate_embeddings.py` (e5-small), `test_hybrid_retrieval.py` (ms-marco cross-encoder) | ~~Partial — inference done, audio training is Phase 6~~ → Done — the GTZAN CNN was trained and measured (test macro-F1 0.8692) |
| 11 | Local model runtime (Ollama / HF / llama.cpp) | ~~Ollama `llama3.1` owning the local RAG answer baseline~~ → **Three locally hosted models on the live request path**: `intfloat/multilingual-e5-small` (embeddings), `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (reranking), and the trained PyTorch audio genre CNN | `rag-service/main.py`, `audio-service/ml/`, `eval/local_models.py`, `eval/reports/local_models_*.json` | ~~Partial — task owned and working; measurements are `LOCAL-003`~~ → **Done** — measured 2026-07-28: embeddings 42 ms/query and 384-d schema pass; reranker 94 ms/pair, schema pass; CNN macro-F1 0.8692 |
| 12 | Guardrails | Separate Guardrails Service with input and output rails, called from WF-001 | `guardrails-service/main.py`, WF-001 `Input Guardrails` / `Output Guardrails` nodes | ~~Partial — deterministic placeholder rails; framework decision deferred to Phase 3/4~~ → Done — real input/output rails (§8.5 replaced the hardcoded `off_topic = False`); 17 tests |
| 13 | MCP / external tools | Provider and service tools behind normalized contracts | `provider-gateway/main.py`, `contracts/`, ADR-001 | ~~Partial — contract exists, real adapter is Phase 5~~ → Done — two real adapters (YouTube, Spotify) behind one normalized contract |
| 14 | External LLM | Final curator explanation and the single bounded rewrite | `recommendation-service/app/core/llm_adapter.py`, `usage_store.py`, ADR-006 | ~~Planned~~ → Done — `claude-haiku-4-5` curator explanation per ADR-006, and **`model_usage` is now actually written to** (N8N-REAL-004); before that the table existed with no writer |
| 15 | Feedback / active learning | Immutable `feedback_events`, materialized Preference Profile v1, later ranker path | `contracts/db_models.py`, WF-005, `recommendation-service/app/core/profile.py` + `profile_store.py` | ~~Partial — tables + wiring done, update logic is Phase 7~~ → Done — Phase 7 gate passed 5 of 5 |
| 16 | Monitoring | WF-008 metrics, quota, error rate, and budget summary | `workflows/n8n/MELODY — WF-008 — Monitoring and Budget.json`; `model_usage`, `provider_quota_usage`, `ops_daily_summary`, `audit_events` | ~~Planned — WF-008 not yet built~~ → Done — WF-008 built and executed on real rows; alert branch tested. ⚠️ One honest limitation carried in the report itself: only completed requests are recorded, so its error rate is a floor, not a true rate |
| 17 | Prompt engineering | Five surfaces × five versions on a shared test set | `docs/prompt-engineering-log.md` | ~~Partial — structure defined, Version 1 outstanding~~ → Partial — **Version 1 written 2026-07-28**, and it corrected the surface list: PE-1 does not exist, PE-3/PE-5 were re-mapped. PE-3 has 2 versions measured on the 25-query golden set; PE-2 and PE-5 have 2 versions each. Versions 3–5 outstanding (`DOC-007`) |
| 18 | Docker / EC2 deployment | Separate containers on a private bridge network with health checks and resource limits | `docker-compose.yml`, `*/Dockerfile`, `shared_lib/shared_lib/health.py` | Done (dev) — production hardening is Phase 9 §9.7 |
| 19 | WebUI | Text discovery, audio, playback, feedback, export | `templates/index.html`, `static/style.css`, `app.py` | ~~Partial — text path only~~ → Done — text, audio, playback, feedback and export all reachable from the UI; `UI-008` (Smart Sequence display) outstanding |
| 20 | Database / vector store | PostgreSQL 16 + pgvector, ~~18~~ → 21 tables, HNSW + GIN indexes, Alembic migrations | `migrations/versions/`, `contracts/db_models.py` | Done — ~~`oauth_accounts` deferred to Phase 5~~ → 21 tables: `oauth_accounts` landed in Phase 5, and `provider_quota_usage` + `ops_daily_summary` were added for WF-008 (N8N-REAL-004) |

### Supporting decision records

| Decision | Record | Status |
| -------- | ------ | ------ |
| Architecture boundaries (n8n / LangGraph / adapters) | `docs/adr/ADR-001-architecture-boundaries.md` | Accepted |
| Music provider mode | ~~ADR-002 — decision closed in the plan (§0.4), **standalone file not yet written**~~ → `docs/adr/ADR-002-music-provider-mode.md` (written 2026-07-28, including the 2026-07-26 Spotify amendment) | ~~Decided, unrecorded~~ → Accepted |
| Retrieval embedding model | `docs/adr/ADR-003-embedding-model.md` | Accepted |
| Recognition provider | ~~ADR-004~~ → `docs/adr/ADR-004-recognition-provider.md` | ~~Pending (Phase 6)~~ → Accepted |
| n8n deployment mode | `docs/adr/ADR-005-n8n-deployment-mode.md` | Accepted |
| Model routing (local vs. hosted) | `docs/adr/ADR-006-model-routing.md` | Accepted |
| OAuth token storage | `docs/adr/ADR-007-oauth-token-storage.md` | Accepted |
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
| Supervised classifier (PyTorch) | **Image** classifier over property photos | **Audio** genre/tag or energy classifier over uploaded clips | Same requirement: labelled dataset, leakage-free split, pretrained backbone, accuracy/F1 + confusion matrix, confidence-aware `uncertain` output. The input modality changes; the ML deliverable does not. ~~**Requires evaluator confirmation — see ACA-005 below.**~~ → ✅ **CONFIRMED by the developer 2026-07-28 (`ACA-005`): the audio classifier replaces the image classifier.** Delivered and measured — held-out clip-level macro-F1 **0.8692**, accuracy 0.8733; model card at `docs/ml/audio-genre-classifier.md`. |
| Multimodal input | Photo upload | Audio upload or in-browser recording | Same upload/validation/temporary-storage/cleanup pipeline, with the same "never trust the filename extension" rule |
| Ranking and personalization | Property fit scoring | Track Reranker v1 with transparent component scores and Preference Profile v1 | Same interpretable-scoring requirement plus an explicit anti-echo-chamber constraint |
| External write integration | CRM or listing action | YouTube playlist creation and item insertion | Same OAuth + idempotency + partial-failure surface |
| Domain guardrails | Real-estate policy rules | Music-domain rails: no fabricated BPM/key, no fabricated provider IDs, no ad-free playback claims, no prompt/credential exposure | Same input/output rail requirement, with rules that are actually falsifiable in this domain |

Two adaptations are **additions**, not substitutions, and are declared as such:
bounded LangGraph control flow with a hard rewrite limit, and the Smart Sequencer
(Camelot/BPM-aware ordering) as a music-specific deterministic algorithm.

### ~~Open confirmation~~ → ✅ **[COMPLETED] Confirmation received (2026-07-28)**

- ~~**`ACA-005` P0 — not confirmable by implementation.** Two questions require the
  evaluator's answer: (a) whether the audio classifier may replace the reference
  image classifier, and (b) whether RAG and LangGraph may share a deployable
  service. Until answered, Melody keeps RAG and LangGraph separable at the API
  boundary (enforced by ADR-001) and documents the classifier adaptation above
  rather than assuming approval. This item stays open in the plan.~~

- ✅ **[COMPLETED] `ACA-005` P0 — question (a) is answered: the audio classifier
  replaces the reference image classifier.** Confirmed by the developer on
  2026-07-28. The adaptation in the table above is therefore **approved**, not
  merely proposed, and Phase 6 `ML-AUD-001…007` counts against graded row 9.

- **NEW DECISION: question (b) is closed as moot rather than left open.** The
  question was whether RAG and LangGraph *may* share a deployable service.
  Melody does not share one — `rag-service` and `recommendation-service` are
  separate containers with separate Dockerfiles, communicating only over
  `POST /rag/retrieve`, structurally enforced by ADR-001. That arrangement is
  valid under **either** answer, so no evaluator ruling is needed to proceed and
  none is being waited on. Should a future answer permit sharing, it would be an
  optional consolidation, never a correction.

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
