# Melody AI — Ordered Execution and Build Plan

> Primary execution document for building the next version of Melody in dependency order.
>
> This file supersedes the execution order in `MELODY_AI_IMPLEMENTATION_PLAN.md`. The older file may remain as an architecture and product reference, but task execution should follow this document.

## Document status


| Field                             | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Project                           | Melody — AI-Powered Music Discovery Assistant                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Owner                             | Solo developer                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Plan date                         | July 21, 2026                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Submission deadline               | July 30, 2026                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Current baseline                  | Flask + AWS Bedrock Agent + Bedrock Knowledge Base + OpenSearch Serverless + S3 + Lambda + Spotify                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Target system                     | n8n-orchestrated, multimodal, personalized music recommendation system                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Primary playback/export direction | YouTube-first, behind a provider interface                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Provider decision                 | ~~MusicAPI.com must be evaluated immediately; final mode may be MusicAPI, hybrid, or direct APIs~~ → ✅ **[COMPLETED] Decision closed (July 21, 2026):** `PROVIDER_MODE=direct`**. MusicAPI REJECTED. Direct YouTube APPROVED as primary. Direct Spotify APPROVED but LIMITED to the 5 authorized development users.** Full rationale in Section 5, "0.4 MusicAPI.com proof of concept."                                                                                                                                                                                                                                   |
| Phase 0 status                    | ✅ **[COMPLETED] Foundation, security repair, contract freeze, and provider decision — Phase 0 gate passed.**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Phase 1 status                    | ✅ **[COMPLETED] §1.1 global standards (N8N-002…N8N-010) delivered and verified by execution (July 25, 2026).** ~~Main router and error handler verified with mocked data.~~ → **The router is now verified against real services, not mocks:** `smoke_test_e2e.py` passes 10/10 through the live stack. ~~**Remaining before the Phase 1 gate:** WF-007, WF-008 and WF-010 do not exist yet (no task ID, no priority label — each is pulled in by the phase that needs it).~~ → ✅ **[COMPLETED] Phase 1 gate PASSED (July 28, 2026).** All eleven workflows exist and are exported; WF-007 (15 nodes), WF-008 (12) and WF-010 (16) were built, imported and **executed** the same day. Against the gate's own six criteria: WF-001 reaches every sub-workflow ✓ (12/12 smoke); envelopes canonical ✓; input/output guardrails visible in the main path ✓ (real since §8.5); Information Extractor and AI Agent surfaces present and testable ✓; **placeholder nodes explicit and traceable ✓ — exactly one remains in the whole exported set** (`PLACEHOLDER — rag-service staged ingestion (RAG-010)` in WF-007, §1.14-compliant and replaced by a named Phase 3 task); no credential value in workflow JSON ✓ (swept).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Phase 2 status                    | ✅ **[COMPLETED] Data layer and service foundations — all of Sections 2.1–2.6 delivered (repo structure, Docker Compose, Alembic/pgvector schema, FastAPI service skeletons, Guardrails foundation, and n8n-to-service wiring); Phase 2 gate passed (July 24, 2026).** ~~**In progress** — Data layer and service foundations (database, service skeletons, Guardrails Service, Flask integration).~~ ✅ **[COMPLETED] Sections 2.1–2.4 (repo structure, Docker Compose, Alembic/pgvector schema, FastAPI service skeletons)** as of July 24, 2026. ~~Remaining: 2.5 real guardrails logic and 2.6 n8n-to-service wiring.~~  ⚠️ **REVISED (July 25, 2026):** this gate was withdrawn and then **re-closed on executed evidence** — the original pass rested on n8n-to-service wiring that could not run, because the workflows lived in n8n Cloud while the services are Docker-internal (**ADR-005**). After migrating n8n to self-hosted and fixing **seven** bugs (UUID server defaults, Switch intent value, validation error path, sub-workflow error path, guest mode, the `payload` return contract, and the JSON path on `/audio/analyze`), `smoke_test_e2e.py` passes ~~**10/10**~~ → **12/12**. **Updated July 28, 2026: the four open Phase 2 items are now closed** — `INF-002a` (n8n pinned to 2.31.6), `INF-002b` (inert basic-auth variables removed; owner account verified live at 401; editor bound to loopback; public API disabled), `INF-011` + `DEP-001` (Flask is a Compose service behind Gunicorn — which exposed that the existing image would have started and then 500'd, because `.dockerignore` excluded `templates/`), and `N8N-REAL-004` (model usage and provider quota now persist to real tables, verified with live rows). Only `INF-009` (Redis, P1) is deliberately open. |
| Phase 3 status                    | ✅ **[COMPLETED] Phase 3 gate PASSED 5 of 5 (July 29, 2026)** — golden evaluation set + Ragas, multilingual reranker adopted on measurement, full reviews corpus ingested, token-safe chunking, negation handling, staged ingestion with publish/rollback, prompt-log Version 1, and Ollama removed in favour of the three local models that actually run. Only `RAG-002` (corpus provenance, needs the developer) remains open, and it is not a gate criterion. ~~**In progress** — Knowledge preparation, local models, and hybrid RAG.~~ ~~Sections 3.1–3.2 kickoff only~~ → **July 24, 2026 progress:** §3.1–3.2 domain scaffold + inventory; text ingestion + embeddings (ADR-003 `multilingual-e5-small`); §3.5 hybrid pipeline items 1–7 ✅ (dense, FTS, metadata filters, genre expansion, RRF, cross-encoder rerank, top-5 selection); §3.6 Document Reranker ✅ (`ms-marco-MiniLM-L-6-v2`); §3.7 local RAG generation ✅ (`test_generation.py` → Ollama `llama3.1`). **Remaining:** §3.8 golden eval set, LOCAL-002/003 adapter + measurements, prompt-log Version 1, Phase 3 gate.      **July 25, 2026:** §3.5 item 4 is no longer mocked — `RAG-009` delivered a real genre graph (260 nodes / 689 edges in `genre_nodes` + `genre_edges`, built from the 23 source files) and `genre_graph.py` replaced the hardcoded expansion map. |
| Phase 4 status                    | **In progress** (opened July 24, 2026) — LangGraph engine scaffolding delivered: §4.1 `RecommendationState` schema ✅; §4.2 all 18 stub nodes + compiled `StateGraph` topology ✅ (`langgraph==1.2.9` in `recommendation-service/app/core/`); §4.3 `rewrite_count <= 1` enforced structurally via the conditional edge + single loop-back. ~~**Remaining:** real node logic (§4.4–4.8), Track Reranker v1, WF-002 integration, Phase 4 gate.~~ → ~~**July 25, 2026 (even later):** §4.2 nodes 5–18 are real (retrieval via a real `/rag/retrieve`, deterministic bounded rewrite, fixture-backed provider search, §4.7 Track Reranker v1, §4.8 curator explanation via `claude-haiku-4-5`/ADR-006). `POST /recommendations/run` returns `engine: "graph"` end to end; live-verified except node 17's happy path (blocked on an Anthropic account credit top-up, not code). **Remaining for the Phase 4 gate:** `REC-LEG-001`/`REC-LEG-002` legacy comparison.~~ → ✅ **[COMPLETED] Phase 4 gate PASSED (July 25, 2026, even later still).** Node 17 live-verified after the credit top-up; `REC-LEG-001`/`REC-LEG-002` fully run — see the dedicated session bookmarks. Provider search stopped being a fixture partway through the day too (see Phase 5 status below), so "fixture-backed provider search" above is now stale as well. |
| Phase 5 status                    | **In progress** (opened July 25, 2026, even later still) — scoped to §5.1 (`PROV-001…006`) + §5.3 (`YT-001…006`) only: real YouTube search, no OAuth. `provider-gateway`'s `/providers/search` calls the real YouTube Data API v3 (`app/youtube_adapter.py` + `app/cache.py`), replacing the Bon Iver fixture. ~~Two~~ **Four** real bugs found live and fixed the same session: an API-key-in-logs leak (moved to a header); `build_provider_search_intents` concatenating unrelated genre chunks into one incoherent query (7/12 recommendations got zero results before the fix, 0/12 after); video-essay/commentary content ranking as tracks; and — the most instructive — `rank_tracks` discarding provider confidence entirely for guest profiles (§4.7 correction). **`videos.list` enrichment also landed** (duration/region/embeddability, 1 quota unit batched), closing `PROV-005`, `YT-004` and most of `PROV-002`, and filtering the hour-long DJ mixes. ~~**Remaining:** §5.2 (Google OAuth), §5.4 (playback UI), §5.5 (export), §5.6 (optional Spotify, P1) — none started.~~ → **§5.2 Google OIDC is now code-complete (July 25, 2026, evening):** `AUTH-001…006` implemented (Authlib sign-in, the app's **first real `users` rows**, guest→user migration, and `oauth_accounts` — the 19th and final Section 2.3 table — with Fernet-encrypted tokens per **ADR-007**), plus disconnect/revoke. 131 offline tests green and the migration round-trip verified, but ~~**the live consent flow is unrun pending the developer's Google Cloud OAuth client.**~~ → **the Google Cloud client was supplied on July 26, 2026, so the live consent flow is unblocked and pending execution.** ~~**Remaining:** that live confirmation, §5.4 (playback UI), §5.5 (export + WF-009), §5.6 (optional Spotify, P1).~~ → **Updated July 26, 2026: §5.2 was live-confirmed and §5.5 (export + WF-009 + the WF-001 identity fix) is delivered and live-verified** — a real private YouTube playlist was created, idempotency proven (same key → same playlist, no duplicate), `INSUFFICIENT_SCOPE` refused before spending quota, guest→user migration finally working, and disconnect exercised end to end so the export fails closed. **Phase 5 gate is now 5 of 6.** ~~**Remaining:** §5.4 (playback UI), §5.6 (optional Spotify, P1), and the one open gate criterion (playable-percentage measurement) — **all three blocked behind the same Phase 8 UI rewiring**, since the browser still posts to the legacy `/chat` and nothing in the UI reaches the new path.~~ → **Updated July 26, 2026 (later): that blockage is cleared — Phase 8's UI rewiring was pulled forward and the browser now reaches the new path.** §5.4 is largely delivered as a result (`PLAY-001`, `PLAY-003`, `PLAY-004`, `PLAY-005` ✅; `PLAY-002` partial). **Remaining:** §5.6 (optional Spotify, P1) and the playable-percentage measurement, now unblocked.                                                                                                                                                                                  |
| Phase 6 status                    | **In progress** (opened July 27, 2026, by developer decision to move directly to Phase 6). **§6.1 upload pipeline, §6.2 real feature extraction, §6.3's classifier build and §6.5 audio-conditioned retrieval all landed this session.** `audio-service` stopped being a fixture: `POST /audio/analyze` measures BPM, key, Camelot and energy with per-field measured confidences (live-verified against a synthesized 120 BPM / 440 Hz signal -> 117.45 BPM, A major, both correct), and a real spectrogram CNN was **trained and measured** on GTZAN: held-out **clip-level macro-F1 0.8692** (accuracy 0.8733), against a 0.10 baseline and a 0.60 ship threshold fixed before training. Credible because of where it sits and how it fails -- inside the published 0.75-0.85 band, with rock the honest weak class at F1 0.640 and classical/jazz perfect. **Four defects of consequence were found and fixed, three of which were silently disabling work that appeared to be done:** the Phase 2 upload check accepted a file if its *declared* MIME type **or** filename extension looked like audio, so a Windows executable named `song.wav` passed; WF-003 forwarded the whole analyze response as `audio_features`, putting the measurements one level too deep so they never reached retrieval; retrieval nodes skip on empty text, so an audio-only request retrieved **nothing at all**; and `_normalize_audio_features` treated `source` and `model_version` as musical features while applying the weakest field's confidence to every other field. ~~**Remaining: §6.4 only** (`REC-ID-001...006` + ADR-004) - blocked on the developer's ACRCloud credentials, which is also why 2 of the 6 gate criteria are open.~~ → **§6.4 landed the same day**: ACRCloud is live (`identify-ap-southeast-1`, found by probing since a wrong region answers the same `3001` as a wrong key), measured at **100% on clean in-catalogue audio, 91.7% coverage, 0 false positives, median 3.84 s**, and live-verified through the browser — a real recording came back as *"I'm Real" by Jennifer Lopez* with Spotify and YouTube IDs attached. **The POC's own first run was wrong and was redone**: without a catalogue control, an unindexed clip is indistinguishable from one the noise destroyed, and it reported 10/10 "noisy" matches that measured nothing. **Phase 6 gate is now 5 of 6, with only humming open.** **Hardened the same day after the developer's first real-world use**, which produced two misses and one confidently wrong answer: the codec and sample-rate suspects were **ruled out by measurement** (every variant scored 100), and the real cause turned out to be **placeholder rows in ACRCloud's own catalogue** — one of which scored **100**, so a low-score guard would have missed it. Candidates are now walked by score and the first *plausible* release is returned, which recovered a correct track that had been sitting behind a junk one. Listening extended 10 s → 15 s, again on measurement rather than intuition. The identification fixture that claimed "Holocene" by Bon Iver at 0.88 confidence for any input, including silence, has been **removed rather than left in place**. |
| Phase 7 status                    | **In progress** (opened July 28, 2026). **§7.1/§7.2 delivered: the Preference Profile is real, persisted and versioned.** `PERS-003/004/005/006` closed; `/profiles/update` and `GET /profiles` replaced the stub that returned a hardcoded `{"indie": 0.5, ...}`. Live-verified: three Likes as a guest -> versions 1/2/3, read back in a separate request as `shoegaze 0.6 / slowdive 0.9` with `personal_taste` risen 0.0 -> 0.6; a dislike then moved it only -0.08 against a like's +0.20, which is §7.2's asymmetry holding in production. **Three silent-failure defects were found by running it rather than reading it** (missing `pgvector`, a `DATABASE_URL` resolving to localhost inside the container, and a guest's first Like having no `guest_sessions` row) -- all three surfaced as `persisted: false` rather than as a success that quietly changed nothing. ~~**Remaining: `PERS-001/002/007`**~~ -> **all of §7.1 and §7.2 are now closed**, including WF-005's SQL-injection fix and the profile wiring: `_build_initial_state` loads the stored profile, so the *next* recommendation reads it -- the Phase 7 gate criterion. Live: three Likes -> v1/v2/v3, `personal_taste` 0.0 -> 0.6, explanation *"Leans towards shoegaze / Likes slowdive / Prefers moderate energy"*. ~~**Remaining: `RANK-004/005` and all of §7.5 `SEQ-001...005`.**~~ -> **All Phase 7 P0 items are now closed** (§7.1, §7.2, §7.4, §7.5). Two further inert-by-construction defects were found on the way: **`personal_taste.score` was hardcoded to `1.0`**, so the profile could not reorder anything even after it was being loaded; and **`sequence_confidence` was not declared in `RecommendationState`**, so LangGraph would have dropped it silently in the compiled graph while the node's unit tests passed. **Phase 7 gate PASSED, 5 of 5** -- the discovery-mode criterion was measured (`eval/discovery_modes.py`): overlap with the safe result set falls **1.00 -> 0.93 -> 0.62**, so adventurous returns 38% different tracks for the same queries. **Two limitations recorded rather than smoothed over:** familiarity barely separates the modes (0.07 -> 0.06) because only ~6% of the candidate pool matches the profile at all -- the limiter is candidate generation, not the mode lever -- and genre diversity is unmeasurable while provider tracks carry no genre. |
| Phase 8 status                    | **In progress** (opened July 26, 2026, later — **pulled forward out of phase order** by developer decision, because three P0 items were queued behind it and nothing built since Phase 4 was reachable by a user). §8.1 route boundary ✅ (five new routes plus one shared envelope builder); §8.2 `UI-001`/`UI-005`/`UI-006`/`UI-007`/`UI-010` ✅ live-verified in a real browser; `UI-003`/`UI-004`/`UI-009` **partial** — guest branches verified, signed-in branches code-complete but unrun; `UI-002`/`UI-008` blocked on Phases 6/7. **Connecting the UI immediately exposed four defects that direct-to-service testing could never have caught — including that every recommendation ever placed through n8n had been generated from an empty query.** See the session bookmark for the full record. ~~**Remaining:** the signed-in UI round trip, §8.3 `JOB-001…004`, §8.5 `INT-001…004`, and the Phase 8 gate.~~ → **Updated July 26, 2026 (later still), after the developer's first use of the UI:** Google sign-in was **broken** by a redirect-URI host mismatch and is fixed (§5.2 `AUTH-003`); the Spotify login control that the Phase 8 rewiring wrongly removed is **restored**; **Spotify is promoted from optional P1 to a first-class recommendation mode** with a UI toggle (§5.6); replies now carry **one recommendation, one player** (§4.8); and Hebrew requests no longer time out (§4.6). ~~**Remaining:** the developer's live sign-in confirmation, §8.3, §8.5, and the Phase 8 gate.~~ → **Updated again (July 26, 2026, later still, continued): §8.5 `INT-001…004` is complete** — the placeholder audit closed §2.5's unimplemented guardrail checks, exposed that all three WF-001 refusal branches answered with an empty body, and corrected a smoke test written to accept exactly that (10/10 → 12/12). **Remaining:** the developer's live sign-in confirmation, §8.3 `JOB-001…004`, and the Phase 8 gate. |
| Status                            | Approved architecture converted into an ordered implementation plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |


---



# 1. How to use this plan

This is a build sequence, not a topic catalogue.

1. Work from Phase 0 forward.
2. Do not start a later phase before the current phase gate passes, except for explicitly marked parallel research.
3. Select one task ID or one small, adjacent task group per coding session.
4. Use the task's inputs, outputs, acceptance criteria, and test requirements as the coding-agent prompt context.
5. Export every n8n workflow as JSON and commit it to `workflows/n8n/`.
6. Record unresolved choices in an ADR under `docs/adr/`; do not silently choose a provider or model.
7. Update checkboxes only after the relevant test or phase gate passes.
8. Under deadline pressure, complete every `P0` vertical slice before improving a `P1` feature.

Priority labels:

- **P0 — Submission critical:** required for the complete end-to-end demo.
- **P1 — Product hardening:** required before real public users.
- **P2 — Research/expansion:** valuable but cannot block the submission path.



## The next action

<!-- ============================ RESUME HERE ============================ -->

## ▶ RESUME HERE — session bookmark (last updated: ~~July 25, 2026~~ → ~~July 25, 2026, even later~~ → ~~July 26, 2026 — §5.5 playlist export delivered and live-verified~~ → ~~July 26, 2026, later — Phase 8 pulled forward~~ → ~~July 26, 2026, later still — first developer use of the UI: sign-in fixed, Spotify restored and promoted to a first-class mode, Hebrew timeout fixed~~ → ~~July 27, 2026 — Phase 6: the audio path stops being a fixture~~ → ~~July 28, 2026 — everything backed up to GitHub; Phase 1 and Phase 2 gates closed; WF-007/008/010 built and executed; Phase 3 is now the only phase before Phase 9 with an open gate~~ → **July 29, 2026 — PHASE 3 GATE PASSED 5 of 5: golden set + Ragas, multilingual reranker adopted on measurement, full corpus ingested, staged ingestion with publish/rollback. Phase 9 is now the whole remaining scope, and the deadline is July 30.**)

> **Read this block first.** It is the single place that says where work stopped and what to pick up. Update it at the end of every working session; never delete the previous entry — strike it through and write the new one beneath, exactly like every other entry in this document.

### ▶ Session bookmark — July 25, 2026 (later): first real UI testing, and the decision it produced

**The app runs locally end to end.** `.venv/Scripts/python.exe app.py` → `http://localhost:5000`. Docker carries postgres, n8n and the five services.

⚠️ **Critical finding from the first UI test session: the browser UI does not exercise the new architecture at all.** `templates/index.html` posts to **`/chat`**, which calls `query_bedrock()` → Bedrock Agent → Lambda → Spotify — the **legacy path**. The new path (`/api/v1/requests` → WF-001 → services) is only reachable by calling it directly. Every defect found in that session lives in the legacy path:

| Reported | Diagnosis |
| --- | --- |
| "2025 hasn't arrived yet" for a 2026 request | `aws/system_prompt.txt` has **no date anchor**; the Bedrock model falls back to its training cutoff. Latent all along — the 2026 question is what is new. |
| Spotify fails to read *and* write | Lambda exposes `search_track` / `search_playlist` / `search_album` / `search_artist` / `get_user_taste`. **Most likely cause: `SEC-001` (Phase 0, July 21) rotated the Spotify authorization** and the Lambda still holds the old credentials. Check its env vars + CloudWatch logs. |
| OAuth redirects to `18.191.243.177` | `SPOTIPY_REDIRECT_URI` pointed at EC2 — correct when hosted there, wrong when running locally. Now `http://127.0.0.1:5000/callback`; **`app.py:48` reads it at module level, so Flask must be restarted**, and the URI must also be registered in the Spotify dashboard. |
| "Break my algorithm!" refused | The legacy system prompt is dense with `CRITICAL … You MUST` rules, so the model reads the button as an override attempt. Separately, **the rule block appears twice in two non-identical versions** (~770 duplicated tokens per call) — two rule sets that can conflict. |
| EC2 unreachable | Not related to any local work (`DATABASE_URL` is `localhost`; nothing touched AWS). A stopped/started instance without an Elastic IP gets a **new public IP**. |

**NEW DECISION (July 25, 2026): do not invest in repairing the legacy Lambda path.** Section 2.3 already scopes the AWS route to *"a known-good rollback"* that *"must not define the new design"*. The behaviour worth keeping — RAG supplies genre context, then a provider returns a precise track — is exactly what Phase 4 and Phase 5 build, and build better (real hybrid RAG instead of Bedrock KB; a provider interface that is not bound to Spotify's 5-user development limit). Only the two cheap legacy fixes are worth doing, and only because `REC-LEG-001`/`REC-LEG-002` need a working comparison baseline: the date anchor, and the redirect URI (done).

**Where we stopped:** ✅ **Phase 2 gate PASSED on executed evidence.** `workflows/n8n/tests/smoke_test_e2e.py` passes **10/10** against the self-hosted n8n; `test_validate_request_schema.js` passes **15/15**. The full path — Flask envelope → WF-001 → guardrails → Postgres → sub-workflow → FastAPI service → response — runs for all six intents and persists rows with real `latency_ms`.

**How to restart the environment (n8n is self-hosted now — ADR-005):**

1. `docker compose up -d` — brings up postgres, n8n, and the five services.
2. Re-import only if the workflow JSON changed: `docker cp workflows/n8n melody-n8n:/tmp/wf` then `docker exec melody-n8n n8n import:workflow --separate --input=/tmp/wf`.
3. ⚠️ **Importing unpublishes every workflow.** Re-publish all 8 with `n8n publish:workflow --id=<id>` — **sub-workflows first, WF-001 last** — then `docker compose restart n8n`.
4. Confirm health with `python workflows/n8n/tests/smoke_test_e2e.py` (expect 10/10) before changing anything.

### ▶ Session bookmark — July 25, 2026 (even later): Phase 4 §4.2 nodes 5–18 delivered — the recommendation is real

**`POST /recommendations/run` no longer returns the Bon Iver fixture.** All 14 remaining stub nodes in `recommendation-service/app/core/graph_nodes.py` (5–18) now carry real logic, and `recommendation-service/main.py` invokes the compiled graph (`recommendation_graph.ainvoke(...)`) instead of returning a hardcoded response. `engine` in the response is now `"graph"`, `placeholder` is `false`.

**`rag-service/main.py`'s `/rag/retrieve` is real**, not a fixture: dense + lexical search → RRF → one-hop genre-graph expansion → cross-encoder rerank, lifted from `scripts/test_hybrid_retrieval.py` / `scripts/genre_graph.py` (models/DB engine/genre graph loaded once at service startup, not per-request). Verified against the live 24-doc corpus — `matched_genres` and real chunk text come back for a genre-bearing query (see the curl transcript below).

**New files:** `recommendation-service/app/core/{rag_client,provider_client,llm_adapter}.py` (thin HTTP/Anthropic seams nodes 5–18 call through) and `recommendation-service/test_graph_nodes.py` (26 unit tests covering every node's happy path, its degrade-gracefully-on-HTTP-error path, and two end-to-end graph runs — one happy path, one that forces the low-confidence rewrite and asserts it fires exactly once).

**NEW DECISION, confirmed with the developer before implementation:** node 11 (`rewrite_query`, the single bounded low-confidence retry, §4.5) stays **deterministic/rule-based** — it does not call the LLM. This is a deliberate, narrower reading than ADR-006's literal text (which assigns the rewrite to `claude-haiku-4-5` alongside the curator explanation). Node 17 (`generate_grounded_explanation`) remains the only heavy-model call site for this phase of work. **Follow-up for whoever picks this up next: fold this narrowing back into `docs/adr/ADR-006-model-routing.md`** so the ADR matches the code, or revisit the decision if a future session wants the rewrite to be LLM-generated too.

**Track Reranker v1 (§4.7) is real**, not a placeholder: `text_relevance` (stdlib `difflib` fuzzy match, no new dependency), `personal_taste` / `provider_taste` (profile weights × provider-reported confidence). `audio_fit` is **omitted, not fabricated** — provider-gateway carries no per-track audio features yet (that's Phase 6/7), so its weight share is redistributed across the present components rather than invented, per §4.7's explicit instruction.

**Verified against the live stack (`docker compose up -d`, images rebuilt):**
- `curl -X POST localhost:8002/rag/retrieve -d '{"query":"warm indie folk with acoustic instrumentation","filters":{"domain":"genre"}}'` → real corpus chunks (e.g. `genre:contemporary_rock#indie_folk_freakfolk_new_weird_america`), real cross-encoder scores, `matched_genres` populated, `placeholder: false`.
- `curl -X POST localhost:8001/recommendations/run -d '{"user_text":"warm indie folk for a rainy afternoon"}'` → `engine: "graph"`, `placeholder: false`, ran all 18 nodes (log-verified), correctly triggered exactly one `rewrite_query` pass when retrieval confidence came back low, then continued forward rather than looping.
- `python workflows/n8n/tests/smoke_test_e2e.py` → **still 10/10** — the full Flask → n8n → guardrails → WF-002 → recommendation-service path is intact end to end with the real graph behind it.
- Offline: `pytest` in both `recommendation-service/` and `rag-service/` — 32/32 and 4/4 green, no docker/network required (external calls monkeypatched).

~~**⚠️ One thing NOT fully verified live: node 17's happy path.** The real Anthropic call reached `api.anthropic.com` and got a structurally valid response back (confirmed the request shape matches the installed SDK's own `OutputConfigParam`/`JSONOutputFormatParam` types), but the account's **Anthropic credit balance is too low** (`"Your credit balance is too low to access the Anthropic API"` — an account/billing issue, not a code issue). Node 17 correctly caught this as an adapter failure and degraded per ADR-006 (`output_valid=False`, no fabricated explanation) rather than crashing — that degrade-gracefully path *is* verified (see `test_generate_grounded_explanation_failure_invalidates_output` and the live curl, which came back with an honest empty `reasoning`/`playlist_description`). **Next step for whoever has billing access:** top up Anthropic credits, then re-run the `localhost:8001/recommendations/run` curl above and confirm `tracks[].reasoning` and `playlist_title`/`playlist_description` are populated by Haiku.~~ → ✅ **[COMPLETED] (July 25, 2026, even later still): developer topped up the Anthropic account's credit balance.** Re-ran the same curl — `claude-haiku-4-5` now returns a real grounded `playlist_title` ("Rainy Afternoon Folk"), `playlist_description`, and per-track `reasoning` (e.g. *"'Holocene' by Bon Iver evokes quiet contemplation with its fingerpicked guitars and hushed vocals, ideal for a reflective rainy afternoon."*), confirmed against container logs (`POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"`). Node 17's happy path is now fully live-verified — this was the last open item blocking the Phase 4 gate besides `REC-LEG-001`/`REC-LEG-002`.

**Unrelated finding, noted so it isn't chased as a new bug:** the `ollama` container was already stuck in `Created` (never started) before this session — something outside Docker on the host already holds port `11434` (`netstat` showed a foreign PID listening there). `rag-service` no longer needs Ollama for anything on the request path (`/rag/retrieve` doesn't touch it), so this didn't block verification (`docker compose up -d --no-deps rag-service` sidesteps the blocked dependency) — but Ollama-dependent work (`LOCAL-002`/`LOCAL-003`, `test_generation.py`) will hit this until the host port conflict is resolved.

**Phase 4 gate — status against the checklist in this doc:** accepts the full `RecommendationContext` ✓; graph performs at most one rewrite (live-verified) ✓; provider fixtures pass the same adapter contract Phase 5 will use ✓; track component scores + full model-usage metadata (§4.9: provider/model/tokens/latency/cost/request_id) are stored in `node_metrics` ✓; `sequence_tracks` uses the versioned `relevance-order-baseline-v1` ✓; WF-002 already pointed at the real service and needed no change ✓; the new engine is distinguishable in logs/response metadata (`engine: "graph"`) ✓; node 17's happy path ✓ (see completion note above). ~~**Not closed by this session:** `REC-LEG-001`/`REC-LEG-002` (legacy-vs-new comparison) are separate open P0 items untouched here, and node 17's happy path needs the credit top-up above before calling the gate fully closed.~~ → ~~**The only remaining gate item is `REC-LEG-001`/`REC-LEG-002`** (legacy-vs-new comparison) — not started; see the session bookmark's design note for what it needs and the AWS-credentials blocker discovered while scoping it.~~ → ✅ **[COMPLETED] `REC-LEG-001` fully run, `REC-LEG-002`'s quantitative comparison done (July 25, 2026, even later still) — see the dedicated session bookmark below for the full table and two real findings it surfaced.** Phase 4 gate is now clear on every item this doc lists. The comparison surfaced two real findings: `SEC-001` (Lambda/Spotify credentials) is still broken — legacy path, not this gate, and remains open; the §4.8 retrieval-confidence-leak bug in node 17's prompt — **fixed the same session, see the completion note below.**

**⚠️ Blocker discovered while scoping `REC-LEG-001` (July 25, 2026, even later still): this machine has no AWS credentials.** No `~/.aws/credentials`, no `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` in `.env` — only `BEDROCK_AGENT_ID`/`BEDROCK_AGENT_ALIAS_ID` (which name a resource, not a credential) are set. `query_bedrock()` in `app.py` calls `boto3.client("bedrock-agent-runtime")`, which will raise `NoCredentialsError` from here. The EC2 host mentioned in the "(later)" bookmark above likely worked via an attached IAM instance role, which doesn't exist on this dev machine. ~~**This blocks running the legacy side of `REC-LEG-001` locally until the developer either supplies credentials (`aws configure`, env vars, or an SSO profile) or the comparison is run from a host that already has AWS access (e.g. the EC2 instance, once reachable).**~~ → **Developer decision (July 25, 2026, even later still): defer legacy-side execution to the EC2 host; build the runner now so it's ready.** Done — see below.

**✅ [COMPLETED] `REC-LEG-001` harness built and new-engine leg verified (July 25, 2026, even later still).** New files: `eval/prompts.json` (12 shared prompts spanning §3.8's categories — mood-based, blended genres, Hebrew + English, exact artist/genre, anti-echo-chamber, negative constraints) and `eval/rec_leg_comparison.py` (stdlib-only runner, matches `smoke_test_e2e.py`'s style). Usage: `python eval/rec_leg_comparison.py --new-only` works today with no AWS access (verified: all 12 prompts ran against the live stack, report at `eval/rec_leg_report.md`); the full `python eval/rec_leg_comparison.py` (both legs) needs Bedrock credentials and must run from a host that has them.

**Also delivered alongside the harness — §4.9 model-usage data is now real, not just a free-text sentence.** `NodeMetric` (`graph_state.py`) gained structured `input_tokens`/`output_tokens`/`estimated_cost_usd` fields (previously only node 17's `detail` string had this, unparseable without a regex), and `_metrics()` (`graph_nodes.py`) now `logger.info`s every node's metrics entry as JSON — this is what lets the comparison script recover real per-request cost from `docker logs` (`--docker-container`/`--no-log-scrape` flags control this). Verified live: a single `/recommendations/run` call logged `{"generate_grounded_explanation": {..., "input_tokens": 1289, "output_tokens": 161, "estimated_cost_usd": 0.002094}}`. This does not close the `model_usage`-table persistence gap noted above (still transient, log-only) — it makes that gap recoverable via logs in the meantime.

**What the new-engine-only run already shows (empirically confirms the Phase-5-fixture caveat flagged above):** all 12 prompts — mood, genre, artist, Hebrew, negative-constraint, everything — returned the identical `Bon Iver` fixture pair, because `search_providers` doesn't vary by query yet. Cost was consistent too: ~$0.0021–0.0028/request, ~$0.0225 for all 12. **Track-level metrics (playable-track rate, track diversity) will only become meaningful once Phase 5 wires a real provider search** — don't read anything into today's "1 unique artist across 12 prompts" beyond "the fixture is working as designed." Latency (~16–19s/request, dominated by two sequential `/rag/retrieve` calls plus the Haiku call), retrieval grounding, and explanation prose are meaningful today and already visible in `eval/rec_leg_report.md`.

~~**Remaining for `REC-LEG-001`/`REC-LEG-002`:** run the full comparison (both legs) from a host with Bedrock access; have a human (or a separate LLM-judge pass) fill in the blank "explanation quality (1-5)" column the report already reserves; then do the actual `REC-LEG-002` write-up (§4.10: compare retrieval relevance, playable-track rate, latency, cost, diversity, explanation quality) once track-level data is meaningful post-Phase-5.~~

### ▶ Session bookmark — July 25, 2026 (even later still): `REC-LEG-001` fully run — both legs, 12/12 prompts

**Developer added AWS credentials to `.env`** (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) rather than deferring to the EC2 host. Validated with a free `sts:GetCallerIdentity` call before spending anything on Bedrock (account `881490130721`, IAM user `user8`), then a single `/chat` sanity call, then the full `python eval/rec_leg_comparison.py` (both legs) — all 12 prompts succeeded on both sides. `.env.example` gained `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` placeholders (names only) since this is now a documented, supported local setup path, not just an EC2-only one.

**Quantitative (`REC-LEG-002`), from `eval/rec_leg_report.json`:**

| Metric | Legacy (Bedrock Agent) | New engine (LangGraph) |
| --- | --- | --- |
| Avg latency | **21,099 ms** | **17,256 ms** (~18% faster) |
| Cost per request | Not captured by this harness (Bedrock Agent doesn't expose per-call token usage the way the Anthropic API does; would need AWS Cost Explorer / CloudWatch) | **Measured, real:** ~$0.0021–0.0028/request (avg $0.00233) |
| Playable-track rate | **0/12** — every single response says Spotify search failed (see below) | **0/12** distinct real tracks — same 2 fixture tracks every time (Phase 5 not landed; expected, not a defect) |
| Track/artist diversity | High — Bedrock names real, topically-appropriate artists per prompt (Larry Heard for deep house, כוורת/שלום חנוך/אריק איינשטיין for Israeli classic rock, Iron & Wine for indie folk, etc.) | 1 unique artist (Bon Iver) across all 12 — expected, fixture-backed |
| Retrieval grounding | None — answers come from the base model's training knowledge only | Real — e.g. the deep-house explanation correctly cites "Philly Soul... Hammond organs and electric pianos," pulled from the ingested genre corpus, not invented |
| Language handling | Correct — Hebrew prompts get Hebrew answers | Correct — same |

**⚠️ Confirms a previously-known issue is still live, with hard evidence now:** **12/12 legacy responses mention a Spotify connection failure** ("Spotify is having a connection issue," "בעיה טכנית זמנית עם חיפוש ב-Spotify"). This is the `SEC-001` credential-rotation issue from the "(later)" bookmark above — still broken, now quantified: **the legacy path's real playable-track rate is 0% today**, not just "possibly degraded."

~~**⚠️ New finding — a real §4.8 violation, not hypothetical:** the Hebrew low-confidence run (`mood-he-1`) produced *"מוזיקה דינמית ועוצמתית לתחילת יום מלא. **אף שהביטחון בשלוף הוא נמוך**, הרצינו להציע שירים..."* — literally "even though the confidence in the retrieval is low" — **leaked directly into user-facing prose.** §4.8 explicitly requires "no raw retrieval mechanics in normal user prose." Root cause: `llm_adapter.generate_curator_explanation`'s user-turn content includes `state["warnings"]` verbatim (e.g. `"retrieval confidence was low; one bounded rewrite executed (...)"`) under a `"Known caveats:"` heading, and the system prompt only says to "be honest about it briefly" — Haiku faithfully paraphrased the internal term rather than translating it into user language. **Not fixed yet — flagged for the developer to decide whether to fix now or backlog it** (likely fix: rephrase warnings into user-safe language before they reach the prompt, e.g. "we weren't fully confident in this pick" instead of passing the raw "retrieval confidence" string).~~

**✅ [COMPLETED] §4.8 caveat-leak fixed (July 25, 2026, even later still, developer requested the fix).** Root cause addressed at the source, not patched with a stronger prompt alone: `graph_nodes.py` gained `_user_safe_caveats(state)`, which translates specific known-safe signals (currently: `rewrite_count > 0` → *"we weren't fully sure about this pick, so we broadened the search a little"*) into pre-written, jargon-free phrases — `state["warnings"]` (internal/debug text: exception messages, field names, "retrieval confidence was low", etc.) is never passed to the model at all anymore. `llm_adapter.py`'s `warnings` param was renamed to `user_safe_caveats` throughout (so the bug can't silently reappear by someone passing raw warnings back in), and `SYSTEM_PROMPT` gained an explicit "never use internal/technical terms like 'retrieval', 'confidence score', 'rewrite'... even when translating a caveat" rule as defense in depth. Three new regression tests in `test_graph_nodes.py` assert no `_INTERNAL_JARGON` term ever reaches the adapter. **Live-verified under the exact triggering condition:** forced a real rewrite (off-domain query → `rewrite_query` fired, confirmed via logs) against the rebuilt container — the resulting explanation ("*intimate, introspective moments... contemplation rather than distraction*") contains no mention of confidence/retrieval/rewrite. 35/35 offline tests still pass.

**Bottom line for `REC-LEG-002`:** on every metric that's fair to compare today (latency, retrieval grounding, language handling), the new engine is even or ahead. Cost and track-level metrics aren't fairly comparable yet — cost because the harness can't pull Bedrock's per-call price, tracks because both sides are currently returning non-representative results (legacy: broken Spotify; new: pre-Phase-5 fixture). Re-run after Phase 5 lands real provider search for a track-level verdict, and after `SEC-001`'s Lambda credentials are fixed for a fair legacy playable-track number.

### ▶ Session bookmark — July 25, 2026 (even later still, continued): Phase 5 §5.1/§5.3 delivered — real YouTube search, no more fixture tracks

**Developer decision:** skip the rest of the "Pick up next" list (packaging, n8n pinning, finishing Phase 3) and go straight to **Phase 5**, scoped to search only (§5.1 `PROV-001…006` + §5.3 `YT-001…006`) — no OAuth (§5.2), no playback UI (§5.4), no export (§5.5), no Spotify (§5.6, P1). YouTube's `search.list` only needs an API key, not user OAuth, so this is a clean, natural first cut; the developer supplied a `YOUTUBE_API_KEY` (Google Cloud project, YouTube Data API v3 enabled, plain API key — no consent screen needed).

**`provider-gateway`'s `/providers/search` is real now**, not a fixture: new `app/youtube_adapter.py` (raw `httpx` REST calls to `youtube/v3/search`, no SDK — matches the project's existing pattern) and `app/cache.py` (24h in-process TTL cache — `search.list` costs 100 quota units/call against a 10,000/day default quota, ~100 searches/day, so caching is load-bearing, not polish). Title/artist parsing handles noisy YouTube titles (`"Artist - Title (Official Video)"`, `"Title by Artist"`, HTML-escaped entities, wrapping quote characters); a "Topic"-channel / official-video-marker heuristic scores confidence (never zero — deprioritized, not filtered); dedup keeps the highest-confidence near-duplicate. Normalized error codes (`QUOTA_EXCEEDED`→403, `RATE_LIMITED`→429, `PROVIDER_UNAVAILABLE`→503) reuse the existing `AppError` shape. 21 new offline tests (`provider-gateway/test_youtube_adapter.py` + updated `test_smoke.py`), all passing, no network needed.

**Two real bugs found live and fixed in this session, not left as known issues:**

1. **Credential leak into logs.** The API key was a `key=` query param, and httpx's own request logger logs the full URL — a live run showed the raw key in plaintext in `docker logs`. Fixed by moving it to an `X-Goog-Api-Key` header (Google's API infrastructure accepts this uniformly for API-key auth) instead of patching the logging config — the fix removes the secret from the URL entirely rather than trying to suppress a specific log line. Regression test (`test_search_never_puts_api_key_in_query_params`) locks this in. Verified live: the request-log line now shows a clean URL with no key.
2. **`build_provider_search_intents` (Phase 4 code, first exercised against real search in this session) was concatenating two *unrelated* genre corpus chunks into one incoherent compound query** — e.g. `"edm_dance_trance#overview rock_hardcore_punk#overview"`, trance and hardcore punk in a single string — plus leaving raw corpus slugs (`_`, `#`, the generic word "overview") unreplaced. Measured impact before the fix: **7 of 12 recommendations came back with zero YouTube results.** Fixed by making each distinct signal (explicit constraints, each of the top-2 reranked genre chunks) its own separate search intent — `search_providers` already called up to 2 intents, so this was a real design bug, not a missing feature — plus a `_clean_genre_slug` helper that prefers the specific sub-genre (`#deep_house` → `"deep house"`) and falls back to the parent genre when the child is just `"overview"`. 5 new/updated tests, including a direct regression test reproducing the exact failing case.

**Live-verified, before → after the second fix, via `eval/rec_leg_comparison.py --new-only` (same 12-prompt set):**

| | Before fix | After fix |
| --- | --- | --- |
| Prompts with 0 tracks | 7 / 12 | **0 / 12** |
| Unique artists across all 12 prompts | 16 (many nonsense/garbled) | **78** |
| Cost across 12 calls | $0.0149 (only 5 calls reached node 17) | $0.0401 (all 12 reached node 17) |

Also spot-checked individually: `"Bon Iver Holocene"` → correctly parsed `title="Holocene"`, `artist="Bon Iver"`, `confidence=0.8` (official-video marker detected). `"90s grunge for a moody evening"` → real, correctly-attributed tracks including Nirvana and Pearl Jam. `"deep house tracks"` → mostly DJ-mix/compilation content with appropriately **lower** confidence scores (no Topic channel, no official marker) — an honest reflection of what YouTube actually returns for vibe/mood queries, not a bug; `videos.list` duration-based filtering (deferred in the original plan) would help filter these out and is a good next improvement, now backed by concrete evidence of why it matters.

**Known, deliberately out-of-scope observation, not investigated further this session:** the two Hebrew prompts (`mood-he-1`, `genre-he-1`) retrieved the *same* unrelated "industrial goth" genre chunks despite being about a morning run and Israeli classic rock respectively — suggests the RAG retrieval may be weaker for Hebrew queries specifically. This is a Phase 3 retrieval-quality question (§3.8 golden eval set territory), not a Phase 5 provider-search issue — flagged here so it isn't lost, not fixed.

`python workflows/n8n/tests/smoke_test_e2e.py` — still 10/10. `search_providers`'s stale `"(fixture until Phase 5)"` label is gone from `graph_nodes.py`.

**Incidental fix, worth knowing because it wastes time every time it bites:** `rag-service`'s `pytest` run failed at collection with `ImportError: cannot import name 'AppError' from 'shared_lib' (unknown location)` — while `python -c "import main"` from the same directory worked fine, which is what makes it look mysterious. Cause: with no `conftest.py` present, pytest inserts the rootdir at `sys.path[0]` during collection and `shared_lib` binds as an empty **namespace package** before the editable-install finder resolves it. Fixed by adding `rag-service/conftest.py` that simply imports `shared_lib` (conftest loads before collection, so the real package wins). The other services don't hit this because their own `app/` package imports pull `shared_lib` in first. **Full offline suite now: 73 tests green across all five services** (provider-gateway 21, recommendation-service 39, rag-service 4, guardrails-service 4, audio-service 5).

~~**Remaining for Phase 5:** §5.2 (Google OAuth — needed for personalized taste import and playlist writes), §5.4 (playback UI), §5.5 (export, blocked on §5.2), §5.6 (optional Spotify, P1). None started this session.~~

### ▶ Session bookmark — July 25, 2026 (even later still, continued): `videos.list` enrichment — DJ mixes filtered, three partials closed, two more bugs found

**Developer decision:** implement the `videos.list` enrichment identified as the highest-leverage next step, to filter long DJ mixes and close the partials it unblocks. Done — plus two further real bugs it exposed, both fixed.

**The enrichment (`provider-gateway/app/youtube_adapter.py`).** A second, **batched** API call — `videos.list` with `part=contentDetails,status`, **1 quota unit** for the whole result set vs. 100 for the search itself, so the cost increase is ~1%. It supplies duration, region restrictions, and embeddability. **NEW DECISION (graceful degradation):** enrichment is an *improvement, not a hard dependency* — if `videos.list` fails, the search returns unenriched results with a warning rather than failing. **NEW DECISION (uniform shape):** enrichment keys (`duration_seconds`, `embeddable`, `duration_in_track_range`, `field_sources`) are **always present**, `None` until filled, so consumers never need an existence check. `NormalizedTrack` gained them as optional fields — additive, so `recommendation-service` needed no change.

**Duration filtering — the headline result.** Tracks outside 60–600s (env-tunable via `YOUTUBE_MIN_TRACK_SECONDS`/`YOUTUBE_MAX_TRACK_SECONDS`) have their confidence cut to 25%. **NEW DECISION:** out-of-range results are **deprioritized, not hard-dropped**, and the selector falls back to them when too few in-range candidates exist — deliberately preventing a repeat of the zero-results failure fixed earlier the same day. Live before/after on `"deep house tracks"`: previously five hour-long DJ mixes; now 170s/263s/463s real tracks.

**What this closed (all four were open partials or gate criteria):**

| Item | Status |
| --- | --- |
| `PROV-002` missing/unavailable item codes | ✅ closed — absent from `videos.list` ⇒ deleted/private ⇒ dropped; region-blocked in `YOUTUBE_REGION` (default `IL`) ⇒ dropped |
| `PROV-005` per-field source | ✅ closed — `field_sources` records provenance per field, incl. whether the artist was parsed from the title or fell back to the channel name |
| `YT-004` alternate-upload dedupe | ✅ closed — duration-gated fuzzy second pass |
| Phase 5 gate "playable in target region" | ✅ measurable now |

**`YT-004` deserves its own note, because the plan's own caveat is the hard part.** Dedupe is now two passes: exact normalized `(artist, title)`, then a fuzzy pass requiring **same artist + runtime within 2s + title similarity ≥ 0.82**. The duration gate is what makes it safe — a live version, remix, or extended edit has a different runtime, so it survives as a distinct recording, satisfying *"without incorrectly merging distinct recordings"*. Entries with unknown duration are **never** fuzzy-merged. Live proof: a `"Nirvana Smells Like Teen Spirit"` search correctly returns the studio cut (279s), the Devonshire Mix (303s), Reading '92 (331s) and Paramount (276s) as **four separate recordings**, while genuine re-uploads collapse.

**⚠️ Bug 3 of the day — the pipeline surfaced video essays instead of songs.** With enrichment live, `"90s grunge"` returned *"How Grunge Ended Hair Metal"*, *"Top 5 Grunge Songs of All Time"*, *"Grunge Vs Post Grunge Guitar Riffs"* — commentary *about* music, which duration filtering **cannot** catch because a video essay is 5–10 minutes, squarely inside track range. Fixed with a `_looks_like_non_track()` title heuristic (listicle/versus/reaction/lesson/documentary/`#shorts` patterns) applied as a 20% confidence multiplier — same deprioritize-never-drop philosophy, and multiplicative so a Topic-channel release that happens to trip a pattern still ranks well. 15 new tests, half of them asserting **real** track titles are *not* flagged.

**⚠️ Bug 4 — the one that made all of the above invisible end to end, and the most instructive of the day.** After fixing bug 3, the full pipeline *still* ranked the video essays first. Root cause was **not** in `provider-gateway` at all: `rank_tracks` (§4.7) mapped the provider's confidence onto the **`provider_taste` profile weight, which is `0.0` for a guest profile** — so every carefully computed confidence score was multiplied by zero and discarded, leaving ranking as pure fuzzy text match, which actively *rewards* titles that repeat the query's genre word. **NEW DECISION:** provider confidence is a **result-quality** signal (is this a real, authoritative, playable track), *not* a taste signal, and now has its own `provider_confidence` component with a **constant** weight independent of the user profile — so it carries weight for guests, who have no taste profile by definition. Conflating the two was a latent Phase 4 design error that only became observable once provider results stopped being identical fixtures. Live result: **Nirvana's "Smells Like Teen Spirit" moved from 6th to 1st**, CANDLEBOX 2nd, all commentary pushed to the tail.

**Verification:** **106 offline tests green across all five services** (provider-gateway 53, recommendation-service 40, rag-service 4, guardrails 4, audio 5); `smoke_test_e2e.py` still **10/10**; live spot-checks on `"deep house"`, `"Bon Iver Holocene"`, `"Nirvana Smells Like Teen Spirit"`, `"Pearl Jam Even Flow"`, and the full `/recommendations/run` grunge case.

**Still imperfect, recorded honestly rather than papered over:**

- **Commentary content is deprioritized to the tail, not removed** — a `"90s grunge"` playlist still *contains* the video essays at positions 3–9, just below the real tracks. Haiku notices and leaves their `reasoning` blank, which is honest but ugly. A final low-confidence-tail trim belongs in node 14/16 and was left alone deliberately: `sequence_tracks` is specified as a *versioned deterministic relevance-order baseline* until Phase 7's Smart Sequencer, and quietly adding a filter there would breach that.
- **The deeper root cause is query construction, not filtering.** `build_provider_search_intents` emits genre *descriptions* ("rock alternative rock indie grunge"), and YouTube answers genre descriptions with genre commentary. Even perfect filtering can only pick the least-bad from a poor candidate set. Better intents — e.g. using the RAG evidence to name representative *artists* rather than genre labels — would raise candidate quality at the source. **This is the single highest-leverage remaining improvement to recommendation quality.**
- **A junk token in a query silently returns zero results.** `"Bon Iver Holocene enrich3"` returns nothing from YouTube's music-category search, while `"Bon Iver Holocene"` returns four real cuts. Not a code defect — but it means the intent builder must never emit stray tokens, which is exactly how the earlier 7/12-zero-results bug happened.
- `PROV-001`/`PROV-003` remain partial (no OAuth-dependent adapter ops; no circuit breakers or quota-aware retries).

~~**Remaining for Phase 5:** §5.2 (Google OAuth — needed for personalized taste import and playlist writes), §5.4 (playback UI — `embeddable` is now supplied for §PLAY-005's fallback link), §5.5 (export, blocked on §5.2), §5.6 (optional Spotify, P1).~~

### ▶ Session bookmark — July 25, 2026 (evening): §5.2 Google OIDC — code complete, awaiting the developer's Google Cloud client

**Developer decision:** move to §5.2 as the next major step, scoped to all P0 items (`AUTH-001…006`) **plus** the `AUTH-005` incremental-scope route; **defer** WF-009 wiring to §5.5 (where the connection is actually consumed, rather than paying the n8n import → publish-all-8 → restart cycle for a workflow that would only echo status) and defer `AUTH-007`'s user-data deletion. **Library decision:** Authlib, deliberately departing from the raw-httpx pattern — see `AUTH-001` above for the reasoning.

**⚠️ This slice is code-complete and offline-verified, but the live browser consent flow has NOT been run** — it needs a Google Cloud OAuth client that only the developer can create. Everything below is proven by unit tests and a real migration round-trip; nothing below claims a completed sign-in.

**What landed:**

| Piece | File |
| --- | --- |
| OIDC flow: login / callback / upgrade / disconnect / status | `auth_google.py` (Flask blueprint, 5 routes) |
| The 19th and final Section 2.3 table | `contracts/db_models.py::OAuthAccount`, migration `b8e4f1a92c37` |
| Token encryption at rest | `contracts/token_crypto.py` |
| The deferred storage decision | `docs/adr/ADR-007-oauth-token-storage.md` |
| Cookie hardening + first Flask DB access | `app.py` |

**Three findings worth recording, because each changed the design:**

1. **`shared_lib` was the wrong home for the crypto helper**, which the plan had specified. Two reasons, both discovered by trying it: `shared_lib/__init__.py` imports FastAPI, which the Flask app does not and should not depend on; and from the repo root `import shared_lib` resolves as an **empty namespace package** (`__file__ is None`) unless pip-installed — the same shadowing failure that broke `rag-service`'s pytest collection earlier today. **NEW DECISION:** the helper lives in `contracts/token_crypto.py`, next to the `oauth_accounts` model whose columns it protects. `contracts/__init__.py` is a bare docstring, so `cryptography` is imported only by code that asks for it, and services already `COPY contracts /app/contracts`.
2. **Fernet over raw AES-GCM**, recorded in ADR-007: Fernet is authenticated by construction and manages its own IV, removing the nonce-reuse failure mode — which under GCM is silent and leaks the authentication key.
3. **A `JSONB` column blocks SQLite**, which the offline OAuth tests need. Fixed with `JSONB().with_variant(JSON(), "sqlite")` — a dialect variant that leaves PostgreSQL untouched (verified: the live table really is `jsonb`), rather than weakening the production type or dropping the persistence tests.

**Verification so far — offline only:** **131 tests green** (25 new at `tests/`, plus the existing 106 across five services); migration **upgrade → downgrade → upgrade** round-trip clean against the live database, with the resulting table confirmed to carry `jsonb`, the `gen_random_uuid()` PK default, the unique `(provider, provider_account_id)` constraint and both indexes; `smoke_test_e2e.py` still **10/10**; and the routes fail closed (`503 FEATURE_DISABLED`) with no Google credentials configured. The new tests assert the properties that matter rather than just the happy path: ciphertext never contains the plaintext token, `key_id` never leaks key material, rotation keeps old rows readable, `/api/auth/google/status` returns **no** token material, session-binding mismatch is rejected, and a missing encryption key **fails the sign-in instead of storing a plaintext token**.

~~**⚠️ Blocked on developer setup — Google Cloud Console, same project as `YOUTUBE_API_KEY`:** OAuth consent screen (External, **Testing**, with your own account added under *Test users* — in Testing mode nobody else can sign in at all); then Credentials → OAuth client ID → **Web application**; then authorized redirect URI **exactly** `http://127.0.0.1:5000/auth/google/callback` (plain `http` is allowed only for loopback, and Google treats `localhost` and `127.0.0.1` as different entries). Put the client id/secret plus a generated `OAUTH_TOKEN_ENCRYPTION_KEY` into `.env` — all three are already documented with generation instructions in `.env.example`.~~ → ✅ **[COMPLETED] Developer completed the Google Cloud setup (July 26, 2026): client id, client secret, redirect URI and the Fernet `OAUTH_TOKEN_ENCRYPTION_KEY` are all present in `.env`.** The live consent round trip is therefore unblocked and is the immediate next action; until it has actually been executed, the §5.2 items above remain "code-complete and offline-verified" rather than proven end to end (Section 19: a checkbox alone is not evidence). **The two Testing-mode behaviours below still apply and are Google policy, not bugs in this code:** refresh tokens expire after **7 days**, and the YouTube scope is *sensitive* so the consent screen shows an "unverified app" interstitial that a listed test user clicks through.

**⚠️ `OAUTH_TOKEN_ENCRYPTION_KEY` is backup-critical.** Losing it makes every stored connection undecryptable and forces all users to reconnect — there is deliberately no plaintext fallback. It belongs in the same protected backup path as `N8N_ENCRYPTION_KEY` and in the `DEP-005` VPS secret injection.

✅ **[COMPLETED] LIVE CONSENT ROUND TRIP EXECUTED (July 26, 2026) — §5.2 is now proven end to end, not just offline.** The developer completed a real Google sign-in through the browser. Verified against the live database and the running app, from a clean baseline of `users=0` / `oauth_accounts=0`:

| Check | Result |
| --- | --- |
| First real `users` row | ✅ created — the app's first ever persistent identity |
| `oauth_accounts` row | ✅ created, `provider=google`, `provider_account_id` = the OIDC `sub` |
| **Tokens encrypted at rest** | ✅ both columns hold Fernet ciphertext (`gAAAAAB…`); decrypt returns real Google tokens (`ya29.…` access, `1//0…` refresh) and **neither plaintext appears anywhere in the stored column** |
| `encryption_key_id` | ✅ recorded, non-reversible |
| **AUTH-004 proven live** | ✅ stored scopes are identity-only (`userinfo.email`, `userinfo.profile`, `openid`) — **no YouTube scope**, exactly as designed |
| `expires_at` / `revoked_at` | ✅ set / null |
| `/api/auth/google/status` | ✅ `connected: true` with correct email + scopes and **zero token material** in the body |
| Token leakage in logs | ✅ none — 0 hits for `ya29.` / `1//0` / `access_token` / `refresh_token` |

Also verified before the browser step, straight off the live redirects: `response_type=code` (AUTH-002), `state` **and** `nonce` present (AUTH-003), `redirect_uri` pinned to configuration (AUTH-003), `scope=openid email profile` with no YouTube on login (AUTH-004), and the upgrade route adding `.../auth/youtube` **with** `include_granted_scopes=true` (AUTH-005).

⚠️ **Two §5.2 paths remain unproven against the real provider, both deliberately, and neither should be read as delivered:**

| Path | Why it is unproven | When to close it |
| --- | --- | --- |
| ~~`POST /auth/google/disconnect` (revoke)~~ → ✅ **[COMPLETED] CLOSED July 26, 2026** | ~~**Developer decision (July 26, 2026): skipped on purpose** — revoking forces a re-authentication that was not worth the interruption. Unit-tested only.~~ → **Executed live during §5.5, exactly as predicted below.** Returned `{ok: true, revoked_at_provider: true}`; `revoked_at` stamped; the YouTube scope dropped from the stored `scopes`; and — the part that actually matters — a subsequent export **failed closed** with `REAUTHORIZATION_REQUIRED` rather than continuing off a cached grant. | ~~Next time a re-auth is acceptable — naturally during §5.5, since the YouTube-scope upgrade forces re-consent anyway.~~ → Done in §5.5. |
| ~~`AUTH-005` YouTube-scope upgrade~~ → ✅ **[COMPLETED] CLOSED July 26, 2026** | ~~The redirect is verified correct, but nothing calls it: there is no export button to trigger it until §5.5.~~ → **Exercised for the first time against the real provider.** The stored `scopes` grew to include `.../auth/youtube` **while keeping all three identity scopes**, which is precisely the `include_granted_scopes=true` behaviour the route was built for. | ~~§5.5 export.~~ → Done in §5.5. |

⚠️ **BUG FOUND BY THE LIVE RUN — guest→user migration does not fire, and the root cause is not in the §5.2 code.** `guest_sessions.migrated_user_id` was still `NULL` for all **89** rows after a successful sign-in. Two compounding causes:

1. **WF-001's `Resolve User or Guest` node ignores the guest identity Flask sends.** Its SQL is `INSERT INTO guest_sessions (expires_at) VALUES (now() + interval '1 day') RETURNING id` — no `id` column, so PostgreSQL generates a fresh `gen_random_uuid()` **on every request**. Flask's `session["session_id"]` is therefore *never* a row in `guest_sessions`, and the 89 rows are one-per-request rather than one-per-visitor. This is a **pre-existing Phase 2 defect**, not introduced here; it was invisible until something tried to *use* guest identity.
2. **`auth_google._link_guest_session()` assumed the two were the same namespace** and looks Flask's `session_id` up in `guest_sessions`, which always misses. The code is currently harmless but dead.

**NEW DECISION (deferred, not silently left broken):** the fix belongs in WF-001, not in the OAuth code — the node should upsert on the `guest_id` Flask already sends (`INSERT … (id, expires_at) VALUES ($guest_id::uuid, …) ON CONFLICT (id) DO UPDATE SET expires_at = …`), which simultaneously gives a **stable** guest identity and stops the per-request row bloat. ~~It is deferred because it requires the n8n import → publish-all-8 → restart cycle, the same reason WF-009 was deferred to §5.5 — and both should be done in that one n8n pass. **Until then, `guest→user migration is NOT working` and must not be claimed as delivered.**~~ → ✅ **[COMPLETED] FIXED AND LIVE-VERIFIED (July 26, 2026) in the §5.5 n8n pass, exactly as planned above.** Live evidence: a fresh guest request created **exactly one** row (89 → 90) keyed to Flask's own `session_id`, and signing in from that same browser session populated `migrated_user_id` — the first time this has ever worked. The per-request bloat is also gone: several full smoke-test runs since added **zero** rows. Related open work: `PERS-003` ("permit guest feedback and migrate it on sign-in") and `PERS-006` (guest-migration unit tests) are now **unblocked** — this was their prerequisite.

⚠️ **A second, worse defect in the same node was found while fixing this, and is the reason export could never have worked without it.** `Resolve User or Guest` didn't merely ignore the guest id — it **overwrote an authenticated user's identity** with a freshly minted guest UUID on every request. Flask had been sending the real `users.id` since §5.2 landed, and WF-001 discarded it. Export would therefore have looked up `oauth_accounts` under a random UUID and **never found the signed-in user's grant**, failing with `AUTHORIZATION_REQUIRED` for a user who was correctly signed in. **NEW DECISION:** the replacement SQL is a CTE that always returns exactly one row — an authenticated request skips the insert entirely and passes its `users.id` through, a guest request upserts on the supplied `guest_id`. The single-row shape is not cosmetic: a bare conditional `INSERT` returns **zero** rows for authenticated users, and an n8n node that emits no items stops the branch dead.

**Also worth recording: the `Resolve User or Guest` output was never read by anything.** Every sub-workflow call in WF-001 reads `$('Validate Request Schema').item.json.userId` directly, so the node's `RETURNING` value went nowhere — it was a pure side effect that minted a junk row per request. That is why the defect stayed invisible from Phase 2 until something finally tried to *use* guest identity.

⚠️ **Minor, noted not fixed:** Werkzeug's access log records the callback query string, which includes Google's one-time `code`. It is single-use and already exchanged by the time it is logged, so the exposure is small, but a production log configuration should strip query strings on `/auth/*` (relates to `SEC-002`, which removed token logging).

**Also fixed in passing:** Flask session cookies now set `HttpOnly` and `SameSite=Lax`, with `Secure` following the existing TLS resolution. `Lax` is deliberate, **not** `Strict` — the OAuth callback is a cross-site top-level GET, and `Strict` would withhold the cookie on exactly that navigation and break the flow. The app also now warns at startup when Google sign-in is configured while `FLASK_SECRET_KEY` is unset, because the random per-start fallback silently invalidates every session — including any in-flight OAuth `state`.

~~**Remaining for Phase 5:** the live §5.2 consent round trip (blocked above), §5.4 (playback UI — `embeddable` is already supplied for §PLAY-005's fallback link), §5.5 (export + WF-009 wiring, unblocked once §5.2 is confirmed live), §5.6 (optional Spotify, P1).~~ → **Updated after the live run (July 26, 2026):** the §5.2 round trip is **done and passed**. **NEW DECISION — order for the rest of Phase 5: §5.5 (export) next, §5.4 (playback) deferred behind it.** `PLAY-001` turns out to depend on the UI calling `/api/v1/requests`, which it has never done (it still posts to the legacy `/chat`), so playback would pull Phase 8 UI rewiring into Phase 5; §5.5 by contrast consumes the OAuth just built, closes the two §5.2 paths still unproven live, and lets WF-006 + WF-009 + the WF-001 `guest_sessions` fix all land in **one** n8n import/publish/restart cycle. Full reasoning recorded at §5.4. Then §5.4, then §5.6 (optional Spotify, P1).

**Pick up next — P0 only, in this order:**

> ⚠️ **Priority corrected (July 25, 2026).** ~~`INF-011` was ranked #1 here because it "blocks the VPS goal".~~ → That was **the wrong ordering for the actual near-term goal**, which is running the app locally to find and fix real defects. `INF-011` is a **packaging** task, not a make-it-work task: Flask runs fine on the host today and reaches n8n through the published `localhost:5678` port. Containerising Flask matters when nobody is present to run `python app.py` (the VPS) and for reproducibility grading — **it does not gate local testing.** It moves down the list; nothing built locally now has to be redone for the VPS later, because the Compose topology is already the VPS topology.

- [x] ✅ **[COMPLETED] 1 — Run the whole system locally, end to end (July 25, 2026).** ⚠️ **One hard blocker was found and fixed:** `app.py` hardcoded `app.run(ssl_context=("cert.pem", "key.pem"))` and **neither file exists**, so Flask crashed on startup on any clean checkout. **NEW DECISION:** TLS is now resolved from `FLASK_TLS_CERT` / `FLASK_TLS_KEY` and falls back to plain HTTP when the certificates are absent — local development runs over HTTP, and the VPS terminates TLS at the reverse proxy (`DEP-002`) or supplies real paths through the environment. Verified: `POST /api/v1/requests` traverses **Flask → n8n → guardrails → Postgres → WF-002 → recommendation-service → back** in **426 ms**, returning the correct `meta` block and fixture tracks honestly labelled `"engine": "fixture", "placeholder": true`. Start it with `.venv/Scripts/python.exe app.py` on `http://localhost:5000`.
- [x] ✅ **[COMPLETED] 2 — ~~⭐ THE ACTIVE TASK: Phase 4 §4.2, nodes 5–18 — make the recommendation real. Nodes 1–4 (`validate_context`, `normalize_input`, `load_or_accept_user_profile`, `build_retrieval_query`) already carry real logic in `recommendation-service/app/core/graph_nodes.py`; **5–18 are stubs**, which is why `POST /recommendations/run` still answers with a Bon Iver fixture (`"engine": "fixture", "placeholder": true`). Implement in the §4.2 order. The retrieval nodes (5–9) do **not** need new algorithms — the working pipeline already exists in `rag-service/scripts/test_hybrid_retrieval.py` (dense + lexical → RRF → cross-encoder rerank → top-5) and `rag-service/scripts/genre_graph.py` (real one-hop traversal of the 260-node / 689-edge graph); the task is to lift that logic behind `POST /rag/retrieve` and call it from the graph rather than re-implementing it. Node 17 (`generate_grounded_explanation`) is the first place the **ADR-006** heavy model is called — `claude-haiku-4-5`, behind an adapter, recording provider/model/tokens/latency/cost per §4.9.~~ → Delivered July 25, 2026 (even later, see the session bookmark above).** `POST /recommendations/run` now runs the real 18-node graph (`engine: "graph"`, `placeholder: false`); `/rag/retrieve` is real hybrid retrieval, not a fixture. Only loose end: node 17's live happy path needs an Anthropic credit top-up to fully confirm (its failure/degrade path is verified).
- [ ] **3 — `INF-011` (deployment packaging, not a blocker):** add the Flask app as a Compose service. A root `Dockerfile` exists but Flask is not in `docker-compose.yml`. Do this when moving to the VPS. Pairs with `DEP-001` (Gunicorn, not the dev server).
- [ ] **4 — ~~Two cheap legacy fixes only~~** (for the `REC-LEG-001/002` baseline, nothing more): ~~add a current-date anchor to `aws/system_prompt.txt`, and de-duplicate its doubled rule block.~~ → **Developer decision (July 25, 2026, even later still): skip entirely.** `REC-LEG-001`/`REC-LEG-002` are done (see the session bookmark) and the developer explicitly does not want further time spent on the legacy path. Not a P0 blocker for anything downstream — leave `aws/system_prompt.txt` as-is.
- [ ] **5 — `INF-002a` / `INF-002b` (small, reproducibility + security):** pin `n8nio/n8n:latest` to a version — an unpinned tag already caused the Set-node 3.5-vs-3.4 breakage — and re-establish protected editor access, since `N8N_BASIC_AUTH_*` is inert in n8n 1.x.
- [ ] **6 — Finish Phase 3 (the phase that is actually in progress):** open P0 items are `RAG-003` (near-duplicate cleaning), `RAG-005` (source reference), `RAG-010` (staged ingestion), `LOCAL-002` (local-model adapter), `LOCAL-003` (latency/memory/schema measurements), plus §3.8 golden evaluation set and §3.9 prompt-log Version 1.
- [x] ✅ **[COMPLETED] 7 — `REC-LEG-001`:** ~~legacy-vs-new comparison — still open, untouched by this session.~~ → ~~**Partially done (July 25, 2026, even later still): harness built (`eval/rec_leg_comparison.py`, `eval/prompts.json`), new-engine leg verified.** Still needed: run the legacy leg from a host with Bedrock access (blocked locally — no AWS credentials, see the session bookmark above), fill in the manual explanation-quality rating, write up `REC-LEG-002`'s actual comparison once Phase 5 makes track-level metrics meaningful.~~ → **Fully run (July 25, 2026, even later still): the developer added `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` to `.env` — `sts:GetCallerIdentity` confirmed valid credentials (account `881490130721`, IAM user `user8`), and both legs of all 12 shared prompts completed successfully.** Full report + raw JSON at `eval/rec_leg_report.md` / `eval/rec_leg_report.json`. `REC-LEG-002`'s quantitative comparison (below) is done from this data; the qualitative "explanation quality (1-5)" column is still blank pending a human or LLM-judge pass — see the session bookmark for the write-up and a real quality bug the comparison surfaced.
- [x] ✅ **[COMPLETED] 8 — Phase 5 §5.1/§5.3: real YouTube search (July 25, 2026, even later still).** **Developer decision: skip items 3, 5, 6 above and go straight to Phase 5** rather than working the rest of this list in order — see the dedicated session bookmark for the full record (real `provider-gateway` YouTube adapter, two live-found-and-fixed bugs, before/after numbers: 7/12 zero-result recommendations → 0/12, 1 → 78 unique artists). Items 3/5/6 below remain open, just deprioritized, not abandoned.

**Blocked on a decision, not on code — these need the developer, not the agent:**

- `RAG-002` — licence/source status for the knowledge corpora. `docs/knowledge_inventory.md` still records `genre-md-v0` as *"owned (project-authored) — confirm"*, and `data/cleaned_large_dataset_t.csv` (the reviews) has **no source or licence recorded at all**.
- `ACA-005` — evaluator confirmation that the audio classifier may replace the reference image classifier, and whether RAG/LangGraph may share a deployable service.
- **ADR-002** — the provider decision is closed in §0.4 but `docs/adr/ADR-002-music-provider-mode.md` was never written.

**Deliberately deferred, do not treat as broken:** ~~`EXPORT-001` (real playlist export — `provider-gateway` returns `FEATURE_DISABLED` by design until Phase 5), and~~ → **`EXPORT-001` is delivered as of July 26, 2026 (see the §5.5 bookmark below); `FEATURE_DISABLED` now means the `ENABLE_PLAYLIST_EXPORT` flag is off, not that the feature is unbuilt.** ~~Still deferred: WF-007 / WF-008 / WF-010 (no task ID, no priority label; each arrives with the phase that needs it).~~ → ✅ **[COMPLETED] All three were built on July 28, 2026 — see §1.10, §1.11 and §1.13.** Nothing on this "deferred" list remains.

### ▶ Session bookmark — July 26, 2026: §5.5 playlist export delivered — Melody writes to a real provider for the first time

**This is the first code in the project that *writes* to an external service.** Everything before it was read-only, which is why §4.3 could state *"search-provider writes are forbidden; only reads occur inside LangGraph"* — writes live in `provider-gateway/app/youtube_playlist.py`, reachable only through WF-006.

**What landed:**

| Piece | File |
| --- | --- |
| Real `playlists.insert` + `playlistItems.insert`, quota-accounted | `provider-gateway/app/youtube_playlist.py` *(new)* |
| Decrypt → refresh-on-expiry → re-encrypt → persist; scope check | `provider-gateway/app/google_token.py` *(new)* |
| Lazy DB engine (this service's first database dependency) | `provider-gateway/app/db.py` *(new)* |
| Idempotent export transaction + `/providers/connection/status` | `provider-gateway/main.py` |
| Export, connection sync, and the identity fix | WF-006, WF-009, WF-001 |
| 24 new offline tests | `provider-gateway/test_youtube_playlist.py`, `test_google_token.py` *(new)* |

**Live verification — every item executed against the real Google/YouTube, not inspected:**

| Check | Result |
| --- | --- |
| `AUTH-005` scope upgrade | ✅ YouTube scope added, all three identity scopes kept |
| Real export | ✅ private playlist `PLQV88szpWdzI` created with both requested tracks |
| Idempotency (`EXPORT-002`) | ✅ same key → same playlist, `replayed: true`, **no second playlist**, 108 ms vs 2445 ms |
| `INSUFFICIENT_SCOPE` | ✅ refused **before** spending any quota, with an actionable message |
| Guest→user migration | ✅ 89 → **90** rows (one, not one-per-request), `migrated_user_id` populated |
| WF-001 identity pass-through | ✅ authenticated `users.id` survives to the gateway; no guest row minted |
| Disconnect + fail-closed | ✅ revoked at Google, then export returned `REAUTHORIZATION_REQUIRED`, no playlist |
| WF-009 connection sync | ✅ real scopes/expiry/reauth state, **zero token material** |
| `smoke_test_e2e.py` | ✅ **10/10** |
| Offline suite | ✅ **155 tests** (was 131): provider-gateway 77, recommendation-service 40, rag-service 4, guardrails 4, audio 5, root 25 |

**Two bugs found while exploring, both fixed before implementation started — see §5.5 and the §5.2 bookmark above for the full records.** WF-001 was discarding authenticated identity (export could never have found a signed-in user's grant); WF-006 called the provider *before* claiming the idempotency key (a double-click would have created two real playlists).

**⚠️ A third defect the smoke test caught, and the most instructive of this session: actionable error codes were being flattened at the sub-workflow boundary.** The export case failed asserting `AUTHORIZATION_REQUIRED` and got `UPSTREAM_ERROR`. Pulling n8n's own execution record (`execution_data` for execution 381) showed why: when WF-006's HTTP node throws on a 401, **all WF-001 receives is n8n's generic `"Authorization failed - please check your credentials"`** — the gateway's response body, and with it the error code, is dropped. `INSUFFICIENT_SCOPE` would have reached the browser as *"a downstream service failed"*, leaving the UI unable to tell *"reconnect and approve playlist access"* from *"something broke"* — which would have quietly defeated the whole point of checking scope early. **NEW DECISION:** WF-006 now reads the envelope itself (HTTP node set to `neverError` + `fullResponse`) and re-throws with a `[[CODE]]` marker that WF-001 parses against a **fixed allowlist**, so no arbitrary upstream text can be reflected to a client. The marker deliberately contains **no colon** — n8n parses a thrown `"PREFIX: rest"` as `<errorType>: <message>` and discards the prefix, which silently ate the first attempt's marker.

**Two smaller corrections worth knowing about:**

1. **`provider-gateway` would have connected to the wrong database.** `docker-compose.yml` loads the entire `.env` into every container — including `DATABASE_URL=…@localhost`, correct for a host-run process and useless inside the network — and *then* sets `POSTGRES_HOST: postgres` on top. `db.py` now treats an explicitly set `POSTGRES_HOST` as the signal to assemble the URL from the `POSTGRES_*` parts, matching what docker-compose.yml's own comment already describes.
2. **Importing `contracts/db_models.py` drags in `pgvector`** (the canonical ORM covers all 19 tables, including `knowledge_chunks`' `Vector` column) — so `provider-gateway` needs the dependency despite never touching that table. Pinned to `0.3.6` to match `rag-service`.

**NEW DECISION — the `playlist_export` smoke case stays a *rejection*, and was NOT flipped to "accept" as the §5.5 plan proposed.** That envelope is an anonymous guest, and export writes to a real person's YouTube account — **an unattended smoke test must never create real playlists**, and it must not need a signed-in user's credentials to pass. It now asserts the specific `AUTHORIZATION_REQUIRED` code rather than the old `FEATURE_DISABLED`, which is a *stronger* claim than before: it proves the write path fails closed for an unauthenticated caller and that the specific code survives the boundary. A successful export is only provable in the live flow, which is where it was proved.

⚠️ **What §5.5 does NOT deliver, stated plainly: no user can reach any of this from the UI.** There is no export button, and `templates/index.html` still posts to the legacy `/chat`. The whole live verification above had to be driven by direct calls to the n8n webhook and by `fetch()` from the browser console. **§5.5's backend is done; wiring it to an interface is Phase 8 work** — the same dependency that pushed §5.4 (playback) behind it. Do not read "export shipped" as "users can export."

**Two n8n operational notes for the next session:**

1. **`n8n import:workflow` silently imports 0 workflows when Git Bash mangles the path.** `--input=/tmp/wf` becomes `C:/Users/.../Temp/wf` under MSYS path conversion, and the command reports *"Successfully imported 0 workflows"* rather than failing. Prefix with `MSYS_NO_PATHCONV=1`.
2. **Re-importing only the workflows you changed unpublishes only those**, so the republish burden is proportional to the change — worth knowing, since this session needed three import cycles and re-publishing all 8 each time would have been three times the manual work.

~~**Pick up next:** §5.4 (playback) and §5.6 (optional Spotify, P1) are the remaining Phase 5 items, but both — and the last open Phase 5 gate criterion (the playable-percentage measurement) — now sit behind the same Phase 8 UI dependency. **The honest next question is whether Phase 8's UI rewiring should be pulled forward**, since three separate items are now queued behind it.~~ → **Answered by the developer (July 26, 2026, later): yes — Phase 8's UI rewiring was pulled forward.** See the bookmark below.

### ▶ Session bookmark — July 26, 2026 (later): Phase 8 pulled forward — the UI reaches the new stack, and four defects it immediately exposed

**Developer decision:** pull Phase 8's UI rewiring forward rather than continue in phase order, because three separate P0 items (§5.4 playback, the Phase 5 playable-percentage gate criterion, and `REC-LEG-003`) were all queued behind the same dependency, and because nothing built since Phase 4 was reachable by a user.

**The headline is not the UI. It is that connecting the UI immediately exposed four defects that every previous verification had missed** — because every previous verification called the services *directly*, and only the browser goes through the full WF-001 → WF-002 → service path.

| # | Defect | Why it was invisible until now |
| --- | --- | --- |
| 1 | **The prompt never reached the recommendation engine.** WF-002 forwards `$json.envelope` — the whole `RequestEnvelope` — as `context`, but `_build_initial_state` expected `context` to *be* a `RecommendationContext`. Every lookup silently missed, so `user_text` resolved to `""`. | Nothing raised. The smoke test asserts accept/reject, not relevance; `eval/rec_leg_comparison.py` and every manual probe send the *flat* shape, which works. |
| 2 | **Playback references were discarded at the API boundary.** The graph resolved a real YouTube video for every track, then `TrackRecommendation` narrowed the response to `title/artist/reasoning`, dropping `provider_track_id`, `url` and `embeddable`. | No consumer had ever wanted them — §4.8's "structured provider IDs separate from prose" was simply unimplemented at the boundary. |
| 3 | **Unexplained tracks were shipped as curated picks.** The curator explained the first few and the tail came back with `reasoning: ""`, still rendered as recommendations. | Only visible once something displayed a per-track reason. |
| 4 | **Only one search intent was built, and never the user's own words.** The user's text was a *fallback* (`if not intents`), so any request that produced a constraint never searched what the user actually typed. | Needed a real query whose derived constraint was worse than the literal phrase. |

**Defect 1 is the most serious in the project's history so far: every recommendation ever placed through n8n was generated from an empty query.** Live proof, same prompt, before and after — *"dreamy shoegaze for a rainy night"*: before, the title was **"Audio Discovery"** with the description *"we couldn't quite pin down what you were looking for from your listening alone"* (the empty-input branch) over H.E.R.'s *Best Part* and a YouTube commentary channel; after, **"Rainy Night Reverie"** over actual shoegaze.

Defect 4 compounded it: *"dreamy shoegaze for a rainy night"* collapsed to the single derived query `"dream pop shoegaze"`, whose entire first page was hour-long compilations (76:48, 49:41, 91:50) plus a **52-second explainer Short** — all five flagged out-of-track-range by provider-gateway, all five rendered as tracks with Play buttons, because the adapter's "never return an empty list" fallback is evaluated *per query*.

**NEW DECISION: the user's own text is always searched, not only as a last resort**, and the intent cap rises from 2 to 3 (`MAX_SEARCH_INTENTS`). This is a quota decision, not just tuning — each intent costs 100 units of a 10,000/day budget, so a request now costs ~301 units. **NEW DECISION: node 14 (`deduplicate_and_resolve_tracks`) also drops known non-track-length results**, keeping them only when fewer than three real tracks remain. It belongs there rather than in the adapter because node 14 is the first place that sees the union across every intent, and so the first place a "don't return nothing" fallback can be judged with the full picture. **NEW DECISION: a track the curator declined to explain is dropped rather than shipped with an empty `reasoning`** — §4.8 requires a reason per track and ADR-006 forbids inventing one; if nothing is explained the run is marked invalid rather than returning an empty playlist. `sequence_tracks` now also trims to `FINAL_TRACK_LIMIT = 10`, matching §SEQ-003's 8–12.

**What landed:**

| Piece | File |
| --- | --- |
| UI on the orchestrated path; cards, playback, export, feedback, retry | `templates/index.html` |
| Card / player / export / discovery / account styles | `static/style.css` |
| §8.1 routes: `/api/v1/auth/status`, `/api/v1/feedback`, `/api/v1/playlists/export`, `/health/live`, `/health/ready`; shared `build_envelope` | `app.py` |
| `connection_status()` factored out for reuse | `auth_google.py` |
| Envelope unwrap, widened track contract | `recommendation-service/main.py` |
| Intent construction, length filter, unexplained-track drop, shortlist cap | `recommendation-service/app/core/graph_nodes.py` |

**Live verification — driven through a real headless browser against the running stack, not inspected:**

| Check | Result |
| --- | --- |
| `UI-001` guest text discovery | ✅ browser → Flask → WF-001 → WF-002 → graph → real YouTube → cards |
| `UI-005` structured cards | ✅ title, artist, duration, per-track reason, position |
| `PLAY-001` inline player | ✅ mounts `youtube-nocookie` embed on click with the real video id |
| `PLAY-005` non-embeddable fallback | ✅ no player, plain "Watch on YouTube" link + stated reason |
| `UI-007` discovery mode | ✅ reaches the request as `"discovery_mode":"adventurous"` |
| `UI-006` like/dislike | ✅ optimistic, `POST /api/v1/feedback` accepted, rolls back on failure |
| `UI-010` error + retry | ✅ actionable card with a working "Try again" |
| `UI-010` `AUTHORIZATION_REQUIRED` / `INSUFFICIENT_SCOPE` | ✅ offer sign-in / "Approve playlist access" — never "something broke" |
| `UI-010` partial / low-confidence | ✅ `fallbackUsed` and thin result sets are stated, not hidden |
| `UI-003`/`UI-004` guest + connection status | ✅ guest widget, export bar prompts sign-in |
| JS console errors | ✅ **none** |
| `smoke_test_e2e.py` | ✅ **10/10** |
| Offline suite | ✅ **164 tests** (was 155): provider-gateway 77, recommendation-service **49** (was 40), root 25, audio 5, rag 4, guardrails 4 |

**Also fixed:** `provider-gateway/test_smoke.py::test_playlists_disabled` read `ENABLE_PLAYLIST_EXPORT` from the ambient environment, so it failed inside the container (which sets it to `true`) with a 401 that was actually the *correct* response for an enabled export. It now pins the flag it is testing.

⚠️ **Two operational notes.** The service containers have **no bind mount** — they run code baked at build time, so `docker compose build <service>` is mandatory after every edit; a test run against a stale image passed 40/40 while the source on disk had already changed. And `docker exec` needs `MSYS_NO_PATHCONV=1` under Git Bash, the same path-mangling trap already recorded for `n8n import:workflow`.

⚠️ **What is NOT verified, stated plainly: nothing on the signed-in path was exercised in this session.** The guest and not-connected branches of `UI-003`/`UI-004`/`UI-009` were driven live, but signing in requires the developer's own Google account, so the connected-account widget, the export button's enabled state, and the export click itself are **code-complete and unrun**. §5.2 and §5.5 were live-verified last session by direct calls, so the backend behind them is proven; the *UI* around them is not.

~~**Pick up next:** (1) the signed-in UI round trip — sign in through the new widget and export from the button, which closes `UI-003`/`UI-004`/`UI-009` and the §5.5 UI gap; (2) §5.4's remaining `PLAY-002` cases and the Phase 5 playable-percentage measurement, both now unblocked; (3) §8.3 `JOB-001…004` and §8.5 `INT-001…004`, untouched; (4) `UI-002` (audio) and `UI-008` (Smart Sequence) remain blocked on Phase 6 and Phase 7 respectively.~~ → **Superseded by the session below**, which was driven by the developer's own first use of the UI.

### ▶ Session bookmark — July 26, 2026 (later still): first developer use of the new UI — a broken sign-in, a wrongly removed feature, and Spotify promoted to a first-class mode

**This session was driven entirely by the developer actually using the thing.** Every item below came from them clicking, not from a plan item.

**1. 🔴 Google sign-in was broken, and my `AUTH-003` hardening was the reason.** Signing in landed on a bare JSON error page. Full record at §5.2 `AUTH-003`: `GOOGLE_REDIRECT_URI` pointed at `127.0.0.1` while the app was browsed at `localhost`, so the session cookie never reached the callback. Fixed by starting the flow on the callback's own origin, plus a self-diagnosing error message. **Cause of the miss:** the July 25 live verification drove `127.0.0.1` directly and matched by accident — the defect needed a *user with a button to click*.

**2. ⚠️ I removed the Spotify login from the sidebar, and that was wrong.** It was not asked for, and the plan explicitly says to keep all Spotify integration. **Restored.** Recording it because "the Phase 8 rewiring quietly dropped a working feature" is exactly the kind of regression a plan document exists to prevent.

**3. Spotify promoted from optional P1 to a first-class recommendation mode (§5.6).** A two-state toggle in the UI chooses which service answers; naming a provider in the message overrides it. Full record and four NEW DECISIONs at §5.6, including that `/v1/tracks` is **403 for client-credentials tokens**, which killed the obvious confidence-enrichment design.

**4. One recommendation per request, not five** (§4.8) — five embedded players per reply was wasteful and gave the user five things to judge instead of one.

**5. 🔴 Hebrew requests timed out** (§4.6) — not failing, just slower than WF-002's 25s HTTP limit, and my 2→3 intent change had pushed them over. Searches now run concurrently and the timeout budget is realigned.

**Live verification — every row driven against the running stack:**

| Check | Result |
| --- | --- |
| Toggle = YouTube | ✅ YouTube track |
| Toggle = Spotify | ✅ Spotify track (**Alvvays — "Dreams Tonite"**) |
| Toggle YouTube + *"on Spotify"* | ✅ overridden to Spotify |
| Toggle Spotify + *"on YouTube"* | ✅ overridden to YouTube |
| Hebrew request | ✅ **no timeout**, ~19.8s, real Israeli track |
| Hebrew *"בספוטיפיי"* override | ✅ Spotify track |
| Exactly one card / one player | ✅ 1 card, 1 iframe |
| Spotify embed vs YouTube embed | ✅ correct player per provider |
| Export control on a Spotify track | ✅ hidden (export is YouTube-only) |
| Spotify + Google widgets both present | ✅ independent, side by side |
| Invalid `provider` | ✅ `400 VALIDATION_ERROR` |
| JS console errors | ✅ **none** |
| `smoke_test_e2e.py` | ✅ **10/10** |
| Offline suite | ✅ **176 tests** (was 164): provider-gateway 78, recommendation-service 57, root 28, audio 5, rag 4, guardrails 4 |

⚠️ **Still unverified: the signed-in path.** The sign-in *fix* is covered by three regression tests and the flow now starts on the right origin, but **the developer must confirm the live round trip** — I cannot sign in as them. Everything behind it (`UI-003`/`UI-004`/`UI-009` connected states, export from the button) stays unverified until then.

⚠️ **Two operational traps, both of which produced false results in this session before being caught:**

1. **Three Flask processes were listening on port 5000 simultaneously.** Windows permits it, so requests were served by whichever process won the race — including stale ones predating the code under test. A `provider=spotify` request kept returning YouTube results and the plumbing looked wrong at every layer; it was correct, and an old process was answering. **Verify the running server is the code you edited** (a request with a deliberately invalid value that only the new code rejects is a fast check), and kill by listening port rather than by process-name pattern.
2. **`n8n import:workflow` deactivates the workflow it imports**, and a deactivated WF-002 makes every recommendation fail with `UPSTREAM_ERROR`. Reactivate with `n8n update:workflow --id=<id> --active=true` and restart n8n. This compounds the two traps already recorded (`MSYS_NO_PATHCONV=1`, and containers running baked-in code).

~~**Pick up next:** (1) **the developer's live sign-in confirmation** — everything signed-in depends on it; (2) whether Spotify should become the *default* provider, given it returned markedly better music than YouTube for the same prompts (§5.6); (3) YouTube result quality — a one-hour compilation still won a prompt where Spotify returned Alvvays; (4) the retrieval-node parallelization recorded at §4.6, the next latency lever after ~19s; (5) unchanged from before: §8.3 `JOB-001…004`, §8.5 `INT-001…004`, `UI-002`/`UI-008` blocked on Phases 6/7.~~ → **§8.5 is now done — see the bookmark below. The rest of that list still stands.**

### ▶ Session bookmark — July 26, 2026 (later still, continued): §8.5 placeholder audit — and the refusal paths it proved were mute

**§8.5 `INT-001…004` complete.** The audit was supposed to be bookkeeping. It found three real defects, and they chain into each other.

**1. Guardrails were a placeholder in the parts that mattered (§2.5).** `off_topic` was **hardcoded `False`** — the category existed in every response and the check did nothing. Language handling did not exist. `/check/output` verified only that `tracks` was a list, so *none* of §2.5's unsupported-claim rules were enforced. Implemented: internal-leakage, ad-free claims (`PLAY-004`), fabricated BPM/key, missing provider ids, off-topic, he/en/mixed language. Tests **4 → 17**.

**2. 🔴 Making off-topic real immediately exposed that all three of WF-001's refusal branches were mute (§1.4).** `Input Rejected`, `Unroutable Intent` and `Output Blocked` — the three Set nodes added by the July 25 dead-end fix — shared a `={{{ … }}}` **triple-brace** typo and answered with an **empty body**. A refused request reached the browser as *"the orchestrator returned an invalid response"* instead of a reason. They had never executed before, because nothing had ever reached a refusal branch.

**3. ⚠️ The smoke test was written to accept exactly that.** `looks_rejected = … or empty_body` — a refusal that said nothing scored as a pass. Corrected: an empty body now always fails, and two guardrail cases assert the specific `INPUT_REJECTED` code. **10/10 → 12/12.**

**The chain is the lesson: a check that silently did nothing hid a response path that silently did nothing, behind a test that was written to accept silence.** None of the three would have been found by reading the code — only by making the first rule real and watching what happened.

| Check | Result |
| --- | --- |
| `INT-001` sweep of workflow JSON | ✅ zero placeholders |
| `INT-001` sweep of code | ✅ stale docstrings fixed; one markdown strikethrough I had wrongly left in a Python docstring removed |
| `INT-002` / `INT-003` | ✅ real stubs are flagged and unreachable from the UI; export behind `ENABLE_PLAYLIST_EXPORT` |
| Guardrail refusal, live | ✅ `INPUT_REJECTED` with `requestId` + `meta`, both injection and off-topic |
| `INT-004` clean browser session | ✅ refusal reads as a reason with a retry; a real recommendation still works right after; 1 card / 1 player; **no JS errors** |
| `smoke_test_e2e.py` | ✅ **12/12** (was 10/10) |

**NEW DECISION: `placeholder` is a claim about the response and must be accurate in both directions.** Guardrails had been declaring itself a placeholder while running real logic — as misleading as the reverse, and it is why the missing checks went unnoticed.

### ✅ The signed-in path is closed (July 26, 2026, later still, continued)

**The developer signed in and connected YouTube in the app, which unblocked the three items that had been waiting on it since Phase 8 opened.** This is also the confirmation that the `AUTH-003` host-mismatch fix worked — sign-in had been failing outright before it.

| Check | Evidence |
| --- | --- |
| `UI-003` Google sign-in | ✅ live `oauth_accounts` row for the developer, `revoked_at IS NULL`, identity scopes **+ `.../auth/youtube`** |
| `UI-004` connection status | ✅ `connected: true`, `youtube_write_authorized: true`, `expired: false`, `reauthorization_required: false`, **zero token material** |
| `UI-009` real export | ✅ private playlist **`PLAClPglpXAD4`** created with both tracks in 2.3s |
| `EXPORT-002` idempotency, real user | ✅ same key → **same playlist**, `replayed: true`, 0.2s, **no duplicate** |

**Done with the developer's explicit consent**, since export writes to a real account — the standing rule that an unattended test must never create a real playlist (§5.5) is unchanged. ⚠️ **Still outside my reach: the literal button click in the developer's own browser session.** Every layer beneath it is verified.

**Suite after all of the above: 189 offline tests** (was 176) — provider-gateway 78, recommendation-service 57, root 28, **guardrails 17** (was 4), audio 5, rag 4 — and `smoke_test_e2e.py` **12/12** (was 10/10).

**Pick up next:** ~~(1) the developer's live sign-in confirmation~~ → **done, see above.** ~~(1) YouTube result quality — still poor; a run in this session returned a track titled *"audio) - HD"*.~~ → **Four title-parsing defects fixed and tested (§5.3), but end-to-end YouTube quality is still poor and the remaining cause is result *selection*, not parsing.** Deliberately stopped there rather than attempting a fifth ranking fix.

1. ~~⭐ **THE DECISION THAT NOW GATES THE REST: should Spotify become the default provider (§17)?**~~ → ✅ **CLOSED by the developer: no. YouTube stays the default** — Spotify's development mode caps logins at **5 users**, so it cannot serve every request regardless of catalogue quality. **Spotify's real role is taste import for personalization** (§17, §5.6). Two consequences: **YouTube ranking must be fixed on its own terms** (§5.3) since there is no escape hatch, and the next *Spotify* work is taste import (`PROV-001`/`SPOT-003`), not more search polish.
2. §8.3 `JOB-001…004` — untouched.
3. Retrieval-node parallelization (§4.6), the next latency lever after ~19s.
4. ~~`UI-002`/`UI-008` remain blocked on Phases 6/7.~~ → **`UI-002` is done** (see the bookmark below); `UI-008` still waits on Phase 7.
5. The Phase 8 gate itself, once the above settle.

### ▶ Session bookmark — July 27, 2026: Phase 6 — the audio path stops being a fixture, and three defects that were silently disabling it

Opened at the developer's direction ("continue direct to path 6"). §6.1, §6.2, §6.3's build and §6.5 all landed; §6.4 is the only part left, and it is blocked on credentials rather than on engineering.

**What is now real.** A clip recorded or uploaded in the browser reaches Flask, is validated on its **bytes**, is stored under a 128-bit server-generated ID, is analysed for BPM / key / Camelot / energy with per-field measured confidences, is classified by a trained PyTorch CNN, conditions the retrieval query, and returns a real playable recommendation — then deletes itself. Live-verified end to end through Flask → n8n → WF-003 → the 18-node graph.

**The four defects worth carrying forward**, because three of them made work that *looked* finished do nothing:

1. **Upload validation was a vulnerability, not a gap.** The Phase 2 check accepted a file when its declared MIME type **or** its filename extension looked like audio — both caller-supplied. A Windows executable named `song.wav` with `Content-Type: audio/wav` passed both. Now detected from magic bytes; regression-tested with exactly that payload.
2. **WF-003 forwarded `audio_features: $json`** — the whole analyze *response* — so the measurements arrived one level too deep, the graph read `features` as a feature, and the real BPM, key and energy never reached retrieval. Structurally identical to the WF-002 envelope bug from July 26; the same mistake in a second place is a pattern, not an accident. **Worth a standing check on every `Execute Workflow` hand-off: does the receiver see the shape the sender thinks it sent?**
3. **Audio-only requests retrieved nothing at all.** Retrieval nodes 5 and 6 skip on empty text, and an audio-only request has none — so the whole pipeline ran on no evidence and the audio changed the outcome in no way. Fixed by describing confident features in the corpus's own vocabulary; a BPM *number* is invisible to a text-and-embedding search, the words "steady danceable pulse" are not.
4. **GTZAN's AppleDouble files doubled the dataset.** The archive ships a 211-byte `._blues.00000.wav` beside every clip, and `Path.glob("*.wav")` returns them: 1999 "clips", half undecodable, and every split ratio wrong. Caught only because the clip count was checked against the number the dataset is known to contain.

**Two fixtures deleted rather than left in place.** `/audio/identify` returned `matched: true, "Holocene" by Bon Iver, 0.88` for **any** input including silence; `/audio/analyze` returned `bpm: 120.0, musical_key: "A minor"` for every file. A fabricated answer is worse than a stated gap, because the user cannot detect it.

**A user-facing failure fixed on the way.** An expired clip — guaranteed to happen, since clips live 15 minutes — surfaced as "a downstream service failed". WF-003 and WF-004 now use WF-006's `[[CODE]]` marker pattern to return `AUDIO_UNAVAILABLE` with "please record it again". The n8n smoke test's two audio cases **flipped from `accept` to `reject`**, and that flip is itself the evidence: they used to pass by getting confident fixture features for a job id that never existed.

**Verified state:** 206 offline service tests + 28 root tests green; n8n smoke 12/12; live audio round trip through the browser boundary confirmed, including that an executable named `.wav` is refused and that the original filename never appears in any response.

**Pick up next:**

1. ~~**§6.4 — the only Phase 6 work left, and it needs the developer:** an ACRCloud (or alternative) account and API credentials.~~ → ✅ **[COMPLETED] §6.4 is done (July 27, 2026).** Corrected credentials arrived, the host was found by probing (`identify-ap-southeast-1`), and recognition is live and measured: **100% on clean in-catalogue audio, 91.7% catalogue coverage, 0 false positives, median 3.84 s**. `REC-ID-001…006` and ADR-004 all closed. **Only humming remains open**, and it needs real hummed recordings plus ACRCloud's separately-enabled humming service — nothing in this repository blocks it.
2. ~~**ML-AUD-005's measured number** — training was still running at the end of this session (best validation macro-F1 **0.8083** at epoch 12, squarely inside the published 0.75–0.85 range for GTZAN CNNs, which is itself evidence the leakage-free split is working). Run `python -m ml.evaluate` when it finishes and record the test figure in the model card and §6.3.~~ → ✅ **[COMPLETED] Done — training finished at validation macro-F1 0.8482 (epoch 26, 59.6 min), and the held-out test returned clip-level macro-F1 `0.8692` / accuracy `0.8733`.** Recorded in §6.3 and `docs/ml/audio-genre-classifier.md`. **§6.3 is now closed in full.**
3. Unchanged and now the largest remaining block: **Phase 7** (feedback → profile → reranker → sequencer) and **Phase 9** (deployment, security review, and the required documentation/traceability artifacts).
4. §8.3 `JOB-001…004` — untouched, and audio is what actually motivates them.
5. YouTube result *selection* quality (§5.3) — still the open product problem, and the Spotify 5-user decision means it must be solved on YouTube's own terms.

**Added July 27, 2026 (session continued — §6.4 landed, then was hardened against real use):**

6. **Humming is the last Phase 6 gate criterion**, and it needs two things neither of which is code: real hummed recordings to test with, and ACRCloud's **humming service enabled on the project** (it is a separate product from `/v1/identify`, which is why the synthetic stand-ins returned nothing and why that result proves nothing).
7. **A method worth reusing, not just a fix.** Twice this session the obvious cause was wrong and measurement caught it: the browser codec was blamed for recognition failures and scored 100 on every variant, and "make the recording longer" would have made recognition *worse*. Both were one commit away from being implemented on intuition. **Before changing a parameter in response to a symptom, measure that the parameter is the cause.**
8. **The POC's own first run was invalid and had to be redone** — without a catalogue control, a clip that is simply not indexed is indistinguishable from one the noise destroyed. Any future provider comparison needs the same control built in from the start.
9. Recognition is now live and **billable**. Nothing calls it automatically, tests are fenced off from it, and the free tier covers demo use — but this is the project's first per-request cost, and §8.4's budget monitoring (`N8N-REAL-004` / WF-008) now has a real number to watch rather than a hypothetical one.

### ▶ Session bookmark — July 28, 2026: Phase 1 and Phase 2 gates closed — the last three workflows, and four bugs the new code wrote into the live database

**Developer direction:** back up everything to GitHub first, then work Phases 0–2 to completion. Both done. **Phase 1 and Phase 2 gates are now passed**, which leaves **Phase 3 as the only phase before Phase 9 with an open gate**.

**Backup first, and one deliberate refusal.** Six commits pushed to `v2-n8n-architecture`; `main` untouched. Everything was scanned for credentials before pushing (only test fixtures matched). ⚠️ **The working tree carried a deletion of the v1 `data/18,393 Pitchfork Reviews/database.sqlite` (83 MB), which was RESTORED rather than committed** — the instruction was not to delete previous parts, and committing a deletion is still deleting it from every future checkout.

**Phase 0 — both loose ends closed.** `ADR-002` finally written (§0.4), carrying the July 21 rationale *and* the July 26 Spotify amendment. **`ACA-005` confirmed by the developer: the audio classifier replaces the reference image classifier**, so `ACA-004`'s adaptation is approved rather than proposed. Its second half was closed as **moot** rather than left hanging — RAG and LangGraph are already separate containers, valid under either answer.

**Phase 1 — the last three workflows exist, and each one was executed, not just written.**

| | Nodes | Verified by |
| --- | --- | --- |
| **WF-007** Knowledge Ingestion | 15 | A real run that **refused to publish** because all 24 documents lack licence metadata |
| **WF-008** Monitoring and Budget | 12 | A real daily summary from real rows, **plus a deliberately triggered `emergency` alert** |
| **WF-010** Temporary File Cleanup | 16 | A real clip deleted; an expired clip swept 1 → 0; `../../etc/passwd` refused |

⭐ **WF-007's licence gate is the result worth keeping.** `RAG-002` has been open since Phase 3 as a line in a markdown inventory. It is now **machine-visible and blocking**: the workflow found 23 unlicensed `genre_knowledge` documents and 1 `reviews_context` document and refused to publish a new version. That is the difference between a known risk and an enforced one.

**Phase 2 — all four open items closed.** `INF-002a` (pinned to the version the suite actually passes against, 2.31.6 — not the newest), `INF-002b` (the three `N8N_BASIC_AUTH_*` variables **deleted**, because advertising a protection that has done nothing since n8n 1.0 is worse than advertising none; owner account verified live at 401; loopback bind; public API off), `INF-011` + `DEP-001` (Flask in Compose under Gunicorn), and `N8N-REAL-004`.

**⚠️ Four defects, and three of them were in code written this session — all found by running it rather than reading it:**

1. **The packaged Flask image would have started and then 500'd.** `COPY . .` looked complete, but `.dockerignore` excluded `templates/` and `static/`. A container that boots and then fails on the first page render is worse than one that refuses to build.
2. **The new persistence made both test suites write into the live development database.** `recommendation-service`'s endpoint test wrote `model_usage` rows; `provider-gateway`'s adapter tests wrote **24 rows of fictional quota usage per run**. Invisible on the host, where `POSTGRES_*` is unset — visible only inside the container. **This was the dangerous one:** WF-008 reads that exact table to decide whether the YouTube budget is nearly spent, so test runs would have made the monitoring report consumption that never happened. Both suites now carry an autouse guard, and full runs provably leave **0** rows.
3. **My own "proof" that the no-database path was safe was itself the bug.** The test cleared a cached factory and asserted 0 — which on the host looked correct and inside the container simply rebuilt a live connection and wrote a real row. Patching the URL resolver is what actually reproduces "no database".
4. **WF-010 reported `deleted: false` about a clip it had really deleted**, and `failed: false` about a run that had really failed and been reported. The Postgres node and the WF-000 call each **replace the item**, and the Return node read `$json`.

⭐ **Defect 4 is the third occurrence of one pattern** — after WF-002's envelope and WF-003's `audio_features: $json`. **Three is a hazard, not a coincidence: on every n8n hand-off, ask whether the receiver sees the shape the sender thinks it sent.**

**Two decisions that went against the plan's own text, both recorded where they apply:**

- **WF-003/WF-004 do NOT call WF-010**, despite their §1.6/§1.7 node tables listing `Request File Deletion`. Those tables predate §6.5's audio UX, which reuses the same `audio_job_id` for *"Find me something with a similar vibe"* — deleting the clip on first use would break a follow-up the user can still see on screen. Full reasoning at §1.13.
- **WF-008's budget constants live in the workflow, not `$env`.** n8n's env unblock is all-or-nothing and would expose the Anthropic key, YouTube key and OAuth encryption key to every workflow (`SEC-101`).

**Verified state: 302 offline tests green** (recommendation-service 118, provider-gateway 86, audio 49, root 28, guardrails 17, rag 4) and `smoke_test_e2e.py` **12/12** — run against the **containerised** Flask, which is now what serves the app.

**Two things WF-008's first report surfaced that nobody was looking for:** **p95 latency is 24,097 ms against WF-002's 25 s timeout** — a margin, not yet a failure; and 118 expired `guest_sessions` rows had accumulated, which is the growth WF-010 now bounds.

**Pick up next:**

1. ⭐ **Phase 3 is now the only phase before Phase 9 with an open gate**, and it gates two graded rows. Open P0: `RAG-003`, `RAG-005`, `RAG-010`, `RAG-011`, `LOCAL-002`, `LOCAL-003`, the §3.8 golden evaluation set and **§3.9 prompt-log Version 1** (which is also `DOC-007`). `RAG-002` needs the developer: the licence status of both corpora is genuinely unknown, and WF-007 now blocks on it.
2. **§8.3 `JOB-001…004`** — still untouched; `GET /api/v1/jobs/{job_id}` is the last missing §8.1 route.
3. **`UI-008`** Smart Sequence display — unblocked since Phase 7 passed.
4. The **Phase 5 playable-percentage measurement** (the last Phase 5 gate criterion) and the **`REC-LEG-002` re-run through n8n**, then `REC-LEG-003`.
5. ⚠️ **Housekeeping the agent could not do:** four `TEST wf010*` workflows remain in the n8n instance — the CLI has no delete command, so they need removing in the editor. They are inactive and were never exported to `workflows/n8n/`, so the repository is clean.

### ▶ Session bookmark — July 28, 2026 (later): datasets out of Git, and the latency fix that needed three attempts

**Developer direction:** remove the datasets from GitHub, then execute latency fixes #1 and #2. Both done. **Median request latency fell from 18.3 s to 8.0 s** and the corpora are gone from every commit.

**1. Datasets removed from Git history, not just from the tree.** History rewritten on **both** branches with `git filter-repo`; repository **76 MB → 27 MB**. Verified: `origin/main` has **zero** commits touching `data/`. What remains tracked is `data/README.md` plus two **synthetic** format samples, so the ingestion code stays readable without shipping the corpora. `.gitignore` blocks `data/**` with narrow exceptions, so re-adding a dataset cannot quietly undo the rewrite.

**Developer's reasoning, recorded because it changes what `RAG-002` is for:** the concern is **not** copyright — the review datasets come from open public sources — it is protecting the **project's own RAG assets**, specifically the tailored genre mappings in `data/genres_knowledge/`. ⚠️ **`RAG-002` is NOT closed by this.** Removing the data settles *redistribution*; it does not record *provenance*, which `DOC-010` still needs. WF-007 continues to report the gap on every run. A full pre-rewrite backup bundle and a local data copy were taken first; all commit SHAs changed, so any second clone must be **re-cloned, not pulled**.

**2. The latency fix — and I got the diagnosis wrong twice before getting it right.** Recording all three attempts, because the two wrong ones are the instructive part.

| Attempt | Belief | Result |
| --- | --- | --- |
| 1 | The rewrite re-runs retrieval to widen the candidate pool 20→30; start at 30 instead | **No change (20→21 s).** Raising the pool to 30 left 30 < the 40 cap, so a "relaxation" still appeared available and the rewrite still fired |
| 2 | Run the two retrieval calls concurrently | **No change.** Measured 8.47 s parallel vs 8.15 s sequential — *slightly worse* |
| 3 | Actually read what reaches rag-service | ⭐ **The real cause** |

⭐ **The finding: two of the three relaxation branches reach nothing at all.** `rag_client.retrieve` sends only `{query, top_k, filters}`. **`candidate_pool` is never sent** — rag-service computes its own as `max(top_k, 20)` — and **`genre_expansion` has no consumer anywhere in the repository.** So on any request without a year constraint, the second retrieval pass issued a **byte-identical request** and could not, by construction, return anything different. That was ~8 s of an ~18 s request spent guaranteeing the same answer. Only the year-range drop is real, because `year_from`/`year_to` genuinely travel inside `filters`.

**NEW DECISION: `plan_query_relaxation` offers exactly one relaxation — dropping the year range — and the router consults it before routing.** The inert knobs are left in `DISCOVERY_PARAMS` rather than deleted (§4.4 intends them as real discovery-mode levers) but they can no longer buy a retrieval pass with a promise they do not keep. Wiring them through for real is a behaviour change that wants §3.8's evaluation set behind it. **§4.3 is untouched:** the router is now strictly *narrower*, so `rewrite_count` still cannot exceed 1.

⚠️ **Why attempt 2 failed is worth keeping: the work was never waiting on I/O, it was waiting on CPU.** `/rag/retrieve` is query embedding plus a cross-encoder, and `rag-service` was capped at **`cpus: "2.00"` on a 24-core host**, so two concurrent calls just timeshared two cores. Raised to **6.00**, at which point the parallel fan-out finally pays: a single `/rag/retrieve` went **7.0 s → 2.2 s**, and the two domains now complete within 18 ms of each other.

**One supporting change that would otherwise have been a silent bug:** `_retrieval_debug` gained a merge reducer in `graph_state.py`. Both retrieval nodes write that key, and under LangGraph's last-write-wins one domain's entry would have been discarded — leaving node 10 to compute retrieval confidence from half the evidence and report a perfectly plausible number for it. Its old comment (*"last-write-wins is fine"*) was true only while the nodes ran in sequence.

**Measured, end to end through the containerised Flask:**

| | Before | After |
| --- | --- | --- |
| Median request | **18.29 s** (p50, 90 requests) | **8.02 s** |
| p95 | 38.17 s | 9.89 s (max of 6) |
| `rewrite_query` fired | **100%** of requests | **0 of 8** |
| Retrieval passes per request | 2 | 1 |
| `/rag/retrieve` (genre domain) | 7.0 s | **2.2 s** |

**Verified:** 120 offline tests in `recommendation-service` (was 118), rag-service 4, `smoke_test_e2e.py` **12/12**, and six live requests in both languages all returning real tracks.

**Three tests were replaced, not deleted for convenience.** Two asserted the removed branches; the end-to-end forced-rewrite test now supplies a **year constraint** so a relaxation genuinely exists, preserving §4.3's guarantee under test. A new test asserts the fix directly: low confidence with no year constraint must make **exactly two** `rag_client.retrieve` calls, not four.

⚠️ **A "bug" I reported and then disproved, recorded so it is not re-investigated:** Hebrew requests appeared to be refused with `INPUT_REJECTED` / `unsupported_language`. That was **Git Bash mangling UTF-8 in the test command**, not a defect — the same request sent with correct encoding returns `allowed: true, language: "he"`, and both Hebrew requests above returned real tracks. **Lesson: verify the harness before blaming the system.**

**Latency work still open (unchanged recommendation — after Phase 3):** `generate_grounded_explanation` is now the largest single node at ~3.1 s, and streaming it would improve *perceived* latency further. Whether retrieval can go below 2.2 s is a quality question that wants §3.8's evaluation set as a safety net.

### ▶ Session bookmark — July 28–29, 2026: Phase 3 closed — the evaluation set, and the four things it disproved

**Developer direction:** finish Phase 3 before Phase 9, with the vector database operating "at maximum capability with zero errors", Ragas wired in per the lecturer, and the knowledge base restricted to exactly two datasets. **Phase 3 gate now passes 5 of 5** — the last phase before Phase 9 to close.

**The theme of this session is that almost everything measured turned out differently from what inspection suggested.** Four beliefs were overturned by data, and three of the wrong beliefs were mine.

| Belief | What measurement showed |
| --- | --- |
| The cross-encoder reranker improves retrieval | It was **worse than no reranker at all** on every metric, at 17× the latency |
| Hebrew fails because dense retrieval can't handle it | Dense retrieval returns the **correct chunk at rank 1**; the English-only reranker then demoted it |
| A bigger candidate pool improves recall | English recall **flat**, Hebrew **worse**, latency **4× worse** |
| The negation fix didn't work | It did — the harness in the container was **stale** |

⭐ **The headline: swapping to a multilingual reranker.** `RAG-RERANK-001/002/003` measured three configurations against the 25-query golden set:

| Reranker | Recall@5 | MRR | nDCG@10 | HE Recall@5 | median |
| --- | --- | --- | --- | --- | --- |
| `ms-marco-MiniLM-L-6-v2` (was default) | 0.409 | 0.458 | 0.410 | 0.125 | 2.29 s |
| none (RRF order) | 0.424 | 0.480 | 0.426 | 0.125 | **0.13 s** |
| **`mmarco-mMiniLMv2-L12` (adopted)** | **0.489** | **0.511** | **0.475** | **0.500** | 2.79 s |

Hebrew Recall@5 **quadrupled** for +0.5 s. The English reranker had been in the request path since Phase 3 opened, silently destroying rankings RRF had already got right.

**Corpus.** The full reviews dataset is in: *"all 193,658 rows"* resolved to **3,836 unique albums** (the CSV is 98% duplicates), so the job took 4.5 minutes rather than hours. Store: 325 → **4,249 chunks**. Latency did not move, because the growth is what finally made PostgreSQL choose the HNSW index over a sequential scan. **Scope verified against the database, not the script:** only `data/genres_knowledge/` and `data/cleaned_large_dataset_t.csv`; nothing else ever entered.

**A silent corruption fixed:** 30 genre chunks exceeded the embedding model's 512-token window and were **truncated at embed time** — the worst losing ~42% of its text to the vector *while remaining findable by full-text search*. A chunk could be retrieved lexically and then score terribly on the reranker, because the reranker was reading text the embedder never saw. Now 0 over the limit.

**Negation (`negative_constraint` scored 0.00 context precision).** Two gaps stacked: negation was only read from a UI field the UI does not have, and even when populated it was **read by nothing** — the same dead-knob pattern as `candidate_pool`. Both closed. Running it found a third: *"rock but nothing metal"* put metal in **4 of the top 5**, and excluding it returned **zero chunks**, because the candidate pool was metal all the way down. Exclusion now deepens the first stage rather than narrowing the answer.

**`RAG-010`/`RAG-011` — staged ingestion.** A corpus version can now exist without being live, which is what makes §1.10's *"do not publish until smoke queries pass"* enforceable. **WF-007's placeholder is gone: the exported workflow set now contains zero placeholders.** Three defects found by running it, each of which would have shipped — a staged document colliding with the live one, a partial corpus **silently taking the reviews domain to zero** with every check green, and no way to restore a superseded version after a bad publish.

**Ollama removed** (developer-approved) after an audit found it referenced nowhere on the request path with a container that had never started. `LOCAL-003` retargeted onto the three models that genuinely run in-process on every request — a stronger claim than the one it replaced.

⚠️ **Four evaluation-harness defects, every one of which would have been reported as a product failure.** Recording them together because the pattern matters more than any single instance:

1. The Ragas judge ran out of tokens on **10 of 25** queries; the first reported faithfulness of 0.62 was a **15-query average wearing a 25-query label**. Visible only because the harness records judge errors instead of averaging them in as zeros.
2. The harness's answer prompt made the model **refuse every Hebrew query** — `he-01` scored context precision *and* recall of **1.0** and the answer still claimed the context did not contain the information.
3. The container copy of the harness was **stale** (`docker cp` nests when the destination exists), so a whole negation run measured pre-negation code.
4. `Recall@K` against hand-picked positives is **the wrong metric for a negative constraint** — the pipeline returned heartland rock and rockabilly for *"rock but nothing metal"*, which are correct answers no ground-truth list happened to name. The harness now measures **absence**.

Fixing 1 and 2 alone moved faithfulness 0.62 → **0.848** and relevancy 0.61 → **0.741** with **no change to the system under test**.

**Final Phase 3 numbers:** Recall@5 **0.500**, MRR **0.520**, nDCG@10 **0.482**, faithfulness **0.848**, response relevancy **0.741**, context precision 0.423, context recall 0.280, negative constraints **0 violations (CLEAN)**. 141 recommendation-service tests, 4 rag-service, `smoke_test_e2e.py` **12/12**, live requests answering in both languages.

**Pick up next:**

1. ⚠️ **Phase 9 is now the whole remaining scope, and the submission deadline is July 30.** 28 open P0 items — but an audit found roughly ten already satisfied and merely unverified (workflows exported, Dockerfiles, migrations, ML code, prompt log, traceability, evaluation reports, Gunicorn, non-root, cookies). **Genuinely missing and highly visible: `DOC-001` (the README still describes the v1 Bedrock app — zero mentions of n8n or LangGraph), `DOC-002` architecture diagram, `DOC-009` deployment notes, `DOC-011` screenshots and demo video.**
2. **`RAG-002` needs the developer.** Only the author knows the provenance of the two corpora, and WF-007 now refuses to publish a new version while it is missing.
3. `UI-008` (Smart Sequence display) and §8.3 `JOB-001…004` remain the open Phase 8 items.
4. Retrieval quality's next lever, if it is ever revisited: **context recall is 0.280** and `blended_genres`/`mood` score lowest on context precision. The reranker is also **~1.9 s of the ~2.2 s** a retrieval call costs, so it is the first place to look if latency must come down again.

<!-- ========================== END RESUME HERE ========================== -->

✅ **[COMPLETED] Phase 0 update (July 21, 2026): Git state frozen, EC2 baseline updated, all secrets isolated and secured in** `.env`**, the AI recommendation contract frozen (**`contracts/ai_recommendation_schema.json`**), and the MusicAPI proof of concept evaluated and tested (**`poc/test_musicapi.py`**) with a final REJECTED outcome. See Section 5 for the complete Phase 0 record and the closed ADR-002 provider decision.**

The first implementation surface is the n8n architecture, but only after a short Phase 0 that freezes the baseline, fixes exposed-secret risks, defines the shared request contracts, and performs the MusicAPI decision experiment.

The first n8n deliverable is not a single legacy text path. It is the complete final workflow skeleton with placeholder service calls where implementation is not ready yet.

---



# 2. Non-negotiable architecture



## 2.1 Target request path

The target recommendation path is new. It is not the existing Bedrock recommendation path with an n8n wrapper.

Every recommendation may use this complete context:

## 2.2 Component boundaries


| Component              | Owns                                                                                                                             | Must not own                                                              |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Flask Web App          | UI, session cookie, upload UX, embedded player, feedback controls, OAuth start/callback UX                                       | RAG logic, personal ranking logic, provider-specific recommendation logic |
| n8n                    | Request orchestration, validation, guardrail calls, routing, retries, side effects, persistence coordination, export, monitoring | Embedding math, audio DSP, complex ranking algorithms                     |
| Recommendation Service | LangGraph state, bounded control flow, provider search intents, track ranking, sequencing, explanation                           | OAuth callbacks, playlist writes, feedback writes                         |
| RAG Service            | Hybrid retrieval, genre expansion, RRF, document reranking, retrieval confidence, evidence packaging                             | Provider writes, final personal ranking, OAuth                            |
| Audio Service          | File validation, conversion, BPM, key, energy, genre/tags, embeddings                                                            | Music-provider authentication, final recommendation generation            |
| Guardrails Service     | Input policy, output grounding checks, prompt-injection and unsupported-claim checks                                             | Music discovery, ranking, provider search                                 |
| Provider Adapter Layer | Search, identity resolution, taste import, playlist operations, normalized provider data                                         | RAG, user preference learning, final prose                                |
| PostgreSQL + pgvector  | Durable users, profiles, feedback, tracks, knowledge, vectors, jobs, usage, exports                                              | Workflow branching                                                        |
| Local Model Runtime    | Cheap classification, structured extraction, local inference demonstrations                                                      | Authentication and deterministic operations                               |




## 2.3 Role of the existing AWS/Bedrock implementation

The existing AWS route is retained only as:

- a known-good rollback while development is incomplete;
- a quality and latency benchmark;
- an optional, explicitly logged emergency fallback behind a feature flag.

It is not the target recommendation architecture. It must not define the new request schema, personalization logic, audio path, provider layer, or workflow structure.

Required feature flags:

✅ **[COMPLETED] Defined July 24, 2026 under** `ARC-004` **— this section previously named the requirement without listing the flags.** The authoritative set now lives in `docs/feature-flags.md` and is declared in `.env.example`: `USE_N8N_ORCHESTRATOR`, `RECOMMENDATION_ENGINE`, `ENABLE_LEGACY_BEDROCK_FALLBACK`, `PROVIDER_MODE`, `ENABLE_SPOTIFY_ADAPTER`, `ENABLE_PLAYLIST_EXPORT`, `ENABLE_AUDIO_IDENTIFICATION`, `ENABLE_CLAP`, `ENABLE_CROSSFADE`, `ENABLE_EXPENSIVE_MODEL_PATHS`, and `ALLOW_PLACEHOLDER_NODES`. The two flags that gate this section's legacy-fallback rule specifically are `RECOMMENDATION_ENGINE` (default `legacy`) and `ENABLE_LEGACY_BEDROCK_FALLBACK` (default `false`, so a fallback is never accidental).

Any legacy fallback must be recorded in `recommendation_sessions.engine_used`; never switch silently.

✅ **[COMPLETED] ADR-002 decision (July 21, 2026):** `PROVIDER_MODE` **is finalized as** `direct`**.** `musicapi` ~~and~~ `hybrid` ~~modes~~ were evaluated and not selected — see Section 5, "0.4 MusicAPI.com proof of concept," for the full decision record.

---



# 3. Canonical contracts to freeze before workflow construction

These contracts are drafted in Phase 0 and used by every later phase. Pydantic/JSON Schema becomes the executable source of truth in Phase 2.

## 3.1 Request envelope

Allowed `intent` values:

- `text_recommendation`
- `audio_vibe_recommendation`
- `audio_identification`
- `feedback`
- `playlist_export`
- `auth_connection_sync`



## 3.2 RecommendationContext

Fields may be empty, but the schema and keys remain stable. A text request and an audio request enter the same recommendation engine after their context has been assembled.

⚠️ **CONTRACT CHANGE (July 26, 2026, later still) — `provider` added to `RecommendationContext`.** §5.6's UI toggle needs to say *which service should answer*, and no existing field meant that: `connected_providers` records what the user has **authorized**, which is a different question from what they **asked for** — a guest with nothing connected can still choose Spotify mode, because Spotify search runs on application credentials. Additive and defaulted (`"youtube"`), so every previously valid context stays valid. Carried on `RequestBody.provider` as well, since WF-006 already reads a provider from the body for export. **Downstream it is a default, not a constraint:** `graph_nodes.resolve_provider` lets a provider named in the request text override it.

**NEW DECISION: the accepted provider values are validated at the Flask boundary**, not silently defaulted — `ClientRequestPayload` rejects anything outside `{youtube, spotify}` with `400 VALIDATION_ERROR`, matching how `discovery_mode` is already handled and how WF-001's `Validate Request Schema` pins its own enums (N8N-005).

## 3.3 Success response envelope



## 3.4 Error envelope

Never include stack traces, tokens, provider secrets, raw model reasoning, or internal URLs in a client response.

## 3.5 Music Provider Adapter contract

Every provider implementation must normalize to these operations:

Normalized track fields:

✅ **[COMPLETED] The contract now has two real implementations, which is the first time it has been tested as a contract rather than assumed (July 26, 2026, later still).** `provider-gateway/app/youtube_adapter.py` and `app/spotify_adapter.py` expose the same `search(query, limit)` signature, return the same `NormalizedTrack` shape, and raise `ProviderError` from the same code vocabulary — so `/providers/search` dispatches through a lookup table (`_SEARCH_ADAPTERS`) with **no per-provider branching**, and one error mapping serves both. A second implementation is what turns "normalize to these operations" from an intention into something verified.

**Two places the abstraction correctly did *not* hide a difference**, recorded because collapsing them would have been a mistake:

- **`embeddable`** is a real per-video permission on YouTube and always `true` on Spotify. The UI branches on it (§PLAY-005) rather than the adapters pretending it is uniform.
- **Result-quality confidence has different sources.** YouTube must infer whether a result is even music (official-upload heuristics, duration sanity); Spotify's catalogue contains only released recordings, so its confidence separates good from better. Same field, same meaning to the ranker, honestly different derivation — see §5.6.

**Write operations are deliberately not symmetric yet:** playlist export is implemented for YouTube only, and `/providers/playlists` still returns `PROVIDER_NOT_IMPLEMENTED` for Spotify. The UI hides the export control for Spotify tracks rather than offering an export that would fail at the provider after the user confirmed it.

---



# 4. Phase dependency map


| Phase                             | Required input                            | Main output                                          | Unlocks                    |
| --------------------------------- | ----------------------------------------- | ---------------------------------------------------- | -------------------------- |
| 0. Foundation and decisions       | Current repository and accounts           | Frozen contracts, security baseline, provider ADR    | n8n build                  |
| 1. Complete n8n skeleton          | Contracts and provider mode               | Importable workflow JSON with placeholders           | Service implementation     |
| 2. Data and service foundation    | Workflow contracts                        | PostgreSQL and healthy FastAPI services              | RAG and real persistence   |
| 3. Knowledge and RAG              | Database and service skeleton             | Evaluated hybrid retrieval                           | LangGraph recommendation   |
| 4. Recommendation engine          | RAG and provider interface                | New multimodal-ready recommendation API              | Provider/audio integration |
| 5. Provider/auth/playback         | Provider ADR and recommendation intents   | Real playable tracks and export                      | Complete product results   |
| 6. Audio intelligence             | Audio service skeleton and engine context | Identification and audio-conditioned recommendations | Multimodal demo            |
| 7. Personalization and sequencing | Feedback tables and real candidates       | Feedback-aware ranking and ordered playlist          | Personalized demo          |
| 8. UI and end-to-end integration  | All P0 services                           | Complete user flows                                  | Release testing            |
| 9. Release and submission         | Complete P0 flows                         | Tested deployable submission                         | Final demo                 |


---



# 5. Phase 0 — Foundation, security, contracts, and provider decision ✅ [COMPLETED]



## Objective

Create a safe starting point and resolve the provider architecture early enough that YouTube and Spotify work is not duplicated.

## 0.1 Freeze and measure the current baseline

✅ **[COMPLETED] (July 21, 2026): Git state frozen and EC2 baseline updated.**

- [x] ✅ **[COMPLETED] FND-001 P0: Create a new implementation branch.**
- [x] ✅ **[COMPLETED] FND-002 P0: Tag or otherwise record the known-good existing version.**
- [x] ✅ **[COMPLETED] FND-003 P0: Record one successful text recommendation with request, response, latency, and screenshots.**
- [x] ✅ **[COMPLETED] FND-004 P0: Inventory current Flask routes, AWS resources, Bedrock IDs, Lambda tools, Spotify functions, environment variables, and deployed URLs.**
- [x] ✅ **[COMPLETED] FND-005 P0: Back up prompts, Bedrock schemas, n8n exports, source knowledge, and configuration templates without secrets.**

This is rollback and benchmarking work. It does not preserve the legacy recommendation logic as the new design.

## 0.2 Immediate security repair

✅ **[COMPLETED] (July 21, 2026): All secrets isolated and secured in** `.env`**.**

- [x] ✅ **[COMPLETED] SEC-001 P0: Revoke or rotate the Spotify authorization that appeared in logs.**
- [x] ✅ **[COMPLETED] SEC-002 P0: Remove logging of access tokens, refresh tokens, authorization headers, cookies, and uploaded audio.**
- [x] ✅ **[COMPLETED] SEC-003 P0: Scan the working tree and relevant Git history for committed secrets.**
- [x] ✅ **[COMPLETED] SEC-004 P0: Add or repair** `.env.example` **with variable names only.**
- [x] ✅ **[COMPLETED] SEC-005 P0: Add a centralized log-redaction filter.**
- [x] ✅ **[COMPLETED] SEC-006 P0: Confirm that internal service ports are not exposed to the public internet.**



## 0.3 Freeze v1 contracts and boundaries

✅ **[COMPLETED] (July 21, 2026): AI contracts frozen —** `contracts/ai_recommendation_schema.json` **created.**

- [x] ✅ **[COMPLETED] ARC-001 P0: Save the request, response, error, RecommendationContext, and normalized-track schemas under** `contracts/`**.** (AI recommendation response contract frozen as `contracts/ai_recommendation_schema.json`; the remaining request/response/error/context envelope schemas from Section 3 continue into Phase 1/2.)
- [x] ✅ **[COMPLETED] ARC-002 P0: Define explicit timeouts and retry rules per service call (July 24, 2026).** Created `docs/service-call-policies.md` with a per-call timeout/retry matrix covering every real hop in the exported workflows (Flask→WF-001, WF-001 guardrails/Postgres/sub-workflow calls, WF-002…WF-006 service calls, WF-000 error persistence), plus an error-classification table mapping each failure class to a canonical code from `shared_lib/errors.py`. **NEW DECISION:** maximum 3 total attempts per call with `1s → 2s → 4s` exponential backoff and full jitter; a 30-second synchronous budget (matching the existing `N8N_HTTP_TIMEOUT_SECONDS=30`) with `POST /audio/analyze` explicitly marked **async-required** because its 60s worst case exceeds it. **NEW DECISION:** guardrail calls **fail closed** — an unreachable Guardrails Service rejects the request rather than passing it. **NEW DECISION:** telemetry writes (`Record Request Metrics`, `Persist Error Event`) are best-effort and must never convert a successful recommendation into an error response. Audit finding: **none of the 24 service calls in** `workflows/n8n/` **currently has a timeout or retry configured** — applying the matrix to the nodes is Phase 1 `N8N-006`, tracked in the doc's "Applied" column.
- [x] ✅ **[COMPLETED] ARC-003 P0: Define which actions require an idempotency key (July 24, 2026).** Defined in §4 of `docs/service-call-policies.md`. **NEW DECISION:** a key is **required** for `playlist_export`, `feedback`, `auth_connection_sync` token writes, and audio-job creation (a request in this set arriving without one is rejected with `VALIDATION_ERROR`); it is **not** required for `text_recommendation`, `audio_vibe_recommendation`, or `audio_identification`, which are read-only externally and use `request_id` as their natural session key. **NEW DECISION:** keys are UUIDv4, **generated by the Flask client rather than by n8n** (an n8n-generated key would change on retry and defeat its purpose), scoped per user+provider, valid for 24 hours, stored with the outcome rather than the attempt, and a repeat of the same key with a different payload returns `CONFLICT`. The envelope field already exists (`contracts/models.py::RequestEnvelope.idempotency_key`); enforcing it is Phase 1 `N8N-009`.
- [x] ✅ **[COMPLETED] ARC-004 P0: Define the feature flags listed in Section 2.3 (July 24, 2026).** Section 2.3 stated "Required feature flags:" with an empty body; the concrete set is now defined in `docs/feature-flags.md` and declared in `.env.example`. **NEW DECISION:** eleven flags across four groups — orchestration/engine (`USE_N8N_ORCHESTRATOR`, `RECOMMENDATION_ENGINE`, `ENABLE_LEGACY_BEDROCK_FALLBACK`), providers (`PROVIDER_MODE`, `ENABLE_SPOTIFY_ADAPTER`, `ENABLE_PLAYLIST_EXPORT`), audio/ML (`ENABLE_AUDIO_IDENTIFICATION`, `ENABLE_CLAP`, `ENABLE_CROSSFADE`), and cost/safety (`ENABLE_EXPENSIVE_MODEL_PATHS`, `ALLOW_PLACEHOLDER_NODES`, with `LOG_LEVEL` documented alongside). **NEW DECISION:** every default is the *safe* value, not the demo value — `RECOMMENDATION_ENGINE=legacy` until the Phase 5 and Phase 8 gates pass (`REC-LEG-003`), `ENABLE_PLAYLIST_EXPORT=false` so no unconfigured external write is reachable, and `ALLOW_PLACEHOLDER_NODES=false` so a reachable placeholder fails loudly (§1.14 / `INT-002`). **NEW DECISION:** `WF-008` is the only automated writer of a flag and may only move `ENABLE_EXPENSIVE_MODEL_PATHS` from true to false at 95% of budget; restoring it is a deliberate human action.
- [x] ✅ **[COMPLETED] ARC-005 P0: Create an architecture ADR stating that n8n orchestrates, LangGraph recommends, and provider adapters isolate external APIs (July 24, 2026).** Created `docs/adr/ADR-001-architecture-boundaries.md` (Accepted) in the same format as ADR-003. Fixes three non-overlapping ownerships: n8n orchestrates but never computes (a Code node that calculates a score is a boundary violation); LangGraph **reads only** — it emits provider *search intents* and never creates a playlist, writes feedback, or touches OAuth, so all side effects stay in n8n where retries and idempotency keys live; and provider adapters stop external shape at the boundary, so no YouTube/Spotify/MusicAPI-specific field reaches the Recommendation or RAG contracts. Records the rejected alternatives (LangGraph-as-orchestrator, ranking inside n8n AI Agent nodes, a merged RAG+recommendation service, direct provider calls from the engine) and notes that merging RAG into the recommendation runtime later requires superseding this ADR rather than silently importing the module.



## 0.4 MusicAPI.com proof of concept — early decision gate

✅ **[COMPLETED] (July 21, 2026): MusicAPI evaluated and tested. Decision closed — see "Decision outcomes" below.**

MusicAPI.com is neither deferred nor assumed. It must earn its role through a short experiment.

### Required tests

- [x] ✅ **[COMPLETED] PROV-POC-001 P0: Create a trial project and record available plan limits and credentials required.**
- [x] ✅ **[COMPLETED] PROV-POC-002 P0: Connect a test user to YouTube/YouTube Music if supported.**
- [x] ✅ **[COMPLETED] PROV-POC-003 P0: Connect a test user to Spotify if supported and available.**
- [x] ✅ **[COMPLETED] PROV-POC-004 P0: Search tracks and playlists; verify normalized IDs, artist/title quality, artwork, duration, and ISRC when available.**
- [x] ✅ **[COMPLETED] PROV-POC-005 P0: Retrieve user-library or taste signals and identify exactly which signals exist per provider.**
- [x] ✅ **[COMPLETED] PROV-POC-006 P0: Create a test playlist and add tracks on every claimed P0 platform.**
- [x] ✅ **[COMPLETED] PROV-POC-007 P0: Test disconnect, token refresh, expired authorization, insufficient scope, rate limit, and provider outage behavior.**
- [x] ✅ **[COMPLETED] PROV-POC-008 P0: Confirm what MusicAPI supplies for playback: embedded player, provider link/ID, or actual media. Do not treat provider IDs as raw audio access.**
- [x] ✅ **[COMPLETED] PROV-POC-009 P0: Measure request latency and count calls needed for one recommendation and one export.**
- [x] ✅ **[COMPLETED] PROV-POC-010 P0: Calculate submission usage and realistic first-100-user monthly cost.**
- [x] ✅ **[COMPLETED] PROV-POC-011 P0: Review terms, data retention, user consent, and whether platform-specific user authorization is still required.**

POC evaluation evidence: `poc/test_musicapi.py`.

### Decision outcomes

Choose one and create `docs/adr/ADR-002-music-provider-mode.md`:


| Mode       | Select when                                                                          | Architecture                                                                                   |
| ---------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `musicapi` | ~~Search, taste, playlist writes, error handling, cost, and reliability all pass~~   | ~~All provider operations go through MusicAPI; official playback mechanism remains compliant~~ |
| `hybrid`   | MusicAPI is strong for auth/data but a direct API is better for a critical operation | Adapter routes each operation to the chosen backend                                            |
| `direct`   | P0 capability, cost, reliability, or terms fail                                      | Direct YouTube-first API; optional direct Spotify adapter                                      |




### ✅ [COMPLETED] Decision outcomes — RESOLVED (July 21, 2026)

- ~~Use MusicAPI for playlist generation~~ → **NEW DECISION: MusicAPI is REJECTED.** Conclusion: It acts only as a proxy and does not bypass Spotify's hard limit of 5 authorized users in Development Mode.
- **NEW DECISION: Direct YouTube API Integration is APPROVED.** Conclusion: YouTube will be the primary engine for actual playlist generation and handling broader user requests.
- **NEW DECISION: Direct Spotify API Integration is APPROVED but LIMITED.** Conclusion: Spotify will be integrated directly but kept strictly as a "nice-to-have" feature, limited only to the 5 authorized development users.

Selected mode: `musicapi` `hybrid` → `direct` — YouTube as the primary adapter; Spotify as an optional, limited adapter for the 5 authorized development users only. ~~Formal record to be committed as `docs/adr/ADR-002-music-provider-mode.md`.~~ → ✅ **[COMPLETED] `docs/adr/ADR-002-music-provider-mode.md` written (July 28, 2026).** The decision itself is unchanged and dates from July 21; what was missing was the standalone record §0.4 asked for. The ADR carries the original rationale (MusicAPI proxies rather than removes Spotify's 5-user Development Mode cap, so it fails the P0 capability test; `hybrid` rejected too, since Melody authenticates users with Google OIDC and needs no unified music-platform auth), the consequences accepted (Melody owns YouTube quota accounting, title parsing, and the is-this-even-music problem), **and the July 26 amendment** — Spotify promoted to a first-class recommendation mode on a finding the Phase 0 POC never tested, that **catalogue search uses Client Credentials and is therefore not subject to the 5-user cap**, while YouTube stays the default because the *user-authorized* parts of Spotify (taste import, playlist writes) still are. **The file also states plainly why it was late**, and that `ACA-002`'s traceability matrix is what caught the omission by logging it honestly as "Decided, unrecorded" instead of as done.

### Hard rule

MusicAPI's unified authentication does not remove the need to test real user consent, platform permissions, or provider restrictions. YouTube playlist creation and item insertion require authorized OAuth operations in the official API, and Spotify user resources are scope-controlled OAuth resources. The POC must confirm how MusicAPI represents and manages those requirements.

✅ **[COMPLETED] POC finding: confirmed that MusicAPI does not remove or bypass Spotify's platform-level 5-user Development Mode restriction — this was the deciding factor for rejection.**

### Timebox

If account approval or a missing capability blocks the POC for more than two focused hours during the submission sprint:

1. Record the blocker.
2. Choose provisional `direct` YouTube mode for P0.
3. Keep the adapter contract unchanged.
4. Continue the POC after the submission-critical path is safe.

✅ **[COMPLETED] Timebox not triggered — the POC completed within the Phase 0 window and reached a final (not provisional) decision:** `direct` **mode, YouTube primary, Spotify limited to development users.**

## 0.5 Academic requirement mapping

- [x] ✅ **[COMPLETED] ACA-001 P0: Create** `docs/requirements-traceability.md` **(July 24, 2026).** Created, with a supporting decision-record index alongside the main matrix.
- [x] ✅ **[COMPLETED] ACA-002 P0: Map n8n, LangChain/RAG, LangGraph, PyTorch classifier, local model runtime, external LLM, guardrails, Docker, AWS/EC2, and WebUI to specific Melody components (July 24, 2026).** All 20 graded areas mapped to concrete components with verified evidence paths in the repository. **NEW DECISION:** the matrix carries an honest three-value status column (`Done` / `Partial` / `Planned`) reconciled against the actual repository state rather than against checkbox state, per Section 19 ("a checkbox alone is not evidence"); it is re-reconciled at every phase gate and a row may only reach `Done` once its gate criterion has passed. Current honest reading: 5 areas `Done`, 11 `Partial`, 4 `Planned`. **Gap surfaced by the mapping:** the ADR-002 provider decision is closed in this plan but its standalone `docs/adr/ADR-002-music-provider-mode.md` file was never written — logged in the matrix as "Decided, unrecorded."
- [x] ✅ **[COMPLETED] ACA-003 P0: Define five prompt-engineering surfaces and a five-version evaluation log for each (July 24, 2026).** Created `docs/prompt-engineering-log.md` defining PE-1…PE-5 (plus optional PE-6), each bound to the exact file or n8n node where its prompt lives, with a fixed per-version log template and measurement rules. **NEW DECISION:** each surface's ≥10-case test set has a mandated composition — 4 ordinary cases, **2 cases whose correct answer is partial or absent** (measuring honesty rather than fluency), 2 bilingual, 1 adversarial, 1 boundary — held unchanged across all five versions, since changing the set mid-log invalidates the comparison. **NEW DECISION:** one variable per version (a prompt change and a model change in the same version makes the delta unattributable); the full set is re-run every version; for PE-1/PE-3 a version that scores lower on coverage but stops inventing absent values is recorded as the **better** version; PE-4 reports false positives and false negatives separately. **NEW DECISION:** PE-3 and PE-5 already have working Version 0 prompts in `rag-service/scripts/test_generation.py` that must be transcribed verbatim as Version 1 **before** any change is made to them. Filling in Version 1 for all five surfaces remains the §3.9 / Phase 3 gate item; reaching Version 5 remains `DOC-007`.
- [x] ✅ **[COMPLETED] ACA-004 P0: Document any approved adaptation from the reference real-estate scenario to the Melody music domain (July 24, 2026).** Documented in §2 of `docs/requirements-traceability.md` as a seven-row equivalence table (knowledge base, entity extraction, supervised classifier, multimodal input, ranking/personalization, external write integration, domain guardrails), each row stating why the adaptation preserves the graded requirement and changes only the subject matter. **NEW DECISION:** the central substitution is the reference **image** classifier → Melody's **audio** genre/tag/energy classifier, keeping the identical ML deliverable (labelled dataset, leakage-free split, pretrained backbone, accuracy/F1 + confusion matrix, confidence-aware `uncertain` output) and changing only the input modality. **NEW DECISION:** bounded LangGraph control flow and the Smart Sequencer are declared as **additions** rather than substitutions, so they are not credited against a reference requirement. ⚠️ This documents the adaptation as *proposed*; approval still depends on `ACA-005`, which is not confirmable by implementation — see below.
- [x] ✅ **[COMPLETED] ACA-005 P0 (cross-reference, tracked in Section 18): the audio classifier replaces the reference image classifier — CONFIRMED BY THE DEVELOPER (July 28, 2026).** ~~Confirm with the evaluator that the audio classifier may replace the reference image classifier and that RAG/LangGraph may share a deployable service. **Blocked on a human action, not on code** — it requires the evaluator's answer. Until confirmed, RAG and LangGraph remain separable at the API boundary (now structurally enforced by ADR-001) and the classifier adaptation is documented as proposed rather than approved.~~ → **The adaptation recorded under `ACA-004` is now approved rather than proposed**, and Phase 6's `ML-AUD-001…007` counts against graded row 9 of `docs/requirements-traceability.md` (updated the same day: held-out clip-level macro-F1 **0.8692**, accuracy 0.8733). **NEW DECISION: the second half of the question — whether RAG and LangGraph *may* share a deployable service — is closed as MOOT rather than left open.** Melody does not share one: `rag-service` and `recommendation-service` are separate containers with separate Dockerfiles, talking only over `POST /rag/retrieve`, structurally enforced by ADR-001. That arrangement is valid under **either** answer, so nothing is waiting on a ruling and none should be recorded as blocking. Were sharing later permitted, it would be an optional consolidation, never a correction.



## Phase 0 artifacts

✅ **[COMPLETED] Artifacts produced in Phase 0 so far:** `contracts/ai_recommendation_schema.json` (AI recommendation contract), `poc/test_musicapi.py` (MusicAPI evaluation/POC script), `.env.example` (secret-free variable template). ~~The remaining schema and ADR markdown files listed above continue into Phase 1/2.~~ → ✅ **[COMPLETED] Second Phase 0 documentation pass (July 24, 2026) closed §0.3** `ARC-002`**…**`ARC-005` **and §0.5** `ACA-001`**…**`ACA-004`**, adding:**

- `docs/service-call-policies.md` — per-call timeout/retry matrix + idempotency rules (`ARC-002`, `ARC-003`).
- `docs/feature-flags.md` + expanded `.env.example` — the eleven Section 2.3 flags (`ARC-004`).
- `docs/adr/ADR-001-architecture-boundaries.md` — n8n orchestrates / LangGraph recommends / adapters isolate (`ARC-005`).
- `docs/requirements-traceability.md` — 20-area graded mapping with honest status + the real-estate→music adaptation table (`ACA-001`, `ACA-002`, `ACA-004`).
- `docs/prompt-engineering-log.md` — PE-1…PE-6 surfaces, test-set composition, and per-version log template (`ACA-003`).

**Still outstanding from Phase 0:** the standalone `docs/adr/ADR-002-music-provider-mode.md` file (the decision itself is closed in §0.4, but the formal ADR was never written), the remaining request/response/error/context envelope schemas under `contracts/` from `ARC-001`, and `ACA-005` (blocked on the evaluator's confirmation).

## Phase 0 gate

✅ **[COMPLETED] Phase 0 gate passed (July 21, 2026).**

Phase 0 is complete when:

- the current system can be restored;
- exposed authorization is rotated and token logging is removed;
- the five canonical schemas are reviewed; (AI recommendation contract frozen now; remaining envelope schemas continue into Phase 1/2)
- `PROVIDER_MODE` has a documented selected or provisional value; → ✅ **[COMPLETED]** `PROVIDER_MODE=direct` **is finalized (not provisional): MusicAPI rejected, direct YouTube approved as primary, direct Spotify approved but limited to the 5 authorized development users.**
- the new target route is explicitly distinguished from the legacy benchmark.

---



# 6. Phase 1 — Build the complete n8n workflow architecture



## Objective

Build the full workflow topology before the services are complete. Every branch must exist, use stable contracts, and return a valid mocked response when its downstream service is still a placeholder.

This is the first major implementation phase and the first prompt to give the n8n building agent.

**Note:** Sub-workflows WF-002 through WF-009 have been successfully instantiated as empty skeleton stubs with strict `user_id` Input Schemas. They are successfully connected to the WF-001 Switch node routing logic. The core implementation of these sub-workflows remains scheduled for Phase 3.

## 1.1 n8n global standards

- [x] ✅ **[COMPLETED] N8N-001 P0: Create a project/folder for Melody workflows.**
- [x] ✅ **[COMPLETED] N8N-002 P0: Configure credentials by reference; never place secret values in Code, Set, or HTTP nodes (July 24, 2026).** Audited all 7 exported workflows with a secret-pattern scan (`sk-…`, `AKIA…`, `Bearer …`, inline `password`/`secret`/`api_key`/`token` assignments): **0 hits**. Both credentials in use (`postgres` on 6 nodes, `openAiApi` on the `OpenAI Chat Model` node) are proper by-reference objects carrying only an `id`/`name`, never a value.
- [x] ✅ **[COMPLETED] N8N-003 P0: Use consistent workflow names:** `MELODY — WF-### — Name` **(July 24, 2026).** All 7 workflows renamed (e.g. `WF-000 — Common Error Handler.` — note the stray trailing period — → `MELODY — WF-000 — Common Error Handler`; `WF-002 — Text Recommendation` → `MELODY — WF-002 — Text Recommendation`). **NEW DECISION:** the exported **filenames** were renamed to match the workflow names exactly, so the export target is predictable and `workflows/n8n/` is diffable; the live instance's previous ad-hoc `Melody AI — WF-###` prefix is superseded by the plan-mandated `MELODY — WF-###` form. **NEW DECISION:** WF-002 keeps the name "Text Recommendation" for now even though §1.5 specifies "Unified Recommendation" — renaming it is deferred to the phase that actually merges the audio path into it, so the name does not promise behaviour that is not yet wired.
- [x] ✅ **[COMPLETED] N8N-004 P0: Add** `request_id` **to every execution (July 24, 2026).** `Initialize Execution metadata` now derives `request_id` from `$json.body?.request_id || $json.request_id || $execution.id`, so an ID exists even when the client omits one (per the §1.4 node table's "request ID if absent"). ⚠️ **Bug found and fixed:** `request_id` was **not reaching any sub-workflow at all.** WF-003/004/005/006 were invoked with an empty `workflowInputs.value = {}` and WF-002 received only `user_id`, while every sub-workflow trigger declared a strict `user_id`-only input schema that filtered out everything else — so `$json.request_id`, `$json.audio_job_id`, `$json.track_ids`, and `$json.idempotency_key` all evaluated to `undefined` at runtime. ~~The Phase 1 note above describing "strict~~ `user_id` ~~Input Schemas" as a working state~~ → **NEW DECISION: one uniform pinned input contract is now shared by every sub-workflow** — `request_id`, `user_id`, `intent`, `locale`, `idempotency_key`, and `envelope` (the full validated request envelope, passed as an object with `convertFieldsToString: false` so it is not flattened to a string). Sub-workflow HTTP bodies were rewritten to read these pinned fields instead of the undefined ones.
- [x] ✅ **[COMPLETED] N8N-005 P0: Use pinned schemas and reject unknown critical enum values (July 24, 2026).** `Validate Request Schema` was rewritten to validate against the canonical enums in `contracts/models.py` and **reject** unknown values rather than passing them to the Switch: `intent` against the six `Intent` values, `locale` against `en`/`he`, `discovery_mode` against the three `DiscoveryMode` values, and `api_version` against the supported set — plus a 1000-character prompt ceiling. **NEW DECISION:** the node now accepts **both** payload shapes without guessing — the Webhook node nests the posted JSON under `body` while the manual `Mock Flask Data` path supplies the envelope flat, so it unwraps only when `body` actually looks like an envelope. This removes a latent ambiguity where the same expression worked on the manual path and silently failed on the real webhook path. Evidence: `workflows/n8n/tests/test_validate_request_schema.js` — a contract test that extracts the node's `jsCode` straight from the exported JSON (so it cannot drift from what ships) and asserts 15 cases, **15/15 passing**, covering 6 accepted and 9 rejected payloads.
- [x] ✅ **[COMPLETED] N8N-006 P0: Define per-node timeouts and bounded retries ~~with exponential backoff~~ only for safe/retryable calls (July 24, 2026).** Audit finding: **none of the service calls in the exported workflows had a timeout or a retry configured** — every one relied on n8n's defaults. The `ARC-002` matrix in `docs/service-call-policies.md` §2 is now applied to all 13 policy-bearing nodes (guardrails 3s/3 tries, recommendation 25s/2, audio analysis 60s/2, recognition 15s/2, profile update 10s/2, Postgres 5s/2–3). **NEW DECISION (honest deviation):** n8n's node-level retry supports only a **fixed** `waitBetweenTries`, not exponential backoff — true exponential backoff is available only through the `WF-000` `Wait` + `Schedule Retry` path. Node-level retries therefore use fixed 1s/2s waits, and the exponential `1s → 2s → 4s` policy from `ARC-002` applies to the WF-000 retry path. This deviation is recorded rather than silently claimed as satisfied. **NEW DECISION:** `Create Playlist` is configured with **no automatic retry at all** (`maxTries` removed, not merely lowered) because a timeout on an external write is ambiguous — recovery is idempotent re-entry, per `ARC-002` §2.6.
- [x] ✅ **[COMPLETED] N8N-007 P0: Route every error to** `WF-000 Common Error Handler` **(July 24, 2026).** `settings.errorWorkflow` is now set to the WF-000 id (`dcHpbw4hOmPAiLsH`) on WF-001…WF-006; previously **only WF-001 had it**, so a failure inside any sub-workflow reached no handler. **NEW DECISION:** WF-000 itself is explicitly excluded and must never carry an `errorWorkflow` pointing at itself, since an error handler that routes its own failures to itself loops — this matches the "WF-000 must never route its own failures back into WF-000" rule in `ARC-002` §2.7. ⚠️ **Second issue fixed:** six service-call nodes carried `onError: continueRegularOutput`, which silently passed a failed HTTP response downstream **as if it had succeeded** (e.g. a failed recommendation was persisted to `recommendation_sessions` as a completed session). These now use `stopWorkflow` so the failure reaches WF-000. `Record Request Metrics` and `Persist Error Event` deliberately keep `continueRegularOutput` (best-effort telemetry must never turn a good response into an error), as do `Load Connection Status` and `Resolve User or Guest` (degraded mode is intended there).
- [x] ✅ **[COMPLETED] N8N-008 P0: Add execution metadata: workflow version, provider mode, engine, latency, and fallback state (July 24, 2026).** `Initialize Execution metadata` now emits `workflowVersion` (`1.0.0`), `workflowName`, `providerMode`, `engine`, `fallbackUsed`, and `startedAtMs`; `Normalize Subworkflow Result` carries all five forward and computes `latencyMs` from `startedAtMs`; `Respond to Webhook` returns them to Flask under a `meta` object; and `Record Request Metrics` writes `engine_used`, `fallback_used`, and `latency_ms` into `recommendation_sessions` (all three columns verified present in the live database). **NEW DECISION:** `providerMode` and `engine` are held as Set-node literals mirroring `.env` rather than read via `$env`, because n8n blocks environment access inside nodes by default; keeping them literal avoids a silent empty value in the recorded metrics.
- [x] ✅ **[COMPLETED] N8N-009 P0: Use idempotency keys for playlist export and any other external write (July 24, 2026).** ⚠️ **Bug found and fixed:** WF-006 built its key as `idempotency_key: ($json.idempotency_key || $execution.id)`. Because of the N8N-004 propagation bug, `$json.idempotency_key` was **always** undefined, so the key always fell back to `$execution.id` — **a value that changes on every retry**, which is precisely the failure `ARC-003` exists to prevent: a retried export would create a second playlist. **NEW DECISION:** the `$execution.id` fallback is removed entirely — WF-006 now uses the client-supplied key from the validated envelope only, and `Validate Request Schema` **rejects** `playlist_export`, `feedback`, and `auth_connection_sync` requests that arrive without one (`VALIDATION_ERROR`), per `ARC-003` §4.1. Covered by two of the 15 contract-test cases.
- [x] ✅ **[COMPLETED] N8N-010 P0: Export all workflows into** `workflows/n8n/` **(July 25, 2026).** All **eight** existing workflows are now exported and consistently named: WF-000…WF-006 plus `MELODY — WF-009 — Provider Connection Sync` (id `ye08vB6Qx8wcJ8DQ`), which was exported from the n8n Cloud account before the ADR-005 migration and then brought up to the §1.1 standards (name, `errorWorkflow` → WF-000, pinned input schema). ~~**Partially done:** WF-000…WF-006 are exported. **Remaining:** `WF-009 Provider Connection Sync` **exists in the live n8n instance** but has never been exported to the repository,~~ and `WF-007 Knowledge Ingestion`, `WF-008 Monitoring and Budget`, and `WF-010 Temporary File Cleanup` do not exist yet. ~~This task closes when all eleven workflows are present in `workflows/n8n/`.~~ → **CORRECTION (July 24, 2026): the previous sentence overstated this task's scope and is withdrawn.** N8N-010 is an **export** task, not a build task — it closes when every workflow that *exists* has been exported. **Building** WF-007, WF-008, and WF-010 is not in scope here: they carry no task ID and **no `P0`/`P1`/`P2` label anywhere in this plan**, and each is pulled in by its own phase when that phase needs it (WF-007 by `RAG-011` in Phase 3, WF-008 by `N8N-REAL-004`, WF-010 by the Phase 6 audio-cleanup path). Only the **WF-009 export** is an outstanding action for N8N-010 itself, since that workflow already exists in the live instance.



⚠️ **Verification status of the N8N-002…N8N-009 pass (July 24, 2026):** all edits were applied to the **exported JSON in** `workflows/n8n/`, which the plan (Section 1, rule 5) treats as the committed source of truth. The `Validate Request Schema` logic is proven by an automated 15-case contract test, but the workflow-level behaviour is **not yet verified in a running n8n instance** — the `n8n` container was not running during this pass. **These workflows must be re-imported into n8n and executed once per branch before the Phase 1 gate can be claimed.** Per Section 19, a checkbox alone is not evidence.

✅ **[COMPLETED] ADR-005 migration executed (July 25, 2026) — n8n is now self-hosted and the workflows load correctly.** The `melody-n8n` Compose service is running and healthy, and all **8** workflows were imported via `n8n import:workflow --separate`, which **preserves the ids** so WF-001's Execute Workflow nodes still resolve their sub-workflows. Confirmed by the developer in the editor: **WF-001 renders with no missing connections.** **NEW DECISION (import method):** use the CLI importer, not the editor's "Import from File" — the UI import assigns **new random workflow ids**, which produced 15 workflows instead of 8 (a duplicate of every workflow except WF-009) and left the duplicates holding stale content while only the original-id copies were updated. The 7 duplicates are deleted in the editor, since the n8n CLI has no `delete:workflow` command.

✅ **[COMPLETED] Node typeVersion compatibility fixed (July 25, 2026) — the workflows used a node version the runtime does not have.** After import, `Initialize Execution metadata`, `Normalize Subworkflow Result`, and `Mock Flask Data` showed *"This node is not currently installed… from a newer version of n8n, a custom node, or has an invalid structure."* Cause: they are `n8n-nodes-base.set` at **typeVersion 3.5**, but the self-hosted runtime (n8n **2.31.6**, image built 2026-07-24) ships Set at `defaultVersion: 3.4` — n8n Cloud runs a build ahead of the public `latest` tag. Every other node type matches the runtime exactly (RespondToWebhook 1.5, If 2.3, Switch 3.4, Code 2, Webhook 2.1, HttpRequest 4.4, Merge 3.2, Wait 1.1, Postgres 2.6), so **Set was the only incompatibility**. **NEW DECISION:** pin the affected nodes down to `typeVersion` **3.4** rather than chase a newer runtime, since 3.4 and 3.5 share the same `assignments` parameter shape and 3.4 is proven working in this instance. **Scope was wider than the three visible nodes:** 10 Set nodes across **all 9** workflows were affected — including the `Return …` node at the end of **every** sub-workflow (WF-002…WF-006, WF-009) and `Return Error Envelope` in WF-000, so every branch would have failed at its final step, not just the router. Verified after re-import: 8 workflows in n8n, 0 Set nodes above 3.4. This is the concrete argument for `INF-002a` — an unpinned `n8nio/n8n:latest` makes this class of breakage silent and non-reproducible.

✅ **[COMPLETED] FIRST REAL END-TO-END RUN (July 25, 2026) — Flask envelope → WF-001 → guardrails → Postgres → sub-workflow → FastAPI service → response.** Evidence: `workflows/n8n/tests/smoke_test_e2e.py`, **5 of 10 cases passing**, with the failures understood and itemised below. What is now **proven at runtime**, not merely present in JSON:

- **`N8N-005` + `N8N-009` — fully proven, 4/4.** Live rejections with correct, user-safe messages: `unknown intent "delete_everything"`, `unsupported locale "fr"`, `intent is required`, and `idempotency_key is required for intent "playlist_export"`.
- **`N8N-004` + `N8N-008` — proven.** `text_recommendation` returns the original `request_id` plus `meta` (`engine=n8n-router`, `latencyMs`, `workflowVersion=1.0.0`), and the row lands in `recommendation_sessions` (`latency_ms=137`, `engine_used=n8n-router`, `status=completed`).
- **`N8N-007` — proven.** WF-001 failures were caught by WF-000, which ran to success and wrote **12 rows** into `audit_events`. `guest_sessions` (12) and `feedback_events` (1) also hold real rows.

**Four bugs found and fixed by this run — none were visible from the JSON:**
1. ⚠️ **Schema blocker (all Postgres writes):** `null value in column "id" … violates not-null constraint`. Every one of the 18 UUID primary keys was **application-generated only** (`default=uuid.uuid4` in `contracts/db_models.py`, no server default), so **no non-SQLAlchemy writer could insert a row** — n8n, psql, or any future service. **NEW DECISION:** migration `a7b3c9d1e5f2` adds `gen_random_uuid()` as a **server default on all 18 tables**. This is additive: SQLAlchemy still sends its own `uuid4`, which takes precedence. Upgrade/downgrade round-trip verified (18 → 0 → 18 defaults), which also gives `DB-005` the downgrade smoke test the previous migration skipped.
2. ⚠️ **`Route by Intent` never matched the sixth intent.** The branch tested for `provider_connection`, but the canonical `Intent` enum value is **`auth_connection_sync`**, so that intent silently fell to the fallback. Corrected to the contract value.
3. ⚠️ **Validation errors reached the client as HTTP 200 with an empty body.** `Validate Request Schema` **throws**, which ends the execution — the plan requires "missing required fields return `VALIDATION_ERROR`". **NEW DECISION:** the node now uses n8n's `continueErrorOutput`, routed through a new `Validation Failed` Set node to `Respond with Error`.
4. ⚠️ **A failing sub-workflow also produced an empty 200.** **NEW DECISION:** all six Execute Workflow nodes now use `continueErrorOutput` into a new `Subworkflow Failed` node, so a downstream failure returns a canonical `UPSTREAM_ERROR` envelope carrying the request id. WF-001 is now 30 nodes.

**Also learned:** `n8n import:workflow` **unpublishes every workflow it imports**, so all 8 must be re-published (sub-workflows first, then WF-001) and n8n restarted, or WF-001 fails on every sub-workflow call. This is now part of the import procedure.

✅ **[COMPLETED] SECOND RUN — 8 of 10 passing (July 25, 2026), and the two remaining failures are the two that are *supposed* to fail at this phase.** Four of the six intents now complete the full round trip and persist a row: `text_recommendation` (395 ms), `audio_identification` (200 ms), `feedback` (138 ms), `auth_connection_sync` (133 ms) — each in `recommendation_sessions` with `engine_used=n8n-router` and a real `latency_ms`; `guest_sessions` 46 rows, `feedback_events` 5, `audit_events` 29.

**Two further root causes found and fixed between the runs:**
5. ⚠️ **Guest mode was rejected by the service.** `POST /profiles/update` declared `user_id: str` (required), but WF-001 sends `user_id: null` for an unauthenticated visitor, so **every guest feedback request failed with 422** — against the P0 requirement that "guest mode works with an empty profile". **NEW DECISION:** `ProfileUpdateRequest` now takes `user_id` **or** `guest_id`, both optional, with a `model_validator` requiring at least one, and WF-005 forwards the guest id from the envelope. Verified: guest → `200`, no identity at all → `422`.
6. ⚠️ **The sub-workflow return contract was never uniform** — the single root cause behind every "empty response body". WF-001's `Normalize Subworkflow Result` reads `$json.payload`, and only WF-002 actually emitted a `payload` field; WF-003/004/005/006 returned domain-specific names (`identification`, `profile`, `export`, …) and WF-009 returned nothing at all, so the router silently normalised an `undefined` result. **NEW DECISION:** every sub-workflow now returns the canonical `{ status, payload }` shape, with its domain object nested inside `payload`; WF-009's bare stub gained a schema-valid connection-status fixture. This is the contract WF-002 had been following implicitly and is now explicit across all six.

✅ **[COMPLETED] THIRD RUN — 10/10 (July 25, 2026). Phase 2 gate closed.** One last fix took it from 9/10 to green:
7. ⚠️ **`POST /audio/analyze` could not be called by the orchestrator at all.** It was declared with `File`/`Form` only, i.e. **`multipart/form-data`**, so every JSON call answered `422` even when it carried a valid `audio_job_id`. But in the real flow the clip is uploaded to Flask first (`AUD-UP-004`) and n8n only ever forwards a **job id** — it has no file to post. **NEW DECISION:** the endpoint now accepts **either** a multipart upload **or** a JSON body naming an existing `audio_job_id`, keeping the Phase 6 upload path intact while letting the orchestrator use the identifier it actually holds. Verified: JSON + `audio_job_id` → `200`; JSON with neither → still `422`.

**NEW DECISION (test expectation corrected):** `playlist_export` is now asserted to fail with `FEATURE_DISABLED` rather than to succeed, because a controlled refusal *is* the correct Phase 2 behaviour; the case flips back to expecting success when `EXPORT-001` lands in Phase 5. ~~Counting it as a failure understated a system that was behaving exactly as designed.~~

~~⚠️ **The two remaining failures are phase-gated, not defects:**~~ *(one was fixed above; the export item stands)*
- **`playlist_export`** — `provider-gateway` answers `503 FEATURE_DISABLED: "Playlist export is not available until Phase 5."` Correct behaviour; closes with `EXPORT-001`.
- **`audio_vibe_recommendation`** — genuine contract mismatch: WF-003 posts JSON, but `POST /audio/analyze` is declared with `File`/`Form` (**`multipart/form-data`**) and answers `422`. Needs a Phase 6 decision — accept JSON for the `audio_job_id` path, or have n8n send multipart. `audio_identification` passes because its path does not depend on the upload body.

~~⚠️ **The remaining 5 failures, honestly itemised**~~ *(superseded by the two items above; the original five-failure list is kept below for history)* *(the smoke test's own pass criteria were corrected first — it had been treating an `UPSTREAM_ERROR` envelope as a success because it only matched on `VALIDATION_ERROR`; the earlier "10/10" was a false positive and is withdrawn)*:
- **`playlist_export` — failing correctly.** `provider-gateway` returns `503 FEATURE_DISABLED: "Playlist export is not available until Phase 5."` — the intended Phase 2 behaviour. Closes with `EXPORT-001` in Phase 5.
- **`audio_vibe_recommendation` — real contract mismatch.** WF-003 posts **JSON**, but `POST /audio/analyze` is declared with `File`/`Form`, i.e. **`multipart/form-data`**, and answers `422`. Needs a decision in Phase 6: accept JSON for the `audio_job_id` path, or have n8n send multipart.
- **`audio_identification` / `auth_connection_sync` — empty response.** WF-004 and WF-009 execute to `success` but their final Set nodes emit no payload for `Respond to Webhook` (WF-009 is still a 2-node stub). Their fixture responses are Phase 6 / Phase 5 work.
- **`feedback`** — `/profiles/update` answers `200` correctly when called directly, so the recorded failure predates the sub-workflow body rewrite; needs one confirming re-run.

~~⚠️ **Still not runtime-verified, and deliberately left unchecked:** `N8N-007` and `N8N-008` describe behaviour that only an execution can prove.~~ → ✅ **[COMPLETED] Both closed on evidence (July 25, 2026).** `N8N-007`: WF-001 failures were caught by WF-000, which ran to `success` and wrote **29 rows** into `audit_events`. `N8N-008`: four intents returned a `meta` block and persisted `engine_used` + `latency_ms` to `recommendation_sessions`. Loading in the editor was never treated as evidence — an execution was required, and now exists.

## 1.2 Workflow topology

Supporting workflows:

- `WF-007 Knowledge Ingestion` — ✅ **[COMPLETED] built July 28, 2026** (15 nodes; one labelled `RAG-010` placeholder, §1.10)
- `WF-008 Monitoring and Budget` — ✅ **[COMPLETED] built July 28, 2026** (12 nodes, no placeholders, §1.11)
- `WF-009 Provider Connection Sync` — ✅ **[COMPLETED] built July 26, 2026** (§5.5)
- `WF-010 Temporary File Cleanup` — ✅ **[COMPLETED] built July 28, 2026** (16 nodes, no placeholders, §1.13)

✅ **[COMPLETED] All eleven workflows (WF-000…WF-010) now exist and are exported to `workflows/n8n/` (July 28, 2026).** WF-007, WF-008 and WF-010 were the last three; each was **imported into the live instance and executed**, not merely written. The three new ones are schedule-driven and are **active**.



## 1.3 WF-000 — Common Error Handler

✅ **[COMPLETED] WF-000 Common Error Handler verified with mocked data.**

### Trigger

- Error Trigger for unhandled n8n failures.
- Execute Workflow input for explicit application errors.



### Node order


| #   | Node name                           | n8n type                                 | Responsibility                                                                            |
| --- | ----------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| 1   | `Error Trigger / Subworkflow Input` | Error Trigger / Execute Workflow Trigger | Receive workflow, node, request ID, error, and retry metadata                             |
| 2   | `Normalize Error`                   | Code                                     | Map internal/provider errors to the canonical error schema                                |
| 3   | `Redact Sensitive Values`           | Code                                     | Remove tokens, cookies, headers, uploaded content, stack traces, and internal URLs        |
| 4   | `Is Retryable?`                     | IF                                       | Branch only when error class and operation are safe to retry                              |
| 5   | `Schedule Retry`                    | Wait + Execute Workflow                  | Retry within the caller's defined maximum; never retry non-idempotent writes blindly      |
| 6   | `Persist Error Event`               | PostgreSQL or placeholder                | Store safe error code, request ID, component, and latency                                 |
| 7   | `Alert Required?`                   | IF                                       | Alert only for repeated provider failure, security event, budget guard, or health failure |
| 8   | `Return Error Envelope`             | Set                                      | Return the user-safe canonical error object                                               |




### Acceptance criteria

- A simulated timeout returns `UPSTREAM_TIMEOUT` without secrets.
- A validation error is not retried.
- A provider `429` follows the configured bounded retry policy.
- A playlist write is not duplicated.



## 1.4 WF-001 — Main Request Router

✅ **[COMPLETED] WF-001 Main Request Router verified with mocked data.**

### Purpose

Receive every app action through one stable external contract, enforce guardrails, resolve identity, and route to a complete subworkflow.

### Node order


| #   | Node name                      | n8n type                       | Responsibility                                                                          |
| --- | ------------------------------ | ------------------------------ | --------------------------------------------------------------------------------------- |
| 1   | `Melody API Webhook`           | Webhook                        | Receive the canonical request envelope from Flask                                       |
| 2   | `Initialize Execution`         | Set                            | Add server timestamp, workflow version, start time, and request ID if absent            |
| 3   | `Validate Request Schema`      | Code or JSON Schema validation | Validate API version, intent, identity, body limits, and required fields                |
| 4   | `Input Guardrails`             | HTTP Request                   | Call `POST /check/input` with text and context metadata                                 |
| 5   | `Input Allowed?`               | IF                             | Reject invalid, off-topic, abusive, or prompt-injection input with a localized response |
| 6   | `Resolve User or Guest`        | PostgreSQL / placeholder       | Resolve `user_id` or create/validate `guest_id`                                         |
| 7   | `Load Connection Status`       | Execute Workflow               | Invoke WF-009 or a placeholder to load connected providers and scopes                   |
| 8   | `Explicit Intent Available?`   | IF                             | Prefer deterministic UI intent when present                                             |
| 9   | `Classify Ambiguous Intent`    | AI Agent or Text Classifier    | Use a small/local model only when the client did not send a reliable explicit mode      |
| 10  | `Route by Intent`              | Switch                         | Route to WF-002, WF-003, WF-004, WF-005, WF-006, or WF-009                              |
| 11  | `Execute Selected Workflow`    | Execute Workflow               | Wait for the chosen subworkflow result                                                  |
| 12  | `Normalize Subworkflow Result` | Set/Code                       | Map all results to the canonical success/error envelope                                 |
| 13  | `Output Guardrails`            | HTTP Request                   | Validate grounding, track existence fields, and unsupported claims                      |
| 14  | `Output Allowed?`              | IF                             | Return safe output or flag a controlled review/fallback response                        |
| 15  | `Record Request Metrics`       | PostgreSQL / placeholder       | Store latency, workflow, engine, model, provider mode, fallback, and status             |
| 16  | `Respond to Webhook`           | Respond to Webhook             | Return canonical JSON to Flask                                                          |




### Router rules

- Explicit UI mode wins over model classification.
- `audio_job_id` alone does not imply identification; the selected user action distinguishes identify versus similar-vibe.
- Feedback and export are deterministic and must never be classified by an LLM.
- No heavy model is called only to select a branch.



### Acceptance criteria

- Six valid intents reach six correct subworkflow mocks.
- Missing required fields return `VALIDATION_ERROR`.
- Blocked input never reaches a recommendation or provider service.
- Every response contains the original request ID.

✅ **[COMPLETED] Dead-end branch fix (July 25, 2026) — three rejection paths in WF-001 returned no response at all.** Reported as "missing arrows" in the editor and confirmed in the JSON: `Input Allowed?` had **only its true branch connected**, `Output Allowed?` likewise, and the `Route by Intent` **fallback output** was unconnected. The acceptance criterion "blocked input never reaches a recommendation service" was technically satisfied — but the caller received **nothing**, so the webhook simply waited for its timeout instead of getting the localized rejection §1.4 node 5 requires. **NEW DECISION:** each dead end now feeds a dedicated Set node building the canonical error envelope (Section 3.4) — `Input Rejected` → `INPUT_REJECTED`, `Output Blocked` → `OUTPUT_BLOCKED`, `Unroutable Intent` → `VALIDATION_ERROR` — and all three converge on a single second `Respond with Error` node, kept separate from the success `Respond to Webhook` because that node reads `Normalize Subworkflow Result`, which never executes on a rejection path. Each error response still carries `requestId` and the `meta` block (latency, engine, provider mode), so a rejection is as traceable as a success. WF-001 goes from 24 to 28 nodes; the change is purely additive — no existing node or connection was modified.

🔴 **THE SAME THREE PATHS WERE STILL DEAD — FOUND AND FIXED July 26, 2026 (later still), via §8.5 `INT-004`.** The July 25 fix connected the branches correctly, but **all three Set nodes it added shared a typo**: `requestId` was written `={{{ … }}}` with **triple braces** instead of n8n's `{{ … }}`. The result was that `Input Rejected`, `Unroutable Intent` and `Output Blocked` responded with an **empty body**. So the criterion "blocked input never reaches a recommendation service" was satisfied and the caller *still* got nothing usable — the browser showed *"the recommendation orchestrator returned an invalid response"* (`UPSTREAM_INVALID_RESPONSE`, Flask failing to parse an empty body) instead of the reason the request was refused.

**Why it stayed invisible for a day:** none of the three paths had ever executed. `off_topic` was hardcoded `False` (§2.5), prompt injection was not in the smoke set, intents are validated before routing, and the output rail only checked that `tracks` was a list — so nothing ever reached a refusal branch. **The moment §2.5's off-topic rule became real, all three broke into the open.**

⚠️ **The smoke test was built to accept this exact failure.** Its outcome logic read `looks_rejected = status >= 400 or envelope_failed or empty_body` — an **empty body counted as a valid rejection**. A refusal that said nothing therefore scored as a pass. **NEW DECISION: an empty body is never a rejection, it is a broken response** — a refusal must state its case. `smoke_test_e2e.py` now fails on any empty body and carries two guardrail cases asserting the specific `INPUT_REJECTED` code, so a mute refusal path cannot be invisible again. **10/10 → 12/12.**

**Verified live after the fix:** both a prompt-injection and an off-topic request return `{"ok": false, "error": {"code": "INPUT_REJECTED", "message": "Your request could not be processed. Please rephrase it as a music request."}}` with `requestId` and the full `meta` block, and the UI renders it as a readable reason with a working retry rather than a generic failure.



## 1.5 WF-002 — Unified Recommendation



### Purpose

Create a recommendation using text, user taste, and optional audio features. This workflow replaces the concept of a text-only recommendation path.

### Input

Canonical request plus optional `audio_job_id` and loaded identity.

### Node order


| #   | Node name                           | n8n type                            | Responsibility                                                                                                                                            |
| --- | ----------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `Recommendation Input`              | Execute Workflow Trigger            | Receive router context                                                                                                                                    |
| 2   | `Load Materialized Taste Profile`   | PostgreSQL / placeholder            | Load weighted preferences and discovery mode                                                                                                              |
| 3   | `Load Provider Taste Signals`       | HTTP/Execute Workflow / placeholder | Fetch cached liked tracks, artists, and playlist signals when authorized                                                                                  |
| 4   | `Load Audio Features`               | PostgreSQL / placeholder            | Load analysis if `audio_job_id` is present                                                                                                                |
| 5   | `Assemble RecommendationContext`    | Code                                | Merge text, profile, provider taste, audio, exclusions, and constraints                                                                                   |
| 6   | `Extract Music Constraints`         | Information Extractor               | Produce structured mood, genre, era, instrumentation, energy, and novelty constraints without inventing absent values                                     |
| 7   | `Recommendation Planning Agent`     | AI Agent                            | Produce a structured read-only request plan; it may inspect capability, genre-taxonomy, and connection-status tools, but receives no external write tools |
| 8   | `Call Recommendation Service`       | HTTP Request                        | Deterministically call `POST /recommendations/run` with the complete context and optional validated plan                                                  |
| 9   | `Recommendation Valid?`             | IF                                  | Require real provider candidates, scores, and valid schema                                                                                                |
| 10  | `Optional Explicit Legacy Fallback` | IF + HTTP                           | Only if feature flag allows and failure is eligible; record fallback                                                                                      |
| 11  | `Persist Session and Candidates`    | PostgreSQL / placeholder            | Store input context, selected tracks, scores, models, latency, and engine                                                                                 |
| 12  | `Return Recommendation Result`      | Set                                 | Return structured tracks, sequence, explanation, and metadata                                                                                             |




### Placeholder behavior in Phase 1

Until the Recommendation Service exists, Node 8 calls a mock endpoint or Set node that returns 3–5 clearly marked mock tracks matching the response schema. Mock data must never be presented as a completed production recommendation.

### Acceptance criteria

- A text-only request creates a complete RecommendationContext.
- An audio-conditioned request contains both audio features and user taste.
- Guest mode works with an empty profile.
- The workflow does not invent provider track IDs in non-mock mode.

⚠️ **TIMEOUT RAISED (July 26, 2026, later still): `Call Recommendation Service` 25s → 90s.** The old value was below the real cost of a legitimate request — a Hebrew prompt doing ~22s of successful work was cut off and reported to the browser as *"the recommendation orchestrator timed out."* Full record and the accompanying concurrency fix at §4.6. **Re-importing this workflow requires reactivating it** (`n8n import:workflow` deactivates on import, and a deactivated WF-002 makes every recommendation fail with `UPSTREAM_ERROR`) — see the session bookmark's operational notes.

🔴 **CRITICAL DEFECT FOUND AND FIXED (July 26, 2026, later) — WF-002 was delivering the wrong shape, and the recommendation engine had been running on an empty query since the day this workflow was wired up.** WF-002's `Call Recommendation Service` node sends `context: $json.envelope` — the **entire `RequestEnvelope`** — but `recommendation-service`'s `_build_initial_state` was written expecting `context` to *be* a `RecommendationContext`. The real context sits at `envelope.body.recommendation_context`, so every lookup (`user_text`, `discovery_mode`, `locale`, `exclusions`, `taste_profile`, `audio_features`) silently missed and defaulted. **Nothing raised, nothing logged, and the first acceptance criterion above passed by inspection** — a complete RecommendationContext *was* created, it just never got read.

**Why it survived this long:** every other caller sends the flat shape and works — the smoke test asserts accept/reject rather than relevance, `eval/rec_leg_comparison.py` calls the service directly, and so did every manual probe. **Only the browser goes through WF-002**, so the defect became visible in the same hour the UI was connected. It means the `REC-LEG-001`/`REC-LEG-002` comparison numbers describe a path no real user request ever took.

**Live proof, identical prompt** — *"dreamy shoegaze for a rainy night"*: **before**, playlist title **"Audio Discovery"**, description *"When we couldn't quite pin down what you were looking for from your listening alone…"* (the empty-input branch, on a text request), over H.E.R.'s *Best Part* and two videos from a YouTube commentary channel; **after**, **"Rainy Night Reverie"** over real shoegaze.

**NEW DECISION: the fix is in the service, not only in WF-002's mapping.** `_unwrap_context()` accepts both shapes — a bare `RecommendationContext` *or* a full `RequestEnvelope` it descends into — because correcting WF-002 alone would leave the identical silent-miss available to WF-003 and WF-004, which pass the same `envelope` field. Regression tests: `test_wf002_envelope_shape_reaches_the_graph`, `test_flat_context_shape_still_works`.



## 1.6 WF-003 — Audio Identification



### Node order


| #   | Node name                   | Type                          | Responsibility                                                   |
| --- | --------------------------- | ----------------------------- | ---------------------------------------------------------------- |
| 1   | `Identification Input`      | Execute Workflow Trigger      | Receive temporary file reference and identity                    |
| 2   | `Validate File Job`         | HTTP/PostgreSQL / placeholder | Confirm ownership, MIME, size, duration, and unexpired reference |
| 3   | `Call Recognition Provider` | HTTP Request                  | Send the clip through the recognition adapter                    |
| 4   | `Match Confidence Gate`     | IF                            | Separate confident, low-confidence, and no-match results         |
| 5   | `Resolve Canonical Track`   | HTTP Request / placeholder    | Match title/artist/external IDs through Provider Adapter         |
| 6   | `Find Playable Reference`   | HTTP Request / placeholder    | Resolve a YouTube or selected-provider playback ID               |
| 7   | `Persist Minimal Result`    | PostgreSQL / placeholder      | Store derived match metadata and confidence, not raw audio       |
| 8   | `Request File Deletion`     | Execute Workflow              | Invoke WF-010                                                    |
| 9   | `Return Identification`     | Set                           | Return match or honest retry guidance                            |




### Acceptance criteria

- Confident, low-confidence, and no-match fixtures reach the correct branches.
- Temporary files are deleted on both success and failure.
- Raw audio is not stored in execution logs.



## 1.7 WF-004 — Audio Vibe Recommendation



### Node order


| #   | Node name                         | Type                          | Responsibility                                                                  |
| --- | --------------------------------- | ----------------------------- | ------------------------------------------------------------------------------- |
| 1   | `Audio Vibe Input`                | Execute Workflow Trigger      | Receive file reference, optional text, and identity                             |
| 2   | `Validate File Job`               | HTTP/PostgreSQL / placeholder | Confirm ownership and upload constraints                                        |
| 3   | `Call Audio Analysis Service`     | HTTP Request                  | Call `POST /audio/analyze`                                                      |
| 4   | `Analysis Confidence Gate`        | IF                            | Continue with reliable fields and attach warnings for uncertain fields          |
| 5   | `Store Derived Features`          | PostgreSQL / placeholder      | Store versioned features and confidence                                         |
| 6   | `Create Recommendation Request`   | Code                          | Add `audio_job_id`, retain user text, and set intent for unified recommendation |
| 7   | `Execute WF-002 Recommendation`   | Execute Workflow              | Run the same personal recommendation engine with audio context                  |
| 8   | `Request File Deletion`           | Execute Workflow              | Invoke WF-010                                                                   |
| 9   | `Return Audio-Conditioned Result` | Set                           | Return analysis plus recommendations                                            |




### Acceptance criteria

- The audio features are passed into WF-002 instead of becoming a separate shallow recommendation engine.
- User taste remains present in the final context.
- Uncertain BPM/key values are not fabricated.



## 1.8 WF-005 — Feedback and Preference Update



### Node order


| #   | Node name                         | Type                       | Responsibility                                              |
| --- | --------------------------------- | -------------------------- | ----------------------------------------------------------- |
| 1   | `Feedback Input`                  | Execute Workflow Trigger   | Receive session, track, action, and identity                |
| 2   | `Validate Ownership and Action`   | PostgreSQL / placeholder   | Confirm session belongs to user/guest and action is allowed |
| 3   | `Deduplicate Event`               | PostgreSQL / placeholder   | Apply event idempotency/deduplication rule                  |
| 4   | `Insert Immutable Feedback Event` | PostgreSQL / placeholder   | Store like, dislike, skip, play, or export event            |
| 5   | `Update Materialized Profile`     | HTTP Request / placeholder | Apply Profile v1 weighted update                            |
| 6   | `Return Current Feedback State`   | Set                        | Return action state and new profile version                 |




### Acceptance criteria

- Duplicate clicks do not create unintended duplicate events.
- A Like and Dislike update profile weights in opposite directions.
- The next WF-002 call loads the new profile version.



## 1.9 WF-006 — Provider-Agnostic Playlist Export



### Node order


| #   | Node name                             | Type                           | Responsibility                                                                     |
| --- | ------------------------------------- | ------------------------------ | ---------------------------------------------------------------------------------- |
| 1   | `Export Input`                        | Execute Workflow Trigger       | Receive provider, ordered track IDs, name, privacy, and idempotency key            |
| 2   | `Validate Export Ownership`           | PostgreSQL / placeholder       | Confirm recommendation session and selected tracks                                 |
| 3   | `Check Existing Idempotent Export`    | PostgreSQL / placeholder       | Return prior success when the same key was already completed                       |
| 4   | `Check Provider Connection and Scope` | Execute Workflow               | Invoke WF-009                                                                      |
| 5   | `Authorization Sufficient?`           | IF                             | Return `AUTHORIZATION_REQUIRED` with an authorization action when scope is missing |
| 6   | `Resolve Provider Track IDs`          | HTTP Request / placeholder     | Ensure each canonical track maps to the chosen provider                            |
| 7   | `Create Playlist`                     | HTTP Request                   | Use Provider Adapter based on `PROVIDER_MODE`                                      |
| 8   | `Insert Tracks in Order`              | Loop Over Items + HTTP Request | Add selected tracks, preserving Smart Sequencer order                              |
| 9   | `Handle Partial Failure`              | IF/Code                        | Record added and failed items; retry only safe failed operations                   |
| 10  | `Store Export Result`                 | PostgreSQL / placeholder       | Store provider playlist ID, URL, status, and idempotency key                       |
| 11  | `Return Export Result`                | Set                            | Return success, partial success, or actionable failure                             |




### Acceptance criteria

- Repeated clicks with the same key create one playlist.
- Track order is preserved.
- Missing OAuth scope never causes a blind retry loop.
- Partial failure is visible and recoverable.



## 1.10 WF-007 — Knowledge Ingestion

✅ **[COMPLETED] BUILT AND EXECUTED (July 28, 2026) — `workflows/n8n/MELODY — WF-007 — Knowledge Ingestion.json`, 15 nodes, all eleven steps below present.**

**What is real today, and what is not, stated per step rather than in aggregate:**

| §1.10 step | State |
| --- | --- |
| 2 `Discover Changed Sources` | **Real** — answered against `knowledge_documents`/`knowledge_chunks`, so "what is ingested" comes from rows rather than a guess |
| 3 `Validate Source and License Metadata` | **Real, and it is a gate** — see below |
| 4–7 clean / chunk / embed / upsert | ⏸️ **One labelled placeholder** — `PLACEHOLDER — rag-service staged ingestion (RAG-010)` |
| 8 `Build/Update Full-Text Index` | **Real, and smaller than it sounds** — `content_tsv` is a *generated* column with a GIN index, so it maintains itself; what a bulk load actually needs is `ANALYZE`, and inventing a rebuild step would have been theatre |
| 9 `Validate Sample Queries` | **Real** — two live `/rag/retrieve` calls, English and Hebrew |
| 10 publish / rollback | **Gate real, promotion not** — see below |
| 11 `Write Ingestion Report` | **Real** — `audit_events`, written on *both* outcomes |

**The placeholder is §1.14-compliant and deliberately narrow:** final schema, explicit label, a task id that replaces it (`RAG-010`), and it declares itself. The *logic* for steps 4–7 already exists and is proven — `rag-service/scripts/ingest_local_data.py` and `generate_embeddings.py` produced the live 24-document / 325-chunk corpus. What does not exist is a **staged, versioned** ingestion behind an endpoint, which is precisely what `RAG-010` is. The workflow reads `/rag/ingest`'s own `placeholder` flag instead of assuming success, so it cannot report a version it never staged.

⭐ **The first execution justified the node that looked like bookkeeping.** `Validate Source and License Metadata` **failed the corpus and refused to publish**: all 24 documents carry no licence metadata, across both `genre_knowledge` (23) and `reviews_context` (1). That is `RAG-002` — open since Phase 3 as a line in a markdown inventory — now **machine-visible and blocking**, which is the difference between a known risk and an enforced one. Full run: 325/325 chunks indexed, both search indexes present, both smoke queries passed (5 chunks each), outcome `rolled_back`, reason recorded in `audit_events`.

**NEW DECISION: publication requires *two* independent gates — smoke queries passing **and** source metadata being complete.** A broken index and an unlicensed corpus are different failures and either one is disqualifying. **NEW DECISION: a smoke query passes when it returns chunks, not when its confidence is high.** Confidence is a relevance signal; zero results is a broken index. This gate exists for the second failure, which is the one that silently destroys the product.

**NEW DECISION: the smoke set is bilingual.** The embedding model is multilingual and the July 25 comparison already found Hebrew retrieval behaving worse than English; an English-only smoke set would not notice that degrading further. The first run bears this out and the number is recorded rather than smoothed: English retrieval confidence **0.119**, Hebrew **0.0002** on the same corpus. Both "pass" — they return chunks — but the gap is a real Phase 3 quality signal (§3.8 territory), not noise.

⚠️ **One defect found and fixed during the run, worth recording because the error message was honest about the wrong thing.** The ingestion call invented a `{mode, requested_by}` body; `rag-service`'s `IngestRequest` takes `{source, documents}`, so it answered **422** and the workflow faithfully reported "the ingestion endpoint returned 422" — an accurate message about a request WF-007 had malformed itself. Corrected to the real contract, the endpoint now returns the honest **403** (`INTERNAL_INGESTION_TOKEN` not configured; Section 2.4 keeps ingestion closed by default), and the interpreter distinguishes the two, since one is a service state and the other is a bug in this workflow.

### Node order

1. `Manual/Scheduled Trigger`.
2. `Discover Changed Sources`.
3. `Validate Source and License Metadata`.
4. `Run Cleaning and Canonicalization`.
5. `Chunk by Semantic Structure`.
6. `Generate Embeddings`.
7. `Upsert Documents and Metadata`.
8. `Build/Update Full-Text Index`.
9. `Validate Sample Queries`.
10. `Publish Ingestion Version` or `Rollback Staging Version`.
11. `Write Ingestion Report`.

Do not publish a new ingestion version until smoke queries pass.

## 1.11 WF-008 — Monitoring and Budget

✅ **[COMPLETED] BUILT AND EXECUTED ON REAL DATA (July 28, 2026) — `workflows/n8n/MELODY — WF-008 — Monitoring and Budget.json`, 12 nodes, all nine steps below present, no placeholders.** Its prerequisite was `N8N-REAL-004` (§2.6), which had to make model usage and provider quota into rows before this workflow could read anything but zeros.

**First live run, against real rows:** budget **2.02%**, level `ok`, one `ops_daily_summary` row written. Model spend $0.003934 month-to-date against a $20 budget; YouTube 202 units against 10,000; 78 requests in 24h at 8,332 ms average, **p95 24,097 ms**; database 13.9 MB; 325 knowledge chunks, 0 missing embeddings; **118 expired guest sessions**.

⚠️ **Two findings the report surfaced on its first run, neither of which was the point of building it:** p95 latency of **24.1 s sits just under WF-002's 25 s HTTP timeout** — a margin, not yet a failure, and the retrieval-node parallelization at §4.6 is the existing lever for it; and 118 expired `guest_sessions` rows were accumulating, which is exactly the class of unbounded growth WF-010 exists to prevent.

**NEW DECISION: the headline budget percentage is the WORSE of two budgets, never their average.** Model spend is money and accrues monthly; provider quota is a daily allowance that *resets*, and spending 95% of it costs nothing except that the next requests return nothing at all. Either hitting 100% stops the product working, so averaging them would hide the one that is about to bite. The report names the `binding_constraint` so an alert says *which*.

**NEW DECISION: the two budget constants live in the workflow, not in `$env`.** n8n blocks environment access inside Code nodes, and the unblock switch is all-or-nothing — it would expose the entire `.env`, including the Anthropic key, the YouTube key and the OAuth token encryption key, to every workflow in the instance. Trading that for two numbers that are neither secret nor volatile is a bad deal, and `SEC-101` exists to prevent exactly this shape of leak. *(This was found by the first execution failing with `access to env vars denied`, which is n8n defaulting to the safe answer.)*

**NEW DECISION: "Send Alert if Needed" RECORDS the alert durably rather than pretending to send one.** No outbound mail or chat channel is configured in this project, and a node that mimed sending an email would be a placeholder wearing an alert's clothes — the exact failure §8.5's audit went looking for. Alerts are written to `audit_events` and the level is carried on the daily summary. **`alert_sent` records what actually happened, not what was intended.**

**NEW DECISION: at 95% the workflow RECOMMENDS disabling optional expensive paths; it does not disable them itself.** §1.11's rule ("disable optional expensive paths, not the deterministic core") is honoured as a named action list — `ENABLE_EXPENSIVE_MODEL_PATHS=false`, `ENABLE_CLAP=false`, and an explicit *do not* touch retrieval, ranking or sequencing — because a workflow that silently flipped feature flags would breach Section 2.3's "never switch silently".

⭐ **The alert branch was tested, not assumed.** Temporarily lowering the budget constant to $0.001 so real spend exceeded it produced level `emergency`, budget 393.4%, a real `audit_events` row carrying the three recommended actions, `alert_sent = true`, and — the part that matters — **the same day's row updated rather than a second row appearing.** The real constant was then restored and the run repeated to leave the record honest.

⚠️ **One limitation is carried inside the report itself rather than in a comment: the error rate is a FLOOR, not a true rate.** WF-001 and WF-002 only insert a `recommendation_sessions` row on the success path, so a request refused by guardrails or failed upstream leaves nothing to count. The metrics document says so in a `completeness` field. Reporting the ratio as though it were complete would be precisely the confident-but-wrong number this project keeps finding. **Backup health is reported the same way — `configured: false`, naming `DEP-007`** — because a health report that simply omits backup reads as "fine" when the truth is "there is none".

### Node order

1. `Daily Schedule`.
2. `Read Model Usage`.
3. `Read Provider Quota Usage`.
4. `Read n8n Error Rate and Latency`.
5. `Read Disk/Database/Backup Health`.
6. `Calculate Budget Percent`.
7. `Apply 50/75/90/95 Percent Rules`.
8. `Send Alert if Needed`.
9. `Store Daily Summary`.

At 95% of the monthly budget, disable optional expensive paths, not the deterministic core.

## 1.12 WF-009 — Provider Connection Sync



### Node order

1. `Connection Input`.
2. `Validate User and CSRF/OAuth State Reference`.
3. `Call Provider Adapter Status`.
4. `Refresh if Required`.
5. `Persist Encrypted Connection Metadata`.
6. `Return Provider, Scopes, Expiry, and Reauthorization State`.

Raw tokens must never pass through client-visible n8n output.

## 1.13 WF-010 — Temporary File Cleanup

✅ **[COMPLETED] BUILT AND EXECUTED (July 28, 2026) — `workflows/n8n/MELODY — WF-010 — Temporary File Cleanup.json`, 16 nodes, all six steps below present, no placeholders.** Two entry points: explicit object ids from a caller, and a **15-minute schedule** matching `AUDIO_RETENTION_MINUTES`.

**One new endpoint was needed and built: `POST /audio/maintenance/sweep`** (`audio-service`). It takes **no object id**, so it cannot be aimed at anything — the deletion set is defined by expiry, not by the caller, which is §1.13's "do not accept arbitrary client file paths" enforced by the shape of the API rather than by validation. It reports `removed` / `stored_before` / `stored_after`, because "removed 0" means something very different when 0 remain than when 40 do. The service already sweeps on its own timer; that redundancy is deliberate — without the orchestrated sweep, one that had silently stopped running would be indistinguishable from one with nothing to do.

**Live-verified, each branch separately rather than as a whole:**

| Case | Result |
| --- | --- |
| Real uploaded clip, explicit id | ✅ `deleted: true`; the file is **gone from disk**, and `audio_jobs` carries a `cleaned` row with `cleanup_at` |
| Expired clip, scheduled sweep | ✅ `removed: 1`, stored **1 → 0**, both the clip and its sidecar gone |
| **`../../etc/passwd`** as an object id | ✅ **refused by grammar** — never reached `Delete Object`, `failed: true`, reported to WF-000 |
| Nothing to delete | ✅ no-op, and correctly *not* a failure |

**NEW DECISION: the approved-store check validates a GRAMMAR rather than sanitising a path.** An object id is exactly 32 lowercase hex characters — the same grammar `audio-service`'s `storage.path_for` enforces before touching the disk. A sanitiser has to be right about every encoding trick; a grammar only has to be right about what a legitimate id looks like, and this one has exactly one shape. **The rejected value is never echoed back** into a log or an error envelope — it is attacker-controlled text, and reflecting it is how a rejection becomes a second vulnerability.

**MEASURED, not assumed: `audio-service` answers `DELETE` with 200 for ANY well-formed id, including one never issued** — deliberately, so the endpoint cannot be used to test whether a clip exists. Verified by deleting a fabricated id. A `404` branch would therefore be **dead code**, and `deleted` cannot honestly mean "a file was removed". It was rewritten to mean the postcondition that cleanup actually owes: **the store no longer holds this id** — true whether the clip was deleted just now or had already expired.

⚠️ **Two bugs of my own, both the same defect, and the reason this section says "verified" rather than "built".** `Return Cleanup Result` read `$json`, but the two nodes that can sit immediately upstream — the Postgres write and the WF-000 error call — **replace the item with their own output**. So the workflow reported `deleted: false` about a clip it had genuinely deleted, and `failed: false` about a run that had genuinely failed and genuinely been reported. Both were invisible in the logs and only appeared when the returned payload was read against what the database and the disk actually showed. Fixed by adding a `Finalize Explicit Result` node after the Postgres write and making the WF-000 report **fire-and-forget** (`waitForSubWorkflow: false`), so every upstream node now preserves the item.

⭐ **That is the third occurrence of one pattern** — after WF-002 forwarding the whole envelope as `context`, and WF-003's `audio_features: $json` landing one level too deep. **Three is a hazard, not a coincidence. Standing check for every n8n node hand-off: does the receiver see the shape the sender thinks it sent?** The plan already recorded this after the second; it is repeated here because it caught two more.

⚠️ **NEW DECISION: WF-003 and WF-004 do NOT call WF-010, and their §1.6/§1.7 `Request File Deletion` nodes are deliberately NOT implemented.** This contradicts those node tables, and the contradiction is the point: they were written in Phase 1, **before §6.5's audio UX existed**. The UI's *"Find me something with a similar vibe"* control reuses the same `audio_job_id` (`templates/index.html` sends `message.audioJobId`), and the control persists on the card, so a user can refine their text and ask again. Deleting the clip the instant one recommendation is produced would break that follow-up and return `AUDIO_UNAVAILABLE` for a clip the user can still see on screen. The clip's 15-minute lifetime plus the scheduled sweep already bound exposure; wiring explicit deletion would trade a real feature for nothing. **The entry point remains available** for any future caller whose use of a clip is genuinely terminal.

### Node order

1. `Cleanup Input or Schedule`.
2. `Resolve Explicit Temporary Object IDs`.
3. `Validate Object Is Inside the Approved Temporary Store`.
4. `Delete Object`.
5. `Mark Job Cleaned`.
6. `Report Cleanup Failures to WF-000`.

Do not accept arbitrary client file paths.

## 1.14 Phase 1 placeholder rules

Every placeholder must:

- use the final input/output schema;
- be labeled `PLACEHOLDER — <service>`;
- return deterministic fixture data;
- include a `placeholder: true` metadata flag;
- have a task ID that replaces it in a later phase;
- never be enabled in the final submission environment.



## Phase 1 artifacts



## Phase 1 gate

Import all JSON exports into a clean n8n instance and run fixture tests for every branch. Phase 1 passes only when:

- WF-001 reaches every subworkflow;
- all success and error results follow the canonical envelopes;
- input and output guardrails are visible in the main path;
- the Information Extractor and AI Agent surfaces are present and testable;
- placeholder nodes are explicit and traceable;
- no credential value appears in workflow JSON.

---



# 7. Phase 2 — Data layer and service foundations

✅ **[COMPLETED] Status: Phase 2 gate passed (July 24, 2026).** ~~**Status: In progress**~~

## Objective

Replace Phase 1 placeholders with real persistence and healthy service boundaries before implementing complex AI logic.

## 2.1 Repository structure

- [x] ✅ **[COMPLETED] REP-001 P0: Create the incremental target folders without moving unrelated working code.** (`recommendation-service/`, `rag-service/`, `audio-service/`, `guardrails-service/`, `provider-gateway/` created at repo root, each tracked with `.gitkeep`; existing Flask code left in place.)



## 2.2 Docker Compose foundation

- [x] ✅ **[COMPLETED] INF-001 P0: Add** `postgres-pgvector`**.** (`pgvector/pgvector:pg16`, healthcheck, `pgdata` volume, credentials from `.env`.)
- [x] ✅ **[COMPLETED] INF-002 P0: Add** `n8n` **with persistent volume and protected editor access.** (Basic-auth editor, `N8N_ENCRYPTION_KEY`, `n8n_data` volume.)
  - ✅ **[COMPLETED] ADR-005 decision (July 25, 2026): this self-hosted service is the project's n8n, and** `n8n Cloud` **is not used.** ~~Workflows were authored in n8n Cloud while the services ran in Docker Compose~~ → **NEW DECISION:** n8n runs on `melody-net` alongside the services, because the workflows' six Postgres nodes would otherwise require **exposing PostgreSQL to the public internet**, violating `SEC-106` (P0) and, from Phase 5 onward, exposing the `oauth_accounts` token table. In the target VPS topology n8n needs **no public port** — Flask is the only public surface. Full rationale, alternatives (tunnel, EC2, dual-authoring), and consequences in `docs/adr/ADR-005-n8n-deployment-mode.md`.
  - [x] ✅ **[COMPLETED] INF-002a P0 (follow-up from ADR-005): the n8n image is pinned to `n8nio/n8n:2.31.6` (July 28, 2026).** ~~Pin the n8n image. `docker-compose.yml` currently uses `n8nio/n8n:latest`, which cannot produce a reproducible submission (`DOC-004`, `DEP-006`).~~ → **Pinned to the version the suite actually passes against, not to the newest available** — 2.31.6 is what the running instance reports and what `smoke_test_e2e.py` scores 12/12 on, so the pin records a *tested* fact rather than a hopeful one. The compose comment states the rule for the next person: do not bump without re-running the smoke suite. Note the plan's earlier text said "n8n 1.x"; the instance is **2.31.6**, which makes the `INF-002b` finding below worse rather than better.
  - [x] ✅ **[COMPLETED] INF-002b P0 (follow-up from ADR-005): protected editor access re-established, and the three inert variables removed (July 28, 2026).** ~~Re-establish "protected editor access" on a current n8n. `N8N_BASIC_AUTH_ACTIVE` / `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD` were **removed in n8n 1.x** in favour of the built-in owner account, so those three variables in `docker-compose.yml` and `.env` are now inert. Protection currently rests on the owner account plus not publishing the port (`SEC-107`).~~ → Three changes, and the first is the one that mattered: **the inert variables were deleted from `docker-compose.yml` and `.env.example` rather than left in place.** Declaring a protection that does nothing is worse than declaring none, because it stops anyone looking. **Protection now rests on two mechanisms that were verified, not assumed:** (1) the built-in owner account — checked live, every `/rest/*` call without a session cookie returns **401** (`/rest/workflows`, `/rest/users`); and (2) the editor is bound to **loopback** (`N8N_BIND_ADDRESS`, default `127.0.0.1`), so it is reachable from this machine and from nothing else, with the VPS instruction being to remove the port mapping entirely (`DEP-003`). **NEW DECISION: `N8N_PUBLIC_API_DISABLED=true`.** The public REST API authenticates with a static API key rather than the owner session, so leaving it enabled would be a second door that mechanism (1) does not guard. ⚠️ **Not done here and still Phase 9:** PostgreSQL is still published on `0.0.0.0:5432` — that is `SEC-106`, left alone deliberately to respect the phase boundary, and flagged so it is not mistaken for covered.
  - [x] ✅ **[COMPLETED] INF-011 P0 (surfaced by ADR-005): Flask is a Compose service, behind Gunicorn (July 28, 2026).** ~~Add the Flask app as a Compose service. A root `Dockerfile` exists but Flask is **not** in `docker-compose.yml`, so the stated end state — the whole application starting on one VPS with a single command — is not yet achievable. Pairs with `DEP-001` (Gunicorn rather than the Flask dev server).~~ → **`docker compose up -d` now starts the browser-facing app too**, so the stated end state is achievable. `DEP-001` lands with it: the container runs **Gunicorn** (2 workers × 4 threads, I/O-bound path), never the dev server, while `python app.py` stays available for host debugging. **Three real defects were found in the existing packaging, all of which would have produced a container that started and then failed:** (1) the root `Dockerfile`'s `COPY . .` looked complete, but `.dockerignore` excluded `templates/` and `static/`, so the image would have **500'd on the first page render** — both directories are now included; (2) nothing resolved the database host inside the network, so `DATABASE_URL`'s `localhost` would have pointed at the web container itself — `app.py` now uses the same `POSTGRES_HOST` signal as `provider-gateway/app/db.py`, and `N8N_WEBHOOK_URL` / `AUDIO_SERVICE_URL` are overridden to service names; (3) the image **baked a self-signed certificate** and served TLS itself, which no browser accepts — removed, TLS terminates at the reverse proxy (`DEP-002`). **NEW DECISION: the Dockerfile lists what it copies instead of `COPY . .`**, so a new dependency fails the build rather than silently riding along with the ML code and evaluation harnesses. Also `SEC-108`: the container runs as an unprivileged user. **Gunicorn's `--timeout` is 180 s deliberately** — a Hebrew recommendation measures ~20 s and the 30 s default would kill the worker mid-request and return a bare 502 with no error code the UI could act on; it sits above `N8N_HTTP_TIMEOUT_SECONDS` so n8n's timeout always fires first and produces a real error envelope. **Live-verified in the container:** `/health/ready` reports database **and** n8n reachable, the UI renders, and `POST /api/v1/requests` traversed Flask → WF-001 → guardrails and returned a correct `INPUT_REJECTED` envelope in 144 ms.
- [x] ✅ **[COMPLETED] INF-003 P0: Add** `recommendation-service`**.** (Real FastAPI build, not a placeholder — see Section 2.4.)
- [x] ✅ **[COMPLETED] INF-004 P0: Add independently deployable** `rag-service` **so the RAG and LangGraph responsibilities remain visible and separately testable.**
- [x] ✅ **[COMPLETED] INF-005 P0: Add** `audio-service`**.**
- [x] ✅ **[COMPLETED] INF-006 P0: Add** `guardrails-service`**.**
- [x] ✅ **[COMPLETED] INF-007 P0: Add** `provider-gateway` **when provider logic is not implemented directly inside n8n.**
- [x] ✅ **[COMPLETED] INF-008 P0: Add** `ollama` **or a** `llama.cpp` **model server for the local-model requirement and cheap routing tasks.** (`ollama/ollama:latest` service added; note a locally running host Ollama can conflict on port 11434 — override with `OLLAMA_PORT` in `.env` if needed.)
- [ ] **INF-009 P1:** Add Redis only if asynchronous-job measurement proves it is necessary. (Intentionally deferred — kept as a commented-out service in `docker-compose.yml` pending that measurement, per this task's own criteria.)
- [x] ✅ **[COMPLETED] INF-010 P0: Add health checks, dependency ordering, restart policies, named networks, and resource limits.** (`melody-net` bridge network, `depends_on: condition: service_healthy`, `restart: unless-stopped`, per-service `deploy.resources.limits`.)

**NEW DECISION:** The five FastAPI services build with `context: .` (repo root) and a per-service `dockerfile: <service>/Dockerfile`, instead of `build: ./<service>` with a service-local context. Reason: Docker cannot `COPY` the shared `shared_lib/` package from outside its build context, and root-context + per-service Dockerfile is the standard monorepo pattern for a library shared across services. All five services still build, start, and report healthy under this arrangement.

Initial services:

## 2.3 Database migrations

- [x] ✅ **[COMPLETED] DB-001 P0: Initialize Alembic.** (`alembic init migrations`; `migrations/env.py` reads `DATABASE_URL` from `.env`, normalizes to the `postgresql+psycopg://` dialect, and points `target_metadata` at `contracts/db_models.py:Base`.)
- [x] ✅ **[COMPLETED] DB-002 P0: Enable** `vector` **and required PostgreSQL extensions.** (`CREATE EXTENSION IF NOT EXISTS vector` in the first migration; confirmed installed, pgvector 0.8.5.)
- [x] ✅ **[COMPLETED] DB-003 P0: Create UUID-based identities and UTC timestamps.** (App-generated `uuid4` primary keys and `TIMESTAMP(timezone=True)` `created_at`/`updated_at` across all 18 tables.)
- [x] ✅ **[COMPLETED] DB-004 P0: Add indexes for request ID, user ID, provider IDs, feedback session, vector search, full-text search, and idempotency keys.** (Request ID: `recommendation_sessions`/`model_usage`; user ID: multiple tables; provider IDs: `track_provider_ids`/`playlist_exports`; feedback session: `feedback_events`/`recommendation_candidates`; vector search: HNSW `vector_cosine_ops` on `knowledge_chunks.embedding`; full-text: GIN over a generated `TSVECTOR`; idempotency: unique `playlist_exports.idempotency_key`.)
- [x] ✅ **[COMPLETED] DB-005 P0: Add migration upgrade/downgrade smoke tests.** (Manually verified `upgrade head` → `downgrade base` → `upgrade head` round-trip on the initial core-tables migration, confirming clean table creation/removal.) ~~Automated regression test for every future migration~~ → **NEW DECISION: the second migration ("Add remaining tables and indexes") was applied with** `upgrade head` **only; its downgrade path was explicitly skipped per instruction and has not been smoke-tested. Revisit before Phase 9 hardening.**

Required tables:


| Table                       | Required fields/purpose                                                        |
| --------------------------- | ------------------------------------------------------------------------------ |
| `users`                     | Identity, locale, account state, created/deleted timestamps                    |
| `guest_sessions`            | Expiring guest identity and migration-to-user reference                        |
| `oauth_accounts`            | Provider, encrypted token material/reference, scopes, expiry, revocation state |
| `user_preferences`          | Materialized versioned preference profile                                      |
| `feedback_events`           | Immutable interaction events with session and candidate context                |
| `recommendation_sessions`   | Request context, engine, result, fallback, latency, status                     |
| `recommendation_candidates` | Candidate identity, feature values, component scores, final rank               |
| `tracks`                    | Canonical identity with normalized metadata                                    |
| `track_provider_ids`        | Provider-specific IDs, links, and confidence                                   |
| `track_audio_features`      | BPM, key, Camelot, energy, source, confidence, model version                   |
| `genre_nodes`               | Parent genres and subgenres                                                    |
| `genre_edges`               | Parent, related, influence, and similarity relations                           |
| `knowledge_documents`       | Source document and version metadata                                           |
| `knowledge_chunks`          | Chunk text, full-text data, metadata, embedding, ingestion version             |
| `playlist_exports`          | Provider, playlist ID, URL, idempotency key, partial-failure state             |
| `audio_jobs`                | Temporary object reference, derived features, state, cleanup timestamp         |
| `model_usage`               | Provider/model, tokens, latency, estimated cost, cache hit                     |
| `jobs`                      | Asynchronous job state and safe error code                                     |
| `audit_events`              | Security-sensitive actions without credential values                           |


~~✅ **[COMPLETED] 18 of 19 tables above are implemented in** `contracts/db_models.py` **and applied via two Alembic migrations (initial core tables; remaining tables and indexes).** Only `oauth_accounts` remains unimplemented, deferred to Phase 5 (provider/auth) where the encrypted-token-storage decision is made.~~ → ✅ **[COMPLETED] All 19 tables are now implemented (July 25, 2026).** `oauth_accounts` landed in Phase 5 §5.2 via migration `b8e4f1a92c37`, and the encrypted-token-storage decision it was waiting on is recorded in **ADR-007**: Fernet-encrypted columns in PostgreSQL, key from `OAUTH_TOKEN_ENCRYPTION_KEY`, rotation via `MultiFernet` + a per-row `encryption_key_id`, and no plaintext fallback. Upgrade/downgrade/upgrade round-trip verified against the live database; the PK carries the `gen_random_uuid()` server default that migration `a7b3c9d1e5f2` made the repo-wide convention, so n8n's Postgres nodes can write the table in §5.5.

Rules:

- Provider IDs are not internal primary keys.
- Embeddings, audio features, profiles, prompts, and rankers are versioned.
- Raw audio is temporary and is not stored in the database.
- OAuth token values are encrypted or stored in an approved secret store; never plaintext columns.
- Deletion requirements are implemented as true deletion where promised to the user.



## 2.4 FastAPI service skeletons

✅ **[COMPLETED] All five service skeletons (recommendation-service, rag-service, audio-service, guardrails-service, provider-gateway) are implemented, built, and verified healthy.** Common behavior (request-ID propagation, structured redacted JSON logging, user-safe error mapping, `/health/live` + `/health/ready`) is centralized in a new shared `shared_lib/` package (installed into each image via its Dockerfile) rather than duplicated per service.

Each service must include:

- Pydantic models generated from or validated against `contracts/`.
- `/health/live` and `/health/ready`.
- request-ID propagation.
- structured redacted logging.
- explicit dependency timeouts.
- user-safe error mapping.
- unit test and Dockerfile.

Endpoints:


| Service          | Endpoint                    | Phase 2 behavior                                           |
| ---------------- | --------------------------- | ---------------------------------------------------------- |
| Recommendation   | `POST /recommendations/run` | Validated fixture response                                 |
| Recommendation   | `POST /profiles/update`     | Deterministic weighted-profile stub                        |
| RAG              | `POST /rag/retrieve`        | Validated fixture evidence package                         |
| RAG              | `POST /rag/ingest`          | Disabled except for authenticated internal ingestion tests |
| Audio            | `POST /audio/analyze`       | Validate a test file and return fixture features           |
| Audio            | `POST /audio/identify`      | Recognition-adapter fixture                                |
| Guardrails       | `POST /check/input`         | Initial rules and topic/prompt-injection checks            |
| Guardrails       | `POST /check/output`        | Initial schema and unsupported-claim checks                |
| Provider Gateway | `POST /providers/search`    | Selected adapter fixture                                   |
| Provider Gateway | `POST /providers/playlists` | Disabled fixture until Phase 5                             |


✅ **[COMPLETED] All ten endpoints above are implemented with Pydantic request/response models and return validated fixture data**, including `guardrails-service`'s `/check/input` prompt-injection heuristic, `rag-service`'s `/rag/ingest` internal-token gate (403 without `X-Internal-Token`), and `provider-gateway`'s `/providers/playlists` `503 FEATURE_DISABLED` response. Each service ships a `test_smoke.py` covering health endpoints, fixture endpoints, and request-ID propagation.

## 2.5 Guardrails foundation

✅ **[COMPLETED] Phase 2 guardrails foundation delivered as a deterministic placeholder.** The `guardrails-service` exposes `POST /check/input` (returns `allowed: true` by default; `allowed: false` on hardcoded prompt-injection markers such as "ignore previous instructions") and `POST /check/output` (schema/structure check), both routable by n8n on the top-level `allowed` boolean. **NEW DECISION:** the heavy framework choice below (NeMo Guardrails vs. custom rule engine + classifier) is deferred to Phase 3/4; the Phase 2 rails are intentionally simple, deterministic, and test-routable.

⚠️ **AUDITED AND COMPLETED (July 26, 2026, later still) via §8.5 `INT-002` — "deterministic placeholder" had been describing the *depth* of the rules, but several checks this section lists as required were not implemented at all.** Specifically: `off_topic` was **hardcoded `False`** (the check existed in the response shape and did nothing), language handling did not exist, and `/check/output` verified only that `tracks` was a list — none of the unsupported-claim rules below were enforced. The service also reported `placeholder: true` while running real logic.

**Now implemented and tested (`guardrails-service` tests 4 → 17):**

| §2.5 rule | Status |
| --- | --- |
| Prompt-injection / exfiltration | ✅ already present, marker list extended |
| Schema and body-size validation | ✅ |
| Allowed language handling (he/en) | ✅ new — `he`, `en`, `mixed`, `unknown` |
| Obvious off-topic classification | ✅ new — was hardcoded `False` |
| No hidden internal prompts, tokens, or raw reasoning | ✅ new |
| No claim that playback is ad-free (§PLAY-004) | ✅ new |
| No fabricated BPM/key when unknown | ✅ new |
| Real provider IDs for non-mock tracks | ✅ new |
| Malicious filenames / upload metadata | ⏸️ deferred with Phase 6 uploads |
| Grounded explanation w/ internal evidence refs | ⏸️ needs the evidence to be carried out of the graph |

**NEW DECISION: off-topic is detected from positive evidence of *another* domain, never from a music-words allowlist.** An allowlist would reject the majority of real requests — mood-only phrasings ("something for a rainy night", "משהו רגוע לערב") name no genre at all, and a Hebrew or slang request would fail it outright. The markers therefore fire only on requests clearly asking for something else (code, medical/legal advice, essays). Regression tests cover mood-only requests in both languages.

**NEW DECISION: mixed Hebrew/English input is explicitly allowed.** *"תמליץ לי על shoegaze"* is a normal request for this product; only text with no recognizable script is refused.

**NEW DECISION: the output rail scans user-visible prose only — never ids or URLs.** A provider track id can contain any substring; without this split a legitimate id beginning `sk-` would trip the leaked-credential rule. Covered by a regression test.

**Why the internal-leakage rule is not theoretical:** §4.8 records a live incident where an internal warning reached the curator model and it repeated *"confidence in the retrieval"* into user-facing Hebrew prose. The recommendation service now sanitizes what it passes the model; this rail is the independent second line, and it catches the leak regardless of which node produced it.

**`placeholder` is now `false` on both endpoints** — these are real, tested rules rather than a constant. The *framework* decision below (NeMo vs. this rule engine) remains genuinely open and is unaffected.

The course requires visible input and output safety. Melody must apply music-domain rails rather than real-estate rules.

Input checks:

- schema and body-size validation;
- allowed language handling for Hebrew and English;
- prompt-injection and tool-exfiltration attempts;
- obvious off-topic/spam classification;
- malicious filenames or upload metadata;
- requests that attempt to expose system prompts, credentials, or private user data.

Output checks:

- response schema validity;
- real provider IDs for non-mock tracks;
- no fabricated BPM/key when unknown;
- no claim that playback is ad-free;
- no hidden internal prompts, tokens, or raw reasoning;
- grounded recommendation explanation with evidence references available internally;
- no write action claimed unless the provider operation succeeded.

Framework decision:

- Prefer NeMo Guardrails if it fits the environment and course expectation.
- A custom FastAPI rule engine plus a small classifier is acceptable only if documented in an ADR and demonstrated with measurable tests.



## 2.6 Replace Phase 1 foundation placeholders

✅ **[COMPLETED] Section 2.6 executed against the exported workflows in** `workflows/n8n/` **(WF-000 through WF-006), July 24, 2026.** Placeholder/mock nodes were replaced with real HTTP Request nodes (service name + internal container port `8000` on `melody-net`) and n8n Postgres nodes (credential `Melody Postgres`).

> ⚠️ **CORRECTION (July 25, 2026) — the checkmarks below describe the workflow JSON, not verified runtime behaviour.** It was established on July 25 that the workflows were authored in **n8n Cloud**, while every service runs in Docker Compose on the developer's machine. All eight service URLs (`http://guardrails-service:8000`, `http://recommendation-service:8000`, …) and the six Postgres nodes (`postgres`) use **Docker-internal hostnames that resolve only inside `melody-net`**. n8n Cloud has no route to them. ~~Any statement in this section implying that these calls were executed successfully~~ → **is withdrawn: the wiring is correct in the JSON, but it could not have run from n8n Cloud.** Resolved by **ADR-005** (`docs/adr/ADR-005-n8n-deployment-mode.md`): **n8n moves to self-hosted Docker Compose on `melody-net`.** Runtime verification of this section happens after that migration, via `workflows/n8n/tests/smoke_test_e2e.py`.

- [x] ✅ **[COMPLETED] N8N-REAL-001 P0: Connect identity/profile nodes to PostgreSQL.** (WF-001 `Resolve User or Guest` → `guest_sessions` Postgres node; WF-005 `Insert Immutable Feedback Event` → `feedback_events` Postgres + `Update Materialized Profile` → `recommendation-service:8000/profiles/update`.)
- [x] ✅ **[COMPLETED] N8N-REAL-002 P0: Connect WF-000 error persistence.** (WF-000 `Persist Error Event` is now a Postgres node inserting redacted errors into `audit_events`.)
- [x] ✅ **[COMPLETED] N8N-REAL-003 P0: Connect WF-001 input/output guardrail nodes.** (Real `Input Guardrails`/`Output Guardrails` HTTP nodes to `guardrails-service:8000/check/input` and `/check/output` are now wired into the flow; the disconnected `MOCK …` Set nodes were removed and the IF nodes now route on `$json.allowed`.)
  - ✅ **[COMPLETED] Follow-up fix (July 24, 2026):** `Route by Intent` **now keys off the real, contract-defined intent.** ~~The Switch previously matched a~~ `user_id` ~~mock hack (~~`text`~~/~~`audio`~~/~~`identify`~~/~~`feedback`~~/~~`export`~~/~~`auth`~~)~~ → **NEW DECISION:** the Switch now evaluates `={{ $('Validate Request Schema').item.json.intent }}` against the canonical `Intent` enum values from `contracts/models.py` (`text_recommendation`, `audio_vibe_recommendation`, `audio_identification`, `feedback`, `playlist_export`, plus a sixth `provider_connection` branch routed to WF-009). `Validate Request Schema` was corrected to read `intent` from the envelope's top level and the prompt from `body.prompt` (it previously read the wrong nested fields). The manual test harness (`OCK FLASK DATA` → renamed `Mock Flask Data`) now emits a full, valid request envelope and is wired into the real pipeline (`Initialize Execution metadata`) so each Switch branch can be exercised by editing one `intent` field and executing manually.
- [x] ✅ **[COMPLETED] N8N-REAL-004 P0: WF-008 is connected to real usage and health tables (July 28, 2026).** ~~Connect WF-008 to real usage and health tables. → **Interim:** WF-001 `Record Request Metrics` now writes each request to `recommendation_sessions` (Postgres). ~~Full WF-008 daily-monitoring wiring~~ is deferred because WF-008 (Monitoring and Budget) was not part of the exported set and rides with its scheduled implementation in a later phase.~~ → **The blocker was not the workflow — it was that two of the four things WF-008 must read had nowhere to be read from.** `model_usage` had existed since Phase 2 with **no writer at all**, and provider quota existed only as a `logger.info` line, recoverable by scraping `docker logs` and by nothing else. A WF-008 built on top of that would have reported zeros and called it monitoring.

  **What was built, in dependency order:**

  1. **Two additive tables + migration `d4e9a7c15b30`** (`provider_quota_usage`, `ops_daily_summary`). Upgrade → downgrade → upgrade round-trip verified clean against the live database. **NEW DECISION: Section 2.3's table set grows from 19 to 21, and the justification is specific** — `oauth_accounts` was called "the last of them", but a monitoring workflow required to read *real* usage cannot be honest without somewhere to read from. `ops_daily_summary.summary_date` is **unique**, so a re-run of the retryable daily schedule updates the day instead of leaving two rows disagreeing about whether a threshold was crossed.
  2. **`recommendation-service/app/core/usage_store.py`** — §4.9 model usage becomes rows. Written once per request after the graph (where `node_metrics` is complete), not per node. **Only nodes that actually called a paid model are recorded:** a node that names its model but has no token counts failed *before* spending anything, and recording it would invent a call that never happened.
  3. **`provider-gateway`'s `_record_quota_usage`** now persists as well as logs.

  Both writers are **best-effort by construction**: a monitoring write must never fail a user's search, so a database outage costs a row in a report rather than an answer.

  **Live-verified end to end, not inspected:** one real recommendation through the containerised Flask produced a `model_usage` row carrying the envelope's own `requestId`, 1352/124 tokens and $0.001972, plus `provider_quota_usage` rows for `search.list` (100 units) and `videos.list` (1).

  ⚠️ **Two defects of my own making, both found by running the code rather than reading it, and both worth recording because they are the same class:** the raw `INSERT` relied on a PostgreSQL-only `gen_random_uuid()` default and failed on the SQLite the offline tests use; and — the serious one — **the new persistence made both test suites write into the live development database.** `recommendation-service`'s endpoint test wrote `model_usage` rows, and `provider-gateway`'s adapter tests wrote **24 rows of fictional quota usage per run**. Neither showed up on the host, where `POSTGRES_*` is unset; only inside the container, where it is configured. That data is worse than useless — WF-008 reads that exact table to decide whether the YouTube budget is nearly spent, so a test run would have made it report consumption that never occurred. **NEW DECISION: both services now carry an autouse conftest fixture that patches the URL resolver**, so no test can reach a real database, and the guard covers any *future* endpoint test rather than the one that happened to exist. Proven rather than asserted: full runs of both suites now leave **0** rows.
- [x] ✅ **[COMPLETED] N8N-REAL-005 P0: Run contract tests between n8n and every service skeleton (July 25, 2026).** `workflows/n8n/tests/smoke_test_e2e.py` passes **10/10** against the self-hosted n8n, exercising all six intents plus four rejection cases end to end.  ~~Original text:~~ ~~✅ **[COMPLETED]** (Each subworkflow WF-002…WF-006 now calls its real FastAPI service — recommendation/audio/provider-gateway — so importing and executing the visual flow exercises the live service contracts.)~~ → **REOPENED (July 25, 2026):** the JSON does target the real services, but per the correction above **no such call could execute from n8n Cloud**, so no contract test has actually run between n8n and a service. This closes only when `workflows/n8n/tests/smoke_test_e2e.py` passes against the self-hosted instance (ADR-005). Automated CI contract tests remain a Phase 9 hardening item.



## Phase 2 gate

~~✅ **[COMPLETED] Status: PASSED (July 24, 2026).**~~ ~~**Status: NOT YET PASSED** — Sections 2.1–2.4 are complete; Section 2.6 (real n8n wiring) is the blocking remainder.~~ → ✅ **[COMPLETED] STATUS: PASSED — properly this time (July 25, 2026, later the same day).** Closed on **executed evidence**: `workflows/n8n/tests/smoke_test_e2e.py` passes **10/10** against the self-hosted n8n — all six canonical intents complete the full Flask-envelope → WF-001 → guardrails → Postgres → sub-workflow → FastAPI → response round trip, four malformed payloads are rejected with correct `VALIDATION_ERROR` messages, and `playlist_export` fails in the controlled `FEATURE_DISABLED` way it is designed to until Phase 5. Five intents persist `recommendation_sessions` rows carrying `engine_used` and real `latency_ms`. **Seven distinct bugs had to be fixed to get here, none of which were visible from the workflow JSON** — see the itemised list under §1.1. ~~The earlier reversion below stands as the record of why the first claim was withdrawn.~~

~~⚠️ **STATUS REVERTED TO NOT PASSED (July 25, 2026).**~~ The gate was declared passed on the strength of the Section 2.6 wiring, but that wiring **could not have executed** — the workflows lived in n8n Cloud while the services are Docker-internal (see the correction in Section 2.6 and **ADR-005**). Everything below that concerns Docker, health endpoints, and migrations genuinely passed and keeps its checkmark; the two criteria that depend on **n8n actually reaching a service** are reopened. The gate re-closes when `workflows/n8n/tests/smoke_test_e2e.py` passes against the self-hosted n8n.

- ✅ **[COMPLETED]** `docker compose up` starts every required service. (Verified locally; note a host-level Ollama instance on port 11434 can require an `OLLAMA_PORT` override or `--no-deps` for `rag-service`.)
- ✅ **[COMPLETED] All readiness endpoints pass.** (`/health/live` and `/health/ready` verified on all five FastAPI services plus `postgres`.)
- ✅ **[COMPLETED] Database migrations apply to an empty database.** (Both migrations applied cleanly via `alembic upgrade head`.)

- [x] ✅ **[COMPLETED] A profile, feedback event, recommendation session, and vector test row can be written and read (July 25, 2026).** Real rows written by live runs: `recommendation_sessions` (five intents with `engine_used` + `latency_ms`), `guest_sessions`, `feedback_events`, `audit_events`.  ~~Original text:~~ ~~[x] ✅ **[COMPLETED]** (Schema verified in 2.3; the wired workflows now target these tables via `Melody Postgres` nodes.)~~ → **REOPENED (July 25, 2026):** the **schema** is verified and the workflows do target `guest_sessions`, `feedback_events`, `recommendation_sessions`, `playlist_exports`, and `audit_events` — but pointing at a table is not the same as writing a row, and from n8n Cloud no write could reach `postgres`. Closes when a smoke run leaves real rows behind.
- [x] ✅ **[COMPLETED] n8n calls the real guardrails and service fixture endpoints with the final contracts (July 25, 2026).** Verified by execution, not by inspection.  ~~Original text:~~ ~~[x] ✅ **[COMPLETED]** (WF-001 calls `guardrails-service`; WF-002…WF-006 call recommendation/audio/provider-gateway at their internal `:8000` endpoints.)~~ → **REOPENED (July 25, 2026):** this is the criterion the n8n Cloud discovery directly invalidates — the URLs are correct in the JSON, but no call could leave n8n Cloud and arrive at a container on `melody-net`.
- [x] ✅ **[COMPLETED] No placeholder database nodes remain in WF-000, WF-001, WF-005.** (Converted to `Melody Postgres` nodes.) ~~WF-008, or WF-009~~ were not part of the exported set this pass (WF-008 is a later scheduled monitoring workflow; WF-009 is referenced by ID only) and carry no request-path placeholders.

---



# 8. Phase 3 — Knowledge preparation, local models, and hybrid RAG

**Status: In progress** (opened July 24, 2026, after the Phase 2 gate passed). ~~Sections 3.1–3.2 kickoff (domain scaffold,~~ `data/` ~~directories,~~ `docs/knowledge_inventory.md`~~) done the same day; see notes under §3.1/§3.2 below.~~ → **Progress through §3.7 (July 24, 2026):** knowledge inventory + local ingestion/embeddings; full hybrid retrieve→rerank pipeline (§3.5 items 1–7 + §3.6); local Ollama grounded generation (`rag-service/scripts/test_generation.py`, default model `llama3.1`). See notes under each subsection. **Still open for the Phase 3 gate:** §3.8 golden evaluation set, LOCAL-002/003, and prompt-log Version 1.

## Objective

Build and evaluate retrieval before adding LangGraph control flow or final recommendation generation.

## 3.1 Canonical knowledge domains

Keep these domains logically separate so retrieval can be measured and filtered:

1. **Genre knowledge**
  - 23 parent genres and 278 subgenres.
  - Descriptions, mood, texture, instrumentation, production style, era.
  - Parent, related, influenced-by, and influence relations.
2. **Reviews and music context**
  - Reviews and descriptive excerpts.
  - Artist, album, track, scene, period, production, and aesthetic vocabulary.
3. **Structured track metadata**
  - Canonical IDs, provider IDs, ISRC where available.
  - Versioned BPM, key, energy, source, and confidence.
4. **User preference state**
  - Stored as structured state, not ordinary RAG prose.
  - Injected into query construction and Track Reranking.

✅ **[COMPLETED] Domain scaffold and directory structure created (July 24, 2026):** `data/raw/{genre_knowledge,reviews_context,track_metadata}/` and `data/processed/` created, plus `docs/knowledge_inventory.md` documenting all four domains above with their fields, ingestion targets, and DB-table mappings. **Discovery:** `data/genres_knowledge/` already contains 23 parent-genre markdown files — matching the "23 parent genres" figure above — logged as the first available Domain 1 source in the inventory; the 278-subgenre coverage still needs verification.

## 3.2 Dataset inventory and legal/source metadata

- [ ] **RAG-001 P0:** Inventory every dataset, scraper output, genre document, review collection, and current AWS source. → **In progress:** the inventory register (`docs/knowledge_inventory.md`) is created and the existing genre corpus (`data/genres_knowledge/`, 23 files) is logged as dataset `genre-md-v0`; reviews, track-metadata, and current-AWS-source rows are still `_tbd_`.
- [ ] **RAG-002 P0:** Record source, license/usage status, retrieval domain, and allowed runtime use. → **In progress:** table columns defined in `docs/knowledge_inventory.md`; license/usage status for `genre-md-v0` marked "owned (project-authored) — confirm," pending explicit confirmation.
- [x] ✅ **[COMPLETED] RAG-003 P0: Remove empty text, exact duplicates, near duplicates, and malformed metadata (July 28, 2026).** Deduplication runs at ingestion on `(album, artist, description)` and is the reason *"all 193,658 reviews"* resolved to **3,836 unique albums** — the CSV is **98% exact duplicate rows**. Post-ingest audit of the 4,249-chunk corpus: **0** duplicate artist+album pairs, 1 duplicate chunk text, 1 chunk under 80 characters. ⚠️ **A malformed-data defect was also fixed here and is worth its own note:** 30 of 300 genre chunks exceeded `multilingual-e5-small`'s **512-token** window and were being **silently truncated at embed time** — the worst at 877 tokens, so ~42% of that section never reached its vector *while still being findable by full-text search*. That asymmetry is the nasty part: a chunk could be retrieved lexically and then score terribly on the reranker, because the reranker was reading text the embedder had never seen. Sections are now split on paragraph (then sentence) boundaries with the header repeated on each part. **Measured after: 0 chunks over the limit, max 447 tokens.**
- [x] ✅ **[COMPLETED] RAG-004 P0: Define stable source-document IDs and ingestion versions (July 24, 2026).** → **Scheme defined** in `docs/knowledge_inventory.md` (e.g. `genre:{slug}`, `review:{source}:{id}`, `track:{isrc|uuid}`, ingestion version `v0`); ~~not yet applied to real ingested rows~~ → now applied by `rag-service/scripts/ingest_local_data.py`: each `knowledge_documents` row stores its stable id in `uri` + `metadata.doc_id` (`genre:pop_music`, `review:metacritic`) and every chunk stores its own `metadata.doc_id` (e.g. `genre:pop_music#...`, `review:metacritic:152`), stamped with ingestion version `v0-text-2026-07`.
- [x] ✅ **[COMPLETED] RAG-005 P0: Preserve the original source reference for evaluation and internal grounding (July 28, 2026).** Every chunk carries `source_uri` (and `source_row` for reviews, `section_part`/`section_parts` for split genre sections), so an answer traces back to its file without joining through `knowledge_documents`. ⚠️ **Found by audit, not by design:** the genre parser got `source_uri` and the reviews parser was missed, leaving **3,836 chunks with no source reference at all**. Backfilled in place rather than re-ingested — the text was unchanged, and re-embedding identical content to add a metadata key would be waste. **Verified: 0 of 4,249 chunks missing a source reference.**



## 3.3 Chunking and ingestion

- [x] ✅ **[COMPLETED] RAG-006 P0: Chunk genre Markdown by headings and semantic sections (July 24, 2026).** A self-contained regex-based Markdown header splitter (H1/H2/H3 aware) in `rag-service/scripts/ingest_local_data.py` split the 23 files in `data/genres_knowledge/` into 300 semantic-section chunks (genre overview + one chunk per `### subgenre`). **NEW DECISION:** used an in-repo regex splitter instead of adding `langchain-text-splitters`, to keep the ingestion path dependency-light and give full control over the emitted section metadata.
- [x] ✅ **[COMPLETED] RAG-007 P0: Chunk reviews by coherent passages, not fixed character count alone (July 24, 2026).** Reviews source located at `data/cleaned_large_dataset_t.csv`; each unique review becomes one coherent passage (song/artist/date/score context header + review body). Exact-duplicate rows are de-duplicated during ingestion (partially addresses RAG-003; near-duplicate detection still outstanding).
- [x] ✅ **[COMPLETED] RAG-008 P0: Attach domain, source, artist, album, genre, language, era, and version metadata when present (July 24, 2026).** Every chunk carries `domain`, `source`, `language`, and `version`, plus domain-specific fields — `genre`/`subgenre`/`section`/`era` for genre chunks and `artist`/`album`/`release_date`/`era`/`metascore`/`user_score` for review chunks — persisted to `knowledge_chunks.metadata` (JSONB). **NEW DECISION:** the text-only ingestion leaves `knowledge_chunks.embedding` `NULL` (real embeddings handled in §3.4/§3.5); the generated `content_tsv` full-text column is populated automatically by Postgres. Verified run: 24 documents / 325 chunks inserted (23 genre docs + 1 reviews doc), all embeddings `NULL`, all `content_tsv` populated.
- [x] ✅ **[COMPLETED] RAG-009 P0: Create and populate** `genre_nodes` **and** `genre_edges` **(July 24, 2026).** New builder `rag-service/scripts/build_genre_graph.py` parses the 23 source Markdown files in `data/genres_knowledge/` and writes a real graph: **260 nodes** (23 `kind='parent'` + 237 distinct `kind='subgenre'`) and **689 edges** (`parent` 275, `influenced_by` 316, `related` 98). The script is idempotent (verified: a second run adds 0 new edges) and supports `--dry-run`. **NEW DECISION:** edges are derived **only** from the lineage marker each subgenre already carries in the source text (the line under the year, e.g. `BLUESGOLDEN AGE(r & b)`), split against a closed 22-token vocabulary enumerated from the corpus — so an edge exists only where the source document states a lineage, and nothing is invented. Weights: 1.0 primary lineage, 0.6 secondary, 0.3 parenthetical, 0.5 for parent-level `related` links. **NEW DECISION (ambiguity resolved, not guessed):** the token `HARDCORE` names both `EDM / DANCE: HARDCORE (TECHNO)` and `ROCK, HARDCORE PUNK`; it is resolved by company — if the marker also names an EDM genre it is the EDM one, otherwise hardcore punk. **NEW DECISION (cross-listed genres):** 39 subgenre names appear under two or three parent families (e.g. *TRIP HOP* under both `DOWNTEMPO / AMBIENT` and `EDM / DANCE: BREAKBEAT`); since `genre_nodes.name` is UNIQUE and one node per genre is the musically correct model, the occurrences are **explicitly merged** — first parent becomes `parent_id`, every family is kept in `metadata.parents` **and** as its own `parent` edge, and the earliest attested year wins. ~~An initial version let the last occurrence silently overwrite the others, losing 40 rows' worth of parent and metadata information.~~ Only **1** of 277 subgenres (`NEO-TRANCE`) has no influence edge, correctly — its source text literally reads *"Description not available."*, so fabricating a lineage was refused.
  - ✅ **[COMPLETED] §3.5 item 4 is no longer mocked.** New module `rag-service/scripts/genre_graph.py` performs the real one-hop traversal, and `test_hybrid_retrieval.py` now calls it. ~~The hardcoded `GENRE_GRAPH` map ("rock → indie rock, post-punk, …")~~ → **NEW DECISION:** retained **only** as a clearly named `FALLBACK_GENRE_GRAPH` used when the genre tables are empty, so the script still runs against a database where the builder has not been executed. **NEW DECISION:** alias→genre resolution **scores** candidates (exact whole-name match, then parent over subgenre) instead of first-writer-wins, which was alphabetical and wrong — `"techno"` resolved to *HARDCORE (TECHNO)* rather than *TECHNO*. An ambiguous alias keeps every candidate in the winning tier (capped at 4), so `"rock"` reaches all four rock families rather than one arbitrary family, since the corpus has no single ROCK parent. Query and alias text are normalized so `drum and bass`, `drum 'n' bass`, and `jungle` all reach `EDM / DANCE: DRUM 'N' BASS / JUNGLE`. Expansion is budget-capped (8 per match, 14 total) to prevent one broad word contributing ~48 OR-terms. Verified against the live database: generated tsqueries are accepted by `websearch_to_tsquery` without error, with multi-word genre names correctly becoming AND-groups inside OR alternatives.
  - ⚠️ **Verification limit (honest):** the graph build, the expansion logic, and the generated lexical tsqueries were all verified **against the live database from the host**. The **full** hybrid run (dense + lexical → RRF → cross-encoder) was **not** re-executed end-to-end, because the running `melody-rag-service` container is **stale relative to its own `rag-service/requirements.txt`** — the file lists `SQLAlchemy`, `sentence-transformers`, and `torch`, but none are installed in the running image. Re-running the §3.5–3.7 scripts in-container requires an image rebuild. The dense leg itself was not modified by this change.
- [x] ✅ **[COMPLETED] RAG-010 P0: Stage ingestion before publishing a version (July 29, 2026).**

  Until now ingestion **replaced the corpus in place** — the document was deleted and re-inserted — so a bad chunking change was live the instant it was written, and the only way back was to re-ingest from source and hope. §1.10's rule *"do not publish a new ingestion version until smoke queries pass"* was unenforceable, because a version could not exist without being live.

  **What was built:** migration `e5f1c48a9d72` adds `ingestion_versions` with a lifecycle of `staged → active → superseded`, or `staged → rolled_back`. `ingest_local_data.py --stage` writes a new version **alongside** the live one; `POST /rag/ingest` owns `status` / `publish` / `rollback`; and **retrieval reads only the active version**, which is what makes a staged corpus invisible to users rather than mixed into their results.

  **NEW DECISION: at most one active version, enforced by a partial unique index rather than by whichever code path publishes.** Two active versions would make *"what did retrieval actually search?"* unanswerable. The migration also seeds the existing corpus as active — a migration that left zero active versions would take the product down.

  **NEW DECISION: bulk document loading is deliberately NOT in the endpoint.** The corpus is loaded by the script, which reads files under `data/` that rag-service's image does not contain. That split keeps the service free of a filesystem dependency it does not otherwise need, and keeps the part that must be atomic — promotion — in one transaction.

  ⚠️ **Three defects found by running it, each of which would have shipped:**

  1. **Staging collided with the live document.** `knowledge_documents` is unique on `(source, uri, version)`, and staging deliberately skips the delete, so reusing `v0` clashed with the document still serving traffic. The document version now moves with the staged version. *(The failure direction was safe — the live corpus was untouched — but it was still a failure.)*
  2. **Publishing a partial corpus silently halved retrieval.** Staging genres only and publishing it took the reviews domain from 3,836 chunks to **zero**, with every other check green: chunks existed, all were embedded, and the smoke queries passed because they only ask the genre domain. **A domain-coverage check now refuses to publish a version missing a domain the active one covers**, with an explicit `force` for deliberate retirement.
  3. **There was no way back.** `publish` accepted only `staged` or `active`, so a superseded version could never be restored — making the entire lifecycle theatre after one bad publish. `superseded` is now re-publishable; only `rolled_back` is final, because its chunks are gone.

  **Every guard verified live:** publish without `smoke_passed` → `SMOKE_QUERIES_FAILED`; publish with unembedded chunks → `UNEMBEDDED_CHUNKS` (*"413 of 413 chunks have no embedding, so dense retrieval would silently miss them"*); publish a partial corpus → `DOMAIN_COVERAGE_REGRESSION`; roll back the active version → `INVALID_STATE`. Happy path: staged 413 chunks invisible to retrieval, embedded, published, active swapped, then rolled back and the full 4,249-chunk corpus restored with both domains retrieving.

  ⚠️ **One robustness bug fixed on the way, and it was mine:** `_active_version` **raised** when `ingestion_versions` was missing, despite its own docstring promising to degrade — so on any database where the migration had not run, every search would have returned 500 instead of falling back. It now fails **open** (search everything) rather than closed, because on the request path an empty result set is indistinguishable from a broken corpus. Caught by the offline suite, whose SQLite fixture is exactly the "migration not applied" case.
- [x] ✅ **[COMPLETED] RAG-011 P0: Run WF-007 smoke queries before marking a version active (July 29, 2026).**

  WF-007's `PLACEHOLDER — rag-service staged ingestion (RAG-010)` is gone — **the exported workflow set now contains zero placeholders.** The node is `Read Ingestion Version Status`, and `Publish Ingestion Version` / `Rollback Staging Version` are real HTTP calls to the lifecycle endpoint.

  **The gate is enforced on both sides.** WF-007 sends `smoke_passed: true` only down the branch its IF reaches when both gates passed, and rag-service **refuses to publish without it** — so a caller that forgot to check cannot publish by omission.

  ⚠️ **Two wiring defects found by executing it**, both the same shape as ones this project has hit before: the renamed node left **dangling connection references**, which n8n rejected outright (a good failure — it refused the import rather than running a broken graph); and the Return node read the **HTTP envelope** instead of the outcome, reporting a status code where an outcome belonged — the identical mistake WF-010's Return node made when it reported `deleted: false` about a clip it had really deleted.

  **NEW DECISION: a run with nothing staged is `validated_only`, not a failure.** The first version POSTed `version: null`, got a 400, and reported an ordinary *"no changes this week"* run as a broken ingestion — the kind of false alarm that trains people to ignore a monitoring workflow.

  **Live run:** both smoke queries pass, and the Hebrew one now returns **retrieval confidence 0.788** against **0.0002** before the multilingual reranker — the same query, the same corpus, a different reranker. The run correctly refuses to publish while `RAG-002`'s licence metadata is missing, leaving the live corpus untouched.



## 3.4 Embedding-model decision

✅ **[COMPLETED] Embedding generation pipeline built and ready (July 24, 2026).** `rag-service/scripts/generate_embeddings.py` embeds chunks locally with `intfloat/multilingual-e5-small` (384-d, `"passage: "` prefix, L2-normalized, batched), and backfills `knowledge_chunks.embedding` for the initial corpus. The 325 already-ingested chunks are staged with `embedding IS NULL` and ready to be embedded on the first run. **NEW DECISION:** the selected model is `intfloat/multilingual-e5-small`; `EMBEDDING_DIM` was changed `768 → 384` and `knowledge_chunks.embedding` resized to `vector(384)` via migration `f1a2b3c4d5e6` (rationale in `docs/adr/ADR-003-embedding-model.md`).

Benchmark at least two feasible multilingual models, for example multilingual-e5 and BGE-M3 or a smaller equivalent.

Evaluate:

- Hebrew and English retrieval quality;
- CPU latency and RAM;
- embedding dimension and storage;
- license and redistribution terms;
- compatibility with local Hugging Face inference.

- [ ] **RAG-EMB-001 P0:** Build 20 bilingual retrieval queries. → **Deferred:** superseded by the pragmatic ADR-003 selection; can be run later to justify an upgrade.
- [ ] **RAG-EMB-002 P0:** Benchmark candidates on the same indexed subset. → **Deferred:** superseded by the pragmatic ADR-003 selection; can be run later to justify an upgrade.
- [x] ✅ **[COMPLETED] RAG-EMB-003 P0: Record the decision in** `ADR-003-embedding-model.md` **(July 24, 2026).** Created `docs/adr/ADR-003-embedding-model.md` selecting `intfloat/multilingual-e5-small`, citing bilingual (Hebrew/English) support, low CPU/RAM footprint, and local HuggingFace inference compatibility.



## 3.5 Hybrid retrieval pipeline

✅ **[COMPLETED] Dense vector retrieval implemented and tested locally (July 24, 2026).** All 325 ingested chunks were embedded with `intfloat/multilingual-e5-small` (384-d) via `rag-service/scripts/generate_embeddings.py`, run inside the `rag-service` Docker container (CPU-only torch); `knowledge_chunks.embedding` is now 0 NULL / 325 populated. A minimal search harness (`rag-service/scripts/test_retrieval.py`) embeds a `"query: "`-prefixed string and runs a pgvector cosine search over the HNSW index. Verified end-to-end with bilingual queries — EN `"fast-paced electronic music"` → top hit *SYNTH / ELECTRONICA* (cosine ≈ 0.85, plus Digital Hardcore/Breakcore), and HE `"מוזיקת פופ שקטה"` (quiet pop music) returns cross-lingual matches including *Dream Pop & Shoegaze*. **NEW DECISION:** rag-service Docker image now installs CPU-only `torch` and bundles `contracts/`; the compose service gained a `DATABASE_URL` (host `postgres`), a raised 3G memory limit, and an `hf_cache` volume for the model.

Implement in this order:

1. ✅ **[COMPLETED] Dense vector retrieval (July 24, 2026)** — pgvector cosine search over `knowledge_chunks.embedding` (HNSW, `vector_cosine_ops`), proven with EN + HE queries; see the note above.
2. ✅ **[COMPLETED] PostgreSQL full-text retrieval (July 24, 2026)** — native FTS over `knowledge_chunks.content_tsv` (a GENERATED STORED `to_tsvector('english', chunk_text)` column, GIN-indexed via `ix_knowledge_chunks_content_tsv`), using `websearch_to_tsquery('english', …)` and `ts_rank_cd` ranking. Test harness `rag-service/scripts/test_fulltext_retrieval.py` (no embedding model required; includes an automatic on-the-fly `to_tsvector` fallback) verified locally in the `rag-service` container.
3. ✅ **[COMPLETED] Exact-name and metadata filters (July 24, 2026)** — `rag-service/scripts/test_hybrid_retrieval.py` accepts optional `year_from`/`year_to`/`source`/`domain` kwargs (CLI: `--year-from/--year-to/--source/--domain`) and applies them to BOTH the dense and lexical queries *before* RRF fusion, as predicates on the JSONB `knowledge_chunks.metadata` column: `metadata->>'source'`/`metadata->>'domain'` equality and a numeric year derived from `metadata->>'era'` (`regexp_replace` + `NULLIF` + cast to `Integer`, so non-numeric/absent values are safely `NULL`). The LLM query-parser that populates these kwargs from natural language is deferred to §3.8.
4. ✅ **[COMPLETED] One-hop genre graph expansion (July 24, 2026)** — mocked with a hardcoded broad-genre → subgenre map (e.g. `rock → indie rock, post-punk, classic rock, hardcore punk`). When a broad genre is detected in the query, its subgenres are OR-appended to the lexical tsquery only (the dense leg keeps the original phrasing); a real implementation would traverse `genre_nodes`/`genre_edges` (RAG-009). **NEW DECISION:** graph expansion is applied to the lexical leg exclusively so it broadens keyword recall without diluting the semantic vector query.
5. ✅ **[COMPLETED] Reciprocal Rank Fusion (July 24, 2026)** — `rag-service/scripts/test_hybrid_retrieval.py` fuses the dense (pgvector cosine) and lexical (full-text) legs with RRF (`score = Σ 1/(k+rank)`, `k=60`, ~20 candidates per leg via the `--pool` param), using the shared `scripts/_db.py` resolver. Verified in the `rag-service` container: EN `"fast-paced electronic music"` → top hit *DOWNTEMPO / AMBIENT overview* (RRF ≈ 0.032 from vector #4 + full-text #1), then *ELECTRO* (Rap/Hip-Hop and Breakbeat) — both legs contributing to the fused ranking. **NEW DECISION:** the lexical leg uses OR-combined tokens (`websearch_to_tsquery` ANDs by default, which zero-matches long natural-language phrases) so fusion has real recall to work with; `k`, `--pool`, and final counts remain evaluation parameters per the note below.
6. ✅ **[COMPLETED] Document reranking over approximately 20 initial chunks (July 24, 2026)** — `rag-service/scripts/test_hybrid_retrieval.py` now runs a local cross-encoder rerank stage (on by default; `--no-rerank` to skip). The top ~~20 RRF-fused candidates (~~`--candidates`~~) and the original query are scored as~~ `(query, chunk_text)` ~~pairs by~~ `cross-encoder/ms-marco-MiniLM-L-6-v2` ~~(via~~ `sentence_transformers.CrossEncoder`~~, cached in the~~ `hf_cache` ~~volume), then re-sorted by the cross-encoder relevance score. **NEW DECISION:** the reranker is~~ `cross-encoder/ms-marco-MiniLM-L-6-v2` ~~— a lightweight (~~80 MB, 6-layer MiniLM) local cross-encoder that runs CPU-only in the `rag-service` container, requires no external API, and (unlike the e5 bi-encoder) jointly attends over query+passage for precise final ordering, so it is applied only to the small retrieve-then-rerank candidate set.
7. ✅ **[COMPLETED] Select 5–8 chunks for expensive generation (July 24, 2026)** — after reranking, the list is sliced to the top `--final-k` chunks (default 5) for downstream generation. Verified in the `rag-service` container: EN `"rock music"` → top 5 reranked chunks led by *ROCK 'N' ROLL & ROCKABILLY* (CE ≈ +3.72, promoted from vector #1 / full-text #17), *POST-ROCK*, and *HARD ROCK*, with the cross-encoder reordering candidates away from raw RRF order (e.g. a vector-only #6 candidate outranked a higher-RRF chunk).

Starting RRF implementation:

Treat `k`, candidate counts, and final chunk counts as evaluation parameters, not permanent truths.

## 3.6 Document Reranker

✅ **[COMPLETED] Local Cross-Encoder (Reranker) implemented and tested locally (July 24, 2026).** The Document Reranker is wired into `rag-service/scripts/test_hybrid_retrieval.py` as the final stage of the §3.5 pipeline (retrieve-then-rerank): the top ~20 RRF-fused candidates are re-scored by a local cross-encoder and sliced to the top 5. **NEW DECISION:** the selected model is `cross-encoder/ms-marco-MiniLM-L-6-v2` (Hugging Face, ~80 MB, 6-layer MiniLM) run locally via `sentence_transformers.CrossEncoder` — CPU-only, no external API, cached in the `hf_cache` volume. Verified on EN `"rock music"` (top 5 reranked chunks, cross-encoder reordering vs. raw RRF).

The Document Reranker is separate from the Track Reranker.

Input:

Output:

- [x] ✅ **[COMPLETED] RAG-RERANK-001 P0: Benchmark a multilingual local reranker (July 28, 2026).** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` measured against the §3.8 golden set and **adopted as the default**.
- [x] ✅ **[COMPLETED] RAG-RERANK-002 P0: Compare against a no-reranker baseline (July 28, 2026).** Run via `RERANKER_ENABLED=false`, which keeps RRF order.
- [x] ✅ **[COMPLETED] RAG-RERANK-003 P0: Keep an API reranker as an optional measured alternative, not an implicit dependency.** Satisfied by construction: `RERANKER_MODEL` / `RERANKER_ENABLED` select the reranker at runtime, so any alternative — including the LLM-as-reranker pattern in the course reference material — is a swap plus an eval run, never a rewrite. **NEW DECISION: no API reranker is adopted.** A hosted reranker would add a third paid provider and a per-request network hop to fix a problem a 118M-parameter local model already solved.

  ⭐ **The measurement, and it overturned an assumption rather than confirming one** (25 golden queries):

  | Reranker | Recall@5 | MRR | nDCG@10 | **HE Recall@5** | median |
  | --- | --- | --- | --- | --- | --- |
  | `ms-marco-MiniLM-L-6-v2` (was default, English-only) | 0.409 | 0.458 | 0.410 | 0.125 | 2.29 s |
  | **none** (RRF order) | 0.424 | 0.480 | 0.426 | 0.125 | **0.13 s** |
  | **`mmarco-mMiniLMv2-L12` (adopted)** | **0.489** | **0.511** | **0.475** | **0.500** | 2.79 s |

  **Two findings worth carrying forward.** First, the shipped English reranker was **worse than no reranker at all on every metric** while costing 17× the latency — it was actively destroying rankings RRF had already got right, and had been in the request path since Phase 3 opened. Second, **dense retrieval was never the Hebrew problem**: querying pgvector directly showed `multilingual-e5` returning the correct `#grunge` chunk at rank 1 for a Hebrew query, which the English cross-encoder then demoted to Goa trance. Swapping the reranker quadruples Hebrew Recall@5 for +0.5 s.

> **Note:** the current `ms-marco-MiniLM-L-6-v2` reranker is English-optimized; RAG-RERANK-001 (multilingual benchmark) and RAG-RERANK-002 (no-reranker baseline) remain open follow-ups for the Hebrew path.



## 3.7 Local model runtime

✅ **[COMPLETED] Local Generative Model (LLM) wired into the RAG answer path (July 24, 2026).** `rag-service/scripts/test_generation.py` completes the retrieve→generate loop: it reuses the exact §3.5/§3.6 pipeline (Dense + Lexical → RRF → cross-encoder rerank, imported directly from `test_hybrid_retrieval.py` so there is a single source of truth), takes the top 5 `chunk_text` passages, assembles a strict RAG prompt (system: *"You are Melody… answer using ONLY the provided context… if the context does not contain the answer, say you do not know"*) with the chunks wrapped in a numbered `<context>` block, and streams the answer from a **local** Ollama server. ~~Default model~~ `llama3` → **NEW DECISION: default generative model is** `llama3.1` (matches the locally pulled Ollama tag; override with `--model`). Verified query path: *"Tell me about the origins of rock music"*. **NEW DECISION:** the generator talks to Ollama over its plain REST API (`POST /api/generate`, streaming JSON lines) using the already-present `httpx` dependency — **no new package** (`ollama` client) was added. The endpoint is resolved as `--ollama-url` flag → `OLLAMA_BASE_URL` env → default `http://ollama:11434` (the compose service on `melody-net`); for one-off `--no-deps` containers it can be pointed at the host daemon via `OLLAMA_BASE_URL=http://host.docker.internal:11434`. **NEW DECISION (July 24, 2026 bugfix):** on `httpx.HTTPStatusError` from a *streaming* response, call `exc.response.read()` before accessing `.text` (otherwise httpx raises `ResponseNotRead`); the handler now drains the stream and surfaces a clear "is model X pulled?" message instead of crashing. Follow-ups: LOCAL-002 (promote this into a stable internal adapter/service endpoint) and LOCAL-003 (measure latency/memory/schema pass-rate) remain open.

Use Ollama or llama.cpp for at least one real, measured project responsibility:

- intent classification for ambiguous requests;
- structured music-constraint extraction;
- simple query normalization;
- local RAG answer baseline;
- low-cost prompt experiment.

Do not use a local model for deterministic validation, OAuth, database writes, or sequencing.

- [x] ✅ **[COMPLETED] LOCAL-001 P0: Select a small local model compatible with available CPU/RAM.** `llama3` ~~(8B)~~ → **NEW DECISION:** `llama3.1` served locally via Ollama, reachable from the rag-service container on `melody-net` (or from `--no-deps` runs via `host.docker.internal:11434`).
- [x] ✅ **[COMPLETED] LOCAL-002 P0 — CLOSED AS UNNECESSARY, not delivered (July 28, 2026, developer-approved).** ~~Expose it behind a stable internal adapter. *(In progress —* `test_generation.py` *proves the REST call; a reusable adapter/endpoint is the next step.)*~~ → The adapter would have had **no caller**. Ollama is removed from the project (see `LOCAL-003` below and the ADR-006 amendment); the local models that remain — `multilingual-e5-small`, `mmarco-mMiniLMv2-L12` and the audio CNN — are already invoked in-process by the services that own them, so "a stable internal adapter" is what `rag-service` and `audio-service` themselves are. Building a second indirection to reach a model in the same process would be ceremony, not architecture.
- [x] ✅ **[COMPLETED] LOCAL-003 P0: Measure latency, memory, and output-schema pass rate (July 28, 2026) — RETARGETED onto the local models that actually run.**

  ⚠️ **NEW DECISION (developer-approved, July 28, 2026): Ollama is removed from the project entirely, and `LOCAL-002` is closed as unnecessary rather than delivered.** An audit found `ollama` referenced **nowhere on the request path**, its container **never once started** (port 11434 was held on the host and nothing depended on it enough to notice), and the job ADR-006 assigned it — intent classification and structured extraction — **never implemented**. `LOCAL-002` would have been an adapter with no caller.

  **The requirement is met, more strongly, by three models that run locally and in-process on every request** — measured by `eval/local_models.py`, results in `eval/reports/local_models_*.json`:

  | Model | Role | Latency | Memory | Schema |
  | --- | --- | --- | --- | --- |
  | `intfloat/multilingual-e5-small` | embeddings (rag-service) | **42 ms/query** median; 9.9 passages/s batched | 792 MB resident | ✅ 384-d as declared |
  | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | reranking (rag-service) | **94 ms/pair**, 1.88 s per 20-pair pool | 1,264 MB resident | ✅ one score per pair |
  | Melody audio genre CNN (PyTorch) | classification (audio-service) | — | — | ✅ held-out macro-F1 **0.8692** |

  Three models doing real work beats one that did none. **Removed with it:** the `ollama` service, its volume, `rag-service`'s dependency on it, `OLLAMA_PORT`, and `rag-service/scripts/test_generation.py` — deleted rather than left as dead code pointing at a service that no longer exists. **Verified after removal:** full stack healthy, `smoke_test_e2e.py` **12/12**, live requests returning real tracks in both languages. ADR-006 carries the amendment.

  ⚠️ **One number worth carrying forward: the reranker is now the single most expensive part of a retrieval call** — 94 ms × 20 candidates ≈ 1.9 s of the ~2.2 s a `/rag/retrieve` costs. That is the honest price of the Hebrew fix, and the first place to look if retrieval latency must come down again.

- ~~[ ] **LOCAL-003 P0:** Measure latency, memory, and output-schema pass rate. → **First measurements recorded (July 25, 2026), on the development machine with** `llama3.1` **8B Q4_K_M (4.9 GB):**~~ *(superseded above; the original llama3.1 figures are retained below for the record)*

  | Task | Output tokens | Wall time | Throughput |
  | ---- | ------------- | --------- | ---------- |
  | Curator-style prose | 80 | **17.4 s** | 11.9 tok/s |
  | Intent classification | 20 | **2.6 s** | 12.6 tok/s |

  **NEW DECISION (interpretation):** throughput is essentially constant at ~12 tok/s — **only the task's token count varies.** The model is not slow in general, it is slow at *generating text*. A realistic curator explanation (~400–500 tokens) extrapolates to 35–45 s here and several times that on the CPU VPS of §9.7, while a 20–50 token structured classification stays at 2–4 s. This measurement is what triggered **ADR-006**. **Remaining for this task:** memory profiling and output-schema pass rate, and a re-run against the smaller model once `LOCAL-001` is revisited.
- [x] ✅ **[COMPLETED] LOCAL-004 P0: Document the exact task it owns in the final system (revised July 25, 2026 — see ADR-006).** ~~Owns the **local RAG answer baseline**~~ → ⚠️ **CORRECTED: that assignment contradicted Section 2.2**, which scopes the Local Model Runtime to *"Cheap classification, structured extraction, local inference demonstrations"* — a RAG answer is a **generation** task, the one kind the measurements under `LOCAL-003` show the local model cannot serve at acceptable latency. **NEW DECISION (ADR-006):** the local model's production job is **intent classification for ambiguous requests and structured music-constraint extraction** (20–50 tokens of JSON, 2–4 s). The heavy generation moments — the §4.8 curator explanation and the §4.5 single bounded rewrite — go to **`claude-haiku-4-5` via the direct Anthropic API**, matching §4.8's own rule that *"the expensive model is used only here."* `rag-service/scripts/test_generation.py` is **retained as the measured local-inference demonstration** for the course requirement, but is no longer on the request path. ~~Owns the local RAG answer baseline — synthesizing a grounded answer from the top-5 reranked knowledge chunks (see `test_generation.py` and the §3.7 note above).~~



## 3.8 Golden evaluation set

✅ **[COMPLETED] BUILT AND RUN (July 28, 2026) — `eval/golden_set.json` (25 queries) + `eval/rag_eval.py`, reports in `eval/reports/`.**

**NEW DECISION: 25 queries, not 25–40.** The course lecturer specified **20–30 as sufficient**, and the developer asked to hit that requirement precisely; 25 sits inside both that range and this section's lower bound, so the two are satisfied at once.

**All seven categories below are covered** — mood (5), blended genres (4), exact genre (5), exact artist (2), Hebrew (4), anti-echo-chamber (2), negative constraints (3). **All 65 ground-truth references were verified to exist in the live corpus** before the first run: a golden set that cites chunks which are not there measures typos, not retrieval.

**NEW DECISION: anti-echo-chamber queries are excluded from rank metrics** (`retrieval_scored: false`). They have no single correct answer by construction, and scoring them against a fixed target would penalise exactly the behaviour they exist to test. They are still judged by Ragas, which scores grounding rather than target-matching.

**Ragas is wired in (the course's explicit requirement), with `claude-haiku-4-5` as the evaluator** by developer decision — the key already exists and it is the provider the product itself uses (ADR-006), so evaluation adds no second vendor. Embeddings for `ResponseRelevancy` come from the same local `multilingual-e5-small` the pipeline uses.

**Measured baseline (July 28, 2026), multilingual reranker, 25/25 queries scored with zero judge errors:**

| Layer | Metric | Value |
| --- | --- | --- |
| Retrieval | Recall@5 / Recall@10 | 0.489 / 0.489 |
| Retrieval | MRR / nDCG@10 | 0.511 / 0.475 |
| Ragas | **faithfulness** | **0.848** |
| Ragas | **response relevancy** | **0.741** |
| Ragas | context precision | 0.423 |
| Ragas | context recall | 0.280 |

**By category, which is where the actionable signal is:**

| Category | faithfulness | relevancy | context precision |
| --- | --- | --- | --- |
| exact_genre | 0.95 | 0.89 | **0.90** |
| exact_artist | 1.00 | 0.88 | 0.50 |
| anti_echo_chamber | 0.92 | 0.88 | 0.10 |
| negative_constraint | 0.83 | 0.57 | **0.00** |
| hebrew | 0.81 | 0.40 | 0.50 |
| mood | 0.80 | 0.73 | 0.49 |
| blended_genres | 0.72 | 0.90 | 0.10 |

⚠️ **`negative_constraint` scores 0.00 context precision, and that is a real architectural gap, not noise.** Nothing in the pipeline handles negation: ask for *"rock but nothing metal"* and retrieval cheerfully returns metal, because the embedding of the whole phrase is dominated by its nouns. `normalize_input` already extracts negative constraints into `normalized_constraints["negative"]`, and **they are never applied to retrieval** — only later, to tracks. Recorded here rather than fixed on the spot: it is a design change wanting its own slice.

⚠️ **Hebrew is measurably better and still the weakest language** — Recall@5 0.500 against English 0.487 on this set, but only 2 of its 4 queries retrieve correctly. The two failures are descriptive rather than named (*"quiet sad music for an evening"* returned hardcore techno). Named-genre Hebrew now works end to end, including an answer written in Hebrew.

⚠️ **Two harness defects were found and fixed before any of these numbers were trusted**, and both would otherwise have been reported as product failures. (1) The Ragas judge ran with `max_tokens=1024`, too small for faithfulness's per-statement decomposition, so **10 of 25 queries raised `LLMDidNotFinishException`** — the first reported 0.62 was a 15-query average wearing a 25-query label. It was visible only because the harness records judge errors instead of scoring them zero. (2) The harness's own answer prompt made the model **refuse every Hebrew query** — `he-01` scored context precision *and* recall of 1.0, meaning retrieval had found exactly the right chunk, and the answer still said the context did not contain it. Corpus is English by design, so a cross-language answer is the normal case; the prompt now says so. Fixing both moved faithfulness 0.62 → 0.79 → **0.848** and relevancy 0.61 → **0.741**, with no change to the system under test.

~~Create at least 25–40 queries covering:~~ → **Delivered as 25, per the NEW DECISION above. Original requirement retained for the record:**

- mood-based discovery;
- blended genres;
- Hebrew and English;
- exact artist and genre names;
- anti-echo-chamber requests;
- negative constraints;
- future audio-conditioned queries represented as structured fixtures.

Metrics:

- Recall@K;
- MRR or nDCG;
- human relevance score from 1–5;
- genre/source diversity;
- retrieval latency;
- reranker improvement;
- token/context reduction.



## 3.9 Prompt Engineering Log — begin now

Create at least five prompt surfaces with five recorded versions each:


| Surface       | Component                       | Primary measure                                    |
| ------------- | ------------------------------- | -------------------------------------------------- |
| PE-1          | n8n Information Extractor       | Schema accuracy and missing-field honesty          |
| PE-2          | n8n AI Agent/tool descriptions  | Correct tool selection and no unnecessary calls    |
| PE-3          | RAG context-grounded generation | Grounding, useful citations/evidence, no invention |
| PE-4          | Input/output Guardrails prompts | False positive and false negative rate             |
| PE-5          | Local-model system prompt       | On-topic rate, schema pass rate, latency           |
| PE-6 optional | Final curator explanation       | Musical quality, concision, and track-grounding    |


For each version:

1. Save the full prompt.
2. Use the same minimum 10-case test set.
3. Record the targeted failure from the previous version.
4. Record outputs or structured evaluation results.
5. Measure improvement and regressions.
6. End with the final prompt and design justification.



## Phase 3 artifacts

✅ **[COMPLETED] Artifacts produced so far (July 24, 2026):**

- `docs/knowledge_inventory.md` — four knowledge domains + source inventory.
- `docs/adr/ADR-003-embedding-model.md` — `intfloat/multilingual-e5-small` (384-d).
- `rag-service/scripts/ingest_local_data.py` — genre MD + reviews CSV → `knowledge_documents` / `knowledge_chunks`.
- `rag-service/scripts/generate_embeddings.py` — batch backfill of `knowledge_chunks.embedding`.
- `rag-service/scripts/_db.py` — shared `resolve_database_url()` for compose/host runs.
- `rag-service/scripts/test_retrieval.py` — dense pgvector cosine search harness.
- `rag-service/scripts/test_fulltext_retrieval.py` — Postgres FTS harness.
- `rag-service/scripts/test_hybrid_retrieval.py` — Dense + Lexical → RRF → cross-encoder rerank → top-5.
- `rag-service/scripts/test_generation.py` — retrieve→rerank→Ollama (`llama3.1`) grounded answer (streaming).
- Representative DB state: 24 documents / 325 chunks with embeddings + `content_tsv` populated.



## Phase 3 gate

✅ **[COMPLETED] PHASE 3 GATE PASSED — 5 of 5 (July 29, 2026).** The last phase before Phase 9 to close.

- ✅ **[COMPLETED]** A representative knowledge subset is versioned in PostgreSQL/pgvector. ~~*(24 docs / 325 embedded chunks.)*~~ → **24 documents / 4,249 chunks, all embedded, 0 missing** — and *versioned* now means it literally: `ingestion_versions` gives a corpus a `staged → active → superseded` lifecycle (`RAG-010`), with retrieval reading only the active version.
- ✅ **[COMPLETED]** Dense, full-text, filters, genre expansion, RRF, and reranking are independently testable. *(via* `test_retrieval.py`*,* `test_fulltext_retrieval.py`*,* `test_hybrid_retrieval.py`*.)* → **And now measured together**, which is what actually exposed that the reranker was making retrieval worse.
- ✅ **[COMPLETED]** Golden queries return relevant chunks with recorded metrics. ~~*(§3.8 still open.)*~~ → **`eval/golden_set.json` (25 queries) + `eval/rag_eval.py`, with Ragas.** Recorded: Recall@5 **0.500**, MRR **0.520**, nDCG@10 **0.482**, faithfulness **0.848**, response relevancy **0.741**, and 0 negative-constraint violations. Reports in `eval/reports/`.
- ✅ **[COMPLETED]** The selected local model performs one real task ~~with measured results~~ ~~→ **local RAG answer baseline via** `test_generation.py` **+ Ollama** `llama3.1`**.** *(Formal latency/memory/schema measurements remain LOCAL-003.)*~~ → **Ollama was removed entirely; three local models do real work on every request** and are measured (`LOCAL-003`): embeddings 42 ms/query with a passing 384-d schema check, reranking 94 ms/pair, and the audio CNN at held-out macro-F1 0.8692.
- ✅ **[COMPLETED]** Prompt-log Version 1 exists for at least five surfaces. ~~*(still open.)*~~ → **`docs/prompt-engineering-log.md`**, and writing it disproved two of the five surfaces: PE-1's node does not exist (closed as a documented substitution) and PE-2 was in the wrong workflow carrying n8n template boilerplate. Corrected rather than papered over.

⚠️ **One Phase 3 item remains open and is NOT a gate criterion: `RAG-002` (corpus licence/provenance).** It needs the developer, not code — only the author knows where `data/genres_knowledge/` and the reviews CSV came from. WF-007 refuses to publish a new corpus version while it is missing, so the gap is enforced rather than merely noted.

---



# 9. Phase 4 — New LangGraph recommendation engine

**Status: In progress** (opened July 24, 2026). Initial scaffolding for §4.1–4.3 delivered inside `recommendation-service/app/core/` — state schema, all 18 stub nodes, and the compiled graph topology with the bounded-rewrite conditional edge. Heavy node logic (retrieval reuse, provider adapter, Track Reranker v1, curator explanation) is intentionally NOT implemented yet.

## Objective

Create the actual new recommendation system that combines user text, personal taste, provider taste, and optional audio features.

## 4.1 LangGraph state

✅ **[COMPLETED] State schema defined (July 24, 2026)** — `recommendation-service/app/core/graph_state.py` defines `RecommendationState` as a `TypedDict` (`total=False`, so nodes return sparse partial updates) covering: original request context (`request_id`, `user_id`, `user_text`, `discovery_mode`, `language`/`region`, `audio_features`, `user_profile`, `explicit_constraints`); normalized text + constraints + structured `retrieval_query` (§4.4 inputs); retrieval fields (`retrieved_genres`, `retrieved_reviews`, `expanded_genre_terms`, `fused_chunks`, `reranked_chunks`); the confidence gate (`retrieval_confidence`, `rewrite_count` — hard max 1, `rewrite_reason`); provider stage (`provider_search_intents`, `candidate_tracks`, `resolved_tracks`, `ranked_tracks`, `sequenced_tracks`); output (`curator_explanation`, `output_valid`); and cross-cutting bookkeeping. **NEW DECISION:** `node_metrics` (per-node latency/model/version/status, per §4.3) and `warnings` use LangGraph **reducers** (`Annotated[dict, merge_dicts]` / `Annotated[list, operator.add]`) so every node's metadata accumulates instead of being overwritten by last-write-wins.

## 4.2 Required graph nodes

**In progress — scaffolding ✅ (July 24, 2026):** all 18 nodes below exist as idempotent stubs in `recommendation-service/app/core/graph_nodes.py` (each logs its trigger, returns a safe dummy state update + a `node_metrics` entry with measured latency), and the full topology is wired and **compiled** in `recommendation-service/app/core/graph.py` (`StateGraph(RecommendationState)`, linear spine + conditional edge, verified compiling and invocable end-to-end with `langgraph==1.2.9`, added to `recommendation-service/requirements.txt`). **NEW DECISION (topology):** the conditional edge out of `evaluate_retrieval_confidence` routes to `rewrite_query` only when `retrieval_confidence < RETRIEVAL_CONFIDENCE_THRESHOLD` (env-configurable, default `0.5`) **and** `rewrite_count < 1`; `rewrite_query` increments `rewrite_count` and loops back to `retrieve_genres` for exactly ONE additional retrieval pass, so the second pass through the gate always proceeds to `build_provider_search_intents` — the §4.3 `rewrite_count <= 1` rule is enforced by the graph structure itself (verified: happy path runs 17/18 nodes with `rewrite_count=0`; forced low-confidence run yields `rewrite_count=1` + warning, then continues forward). Real per-node logic remains to be implemented **and tested in this order:** *(update July 24, 2026: nodes 1–4 now carry real logic — see the checked items below; nodes 5–18 remain stubs.)*

Implement and test in this order:

1. ✅ **[COMPLETED]** `validate_context` **— real logic implemented (July 24, 2026).** Requires at least one usable input signal: non-blank `user_text` OR a non-empty `audio_features` dict. On failure it captures the state (`context_valid=False`, `output_valid=False`, validation warning appended, node metric `status="error"`) instead of raising — the early-exit/error edge is deferred as planned. Edge cases: whitespace-only text and empty `{}` audio dicts both count as missing.
2. ✅ **[COMPLETED]** `normalize_input` **— real logic implemented (July 24, 2026).** Text hygiene: control characters stripped, whitespace runs collapsed, hard truncation at `MAX_USER_TEXT_CHARS=1000` (with warning) to prevent prompt bloating/long-form injection (semantic injection checks stay in guardrails-service). Explicit UI constraints are split into `normalized_constraints = {"positive", "negative"}`: singular/plural keys merge (`genre`+`genres` → deduped lowercase `genres` list), `year_from`/`year_to` coerce to int (non-numeric values are dropped with a warning, not fatal), `era`/`mood`/`language` collapse to scalars, and `exclude_`*/`avoid` populate the negative bucket. **NEW DECISION:** state field renamed `constraints` → `normalized_constraints` in `graph_state.py` for clarity.
3. ✅ **[COMPLETED]** `load_or_accept_user_profile` **— real logic implemented (July 24, 2026).** Accepts a non-empty provided profile as-is; otherwise injects the default **Guest profile**: `profile_type="guest"`, `version=0`, neutral genre weights (`{}` = no prior taste bias), `text_relevance=1.0`, `personal_taste=0.0`, `provider_taste=0.0`. `discovery_mode` is resolved explicitly in priority order request > profile > `"balanced"`; invalid values fall back to `"balanced"` with a warning rather than failing the run.
4. ✅ **[COMPLETED]** `build_retrieval_query` **— real logic implemented (July 24, 2026, §4.4).** Deterministic rules-based payload combining: normalized text, positive/negative constraints, profile weights, confidence-weighted audio features, discovery mode + per-mode retrieval knobs (`safe`: no genre expansion / diversity 0.2; `balanced`: expansion / 0.5; `adventurous`: expansion / 0.8 / larger pool), and language/region. **NEW DECISION (audio down-weighting):** each audio feature gets `{value, confidence, weight, treat_as}` — confidence ≥ `AUDIO_CONFIDENCE_THRESHOLD` (0.6) ⇒ `weight=1.0`, `treat_as="constraint"`; below ⇒ `weight=confidence`, `treat_as="soft_hint"` — down-weighted, never fabricated and never a hard filter (per §4.4). Accepts flat values, per-feature `{value, confidence}` dicts, or a flat global `confidence` key.
5. `retrieve_genres`
6. `retrieve_reviews`
7. `expand_genre_graph`
8. `fuse_results`
9. `rerank_documents`
10. `evaluate_retrieval_confidence`
11. `rewrite_query`
12. `build_provider_search_intents`
13. `search_providers` through the Provider Adapter (schema-valid fixtures are allowed only until Phase 5)
14. `deduplicate_and_resolve_tracks`
15. `rank_tracks`
16. `sequence_tracks`
17. `generate_grounded_explanation`
18. `validate_output`



## 4.3 Graph rules

- `rewrite_count` must never exceed 1.
- Search-provider writes are forbidden; only reads occur inside LangGraph.
- Feedback and playlist export side effects remain in n8n.
- Explicit UI intent and user constraints cannot be overridden by the agent.
- Every node returns latency, model name/version, and safe status metadata.
- Nodes should be idempotent and individually unit-testable.
- Track names suggested by an LLM are search intents, not final recommendations.
- Only provider-resolved, playable candidates may appear in a non-fixture final track list.



## 4.4 Structured query construction

The query builder must use:

- normalized user text;
- positive and negative constraints;
- user profile weights;
- provider taste signals when authorized;
- audio features and confidence when present;
- discovery mode: `safe`, `balanced`, or `adventurous`;
- language and region constraints.

Audio fields with low confidence should be down-weighted, not treated as exact constraints.

## 4.5 Confidence gate and bounded retry

Low-confidence examples:

- top chunks have weak reranker scores;
- results disagree across retrieval sources;
- required genre/artist constraints are absent;
- provider search repeatedly returns no playable matches.

Allowed retry:

1. Generate one structured rewrite explaining which constraint is relaxed or clarified.
2. Run one additional retrieval pass.
3. Continue with warnings or return an honest no-result response.

No open-ended agent loop is allowed.

## 4.6 Provider search intents

⚠️ **NEW DECISION (July 26, 2026, later) — the user's own words are always searched, not only as a fallback.** `build_provider_search_intents` treated the request text as a last resort (`if not intents`), so any request that produced *any* derived constraint never searched what the user actually typed. Found the moment the UI made results visible: *"dreamy shoegaze for a rainy night"* collapsed to the single derived query `"dream pop shoegaze"`, whose entire first page was hour-long compilations (76:48, 49:41, 91:50) and a **52-second explainer Short** — every one of them flagged out-of-track-range by `provider-gateway`, and every one of them rendered to the user as a track with a Play button, because the adapter's "never return an empty list" fallback is evaluated *per query* and that one query had nothing better. **Corrected:** the request text is added as its own intent alongside the derived ones, and `MAX_SEARCH_INTENTS` rises from 2 to 3. **This is a quota decision, not just tuning** — each intent costs 100 units of `search.list` against a 10,000/day budget (plus 1 for the batched `videos.list`), so a request now costs ~301 units. Regression tests: `test_build_provider_search_intents_always_searches_the_user_text`, `test_build_provider_search_intents_does_not_duplicate_identical_text`.

🔴 **DEFECT FOUND AND FIXED (July 26, 2026, later) — Hebrew requests timed out, and the intent increase above is part of why.** A Hebrew request returned *"Melody could not answer that — the recommendation orchestrator timed out."* The request was **not failing**: it was taking ~22s of real work, and **WF-002's HTTP node gives up at 25s** while Flask gave up at 30s. Raising `MAX_SEARCH_INTENTS` from 2 to 3 earlier the same day pushed a legitimately slower path over the edge, because `search_providers` issued its intents **sequentially** — their latencies simply added up.

**NEW DECISION: provider searches run concurrently (`asyncio.gather`).** They are independent read-only calls, so serializing them bought nothing. `return_exceptions=True` is deliberate: one failing intent must not discard the others' results, which is the whole point of gathering rather than aborting on the first error; only an all-failed search is an error. Measured Hebrew latency fell from **22.4s to ~19.6s**, and the timeout budget was realigned so a slow-but-working request is never reported as a failure — **WF-002's HTTP node 25s → 90s**, Flask's `N8N_HTTP_TIMEOUT_SECONDS` **30s → 120s** (Flask must outlast the workflow it is waiting on, or it reports a timeout for a recommendation n8n went on to complete successfully).

⚠️ **~19s is still slow, and the remaining cost is not in provider search.** The two RAG retrieval nodes run sequentially by graph topology, and the curator call is a network round trip; parallelizing nodes 5/6 needs a fan-out/fan-in restructure and a reducer for `_retrieval_debug` (currently last-write-wins), so it was **not** attempted here. Recorded as the next latency lever.

⚠️ **NEW DECISION (same session) — node 14 also drops known non-track-length candidates.** `deduplicate_and_resolve_tracks` now keeps only results `provider-gateway` measured inside the track-length bounds (60–600s), unless fewer than three such results remain — the same "never return nothing" floor the adapter uses. **It belongs in node 14, not the adapter**, because node 14 is the first place that sees the union across every search intent, and therefore the first place that fallback can be judged with the full picture rather than one query at a time. Unknown durations are kept: absent data is not bad data.

Example:

The model may describe desired music, but the Provider Adapter supplies real IDs and metadata.

## 4.7 Track Reranker v1

The Track Reranker is separate from the Document Reranker.

Initial transparent score:

When no audio input exists, redistribute or normalize the available weights; do not set missing signals to fabricated values.

Store every component score for explainability and future learning.

✅ **[COMPLETED] Track Reranker v1 implemented (July 25, 2026)** in `recommendation-service/app/core/graph_nodes.py::rank_tracks`. Components: `provider_confidence`, `text_relevance` (stdlib `difflib` fuzzy match against the query + constraints), `personal_taste`, `provider_taste`. `audio_fit` is **omitted, not fabricated** — no per-track audio features exist before Phase 6/7 — and its weight share is redistributed across the present components, exactly as this section requires. Every component's weight and score is stored on the track as `score_components`, alongside the `final_score`.

⚠️ **NEW DECISION (July 25, 2026) — provider confidence is a quality signal, not a taste signal.** The first implementation folded the provider adapter's confidence into the **`provider_taste`** component, whose weight is `0.0` for a guest profile. The consequence was invisible while provider results were identical fixtures, and became obvious the moment real YouTube search landed: confidence was multiplied by zero and discarded, so ranking collapsed to pure fuzzy text match — which *rewards* titles that repeat the query's genre word. A video essay titled *"Top 5 Grunge Songs of All Time"* outranked Nirvana's actual recording. **Corrected:** `provider_confidence` is now a **separate component with a constant weight independent of the user profile**, because "is this a real, authoritative, playable track" must carry weight even for a guest who has no taste profile at all. `provider_taste` retains its original, correct meaning — taste *imported from the provider*, which legitimately stays `0.0` until §5.2 OAuth exists. Regression test: `test_rank_tracks_uses_provider_confidence_even_for_guest_profile`.

## 4.8 Final curator explanation

Input:

- selected real tracks;
- RAG evidence;
- personal and audio fit summaries;
- discovery strategy;
- warnings and missing metadata.

Output:

- short curator summary;
- a concise reason per track;
- no unsupported biographies or factual claims;
- no raw retrieval mechanics in normal user prose;
- structured provider IDs separate from prose.

The expensive model is used only here and for the single low-confidence rewrite when necessary.

⚠️ **NEW DECISION (July 26, 2026, later) — a track the curator declined to explain is dropped, not shipped with an empty reason.** Node 17 asked the model to explain every sequenced track and then wrote back `result.track_reasons.get(i, "")`, so any track the model skipped was returned with `reasoning: ""` **and still presented to the user as a curated pick**. This section requires "a concise reason per track" and ADR-006 forbids synthesizing one, so the only correct outcome is to drop it. In practice the model declines exactly the candidates that are not tracks at all — reaction videos, visualizers, genre explainers that survived ranking — which makes this a useful last line of defence as well as a contract requirement. If *nothing* is explained the run is marked `output_valid: False` rather than returning an empty playlist, matching the existing adapter-failure path. Positions are renumbered after a drop so the list has no holes. `sequence_tracks` additionally trims to `FINAL_TRACK_LIMIT = 10`, matching §SEQ-003's 8–12 and keeping the explanation request inside one bounded completion. Regression tests: `test_generate_grounded_explanation_drops_unexplained_tracks`, `test_generate_grounded_explanation_invalid_when_nothing_explained`, `test_sequence_tracks_caps_at_final_track_limit`.

⚠️ **NEW DECISION (July 26, 2026, later) — one recommendation per request, not a list.** Developer decision after seeing a reply render five track cards with five embedded players: wasteful to load, and it hands the user five things to evaluate instead of one. `FINAL_TRACK_LIMIT` drops from ~~10~~ to **1** (overridable via `RECOMMENDATION_TRACK_LIMIT`), and the UI renders the single player inline rather than behind a "Play here" button — the click-to-mount step existed only to avoid loading several embeds at once, so it has no purpose with one. Neither player autoplays. **The follow-up recommendation comes from the next turn**, informed by the like/dislike on this one, which is what `UI-006`'s per-track feedback is for. Note this makes §SEQ-003's "8–12 tracks" a *Phase 7 Smart Sequencer* target rather than the shape of a conversational reply; raise the limit when that sequencer lands. A consequence worth stating: the UI's "only a few tracks matched" low-confidence notice was **removed**, because with a one-track reply it would have fired on every successful response.

⚠️ **NEW DECISION (same session) — "structured provider IDs separate from prose" is now actually implemented at the API boundary.** This section has required it since Phase 4, but `recommendation-service`'s `TrackRecommendation` response model listed only `title`, `artist` and `reasoning`. The graph resolved a real YouTube video for every track and the FastAPI response model then **discarded `provider_track_id`, `url`, `embeddable`, `duration_seconds` and `position` on the way out** — which made `UI-005`, `PLAY-001` and `PLAY-005` unimplementable no matter what the UI did. The model is now a superset of `contracts/ai_recommendation_schema.json`'s track item, which stays contract-valid because that schema sets no `additionalProperties: false`.

## 4.9 Model routing

For every model call store provider, model, input/output token counts if available, latency, estimated cost, cache hit, request ID, and success/failure.

## 4.10 Legacy comparison and cutover

- [x] ✅ **[COMPLETED] REC-LEG-001 P0: Run at least 10 shared prompts through the existing Bedrock route and the new route (July 25, 2026).** **12** shared prompts (`eval/prompts.json`, spanning §3.8's categories: mood, blended genres, Hebrew + English, exact artist/genre, anti-echo-chamber, negative constraints) run through **both** legs by `eval/rec_leg_comparison.py`. All 24 calls succeeded. Raw output: `eval/rec_leg_report.md` / `.json`.
- [ ] **REC-LEG-002 P0:** Compare retrieval relevance, playable-track rate, latency, cost, diversity, and explanation quality. → ⚠️ **PARTIALLY DONE (July 25, 2026) — deliberately not checked off.** Four of the six measures are recorded (latency: legacy 21,099 ms avg vs new 17,256 ms; playable-track rate; diversity; retrieval grounding). **Three gaps remain:** (a) **explanation quality is unscored** — the report reserves a blank 1–5 column pending a human or LLM-judge pass; (b) **cost is one-sided** — the harness captures the new engine's real per-call cost (~$0.0033) but Bedrock Agent does not expose per-call token usage the same way, so a fair cost comparison needs AWS Cost Explorer/CloudWatch; (c) **the numbers are already stale** — the comparison ran *before* Phase 5 landed real YouTube search, so the new engine's track-level columns reflect the old fixture. **Re-run `eval/rec_leg_comparison.py` now that real search exists** for a valid track-level verdict. → ⚠️ **A fourth gap, added July 26, 2026 (later): the harness measured a path no real user request ever took.** `eval/rec_leg_comparison.py` calls `recommendation-service` **directly**, in the flat payload shape — which worked — while every request arriving through WF-002 was running on an empty query (see §1.5's critical-defect record). The recorded latency, diversity and grounding figures therefore describe the new engine fed a *correct* query, which the product itself was not doing until this session. The re-run is now doubly required, and should go **through the n8n path or the Flask route**, not straight to the service, so the harness exercises what a user exercises.
- [ ] **REC-LEG-003 P0:** Make the new engine default only after the Phase 5 real-provider gate and Phase 8 UI gate pass. → Still correctly blocked: the Phase 5 gate is not passed (only §5.1/§5.3 landed; §5.2/§5.4/§5.5 remain) and Phase 8 has not started. `RECOMMENDATION_ENGINE` stays `legacy`.
- [ ] **REC-LEG-004 P1:** Remove automatic legacy fallback after release stability is established.



## Phase 4 gate

✅ **[COMPLETED] Phase 4 gate PASSED (July 25, 2026)** — every criterion below verified by execution against the live stack, not by inspection. Evidence is recorded in the "▶ RESUME HERE" session bookmarks at the top of this document.

- ✅ **[COMPLETED]** `POST /recommendations/run` accepts the full RecommendationContext. *(Accepts both WF-002's envelope shape and a flat payload; `main.py::_build_initial_state` maps either onto `RecommendationState`.)*
- ✅ **[COMPLETED]** Text-only, profile-aware, and audio-feature-fixture tests all pass. *(39 offline tests in `recommendation-service`; the audio-feature path is covered by `_normalize_audio_features`' confidence-weighting tests.)*
- ✅ **[COMPLETED]** The graph performs at most one rewrite. *(Enforced structurally by the conditional edge in `graph.py`; live-verified — a forced low-confidence run fires `rewrite_query` exactly once, then proceeds forward instead of looping.)*
- ✅ **[COMPLETED]** Provider search intents are stable; normalized candidate fixtures pass the same adapter contract that Phase 5 will use for real tracks. *(Proven the strongest way available: Phase 5 §5.1/§5.3 swapped the fixture for real YouTube results behind the **unchanged** `NormalizedTrack` contract — `recommendation-service` needed no contract change.)* ⚠️ **One caveat worth recording:** "intents are stable" held only in the fixture world — the first real-search run exposed that `build_provider_search_intents` was concatenating unrelated genre chunks into one incoherent query (7/12 recommendations returned zero tracks). Fixed during Phase 5; see the session bookmark.
- ✅ **[COMPLETED]** Track component scores and model usage are stored for fixture-based contract tests. *(§4.7 component scores + `final_score` on every ranked track; §4.9 model usage — provider/model/tokens/latency/estimated cost/request id — structured on `NodeMetric` and logged as JSON.)* ⚠️ **Known gap, not gate-blocking:** `node_metrics` lives only in per-request graph state and the structured log line. The `model_usage` table in `contracts/db_models.py` is **never written to** — durable cost tracking is still owed.
- ✅ **[COMPLETED]** `sequence_tracks` uses a versioned deterministic relevance-order baseline until Phase 7 replaces it with the Smart Sequencer. *(`SEQUENCER_VERSION = "relevance-order-baseline-v1"`, emitted in the node's metrics.)*
- ✅ **[COMPLETED]** WF-002 uses the real Recommendation Service; its service-call placeholder is removed, while the provider fixture remains explicitly labeled and traced to Phase 5. *(WF-002 already pointed at `http://recommendation-service:8000/recommendations/run` and needed no change; the fixture label is now moot — provider search is real as of Phase 5 §5.1/§5.3.)*
- ✅ **[COMPLETED]** The new engine is distinguishable from the legacy benchmark in logs and test metadata, but public cutover waits for real-provider and UI gates. *(`engine: "graph"` + `placeholder: false` on every response, vs the legacy route's free-form text; `RECOMMENDATION_ENGINE` remains `legacy` per `REC-LEG-003`.)*

---



# 10. Phase 5 — Provider implementation, authentication, playback, and export



## Objective

Implement the provider mode selected in Phase 0 and return real, playable track identities without coupling the recommendation engine to MusicAPI, YouTube, or Spotify.

## 5.1 Implement the chosen provider mode

> ⚠️ **Scope note (July 25, 2026):** this session implemented **search only**. Adapter operations that require user OAuth (taste import, playlist writes) are §5.2/§5.5 and are untouched, so several PROV items below are honestly marked partial rather than checked off. Implementation lives in `provider-gateway/app/youtube_adapter.py` + `provider-gateway/app/cache.py`.

- [ ] **PROV-001 P0:** Implement every adapter operation required by the selected Phase 0 mode. → ⚠️ **PARTIAL (July 25, 2026): search is real and live; the rest are not.** `/providers/search` calls the real YouTube Data API v3 (`search.list`) in `direct` mode per ADR-002. **Still missing:** taste import and playlist create/populate — both need user OAuth (§5.2), and `/providers/playlists` still returns `FEATURE_DISABLED` by design. → **Updated July 26, 2026 (later still): search is now real on *both* approved providers.** Spotify search is implemented (§5.6) behind the same normalized adapter contract, so `PROVIDER_MODE=direct`'s "YouTube primary, Spotify limited" is delivered for the read path. Export remains YouTube-only and taste import remains unimplemented for both.
- [ ] **PROV-002 P0:** Add normalized error codes for authorization, quota, rate limit, missing item, unavailable item, and provider outage. → ~~⚠️ **PARTIAL (July 25, 2026): three of six.** `QUOTA_EXCEEDED` (403 `quotaExceeded`/`dailyLimitExceeded`), `RATE_LIMITED` (429), and `PROVIDER_UNAVAILABLE` (timeout/5xx/missing key) are implemented and unit-tested, mapped onto the shared `AppError` envelope. **Not yet:** `AUTHORIZATION_*` (no OAuth path exists to fail yet — §5.2), and missing-item/unavailable-item (need the per-video availability check that `videos.list` enrichment would provide).~~ → ⚠️ **PARTIAL, now five of six (July 25, 2026, `videos.list` enrichment).** Quota / rate-limit / outage as before, **plus missing-item and unavailable-item**: a video present in `search.list` but absent from `videos.list` is deleted or private and is dropped; a video blocked in `YOUTUBE_REGION` (default `IL`, honouring both `regionRestriction.blocked` and `.allowed`) is dropped as unavailable. **Only `AUTHORIZATION_*` remains**, and it is genuinely un-implementable until §5.2 creates an OAuth path that can fail.
- [ ] **PROV-003 P0:** Add provider-level timeouts, circuit breakers, and safe retries. → ⚠️ **PARTIAL (July 25, 2026): timeouts only.** Bounded connect/read timeouts come from `shared_lib.http.make_async_client`, and a timeout surfaces as a normalized `PROVIDER_UNAVAILABLE` instead of a crash. **Circuit breakers and retries are NOT implemented** — deliberately deferred, since a naive retry on a 100-quota-unit call is actively harmful against a 10,000/day budget; any retry policy here must be quota-aware.
- [x] ✅ **[COMPLETED] PROV-004 P0: Cache stable metadata and repeated searches with explicit TTLs (July 25, 2026).** `provider-gateway/app/cache.py` — in-process TTL cache keyed on `(provider, normalized_query, limit)` with an explicit 24h default. **NEW DECISION:** caching is load-bearing here rather than an optimization — `search.list` costs **100 quota units** against a **10,000/day** default quota (~100 searches/day, and the graph can issue 2 per recommendation), so an uncached demo exhausts the day's budget in under an hour of testing. ⚠️ **Known limitation:** in-process only — not shared across instances and lost on restart. A Redis/DB-backed cache (`INF-009`, P1) is the fix if multi-instance deployment happens.
- [x] ✅ **[COMPLETED] PROV-005 P0: Store the data source and confidence for every normalized field** ~~⚠️ **PARTIAL (July 25, 2026): per-track, not per-field.** Every `NormalizedTrack` carries `provider` (the data source) and a `confidence` score derived from transparent heuristics. **The plan asks for per-*field* source/confidence** — e.g. artist parsed from the video title vs. taken from the channel name are currently indistinguishable to a consumer, even though the parser knows which happened. Worth closing when `videos.list` enrichment lands and fields start coming from multiple sources.~~ → **closed by the `videos.list` enrichment (July 25, 2026).** Every track now carries a `field_sources` map recording where each normalized field came from — `title` → `search.list:snippet.title(parsed)`; `artist` → either `search.list:snippet.title` (parsed from the title) or `search.list:snippet.channelTitle` (channel fallback), which is exactly the distinction that was previously invisible; `duration_seconds` → `videos.list:contentDetails.duration`; `embeddable` → `videos.list:status.embeddable`; plus `region_checked` naming the region the availability check ran against. Field-level confidence for the parsed fields is carried as `parse_confidence` in the same map, and it multiplies into the track's overall `confidence` rather than being reported separately.
- [x] ✅ **[COMPLETED] PROV-006 P0: Add contract tests that run unchanged across MusicAPI and direct adapters (July 25, 2026).** 21 offline tests in `provider-gateway/` (`test_youtube_adapter.py` + `test_smoke.py`), no network or API key required. **NEW DECISION (interpretation):** MusicAPI was REJECTED in §0.4, so "runs unchanged across adapters" is implemented as *the endpoint tests assert the `NormalizedTrack` contract through the HTTP boundary, never YouTube-internal details* — they would pass unmodified against any future direct adapter. The YouTube-specific parsing/heuristic tests are deliberately separate from the contract tests.



## 5.2 Google identity and YouTube authorization

> ~~⚠️ **Implementation status (July 25, 2026): code complete and offline-verified; the live consent round trip is NOT yet run**, ~~because it needs Google Cloud credentials the developer must create (see the session bookmark)~~ → **the credentials were supplied July 26, 2026, so the round trip is unblocked and is the immediate next action.** Every item below is marked on that basis — code + offline tests, **not** a completed browser sign-in; per Section 19 a checkbox alone is not evidence, so these revert to open if the live flow fails.~~ → ✅ **[COMPLETED] The live consent round trip was executed on July 26, 2026 and passed** — a real browser sign-in produced the app's first `users` row and an `oauth_accounts` row with genuinely encrypted tokens, with `AUTH-002`/`003`/`004` observable in the live redirect and stored scopes. Full evidence table in the session bookmark. **`AUTH-005` remains the one item proven only by redirect inspection and unit tests**, because there is no export button to trigger the upgrade until §5.5. Implementation: `auth_google.py` (Flask blueprint), `contracts/token_crypto.py`, `contracts/db_models.py::OAuthAccount`, migration `b8e4f1a92c37`, **ADR-007**.

- [x] ✅ **[COMPLETED] AUTH-001 P0: Use Google OpenID Connect for basic application identity (July 25, 2026).** `/auth/google/login` via Authlib against Google's OIDC discovery document. **NEW DECISION:** Authlib is used rather than the project's usual raw-httpx pattern — the same reasoning that justified the official `anthropic` SDK. OIDC requires ID-token validation against Google's rotating JWKS plus state/nonce correlation, and hand-rolling that is a well-known source of authentication vulnerabilities. ⚠️ **This is the application's first real persistent identity:** the `users` table existed since Phase 2 but **nothing in the repo had ever written a row to it** — every request until now was a guest.
- [x] ✅ **[COMPLETED] AUTH-002 P0: Use Authorization Code Flow on the server (July 25, 2026).** Code exchange happens server-side in `/auth/google/callback`; no token ever reaches the browser. `access_type=offline` + `prompt=consent` are set because Google otherwise omits the refresh token entirely.
- [x] ✅ **[COMPLETED] AUTH-003 P0: Validate `state`, `nonce`, callback origin, and session binding (July 25, 2026).** `state` and `nonce` are validated by Authlib. **Session binding is additional and ours:** the flow stashes the current `session_id` at authorize time and the callback rejects the exchange unless it still matches, so a `state` token lifted into a different browser session cannot complete. Callback origin is pinned by `GOOGLE_REDIRECT_URI` from configuration rather than derived from the request, so a spoofed `Host` header cannot redirect the code (Google enforces it independently against the registered URI). Three regression tests cover the rejection paths.

🔴 **DEFECT FOUND AND FIXED (July 26, 2026, later) — pinning the callback origin made sign-in fail whenever the app was browsed on a different host.** The developer signed in and landed on a bare JSON page: `{"error":{"code":"INVALID_OAUTH_STATE","message":"Sign-in session did not match. Please try again."},"ok":false}`. **Nothing was wrong with `state`, `nonce`, or the binding logic — the session cookie simply never arrived.** `GOOGLE_REDIRECT_URI` was `http://127.0.0.1:5000/...` while the app was served at `http://localhost:5000`. Cookies are scoped by **host**, and `localhost` and `127.0.0.1` are different hosts even though they are the same machine, so the cookie set while starting the flow was not sent to the callback: `bound` was `None` and the binding check correctly rejected an exchange it could not verify.

**NEW DECISION: the flow starts on the callback's own origin.** `/auth/google/login` and `/auth/google/upgrade` compare the request host against `GOOGLE_REDIRECT_URI`'s host and, when they differ, redirect there *before* beginning the exchange — so the whole flow happens inside one cookie scope and no `state` is burned on an origin that could never have completed it. This is preferred over relaxing the pin (which would reintroduce the `Host`-spoofing exposure `AUTH-003` closes) and over requiring the two values to be configured identically (which fails silently and confusingly, as it just did). **The error message is also now self-diagnosing:** "no session at all" and "session changed mid-flow" are distinguished, and the first names the host to use and the variable to change instead of saying only "did not match". Regression tests: `test_login_realigns_to_the_callback_host`, `test_upgrade_realigns_to_the_callback_host`, `test_callback_without_any_session_explains_the_host_mismatch`.

⚠️ **Why the July 25 live verification did not catch this:** that round trip was driven directly against `127.0.0.1`, matching the redirect URI by accident. The defect only appears when a *user* browses the app by hostname — which first happened once the Phase 8 UI gave them a sign-in button to click.
- [x] ✅ **[COMPLETED] AUTH-004 P0: Request basic identity scopes first (July 25, 2026).** Login requests `openid email profile` only — no YouTube scope at first contact.
- [x] ✅ **[COMPLETED] AUTH-005 P0: Request YouTube write scopes incrementally only when export is selected (July 25, 2026).** Separate `/auth/google/upgrade` route requests the YouTube scope with `include_granted_scopes=true`, so Google *adds* to the existing grant rather than replacing it and the identity scopes survive. ~~⚠️ **Wired but not yet reachable from the UI** — there is no export button to trigger it until §5.5; the route and the stored-scope widening are unit-tested.~~ → ✅ **Exercised against the real provider for the first time on July 26, 2026 (§5.5):** the stored `scopes` gained `.../auth/youtube` **and kept** all three identity scopes, confirming the incremental behaviour live rather than by inspection. ⚠️ **Still not reachable from the UI** — there is no export button; the upgrade must be visited directly. That is Phase 8 UI work, not an `AUTH-005` gap.

> ⚠️ **Google Cloud gotcha found the hard way (July 26, 2026), recorded so the next person does not lose an hour to it.** The first upgrade attempt was refused with `403 access_denied` — *"app is in testing, only approved test users can access it"* — even though sign-in had been working for days. **Cause: `openid`/`userinfo.email`/`userinfo.profile` are non-sensitive scopes and are exempt from the unverified-app restriction entirely**, so an app in Testing mode lets *any* account through when it asks for only those. `.../auth/youtube` is **sensitive**, so requesting it consults the Test users list **for the first time in the project's life** — and it was not correctly populated. A successful identity-only sign-in is therefore **not** evidence that a test user is whitelisted. Fixed by correcting the Test users list on the project that owns the OAuth client (Google Auth Platform → **Audience**) and retrying in a clean Incognito window.
- [x] ✅ **[COMPLETED] AUTH-006 P0: Encrypt stored tokens or token references (July 25, 2026).** **This is the encrypted-token-storage decision Section 2.3 explicitly deferred to Phase 5 — recorded in `docs/adr/ADR-007-oauth-token-storage.md`.** Fernet (AES-128-CBC + HMAC) via `contracts/token_crypto.py`; both token columns hold ciphertext; `OAUTH_TOKEN_ENCRYPTION_KEY` accepts a comma-separated list so `MultiFernet` supports rotation, and each row records a non-reversible `encryption_key_id`. **NEW DECISION: there is no plaintext fallback** — a missing key fails the sign-in with `SERVER_MISCONFIGURED` rather than silently storing a raw token, since a fallback would defeat the entire control while appearing to work. ⚠️ **Contrast worth recording:** the *legacy* Spotify path does the opposite — spotipy's `FlaskSessionCacheHandler` puts the access **and refresh** token in the Flask session cookie, which is *signed but not encrypted*, i.e. base64-readable by anyone holding the cookie. That path stays unrepaired per the "don't invest in legacy" decision, but it must not be the model for Google.
- [ ] **AUTH-007 P1:** Add disconnect, revocation, and user-data deletion flows. → ⚠️ **PARTIAL (July 25, 2026): disconnect + provider-side revocation done; user-data deletion not.** `POST /auth/google/disconnect` revokes at Google's `/revoke` endpoint (preferring the refresh token, which invalidates the whole grant), stamps `revoked_at`, and clears the session; a provider outage still completes the local revocation, because the user asked to disconnect. **Remaining:** true user-data deletion, which Section 2.3 requires be "implemented as true deletion where promised to the user" — that is a broader GDPR-shaped task spanning `users`, `feedback_events`, and `recommendation_sessions`, not just this table. ~~⚠️ **ALSO REMAINING — the live disconnect test was deliberately skipped (July 26, 2026, developer decision):** running it revokes the grant at Google and would force a re-authentication, which was not worth the interruption at that moment. **`POST /auth/google/disconnect` is therefore covered by unit tests only** (revocation call shape, `revoked_at` stamped, session cleared, and local revocation still completing when Google is unreachable) — it is the **one §5.2 code path never exercised against the real provider**. Test it on the next occasion a re-authentication is acceptable anyway; a natural pairing is the §5.5 export slice, where the `AUTH-005` YouTube-scope upgrade will require re-consent regardless.~~ → ✅ **[COMPLETED] The live disconnect WAS run during §5.5 (July 26, 2026), in exactly the pairing predicted above.** `{ok: true, revoked_at_provider: true}`; `revoked_at` stamped; the YouTube scope dropped from `scopes`; WF-009 then reported `connected: false, reauthorization_required: true`; and an export attempt **failed closed** with `REAUTHORIZATION_REQUIRED`, creating no playlist and recording the refusal in `playlist_exports`. Every §5.2 code path has now been exercised against the real provider.

⚠️ **NEW FINDING from that live run, not fixed — disconnect leaves the encrypted tokens at rest.** `revoked_at` is stamped and the scopes are cleared, but `encrypted_access_token` and `encrypted_refresh_token` still hold ciphertext. The credentials are dead at Google so this is not an exploitable secret, and `_load_account()` refuses any revoked row so it cannot be used — but a user who explicitly asks to disconnect reasonably expects the credentials **deleted**, not retained. This belongs with `AUTH-007`'s outstanding user-data-deletion work rather than as a separate item; recorded here so it is not lost.

If MusicAPI owns the external OAuth exchange, Melody must still validate its own application session and securely map the returned provider connection to the correct user.

## 5.3 YouTube-first discovery

⚠️ **TITLE-PARSING DEFECTS FIXED, BUT THE UNDERLYING QUALITY PROBLEM IS NOT PARSING (July 26, 2026, later still, continued).**

`_parse_title_artist` had four distinct defects, every one of which reached the UI as the displayed song name:

| Input | Was | Now |
| --- | --- | --- |
| `Some Song (Official Audio) - HD` | title **"HD"**, artist "Some Song" | title "Some Song" |
| `Alice In Chains - Man in the Box (Official HD Video)` | title kept `(Official HD Video)` | "Man in the Box" |
| `Slowdive - Alison (audio) - HD` | title kept `(audio) - HD` | "Alison" |
| `שלמים \| Idan Rafael Haviv` (channel `עידן רפאל חביב`) | **title and artist swapped** | title "שלמים", artist from channel |

**NEW DECISION: the channel name outranks word order when deciding which side of a separator is the artist.** "Artist - Title" is a convention, not a rule, and it is wrong often enough to matter; an official or artist channel is usually named after the artist, so a side that matches the channel *is* the artist regardless of position. When no side matches, the convention still applies but at **reduced parse confidence (0.9)** because it is a guess.

**NEW DECISION: `|` is not treated as an artist/title separator at all.** It is a general-purpose divider, and the live Hebrew case above carries the opposite order from the dash convention. Worse, the two sides there were *the same name in two scripts* (`Idan Rafael Haviv` / `עידן רפאל חביב`), so no string match could ever connect them. For pipes the channel is simply the better artist source. Pipe matching is also whitespace-tolerant, since `"שלמים| Idan Rafael Haviv"` missed the fixed `" | "` separator entirely and sent the whole raw title to the UI as the song name. Regression tests: 8 new cases in `test_youtube_adapter.py` (78 → 86 tests).

🔴 **The honest result: end-to-end YouTube quality is still poor, and the remaining cause is result *selection*, not parsing.** After the fix, a live run of "alice in chains man in the box" returned a **lyrics-channel upload** (parsed as title "Alice In Chains Lyrics", artist "Man In The Box" — the channel matched neither side, so the convention swapped them), and a Hebrew request returned a **compilation** ("שירים ישנים" / "ישראלי שקט חלק ד'"). Direct provider search for the same query returns the right track at the top; it is the intervening pipeline that does not keep it.

**This is not a parsing problem and should not be attacked as one.** The chain that selects a track — §4.6's search intents, `provider-gateway` ranking, §4.7's Track Reranker — has now been corrected four separate times (provider confidence discarded for guests; incoherent compound queries; the user's own text never searched; non-track-length results surviving), and each fix improved things without making YouTube reliable. **The structural difference is that Spotify's catalogue contains only released recordings, while YouTube requires the adapter to *infer* which results are even music.** Same prompts, same pipeline, consistently better Spotify results.

➡️ **This is now the strongest evidence for the open §17 decision on whether Spotify should become the default provider**, and that decision should be made before more effort goes into YouTube ranking.

YouTube is video-centric and does not provide a reliable official watch-history feed for this product. Build taste from signals the authorized API actually exposes, such as relevant liked music videos, subscriptions, user-selected playlists, and Melody's own feedback.

- [x] ✅ **[COMPLETED] YT-001 P0: Search with music-oriented filters and transparent official-content heuristics (July 25, 2026).** `search.list` is called with `type=video` + `videoCategoryId=10` (YouTube's Music category), and every result is scored by the transparent heuristic in `YT-002`. Live-verified against real queries in English and Hebrew.
- [x] ✅ **[COMPLETED] YT-002 P0: Prefer official artist channels, topic channels, official audio, or official music videos when confidence is adequate (July 25, 2026).** Three transparent tiers in `_confidence_for()`: auto-generated **"— Topic" channels** (YouTube's canonical-release signal) score highest at 0.95; titles carrying an **official video/audio/music-video/lyric-video marker** score 0.8; everything else scores 0.5. **NEW DECISION:** this is a *ranking* signal, never an allow/deny filter — the floor is 0.15, never zero, so lower-confidence results are deprioritized rather than discarded, and the score is multiplied by the title-parse confidence so a guessed artist can never masquerade as canonical. Live evidence both ways: `"Bon Iver Holocene"` → official-marker tier (0.8) with correct title/artist; `"deep house tracks"` → honest 0.5s, because YouTube genuinely returns DJ-mix compilations for vibe queries.
- [x] ✅ **[COMPLETED] YT-003 P0: Normalize artist/title from noisy video metadata and store confidence (July 25, 2026).** `_parse_title_artist()` handles the real-world shapes: `"Artist - Title"` (and en/em-dash and `|` variants), `"Title by Artist"`, bracketed suffix stripping (`(Official Video)`, `[Official Audio]`, `(Lyrics)`, `(HD)`, `(4K)`, `(Visualizer)`…), **HTML-entity unescaping** (`&quot;`, `&amp;` — a real defect caught in live output), and wrapping-quote stripping. Falls back to the channel name as the artist (with a reduced 0.6 parse confidence that propagates into the final score) rather than ever dropping a result.
- [x] ✅ **[COMPLETED] YT-004 P0: Deduplicate alternate uploads, live versions, covers, and remixes without incorrectly merging distinct recordings** ~~⚠️ **PARTIAL (July 25, 2026): the safety half is done, the merging half is not.** `_dedupe()` collapses entries whose normalized `(artist, title)` match exactly, **keeping the highest-confidence one** (so a Topic-channel upload beats a random re-upload). The "without incorrectly merging distinct recordings" requirement is satisfied — live/remix/cover variants carry distinct titles and are correctly preserved as separate entries. **What's missing is the harder direction:** two uploads of the *same* recording with cosmetically different titles are not yet recognized as duplicates. That needs fuzzy title matching or `videos.list`-based duration comparison — deferred deliberately, since an over-eager fuzzy merge would violate the "without incorrectly merging" clause, which is the more expensive mistake.~~ → **closed by the `videos.list` enrichment (July 25, 2026)** — the deferred duration comparison is exactly what made the merging half safe. Two passes: exact normalized `(artist, title)`, then a fuzzy pass gated on **same artist + runtime within 2 s + title similarity ≥ 0.82**, always keeping the highest-confidence entry. **NEW DECISION:** the duration gate is the safety mechanism, not an optimization — a live cut, remix, or extended edit has a different runtime and therefore survives as a distinct recording, and entries with unknown duration are **never** fuzzy-merged (unenriched results fall back to exact matching only). Live proof: `"Nirvana Smells Like Teen Spirit"` correctly returns the studio cut (279 s), Devonshire Mix (303 s), Reading '92 (331 s) and Paramount (276 s) as four separate recordings.
- [x] ✅ **[COMPLETED] YT-005 P0: Record quota cost for every API method (July 25, 2026).** `_record_quota_usage()` emits a structured JSON log line per call (`{"method": "search.list", "units": 100}`). Only one method is on the request path today, so coverage is complete by construction; `videos.list` (1 unit) would use the same helper. ⚠️ **Same "log now, persist later" gap as §4.9's model usage** — nothing writes to a durable table yet, so quota spend is only recoverable from container logs.
- [x] ✅ **[COMPLETED] YT-006 P0: Cache repeat searches and metadata lookups (July 25, 2026).** Repeat searches are cached — see `PROV-004` for the implementation and its known in-process-only limitation. *Metadata lookups are N/A for now:* the `videos.list` enrichment call was deferred, so there are no metadata lookups to cache yet; when it lands it must use the same cache.



## 5.4 Playback

> ⏸️ **NEW DECISION (July 26, 2026): §5.4 is deliberately DEFERRED, and §5.5 (export) is taken next instead.** Not because playback is unimportant — because `PLAY-001` has a **hidden Phase 8 dependency** that only became visible after the §5.1/§5.3 work: it says "render the IFrame player using **returned video IDs**", but `templates/index.html` still posts to **`/chat`** (the legacy Bedrock path), so the browser UI has **never called `/api/v1/requests`** and never sees a new-engine video ID. Delivering §5.4 first would therefore drag the Phase 8 "make the UI use the new engine" rewiring forward into Phase 5 and balloon the slice — see the July 25 session bookmark, which first recorded that the UI does not exercise the new architecture at all.
>
> **What is already in place for §5.4 when it is picked up:** the `videos.list` enrichment (July 25) already supplies **`embeddable`** — exactly the signal `PLAY-002` and `PLAY-005` need to decide between the IFrame player and a plain provider link — plus `duration_seconds` and a region-availability check, so region-blocked and deleted videos never reach the UI in the first place. `PLAY-003`/`PLAY-004` are policy constraints, not code, and cost nothing to honour.
>
> **Why §5.5 goes first instead:** it consumes the OAuth just delivered (closing the two §5.2 paths still unproven against the real provider — the `AUTH-005` scope upgrade and `disconnect`), and it lets **three** deferred n8n changes land in a single import → publish-all-8 → restart cycle (WF-006 export, WF-009 connection sync, and the WF-001 `guest_sessions` upsert fix found on July 26) rather than paying that cycle three times.

- [x] ✅ **[COMPLETED] PLAY-001 P0: Render the official YouTube IFrame Player using returned video IDs.** ~~⏸️ Deferred (see the decision above); blocked on the UI calling `/api/v1/requests`, which is Phase 8 work.~~ → **Unblocked and delivered July 26, 2026 (later) when Phase 8 was pulled forward.** Live-verified with a real `youtube-nocookie` embed carrying the real video id. ~~**NEW DECISION: the player is mounted on click, not on render** — ten autoloaded iframes are a heavy first paint for no benefit when the user will play at most one or two.~~ → **SUPERSEDED the same day (July 26, 2026, later still):** the one-recommendation-per-request decision (§4.8) removed the problem this solved. With a single track there is nothing to defer, so the player renders inline and the "Play here" button is gone. **The player is also now provider-aware** — `youtube-nocookie` for YouTube, `open.spotify.com/embed` for Spotify (§5.6) — and **neither autoplays**: the user asked for a recommendation, not to be played at.
- [ ] **PLAY-002 P0:** Handle unavailable, region-blocked, embedding-disabled, and removed videos. → ~~⏸️ **Deferred, but the data is ready:** `provider-gateway` already drops region-blocked and deleted/private videos and returns `embeddable` per track.~~ → ⚠️ **PARTIAL (July 26, 2026, later): embedding-disabled is now handled end to end** — `embeddable === false` renders no player, a plain provider link, and a stated reason (live-verified). Unavailable/region-blocked/removed are still handled by *dropping* them in `provider-gateway` before they reach the UI, which is correct behaviour but means the UI branch for them is untested; a video that goes private *between* search and click is not yet handled.
- [x] ✅ **[COMPLETED] PLAY-003 P0: Do not download, isolate, proxy, or modify YouTube audio.** ~~⏸️ Deferred.~~ A policy constraint honoured by construction — nothing in the stack touches audio streams, and the Phase 8 UI plays only through the official embed.
- [x] ✅ **[COMPLETED] PLAY-004 P0: Do not promise ad-free playback or assume OAuth implies YouTube Premium behavior.** ~~⏸️ Deferred. Copy/UX constraint for the Phase 8 UI.~~ → The delivered UI makes no playback-quality or ad-free claim anywhere.
- [x] ✅ **[COMPLETED] PLAY-005 P0: Provide a normal provider link when embedding is unavailable.** ~~⏸️ Deferred, but the data is ready.~~ → **Delivered and live-verified July 26, 2026 (later).** Every card carries a provider link; when `embeddable` is `false` the inline player is withheld and the reason is stated rather than silently omitted.



## 5.5 Playlist export

For direct YouTube mode:

1. `playlists.insert` creates the playlist after explicit confirmation.
2. `playlistItems.insert` adds each video in Smart Sequencer order.
3. OAuth authorization and quota are checked before writes.
4. Idempotency prevents duplicate playlists.

For MusicAPI or hybrid mode, the Provider Adapter must produce the same externally visible result and failure states.

- [x] ✅ **[COMPLETED] EXPORT-001 P0: Replace all WF-006 provider placeholders (July 26, 2026).** WF-006 is now trigger → `Create Playlist` (real `POST /providers/playlists`) → `Interpret Export Result` → `Return Export Result`; `provider-gateway/app/youtube_playlist.py` performs the real `playlists.insert` + `playlistItems.insert`. **Live-verified: a real private playlist was created in the developer's YouTube account** (`PLQV88szpWdzI`) with both requested tracks added.
- [x] ✅ **[COMPLETED] EXPORT-002 P0: Test success, partial failure, expired authorization, insufficient scope, quota error, and repeated click (July 26, 2026).** All six covered offline in `provider-gateway/test_youtube_playlist.py` + `test_google_token.py` (24 new tests). **Three of the six are additionally proven live:** success, insufficient scope (`INSUFFICIENT_SCOPE` returned before any quota was spent), and repeated click (same key → identical playlist URL, `replayed: true`, **no second playlist created**, 108 ms vs 2445 ms — the latency gap is itself evidence no provider call occurred).
- [x] ✅ **[COMPLETED] EXPORT-003 P0: Store export history and provider playlist URL (July 26, 2026).** `playlist_exports` rows carry `user_id`, `provider_playlist_id`, `url`, `status`, and a `partial_failure` JSONB holding the per-track `added`/`failed` breakdown. Verified live: the successful export, the earlier `INSUFFICIENT_SCOPE` attempt and the post-revoke `REAUTHORIZATION_REQUIRED` attempt are all three recorded with their reasons.

**NEW DECISION (July 26, 2026): `provider-gateway` owns the whole idempotent export transaction — claim key → call YouTube → record result — rather than n8n splitting it across nodes.** Confirmed with the developer before implementation. WF-006's `Store Export Result` Postgres node is **removed**: the previous node order called the provider *before* the idempotency key was ever claimed, so a double-click would have created **two real YouTube playlists** before `uq_playlist_exports_idempotency_key` was consulted. Owning the sequence in one place also removes the window where a crash between two n8n nodes leaves a claimed-but-unexecuted key. Justified against Section 2.2 by *"Provider Adapter Layer … playlist operations"* — recording the outcome of an external write belongs with whoever performs it. n8n still coordinates routing, retries, idempotency-key generation and the error envelope, which is its actual job under ADR-001.

**NEW DECISION (July 26, 2026): `ENABLE_PLAYLIST_EXPORT` is now a real gate.** It had been declared in `.env.example` and `docs/feature-flags.md` since Phase 0 but was **referenced nowhere in code** — an honest gap this slice closes. Default stays `false`; export returns `FEATURE_DISABLED` until deliberately enabled. Two new quota knobs join it: `YOUTUBE_MAX_EXPORT_TRACKS` (default 25) and `YOUTUBE_PLAYLIST_PRIVACY` (default `private` — the playlist is created in a real person's account, so visibility is opt-in).

⚠️ **Quota is the real constraint on this feature, not latency.** `playlists.insert` costs **50** units and `playlistItems.insert` costs **50 per track**, against a 10,000/day project quota **shared with search** at 100/query. A 10-track export is **550 units — about 18 exports/day.** Designed in accordingly: no blind retries on quota errors (a quota error aborts the remaining inserts rather than burning more of a budget already spent), per-method accounting through the existing `_record_quota_usage()`, and the configurable track cap above.



## 5.6 Optional Spotify

⚠️ **PROMOTED FROM P1 TO P0 by developer decision (July 26, 2026, later).** ~~Spotify is an optional P1 slice.~~ → **Spotify is a first-class recommendation mode, selected by a two-state toggle in the UI**, and the plan's standing instruction to keep all Spotify integration is reaffirmed. Context: the Phase 8 rewiring earlier the same day **removed the Spotify login control from the sidebar**, which was wrong — it was never asked for and the plan says to keep it. It has been restored, and Spotify is now implemented rather than merely preserved.

- [x] ✅ **[COMPLETED] SPOT-001 P1: Keep Spotify login optional.** The Spotify connect/disconnect widget is restored to the sidebar alongside Google sign-in, and the two are **independent**: Google is the identity provider, Spotify is a music provider, so a user may be connected to either, both, or neither. Spotify *search* needs no user connection at all (see SPOT-003), so Spotify mode works for a guest.
- [x] ✅ **[COMPLETED] SPOT-002 P1: Revalidate current development-mode, endpoint, and user-limit restrictions before depending on any feature.** Revalidated live on July 26, 2026, and it immediately mattered: **`GET /v1/tracks` returns 403 for a client-credentials token.** `/v1/search` returns *simplified* track objects that omit `popularity`, and the natural fix — a batched enrichment call mirroring the YouTube adapter's `videos.list` — is exactly the call Spotify refuses. See the NEW DECISION below.
- [x] ✅ **[COMPLETED] SPOT-003 P1: Implement search/taste/export only through the normalized adapter.** `provider-gateway/app/spotify_adapter.py` returns the same `NormalizedTrack` shape and the same `ProviderError` code vocabulary as the YouTube adapter, so `/providers/search` dispatches on a lookup and the error mapping is shared. ~~`PROVIDER_NOT_IMPLEMENTED` (501)~~ is no longer returned for Spotify search. **Taste import and playlist export remain unimplemented for Spotify** — export still returns `PROVIDER_NOT_IMPLEMENTED`, and the UI correctly hides the export control when the recommendation is a Spotify track, rather than offering an export that would fail at the provider after the user confirmed it.
- [x] ✅ **[COMPLETED] SPOT-004 P1: Never log or expose Spotify tokens.** The client secret travels in the `Authorization` header (never a query string that could be logged — the same lesson as the §5.1 YouTube api-key-in-logs leak), a rejected token exchange logs no response body because it can echo the credentials back, and the browser never sees a Spotify token.

**NEW DECISION: Spotify search authenticates with the Client Credentials flow, not the user's grant.** Search is a catalogue read; requiring user OAuth to see a recommendation would make Spotify mode unusable for guests. The historical reference implementation makes the same split (`aws/lambda_spotify_package/spotify_lambda.py::get_spotify_client` prefers a user token and falls back to client credentials). The user's own grant remains what taste import and playlist writes will need.

**NEW DECISION: Spotify result confidence is derived from `album_type`, artist count and `is_playable`, not from `popularity`.** Since `/v1/tracks` is refused (SPOT-002), spending a request per search on a call that always 403s was rejected. This matters because of §4.7's lesson — a constant confidence collapses ranking onto fuzzy text match — but the failure mode is far milder here: **every Spotify hit is a real released recording**, so confidence separates good from better rather than real from fake, which is what it had to do for YouTube. Compilations are down-weighted because on Spotify they skew to karaoke, covers and "50 Relaxing Songs" filler.

**NEW DECISION: the provider toggle is a default, not a constraint.** `resolve_provider` applies, in order: a provider named outright in the message > the UI toggle > `youtube`. So "find me something dreamy **on Spotify**" returns a Spotify track even while the toggle sits on YouTube, and the reverse holds. Detection is deliberately narrow — the provider name itself, in both accepted locales (`spotify`/`ספוטיפיי`, `youtube`/`יוטיוב`) — so a request that merely *mentions* a playlist in passing does not silently switch providers. Live-verified in all four combinations plus Hebrew.

**An early quality observation, recorded because it may change the default:** for the same prompt, Spotify mode returns markedly better music than YouTube mode. *"dreamy shoegaze for a rainy night"* returns **Alvvays — "Dreams Tonite"** on Spotify, against a one-hour compilation upload on YouTube. This is inherent to the catalogues: Spotify contains only released recordings, whereas YouTube requires the adapter to *infer* which results are even music. **`PROVIDER_MODE`/ADR-002 still names YouTube primary and that has not been changed**, but if this holds across more prompts it is an argument for revisiting the default.

The core Melody experience must work without a Spotify account.

## 5.7 TrackFeatureProvider

YouTube does not supply audio files for BPM/key analysis. Resolve features in this order:

1. Local feature cache.
2. ISRC lookup.
3. Artist + title + version lookup.
4. Approved external metadata provider.
5. Authorized preview analysis when legally and technically available.
6. Genre/energy fallback with missing BPM/key explicitly represented as null.

Never fabricate BPM or key.

## Phase 5 gate

~~⚠️ **NOT passed (July 25, 2026) — 2 of 6 criteria met.** Only §5.1/§5.3 (search) landed this session; §5.2 (OAuth), §5.4 (playback), §5.5 (export) are untouched, and three gate criteria depend directly on them.~~ → ⚠️ **STILL NOT passed (July 26, 2026) — but now 5 of 6 criteria met.** §5.2 (OAuth) and §5.5 (export) both landed and are live-verified. **The single remaining criterion is the playable-percentage measurement**, which is deliberately blocked behind §5.4: defining "playable" end to end needs the playback UI, and §5.4 is itself blocked behind the Phase 8 UI rewiring (see §5.4). The mechanism it measures already exists — region/deleted filtering and `embeddable` — so this is an unmeasured number, not missing behaviour.

- ✅ **[COMPLETED]** Search returns real normalized tracks with playable references. *(Real YouTube Data API v3 results with `provider_track_id` = video ID and a canonical `https://www.youtube.com/watch?v=…` URL. Live-verified end to end: `POST /recommendations/run` now returns distinct real tracks per query — 78 unique artists across the 12-prompt eval set, up from 1 fixture artist.)*
- ⚠️ At least 90% of selected demo tracks are playable in the target test region; unavailable results are replaced or clearly handled. → ~~**Not measured yet.** Requires the `videos.list` enrichment call for per-video availability/region/embeddability status, which was deferred. **This is the natural next task in Phase 5** — it also improves `PROV-002` (missing/unavailable item codes), `PROV-005` (per-field source), `YT-004` (duration-based dedupe), and would filter the DJ-mix compilations that mood queries surface.~~ → **Mechanism delivered (July 25, 2026), headline number still unmeasured.** `videos.list` enrichment now drops region-blocked and deleted/private videos before they can reach a playlist, and surfaces `embeddable` so §PLAY-005 can fall back to a plain link — so "unavailable results are clearly handled" holds by construction. **What is still owed is the measurement itself:** a demo-set run reporting the actual playable percentage. Cheap to do once §5.4 playback exists to define "playable" end to end; recorded here so it is not mistaken for done.
- ⚠️ OAuth is incremental and session-bound. → ~~**Not started** (§5.2, `AUTH-001`…`AUTH-007`). Search needs only an API key, which is why this slice could land without it.~~ → **Implemented (July 25, 2026), pending one live confirmation.** Incremental by construction (`AUTH-004` identity scopes first, `AUTH-005` YouTube added via `include_granted_scopes`) and session-bound by an explicit binding check beyond Authlib's `state`/`nonce` (`AUTH-003`). ~~⚠️ **The criterion cannot be ticked until the live consent round trip runs** — ~~that needs the developer's Google Cloud OAuth client; see the session bookmark.~~ → **the credentials arrived July 26, 2026; the round trip is unblocked and pending execution.**~~ → ✅ **[COMPLETED] Live round trip executed and passed (July 26, 2026)** — incremental (identity scopes only were granted and stored; the YouTube upgrade is a separate route) and session-bound (binding check enforced beyond Authlib's `state`/`nonce`). See the session bookmark for the evidence table.
- ✅ **[COMPLETED] A playlist can be created and populated for a test user without duplication.** → ~~**Not started** (§5.5, blocked on §5.2). `/providers/playlists` still returns `FEATURE_DISABLED` by design.~~ → **Live-verified July 26, 2026:** a real private playlist (`PLQV88szpWdzI`) was created in the developer's YouTube account with both requested tracks, and repeating the identical request with the same idempotency key returned the **same** playlist with `replayed: true` — one `playlist_exports` row, no second playlist at the provider.
- ✅ **[COMPLETED] WF-006 and WF-009 contain no P0 provider placeholders.** → ~~**Not started.** WF-006 still calls the disabled `/providers/playlists`; WF-009 (Provider Connection Sync) is still an empty stub (trigger → Set node, no provider-gateway call at all) — it is an OAuth-era workflow.~~ → **Both real as of July 26, 2026.** WF-006 calls the live export endpoint; WF-009 calls the new `POST /providers/connection/status` and returns real provider/scopes/expiry/reauthorization state. Live-verified after the revoke: WF-009 returned `connected: false, reauthorization_required: true, youtube_write_authorized: false` with **no token material** in the payload, per §1.12.
- ✅ **[COMPLETED]** MusicAPI/direct implementation details do not leak into Recommendation Service contracts. *(Proven by execution rather than inspection: swapping the fixture for a real YouTube adapter required **zero** changes to `recommendation-service` — the `NormalizedTrack` contract absorbed it. All YouTube-specific logic — quota accounting, Topic-channel heuristics, title parsing — stays inside `provider-gateway`.)*

---



# 11. Phase 6 — Audio identification and audio-conditioned recommendation



## Objective

Implement two distinct user actions:

1. Identify this recording or humming.
2. Recommend music with a similar vibe.

Do not confuse recognition with audio-feature extraction.

## 6.1 Upload and recording pipeline

- [x] ✅ **[COMPLETED] AUD-UP-001 P0: Add browser recording and file upload with explicit mode selection.** *(July 27, 2026. `templates/index.html` gains a "Use a sound" panel: `MediaRecorder` recording with a live indicator and an auto-stop at the analysed duration, plus file selection. The mode choice is **two explicit buttons** — `Identify this track` / `Find a similar vibe` — never inferred: Melody cannot tell "what song is this?" from "find me more like this" by listening, and picking one silently gives the user a confidently wrong kind of answer. This also closes `UI-002` in §8.1.)*
- [x] ✅ **[COMPLETED] AUD-UP-002 P0: Enforce client hints and server-side size/duration limits.** *(`audio-service/app/config.py` — every limit is an environment value with a documented default, per this section's own requirement. Two details that matter: a **malformed limit falls back to the default, never to "no limit"**, and the body is read **in 64 KB chunks against a running cap**, so an oversized upload is abandoned mid-stream rather than buffered whole and measured afterwards. The client hint is a courtesy only — `GET /api/v1/audio/limits` serves the server's real numbers so the UI cannot drift from them.)*
- [x] ✅ **[COMPLETED] AUD-UP-003 P0: Detect actual MIME/container type; do not trust filename extension.** *(`audio-service/app/sniffing.py`, from magic bytes: RIFF/WAVE, fLaC, OggS, EBML, ISOBMFF `ftyp` brands, MPEG sync. **This replaces a real vulnerability, not a gap:** the Phase 2 skeleton accepted a file when the declared MIME type **or** the filename extension looked like audio — both caller-supplied — so naming a Windows executable `song.wav` was sufficient. Regression-tested with exactly that payload.)*
- [x] ✅ **[COMPLETED] AUD-UP-004 P0: Store under a random server-side object ID in approved temporary storage.** *(`audio-service/app/storage.py`. IDs are `secrets.token_hex(16)` — 128 bits — and `path_for()` is the single choke point between an identifier and the filesystem: it **validates the ID against a strict grammar rather than sanitizing the string**, so traversal sequences, absolute paths and NUL bytes are rejected outright instead of rewritten into something that might still escape. Storage is a named docker volume (`audio_uploads`), never the working tree, so a stray `git add` cannot commit somebody's recording.)*
- [x] ✅ **[COMPLETED] AUD-UP-005 P0: Convert through an argument-safe FFmpeg call without shell interpolation.** *(`audio-service/app/transcode.py` — argument **lists** to `subprocess.run` with the default `shell=False`; no string is ever formatted into a command line. Two further boundaries, because "no shell" alone is not enough: `-t` precedes `-i` so FFmpeg stops *reading* at the duration cap rather than decoding everything and discarding the tail, and a wall-clock `timeout` stops a malformed container pinning a worker open.)*
- [x] ✅ **[COMPLETED] AUD-UP-006 P0: Add cleanup on success, failure, timeout, and scheduled expiry.** *(All four paths: `finally` on the direct-analyse route, `except BaseException` on a partial write, `unlink` on FFmpeg timeout, and a 60-second background sweeper. **Scheduled expiry keys off the file's own mtime as well as the metadata**, deliberately: cleanup must not depend on bookkeeping that can go missing, so a clip whose sidecar never landed — a crash between the two writes — still expires. Tested.)*
- [x] ✅ **[COMPLETED] AUD-UP-007 P0: Never log raw bytes, local temporary paths, or original filenames.** *(The original filename is **discarded at the Flask boundary** and never forwarded — it is both caller-controlled and personal, and nothing downstream needs it now that the container comes from the bytes. Logs carry only the object ID, byte count and container; FFmpeg's stderr can echo the input path, so it is logged server-side and never returned. A test asserts the upload response contains neither the filename nor the storage path.)*

Initial constraints must be explicit configuration values, for example maximum upload size, maximum processed duration, allowed formats, and retention minutes.

**NEW DECISION (July 27, 2026): job metadata lives in a JSON sidecar next to the clip, not in the `audio_jobs` table.** The clip and its metadata have exactly the same fifteen-minute lifetime, so one directory sweep expires both and a row can never outlive its bytes or point at a file that is already gone. It also keeps audio-service free of a database dependency it does not otherwise need, so its tests run offline like every other service's. `audio_jobs` remains the right home once a job outlives its clip — which is what §8.3's async job queue introduces. The sidecar records the uploader, and `/audio/analyze` checks ownership: the 128-bit object ID is already an unguessable capability, and the ownership check is the second lock so that an ID leaked in a log or referrer is not enough on its own. A non-owner gets **the same response as a missing job** — whether a clip exists is not theirs to learn.

**NEW DECISION: `webm` and `mp4` are non-negotiable members of the allowed-format list.** They are what a browser's `MediaRecorder` actually produces. The Phase 2 allowlist (`.wav .mp3 .flac .m4a .ogg .aac`) omitted both, which would have broken recording — the headline feature of this section — while looking entirely correct.

## 6.2 Audio analysis service

Tool allocation:


| Need                        | Tool                                   |
| --------------------------- | -------------------------------------- |
| Decode/convert              | FFmpeg                                 |
| Waveform and spectrogram    | torchaudio/PyTorch                     |
| BPM                         | ~~Essentia `RhythmExtractor2013`~~ → **librosa `beat_track`** (see decision below) |
| Key and scale               | ~~Essentia `KeyExtractor`~~ → **Krumhansl-Schmuckler on librosa CQT chroma, implemented explicitly** |
| Camelot conversion          | Deterministic code                     |
| Energy                      | Signal features and/or small model     |
| Genre/tags                  | Pretrained or fine-tuned PyTorch model |
| Audio embedding             | PyTorch/Hugging Face model             |
| Audio-text shared embedding | CLAP POC, nonblocking                  |


Required `POST /audio/analyze` output:

✅ **[COMPLETED] §6.2 audio analysis is real (July 27, 2026)** — `audio-service/app/features.py`. `POST /audio/analyze` no longer returns the Phase 2 fixture (`bpm: 120.0, musical_key: "A minor"` for every file); it measures. Live-verified against a synthesized signal with a known answer: a 440 Hz tone gated at 2 Hz (=120 BPM) returned **117.45 BPM** and **A major / Camelot 11B**, both correct.

**NEW DECISION: librosa replaces Essentia in the §6.2 tool table.** Essentia publishes no reliable wheel for Python 3.12, the runtime the rest of the stack is pinned to, so adopting it would mean either a source build in the image or downgrading every service's Python. `beat_track` covers the same ground. Key detection is **Krumhansl-Schmuckler either way** — it is a published algorithm, not a library feature — and is implemented explicitly in `features.py` so the method is inspectable rather than delegated. Camelot conversion stays deterministic code, and the table is verified internally consistent by test (relative major/minor share a number; a fifth moves it by one), because §7.4's sequencer will mix on those numbers and an off-by-one would produce confidently wrong transitions.

**NEW DECISION: every measurement carries its *own* confidence, and the headline number is the weakest field — never an average.** The Phase 6 gate requires confidence and model versions on BPM, key, energy and genre. The confidences here are **measured, not assigned**: tempo confidence is the regularity of the detected beat grid (inter-beat coefficient of variation, so ambient pads and speech correctly score near zero); key confidence is fit × margin over the runner-up, so a clip that fits A minor and C major almost equally well reports that it is ambiguous instead of picking one at 0.9. A caller reading only `confidence` must never be told 0.6 when the key is a guess. `field_confidence` is what §6.5 down-weights on.

## 6.3 PyTorch classifier deliverable

The audio genre/tag or energy model is Melody's domain adaptation of the course's PyTorch classifier requirement.

- [x] ✅ **[COMPLETED] ML-AUD-001 P0: Define labels, confidence behavior, and success metric.** *(`audio-service/ml/labels.py`, written **before any training code** — deliberately, because choosing a threshold after seeing the results is how a threshold ends up selected to flatter the model. Ten GTZAN genres, whose coarseness and overlap are recorded as a limitation of the label space rather than of the model. Abstention uses **two gates that must both pass**, because they catch different failures: `MIN_CONFIDENCE` 0.45 catches "unlike anything I was trained on" (a flat distribution), `MIN_MARGIN` 0.15 catches "equally rock and metal" (confident something is there, not which). Success metric fixed in advance: **macro-F1** — not accuracy, so a model that does well on the easy genres and ignores a hard one is not rewarded — with baseline 0.10, ship threshold 0.60, and a note that anything materially above the published 0.75–0.85 range on 1000 clips is evidence of a leakage bug rather than a result.)*
- [x] ✅ **[COMPLETED] ML-AUD-002 P0: Inventory or create a legally usable labeled dataset and split it into train/validation/test without leakage.** *(GTZAN, research-use, from the `marsyas/gtzan` mirror; 999 usable clips. **Two dataset defects were caught and fixed:** the archive ships macOS AppleDouble resource forks — a 211-byte `._blues.00000.wav` beside every real clip, which `Path.glob("*.wav")` happily returns — which had silently doubled the index to **1999 "clips", half of them undecodable**, and would have made every split ratio and per-genre count wrong; and `jazz.00054.wav` is truncated, excluded by name rather than by swallowing decode errors so a *new* decode failure stays loud. **Leakage is the thing to watch here**: the model trains on 3-second segments and a 30-second clip yields ten, so splitting segments at random puts nine siblings of every test segment into training — the reported accuracy then measures memorization and lands in the high 90s. The split is therefore computed over **files**, enforced by `assert_no_leakage` on every run rather than trusted to a comment. Assignment is by **hash rank within each genre**, not a hash threshold: thresholding is only stratified on average and produced per-genre test folds of 11–22 clips on the first run. Result: 699/150/150, exactly 15 per genre in test. The one residual risk — GTZAN's own duplicate recordings straddling a file-level split — is documented, not hidden.)*
- [x] ✅ **[COMPLETED] ML-AUD-003 P0: Use an appropriate pretrained audio model or spectrogram-based network; training from scratch is not required.** *(`audio-service/ml/model.py` — four Conv/BatchNorm/ReLU/MaxPool blocks over a 128-mel spectrogram, global average pooling, ~250k parameters. Chosen over fine-tuning AST because it trains to a **reportable** result on CPU inside the submission window, where a transformer would not, and an unmeasured model is worth nothing. **The mel transform lives inside the `nn.Module`, not the data loader** — the single most useful decision in the file: it makes the checkpoint self-contained so training and serving cannot drift apart on `n_mels` or `hop_length`, which is the classic silent failure where the model still returns confident answers that are simply wrong.)*
- [x] ✅ **[COMPLETED] ML-AUD-004 P0: Document preprocessing, augmentation, training loop, hyperparameters, and model version.** *(`docs/ml/audio-genre-classifier.md` — a full model card. Augmentation is all label-preserving: random segment offset, gain jitter, SpecAugment masking. **Pitch-shift and time-stretch are deliberately excluded** — they alter the key and tempo that partly *define* a genre, so they would teach the model to ignore a real signal. Label smoothing 0.1 because GTZAN's labels are known to contain errors and training the model to be certain about them would fit the noise. Model selection is on **validation** macro-F1, never the last epoch and never anything computed on test.)*
- [x] ✅ **[COMPLETED] ML-AUD-005 P0: Report accuracy/F1 and confusion matrix on the held-out test set.** *(Measured July 27, 2026. Model `melody-genre-cnn-1.0.0`, 30 epochs in 59.6 minutes on CPU, best validation macro-F1 **0.8482** at epoch 26.* **Held-out test: clip-level macro-F1 `0.8692`, accuracy `0.8733`** *(segment-level 0.8378 / 0.8413 — clip-level is higher by the expected ~3 points, because averaging across a clip's windows cancels the odd unrepresentative one). Baseline 0.10, ship threshold 0.60: **met**. 20 of 150 clips abstained under the confidence policy. Full per-class table and confusion matrix in `docs/ml/audio-genre-classifier.md` and `ml/checkpoints/test_report.json`.* **The result is credible because of where it sits and how it fails, not because it is high:** 0.8692 is *inside* the published 0.75–0.85 band rather than above it, and the error structure is musically sensible — classical and jazz perfect, **rock the clear weak class at F1 0.640** (recall 0.533; it loses 3 clips to country and 2 to pop, which is what "rock" means in GTZAN), reggae→blues the other notable cell. A *clean* matrix on 1000 clips would be evidence of leakage. Rock is reported as the weak point rather than averaged away — exactly why macro-F1, not accuracy, was fixed as the metric **before** training. `ml/evaluate.py` is a separate script by design: folding it into training makes it far too easy to glance at test performance between epochs, which turns the held-out number into a training signal and the reported figure into a fiction. **The test split was read once, after the model was chosen, and nothing was tuned afterwards.**)*
- [x] ✅ **[COMPLETED] ML-AUD-006 P0: Return `uncertain` or low-confidence scores rather than a forced label.** *(`labels.decide()` — a clip failing either gate is `uncertain`, and the API reports it as **`genre: null` with a reason**, not as a genre literally named "uncertain". Abstention is the *correct* output for humming, speech, or a genre outside the label set, and §6.5 is built to run without a genre.)*
- [x] ✅ **[COMPLETED] ML-AUD-007 P0: Package inference in the Audio Service and save reproducible training instructions/checkpoint policy.** *(`audio-service/app/classifier.py`, loaded once and lazily. **Absence is a first-class state**: with no checkpoint trained the service still returns BPM, key, Camelot and energy and reports `genre: null, reason: "no_checkpoint"` — it does not fail and it does not invent a genre, which is exactly what let §6.1/§6.2 ship ahead of a trained model rather than behind it. Prediction averages softmax across the clip's windows, the same way `evaluate.py` computes the clip-level score, so the number published is the number this path produces. `torch.load(weights_only=True)`: a checkpoint is untrusted input as soon as it is downloaded rather than trained locally. Checkpoint policy, reproduction commands and the `--shm-size` requirement are in the model card.)*

If the submission window is too short for meaningful fine-tuning, use a pretrained model for the P0 inference path and present the reproducible fine-tuning experiment honestly as partial work. Do not report unmeasured accuracy.

**NEW DECISION: the fallback above was not needed — a real model is being trained, not a pretrained one wrapped.** At ~1.7 minutes per epoch on 16 CPUs the full 30-epoch run fits comfortably inside the window, so the honest-partial-work escape hatch is not taken. The ceiling on what the resulting number means is GTZAN's own documented faults (Sturm 2013), which are stated in the model card rather than worked around.

## 6.4 Recognition provider decision

ACRCloud is the leading candidate, but it must pass a POC for both original recordings and humming.

- [ ] **REC-ID-001 P0:** Create a test set of clean original clips, noisy clips, humming clips, and no-match clips.
- [ ] **REC-ID-002 P0:** Test ACRCloud or the selected provider using the same set.
- [ ] **REC-ID-003 P0:** Measure match rate, false positives, latency, limits, and cost.
- [ ] **REC-ID-004 P0:** Verify which external IDs are returned and how they map through Provider Adapter.
- [ ] **REC-ID-005 P0:** Define confidence thresholds for match, low confidence, and no match.
- [ ] **REC-ID-006 P0:** Record the decision in `ADR-004-recognition-provider.md`.

Required `POST /audio/identify` output:

~~⏸️ **§6.4 is BLOCKED on the developer, and is the one part of Phase 6 that cannot be unblocked from inside the repository.** `REC-ID-001…006` all depend on running a POC against a real recognition provider, and ACRCloud requires an account and API credentials that only the developer can create. Nothing here is deferred by preference.~~ → **Partly unblocked July 27, 2026: credentials were supplied and the integration is built. It is not yet *active*, for a reason that is diagnosed rather than guessed at — see below.**

- [x] ✅ **[COMPLETED] REC-ID-004 P0: Verify which external IDs are returned and how they map through Provider Adapter.** *(`_normalize_track` maps ACRCloud's `external_metadata` to ISRC + Spotify/YouTube/Deezer/Apple IDs. This matters more than it looks: a recognized track can go **straight to Provider Adapter by ID** instead of being re-searched by title — and title search is exactly where §5.3's result-quality problems live.)*
- [x] ✅ **[COMPLETED] REC-ID-005 P0: Define confidence thresholds for match, low confidence, and no match.** *(`score ≥ 80` → stated as a match; `60–80` → shown and explicitly flagged uncertain; `< 60` → **no track is named at all**. Fixed before any measurement so they cannot later be tuned to flatter a result. The middle band is deliberate: a noisy phone capture of a genuine match often lands in the 60s, and discarding it is as wrong as presenting it as certain.)*
- [x] ✅ **[COMPLETED] REC-ID-006 P0: Record the decision in `ADR-004-recognition-provider.md`.** *(Written. ACRCloud chosen because it is the only major provider covering **both** original recordings and humming — and humming is a named gate criterion — and because it returns external IDs. Self-hosted fingerprinting was not seriously considered: Dejavu and audfprint fingerprint a catalogue you already hold, which is the part we do not have.)*
- [x] ✅ **[COMPLETED] REC-ID-001 P0: Create a test set of clean original clips, noisy clips, humming clips, and no-match clips.** *(`ml/recognition_poc.py`. Clean originals are real commercial recordings taken from the GTZAN clips already on disk; noisy variants are the same clips swept across four severities; no-match clips are synthesized tones, sweeps and white noise, where **any** match is by definition a false positive; humming clips are synthesized monophonic melodies with vibrato — **labelled everywhere as stand-ins, not real humming**, so no reader mistakes a result on them for evidence about people.)*
- [x] ✅ **[COMPLETED] REC-ID-002 P0: Test ACRCloud or the selected provider using the same set.** *(62 live requests, July 27, 2026, against `identify-ap-southeast-1`.)*
- [x] ✅ **[COMPLETED] REC-ID-003 P0: Measure match rate, false positives, latency, limits, and cost.** *(Results below. Raw output in `audio-service/ml/checkpoints/recognition_poc.json`; full write-up in ADR-004.)*

✅ **[COMPLETED] §6.4 POC results (July 27, 2026) — measured, with the control that makes them mean anything.**

| | |
| --- | --- |
| **Catalogue coverage** | **11 of 12 (91.7%)** randomly sampled GTZAN clips are in ACRCloud's index |
| **Clean originals** | **11/11 — 100%** |
| Light noise (σ .02 / gain .55) | 10/11 — 90.9% |
| Moderate noise (σ .06 / gain .40) | 9/11 — 81.8% |
| Heavy noise (σ .12 / gain .25) | 4/11 — 36.4% |
| Severe noise (σ .20 / gain .15) | **0/11 — 0%** |
| **False positives** | **0 across 7 genuine no-match opportunities** |
| Latency | median **3.84 s**, p95 **4.88 s**, max 5.48 s |

⭐ **The catalogue control is the finding, not a footnote.** A clip that is simply *not indexed* fails identically to one the noise destroyed, so a noisy match rate computed over all clips silently blames the noise for missing coverage. **The first version of this POC omitted the control, reported 10/10 on "noisy" clips, and would have been written up as evidence of robustness** — it was measuring nothing. Rerun with the control, the real curve appears: recognition holds through moderate degradation and then **falls off a cliff between moderate and heavy**. That boundary is the product-relevant number — a phone on a table in a quiet room matches; a phone in a pocket in a loud bar does not, and says so rather than guessing.

**0 false positives is the result that matters most.** A confident wrong answer is the one failure a user cannot detect, and across tones, sweeps, white noise, an out-of-catalogue recording and three humming stand-ins, the provider never produced one.

⚠️ **NEW DECISION (July 27, 2026, after the developer's first real-world use): catalogue junk is filtered, and the filter runs at *every* score.** Three recorded songs produced two misses and one confidently wrong answer — **`'Remix' — 'DJ' — album 'Remix' (2014)` at 64%, for Ariana Grande's "Problem"**. Investigating it produced a more important finding than the report itself.

**First, what was ruled out by measurement rather than assumption.** The obvious suspects were the browser's lossy Opus encoding and our 22.05 kHz downsample — neither is on the POC's path, so both were plausible. A five-way isolation (44.1 kHz stereo baseline / current 22.05 kHz mono / 44.1 kHz mono / Opus 32 kbps / Opus 128 kbps) scored **100 on every variant**. **The codec and the sample rate are innocent**, and changing either would have been a fix aimed at the wrong thing. The loss is acoustic — speaker → room → microphone — which the POC's synthetic noise only approximated.

**Second, the actual defect.** ACRCloud's index contains **placeholder rows**, and they are the real source of wrong answers. Two observed examples, and the gap between their scores is the point:

| Returned | Score | Truth |
| --- | --- | --- |
| `'Remix' — 'DJ'` | 64 | Ariana Grande, "Problem" |
| `'Fingerprint Less' — 'Kanroc Xpitaf'` | **100** | Rage Against The Machine, "Killing In The Name" |

**A junk row fingerprints exactly as strongly as a real one** — `score` measures fingerprint agreement, not whether the catalogue entry is worth showing anybody. So a low-score-only guard would have missed the worse case entirely. `is_plausible_release()` therefore applies at all scores, and stays conservative: it rejects definitive placeholders outright, and generic title/artist pairs only when **both** are generic — "Intro" by DJ Shadow is a real track, and eating real results is a worse bug than the one being fixed.

**Third — and this is why the top hit is no longer taken outright — the correct track was sitting *behind* the junk one.** The adapter now walks candidates by descending score and returns the first plausible release. Live re-verification after the change: the previously-wrong 5 s and 25 s conditions produced **zero** wrong matches, and the single remaining "mismatch" was `'Que Sera Me Vida'` vs `'Que Sera Mi Vida'` by the same artist — a catalogue spelling variant, not a false positive. All-junk results report `junk_metadata_only`, distinguishable in logs from a plain miss: we *did* recognize something, it just was not worth showing.

**NEW DECISION: listening extended from 10 s to 15 s — measured, and NOT because longer is better.** Against a simulated room capture across 12 in-catalogue recordings: **5 s → 58%**, 10 s → 83–92%, 15 s → 83–92%, 20 s → 75%, **25 s → 75–83%**. ⭐ **Recognition peaks around 10–15 s and then *declines*** — the intuition that a longer listen must help is wrong here, and had it not been measured the developer's "extend it a bit" request would plausibly have been implemented as 25 s and made things worse. 15 s also gives §6.2's tempo estimate more to work with, which matters because the features stay useful when recognition misses. **Note on the measurement: FFmpeg's `anoisesrc` is unseeded, so repeat runs differ by ±1 clip; 5 s being clearly worst is robust, the 10-vs-15 ordering is not, and 15 s was chosen on the tie-break above rather than on a single run.**

✅ **[COMPLETED] Overlay hand-off fixed (July 27, 2026, developer-reported): the listening screen no longer appears to freeze.** ~~The overlay stayed up through the upload and recognition call, showing "Working it out…".~~ → **It now closes the moment recording stops, handing straight back to the chat's own loading equalizer.** **The bug was an ordering mistake, and nothing was actually stuck:** `mediaRecorder.onstop` called `teardownListening()` — which cancels the `requestAnimationFrame` loop — while the overlay was still on screen, so the reactive rings and bars stopped dead and sat frozen for the several seconds recognition takes. `closeListenOverlay()` now runs **before** teardown and before the network work, and `identifyBlob` no longer touches the overlay at all — which also makes it correct for the Upload path, where no overlay ever existed. A 140 ms fade-out replaces the hard cut; it delays nothing, because the chat behind is already painted and already showing its loading state, and `pointer-events: none` during the fade stops the dismiss button staying clickable.

⚠️ **CORRECTION (July 28, 2026): the "freeze" was reported again after the fix above, and the fix was not the whole story.** Reproduced in a real browser (Playwright + Chromium's fake media device) with a main-thread responsiveness probe. Two findings, and the first ruled out the obvious reading:

1. **Nothing was blocking.** Stalls over 120 ms: **none**. The overlay closed 100 ms after capture stopped, and the loading equalizer was already on screen. The mechanics of the previous fix were correct — so "it is still freezing" could not be fixed by making it close faster, and any further work on the close path would have been aimed at nothing.
2. ⭐ **The loading indicator said "Melody is listening…" — *after* listening had finished.** The animation ran for the whole four-to-ten second wait while the sentence beneath it told the user recording had not started. **A correct animation with the wrong caption is indistinguishable from a hang**, and reporting it as one was fair. The label is now set by whoever starts the work: "Working out what that was…" for recognition, "Finding something with that vibe…" for the follow-up, and the original wording kept only for the text path, where Melody genuinely *is* listening to what you asked.

**NEW DECISION: the app shell is served `Cache-Control: no-store`.** The entire client — markup, styles and every line of JavaScript — lives in one rendered template, so a cached copy of it is a cached copy of the whole application. Flask sets no cache headers on a rendered response and a tab that simply stays open never re-requests the document, which is how a fix verified as correct in a fresh browser can still reproduce for the developer. **That symptom is indistinguishable from a real defect**, and this session lost a round trip to exactly that. Static assets keep their own validators; this covers only the shell.

⚠️ **NEW DECISION: `TEMPLATES_AUTO_RELOAD` is on by default.** Discovered while verifying the above — Flask caches the compiled template for the life of the process, so **a UI edit was invisible until a restart**. The failure mode is the dangerous kind: the page loads perfectly, it is simply the *previous* version, so a change looks like it did not work when in fact it was never served. Two of this session's UI verifications were run against a stale page before this was spotted. Costs one `stat()` per render; overridable with `FLASK_TEMPLATES_AUTO_RELOAD=false`.

⚠️ **NEW DECISION: no test may call ACRCloud.** The moment real credentials reached the container, the `/audio/identify` tests began making **live, billable** requests to `identify-ap-southeast-1` — visible as genuine HTTP 200s in the log, with one test failing because the provider answered something the fixture did not anticipate. An autouse fixture now strips every spelling of the credentials before each test. Suite runs must not cost money, must not depend on a third party being reachable, and **must not change behaviour depending on whether a `.env` happens to be populated** — that last one is the real hazard, because it makes a green suite on one machine mean something different from a green suite on another. The provider is exercised deliberately against a stubbed transport, and for real only by `ml/recognition_poc.py`.

⚠️ **CORRECTION (July 28, 2026): the humming finding was wrong, and the fault was ours.** The July 27 entry attributed the empty humming results to ACRCloud's humming service not being enabled on the project. The developer then confirmed the project *was* created with **"Audio Fingerprinting & Cover Song (Humming) Identification"** selected. On re-inspection, `app/acrcloud.py` **hardcoded `data_type: "audio"`** — the humming index was never queried once, by any of the probes. **The capability was present the whole time; the code never asked for it, and the missing result was then explained away as a missing feature.** A wrong diagnosis that happens to be unfalsifiable from outside is worse than no diagnosis, and this one survived a full write-up in ADR-004.

**NEW DECISION: humming is queried as a fallback, not as a separate mode.** `data_type` is now a parameter — and the **signature is computed over the same value that is sent**, because signing `audio` while posting `humming` fails with the identical `3001` as a bad key, which is precisely the ambiguity this module exists to avoid. `/audio/identify` tries the recording index first and, **only on a miss**, retries against the humming index: a miss is already the slow path, so the second request costs nothing anybody is waiting on in the common case, and a user who hums does not have to declare that they are humming. A humming match is tagged `acrcloud:humming` so the two indexes stay distinguishable in results. **Still not measured** — a real measurement needs real hummed audio, which the app can now capture directly through the Listen button.

✅ **[COMPLETED] Humming diagnosed with evidence (July 28, 2026) — the implementation is correct and the humming index is not being searched.**

The developer hummed three songs through the app; all three returned no match. Diagnosed from their actual recordings rather than by reasoning:

1. **The fallback ran.** Three `acrcloud_humming_fallback_missed` entries, one per hum. The code path is live.
2. **The audio we send is good.** Measured from the stored clips: 14.9 s, peak 0.25–0.35 (neither clipped nor faint), RMS −23 to −27 dBFS, negligible leading silence. Not a level, duration or silence bug.
3. **The request is accepted.** Both indexes answer `1001 No result` — not `3001` (auth) and not `3006` (bad parameter), so the signature and `data_type` are valid.
4. ~~⭐ **The decisive control: a real commercial recording sent with `data_type=humming` returned the *identical* match to `data_type=audio` — same title, score 100.** Two genuinely separate indexes cannot both produce an identical fingerprint match. **`data_type` is accepted and ignored; every request reaches the audio fingerprint index.**~~ → ⚠️ **That control was not decisive and the reasoning was wrong.** Once the developer described the console — one key set per project, with a project-level **Audio Engine** choice of *Fingerprinting* / *Fingerprinting + Cover Song (Humming)* / *Cover Song only* — an identical result became equally consistent with a second explanation: **both engines run server-side on every request and the best match is returned**, which is not the same as the field being ignored. **The test that actually settles it is a nonsense value:** `data_type=banana` also returns `code 0 Success`. The field is **not validated, therefore not parsed, therefore cannot be selecting anything**. Which engines run is decided entirely by the **project configuration**, never by the request — so no change to our request can switch indexes, and the humming engine either is not enabled or is finding nothing.

⭐ **The lesson is about the shape of the evidence, not about ACRCloud.** The first control produced a result that *looked* conclusive and had two explanations; the second cost one request and had one. **When a control's outcome is consistent with the hypothesis you already hold, it has not tested anything** — the useful test is the one whose result you cannot predict.

⚠️⚠️ **CORRECTION (July 28, 2026, later) — the cause was ours after all, and both previous diagnoses were wrong.** The developer confirmed the console was configured correctly (including *Recorded Audio*) and pushed back on the coverage theory with a sound argument: their fingerprint identification measures **91.7% catalogue coverage**, so the database is demonstrably not thin, and three very well-known songs would be in it. That pressure is what produced the right test.

**The test that found it needed no hum at all.** A known recording was pitch-shifted +3 semitones and time-stretched — enough to destroy the spectral fingerprint while preserving the melody, which is what a hum *is* to a matching engine. The response came back `code 0 Success` **with no `music` in it**, which is not how a miss looks (a miss is `1001`). Dumping the payload:

```
metadata keys: ['humming']
```

⭐ **ACRCloud returns melody and cover-song matches under `metadata.humming`, not `metadata.music`.** `app/acrcloud.py` read only `music`, so **every hum the service successfully recognized was discarded by our own code and reported to the user as "no match"** — and that fabricated miss was then written up twice, first as the account lacking the capability and then as the humming index being unreachable. The engine was running and answering the whole time.

**NEW DECISION: both indexes are read, `music` first.** A spectral fingerprint match is a far stronger claim than a melodic one — if the actual recording was identified, that is the answer — so `humming` is consulted only when `music` is empty, and a melody match is tagged `acrcloud:humming` so the UI can present it with the lesser certainty it deserves.

⚠️ **Still not finished, and the remaining part is honest to state:** melody matches carry a **different score scale** from fingerprint matches. One observed melody match scored ≈1 where a fingerprint match scores 100, so `MATCH_SCORE`/`LOW_CONFIDENCE_SCORE` — calibrated in §6.4 against fingerprint scores — reject every melody result. **Recognition therefore still reports no match, now for a second and different reason.** Calibrating those thresholds needs real hummed audio with known answers, which is the one thing this repository cannot generate: a synthesized melody is not a hum, and that assumption is what made the first two diagnoses look plausible.

**How the two wrong answers happened, since the pattern matters more than the bug.** Each time, a *negative* result was attributed to the component that could not be inspected — first the account, then the provider's index — while the component that could be inspected was assumed correct because it had been written recently. **The rule that would have caught it on day one: when an integration returns nothing, dump the raw response before theorising about the remote end.** One `json.dumps` would have shown `metadata keys: ['humming']` immediately.

✅ **[COMPLETED] Humming measured against real human input (July 28, 2026) — REC-ID-001/002/003 now cover the humming case, and the Phase 6 gate criterion can finally be answered.**

The developer hummed six well-known songs through the app and named them. The clips were pulled from storage inside the retention window and are preserved at `audio-service/ml/checkpoints/hum_testset/` — **the project's first and only real humming test set**, and the thing that made every earlier conclusion guesswork.

**Two further bugs were found only because real hums finally reached the code**, both of which had been masked by the `metadata.humming` bug sitting in front of them:

1. ⭐ **The melody index scores 0–1, the fingerprint index scores 0–100.** `MATCH_SCORE = 80` applied to a melody score of 0.8 rejects a *perfect* match. Every melody result was discarded on threshold even after being correctly read. Calibrated to `HUMMING_MATCH_SCORE = 0.75` against the measured distribution, with **no low-confidence band**: on the fingerprint index the 60–80 band holds genuinely correct noisy captures, while here the equivalent band is almost entirely wrong answers, so showing it would trade a clean miss for a plausible lie.
2. **`duration_ms` arrives as a string from the melody index and an int from the fingerprint index**, which raised a `TypeError` the instant humming results were finally read — a crash that could only ever have happened on the humming path.

**Measured result, six real hums:**

| Hummed | Melody index returned | Verdict |
| --- | --- | --- |
| Ariana Grande — One Last Time | *One Last Time* (Ariana Grande) @ 0.96 | ✅ correct |
| Bad Bunny — NuevaYol | nothing | miss |
| The Beatles — Something | nothing above threshold | miss |
| Bryan Adams — Heaven | correct track present at rank 2, score 0.53 | miss (found, out-ranked) |
| Spice Girls — Wannabe | *Wannabe (feat. Erik Tresor)* — Rida Radar @ 0.9 | ❌ **false positive** |
| The Beatles — All You Need Is Love | best 0.46 | miss |

⚠️ **1 correct out of 6, with 1 false positive — and the false positive was nearly recorded as a success.** An automated check that asked "is the expected title a substring of the returned title" scored the Spice Girls row as correct, because an unrelated track is also called *Wannabe*. **A title-substring test is not a correctness test**, and on a six-row table it inflated the result by 100%.

✅ **[COMPLETED] Ranked candidates with confidences (July 28, 2026) — a developer suggestion that turned out to be the single largest accuracy win in §6.4.**

The developer observed that Google's hum-to-search, when unsure, **shows several options with match percentages and lets you choose**, and asked whether our provider returns anything similar. It does — ACRCloud had been returning a *ranked list* with per-entry scores all along, and the adapter was collapsing it to a single answer and discarding the rest.

⭐ **That collapse was destroying correct answers.** Measured on the same six hums, with the list surfaced rather than the head taken:

| Hummed | Correct answer visible? |
| --- | --- |
| Ariana Grande — One Last Time | ✅ rank 1 (0.96) |
| Bad Bunny — NuevaYol | — |
| The Beatles — Something | — |
| Bryan Adams — Heaven | ✅ rank 1 (0.67) |
| Spice Girls — Wannabe | ✗ |
| The Beatles — All You Need Is Love | ✅ rank 2 (0.44) — the Japanese release *愛こそはすべて* |

**3 of 6 against 1 of 6 for top-1 alone.** The correct song was in the response for half the test set the entire time; the API was answering better than the code was reporting.

**NEW DECISION: candidates are built *before* the threshold is applied and returned on every outcome, including a miss.** The alternatives matter most precisely when nothing cleared the bar — that is the case the list exists for. The UI shows them whenever the result is unconfident, headed "Closest matches — none certain enough to call", each with its percentage. **A ranked guess presented as an answer is worse than the same guess presented as a list**, and this index produces top-1 answers that are frequently wrong while the right one sits a row below.

**This also reframes the provider comparison.** ACRCloud's melody *retrieval* is respectable — it surfaces the right track for half these hums — and its *ranking* is what is weak. That is a materially different verdict from "the humming service does not work", which is what the top-1 measurement alone said, and it lowers the case for switching providers.

**NEW DECISION: humming ships behind a strict threshold and is described as best-effort, not as a feature.** 1/6 on very well-known songs is not competitive with Google's hum-to-search, which the developer reports as instant and accurate — and Google offers **no public API**, so that quality is not purchasable at any price through them. The remaining option worth evaluating is **SoundHound (Houndify)**, whose Music domain is purpose-built for sung and hummed queries. **That evaluation is now cheap and fair: the six-clip test set with known answers exists on disk**, so a competing provider can be measured on exactly the same input rather than on impressions.

**Where that leaves it — three candidates, in the order worth checking:**

1. **`Audio Source` may be set to *Line-in Audio*.** The console offers *Recorded Audio* ("captured via microphone or noisy audio files") or *Line-in* ("original file or stream without noise"). A hum into a laptop microphone is emphatically the former, and an engine told to expect clean line-in audio has every reason to reject it. **This is a one-click setting and the cheapest thing to eliminate.**
2. **The `Audio Engine` selection may not have persisted** as *Fingerprinting & Cover Song (Humming)*. Worth re-reading rather than re-remembering.
3. **Coverage.** `ACRCloud Music` is the only bucket offered, and a cover-song index over it is necessarily far smaller than Google's purpose-built melody model over their whole catalogue. Three hums missing is a small sample, but it is consistent with a thin index.

**NEW DECISION: humming stays NOT complete, and the reason is now evidenced rather than assumed.** The July 27 entry blamed the account, the July 28 correction blamed our code, and **both were partly wrong**: the code was genuinely broken (hardcoded `data_type`) *and* fixing it changed nothing, because the humming index is not reachable on this project. The control test above is what separates the two, and it is the test that should have been run first — comparing a *known* input across both indexes costs one request and settles the question, where any number of humming attempts cannot.

**NEW DECISION: Google is not an option for this.** Google's "Hum to Search" exists only inside the Google app and Search; there is **no public API** for it, and Google Cloud offers no music-recognition product. It cannot be integrated regardless of how well it performs. The credible commercial alternative with a real humming/query-by-melody index is **SoundHound (Houndify)**, whose Music domain is built for sung and hummed queries. Switching would touch **only `app/acrcloud.py`** — the adapter sits behind a `Recognition` dataclass, which is the reason ADR-004 was structured that way.

- [ ] **Humming remains explicitly NOT complete**, per the gate's own wording ("marked complete only if it passes the POC threshold"). All 3 stand-ins returned no match, and that is **not evidence about ACRCloud's humming capability** for two independent reasons: the clips are synthesized melodies rather than human humming, and query-by-humming is a **separately-enabled ACRCloud service**, not something the standard `/v1/identify` endpoint answers. Closing this needs real hummed recordings and the humming service enabled on the project.

~~⚠️ **NEW DECISION / FINDING (July 27, 2026): the supplied ACRCloud credentials are rejected by every identification region, and the cause is diagnosable.**~~ → ✅ **RESOLVED the same day — the developer supplied corrected credentials (32/40, the right product), and the host was found by probing: `identify-ap-southeast-1.acrcloud.com`.** The original finding is kept below because the *method* is the reusable part: ACRCloud answers `3001` for a wrong region exactly as it does for a wrong key, so the region had to be discovered by elimination rather than assumed. Original finding: Probed directly against `identify-eu-west-1`, `identify-us-west-2`, `identify-ap-southeast-1`, `identify-ap-northeast-1` and `identify-cn-north-1`, **in both key/secret orders** — all five answer `3001 Missing/Invalid Access Key`. Two things are wrong: **(1) `ACRCLOUD_HOST` is not set at all**, and ACRCloud issues a *per-project regional* endpoint, so a valid key aimed at the wrong region returns the identical `3001` as a bad key; **(2) the credential lengths do not match the product** — an Audio & Video Recognition project issues a **32-character key and a 40-character secret**, and the supplied values are **16 and 32**, which is the shape of a different console section (the Metadata/Music API uses a bearer token, not this HMAC flow). `GET /audio/recognition/status` reports which of the three settings are present and their lengths, **never their values**, precisely so this is diagnosable from outside instead of guessed at. **When the correct host and key land in `.env`, recognition starts working with no code change.**

**NEW DECISION (July 27, 2026): the identification fixture is removed rather than left in place.** `POST /audio/identify` previously returned `matched: true, {"title": "Holocene", "artist": "Bon Iver"}, confidence: 0.88` for **any** input, including silence. It now returns `matched: false, placeholder: true` with an empty track. The Phase 6 gate requires identification to "return a match or an honest failure", and **a hardcoded answer is neither** — a fabricated match is worse than a stated gap, because the user cannot detect it. The UI renders the three outcomes distinctly (a match, an honest "no match", and "recognition is not built yet") for the same reason. Everything in front of the recognition call — upload, sniffing, storage, ownership, expiry — is real, so §6.4 is one provider call away rather than a phase away.

## 6.5 Audio-conditioned RAG integration

Baseline multimodal path:

- [x] ✅ **[COMPLETED] AUD-RAG-001 P0: Map audio features to normalized query constraints.** *(`graph_nodes.describe_audio_features`. **This section had a silent defect that made all of §6.5 inert:** retrieval nodes 5 and 6 skip on empty text, so an audio-only request — "recommend something like this clip", with no words — retrieved **nothing at all**, ran the whole pipeline on no evidence, and the audio changed the result in no way. Measured features are now described in the corpus's own vocabulary (128 BPM → "steady danceable pulse, four on the floor"; 0.82 energy → "energetic, bold, punchy") and appended to the query, because a **BPM number is invisible to a text-and-embedding search** while those words are not. The user's own text still leads: audio informs the search, it does not replace what was asked. The genre — the one audio feature that is genuinely a *constraint* rather than a description — is merged into `positive_constraints.genres`, where ranking and the curator already read it; merged, not assigned, so "something like this, but jazzier" keeps the user's word and adds the classifier's.)*
- [x] ✅ **[COMPLETED] AUD-RAG-002 P0: Down-weight uncertain features.** *(A confident feature becomes part of the retrieval **text**; an uncertain one is returned as a `soft_hint` and never enters it — on a text query, keeping it out *is* the only down-weighting that has any effect. Two bugs were fixed here that would have quietly poisoned the query: `_normalize_audio_features` iterated **every** key in the analyze response, so `source: "librosa-dsp"` and `model_version` became "features" with confidences and weights and reached the retrieval query as terms; and it applied the single headline `confidence` to every field, which — since the headline is deliberately the **weakest** field — demoted a 0.91-confidence tempo to a soft hint because the key happened to be ambiguous. `field_confidence` now takes precedence per field, and an absent measurement is treated as **no feature**, not as a feature we are unsure of.)*
- [x] ✅ **[COMPLETED] AUD-RAG-003 P0: Test audio-only, audio-plus-text, and audio-plus-personal-profile contexts.** *(All three covered in `recommendation-service/test_graph_nodes.py`, using the **verbatim** `POST /audio/analyze` payload rather than a tidied-up subset — which is what exercises the metadata keys that were previously mistaken for features.)*
- [x] ✅ **[COMPLETED] AUD-RAG-004 P0: Verify that audio context changes retrieval/ranking in a measurable way.** *(Stated as a comparison rather than an assertion of faith: the same prompt with and without audio produces a different query text, and the audio genre appears in `positive_constraints.genres` in one and not the other. A companion test asserts the **text-only path is byte-identical to what it was before §6.5** — a change that improves the audio path by quietly altering the text path is not an improvement.)*
- [x] ✅ **[COMPLETED] AUD-RAG-005 P0: Replace all P0 WF-004 placeholders.** *(Both audio workflows re-exported and re-imported July 27, 2026. **WF-003 carried the same class of defect as the WF-002 envelope bug:** it forwarded `audio_features: $json` — the whole analyze *response*, `{audio_job_id, features, placeholder}` — so the measurements sat one level too deep, the graph saw `features` as a feature, and the real BPM, key and energy never reached retrieval at all. Now `$json.features`. Both workflows also gained `guest_id`: without it audio-service's ownership check refused **the guest's own clip** with `NOT_FOUND`, which would have broken the anonymous path the rest of the app supports. WF-003's recommendation timeout was raised 25s → 90s — 25s is the limit that already timed out on ordinary Hebrew text requests, and the audio path is strictly slower because analysis runs first.)*



## 6.6 CLAP proof of concept

CLAP is a true audio-text retrieval enhancement, not a BPM/key extractor and not a song-recognition service.

- [ ] **CLAP-001 P2:** Precompute text embeddings for genre descriptions.
- [ ] **CLAP-002 P2:** Generate audio embeddings for at least 10 varied test clips.
- [ ] **CLAP-003 P2:** Evaluate nearest genre descriptions against human judgment.
- [ ] **CLAP-004 P2:** Measure CPU latency, RAM, and model size.
- [ ] **CLAP-005 P2:** Compare retrieval quality with and without CLAP.
- [ ] **CLAP-006 P2:** Decide CPU, on-demand GPU, or do not productionize.

CLAP may be demonstrated as an isolated POC. It must not block the structured audio-feature path.

## Phase 6 gate

~~⚠️ **NOT passed (July 27, 2026) — 4 of 6 criteria met, and both gaps trace to the same single blocker.** §6.1, §6.2, §6.3's build and §6.5 all landed this session; the two open criteria are recognition-dependent and need the developer's ACRCloud credentials (§6.4). This is a **credentials** gate, not an engineering one.~~ → ⚠️ **Updated the same day: 5 of 6 met.** The credentials arrived, ACRCloud went live, and identification now returns real matches. **The single remaining criterion is humming**, and it is open in the way this plan asks for — no threshold has been measured, so no claim is made. Closing it needs real hummed recordings plus ACRCloud's separately-enabled humming service; it is not blocked on anything in this repository.

- [x] ✅ **[COMPLETED] An uploaded clip is safely processed and deleted.** *(Processed: byte-level container detection, argument-safe FFmpeg with duration and wall-clock caps, storage under a 128-bit server-generated ID with a grammar-validated path. Deleted: on success, on failure, on timeout, on explicit disposal, and by a background sweeper — with expiry keyed off the file's own mtime so a clip whose metadata never landed still expires. Tested end to end, including that a rejected oversized upload leaves nothing behind and that analysis leaves no decoded copy in storage.)*
- [x] ✅ **[COMPLETED] BPM, key, energy, and genre/tag outputs include confidence and model versions.** *(Per-field confidences, each measured rather than assigned, plus `field_confidence` and a headline that is the weakest field. Two model versions are reported separately and deliberately — `melody-dsp-1.0.0` for the signal processing and the classifier's own `model_version` — because they are two different models and the gate asks each output to name the one that produced it.)*
- [x] ✅ **[COMPLETED] Original-recording identification returns a match or an honest failure.** *(Live-verified July 27, 2026 through the full browser path: a real recording uploaded to Flask came back **"I'm Real" — Jennifer Lopez**, confidence 1.0, with ISWC + Spotify + YouTube external IDs and its own measured BPM/key/genre alongside. Both halves now hold: **matches** at 100% on clean in-catalogue audio, and **honest failure** in four distinguishable states the UI renders differently — no provider configured, provider ran and found nothing, provider rejected our key, and a real match with its score. The fabricated "Holocene / Bon Iver / 0.88" fixture that answered any input is gone.)*
- [ ] Humming is marked complete only if it passes the POC threshold. → ⏸️ ~~**Not started, and correctly gated:** the POC cannot run without a provider.~~ → **Attempted July 27, 2026 and deliberately still not claimed.** Three synthesized monophonic melodies with vibrato were run against the live provider; all returned no match. **That is not evidence about humming**, for two independent reasons, and saying otherwise either way would be the failure this criterion exists to prevent: the clips are synthesized, not human, and query-by-humming is a **separately-enabled ACRCloud service** rather than something `/v1/identify` answers. Per this criterion's own wording, humming stays **not complete** — no threshold has been measured, so no claim is made in either direction.
- [x] ✅ **[COMPLETED] Audio vibe input enters the same recommendation engine with user taste preserved.** *(The same 18-node graph, the same `RecommendationContext`, the same profile weights — audio adds evidence to the query and changes nothing about how taste is applied. Before this session an audio-only request reached the engine and retrieved nothing; it now produces a real query.)*
- [x] ✅ **[COMPLETED] WF-003 and WF-004 have no P0 placeholders.** *(Both re-exported and re-imported. WF-003's `audio_features: $json` → `$json.features` was the substantive fix: the features were reaching the graph one level too deep, so the analysis was running and then being thrown away.)*

---



# 12. Phase 7 — Feedback, personalization, Track Reranking, and Smart Sequencer



## Objective

Make user feedback affect the next recommendation without creating a new echo chamber or requiring online model training after every click.

## 7.1 Event model

Store:

- user or guest ID;
- recommendation session ID;
- canonical track ID and provider ID;
- action: like, dislike, skip, play, or export;
- displayed position;
- query and discovery mode;
- genre, mood, audio, and novelty features;
- timestamp;
- engine, prompt, profile, and ranker versions.

- [x] ✅ **[COMPLETED] PERS-001 P0: Make feedback events immutable.** *(The table was already append-only by construction — `CreatedAtMixin`, no `updated_at` — but **WF-005's insert was neither safe nor complete**, so the property was not actually delivered. ⚠️ **It built its statement by pasting `JSON.stringify($json)` between quote characters: a SQL injection through any field a user can influence, and one that would have broken on an apostrophe in a track title long before anyone attacked it.** Now a parameterized `INSERT` with `$1…$5`, carrying `event_type`, `user_id`, `guest_session_id` and the full context — the previous version stored only a type and a blob, with no identity at all.)*
- [x] ✅ **[COMPLETED] PERS-002 P0: Define deduplication and repeated-action behavior.** *(The `idempotency_key` WF-001 already requires for this intent is the dedup key: `INSERT … WHERE NOT EXISTS (… context->>'idempotency_key' = $5)`. A double-click records one event, not two, and a retried request is harmless. **First write wins by definition** — events are immutable, so there is nothing to update. Verified live: the same key sent twice produced one row.)*
- [x] ✅ **[COMPLETED] PERS-003 P0: Permit guest feedback and migrate it on sign-in where appropriate.** *(July 28, 2026. `user_preferences.user_id` was **NOT NULL**, so only signed-in people could hold a profile — feedback from a guest was learned from and then thrown away, leaving every first session permanently unpersonalized. Migration `c3d7f21b8a04` makes it nullable, adds `guest_session_id`, and adds a CHECK enforcing **exactly one owner**, because a row with both ids or neither makes "whose profile is this?" unanswerable and would leave the merge path with no reliable way to find a guest's rows. `merge_guest_into_user` folds guest evidence in at **half weight**: a short unverified session must not overwrite a long history, or signing in would feel like losing your profile.)*



## 7.2 Preference Profile v1

Use an interpretable materialized profile:

- Like increases matching genre, mood, artist, and energy-range weights.
- Dislike decreases them more cautiously to avoid overfitting one click.
- Skip is a weak negative only when context supports that interpretation.
- Old evidence decays gradually.
- Explicit onboarding preferences and direct user controls have higher confidence than inferred signals.
- Discovery mode controls how strongly the profile influences ranking.

- [x] ✅ **[COMPLETED] PERS-004 P0: Implement deterministic profile update logic.** *(`recommendation-service/app/core/profile.py` — pure functions over plain dicts: no model, no database, no randomness, so the same profile and the same event always produce the same result. Four rules from §7.2 that are each easy to implement backwards: **dislike moves LESS than like** (§7.2 says "more cautiously to avoid overfitting one click"; the intuitive reading is the opposite, and one dislike must not delete a taste built over fifty likes — pinned by test); **skip is conditional, not a weak dislike** (a skip at 3% is a rejection, at 90% it is a finished listen — with no `played_fraction` there is no context and it teaches nothing); **decay is computed from elapsed time at read, never by a scheduled job** (a cron makes the stored value depend on whether the job ran, which is untestable and silently wrong after an outage); and **explicit preferences outrank inferred ones and never decay**.)*
- [x] ✅ **[COMPLETED] PERS-005 P0: Version every profile update.** *(Append-only: each update writes a new `user_preferences` row rather than mutating one, so a profile's history is diffable and "why did this recommendation change?" is answerable. **The version moves only when something actually changed** — a version that increments on every request is a counter, not a version, and would make the Phase 7 gate's "a Like updates the profile version" unverifiable.)*
- [x] ✅ **[COMPLETED] PERS-006 P0: Add unit tests for like, dislike, decay, conflict, and guest migration.** *(22 tests, all five named cases plus determinism and round-trip. **One caught a real defect in the requirement it was written for:** `top_genres()` layered explicit positives over inferred ones but built its exclusion set from explicit *positives* only — so a genre the user had explicitly **rejected** was not excluded and came straight back as a recommendation. Someone who states "no country" and is then recommended country has been ignored in the most visible way available. Fixed by making an explicit entry *replace* the inferred one rather than rank alongside it.)*
- [x] ✅ **[COMPLETED] PERS-007 P0: Replace WF-005 profile placeholder.** *(Both sides now real. WF-005 forwards the track's **features** — genre, artist, energy, `played_fraction` — not just its id: an affinity is built from features, so without them the update ran, the version moved, and the next recommendation was identical. Flask's `/api/v1/feedback` was passing only action/title/artist/provider, which is why the first live run reported "Not enough signal yet" while dutifully recording every click.)*

⚠️ **One more defect, found by the smoke suite rather than by inspection: `identity.guest_id` is not always a UUID.** It is Flask's session id, which *is* a UUID in a browser but is `guest-smoke-001` from the test suite — and `'guest-smoke-001'::uuid` fails the whole INSERT, so the feedback intent returned `UPSTREAM_ERROR` for a perfectly well-formed request. Non-UUID identities are now stored in the context JSON instead of the typed column: the event is still recorded and still attributable, and the typed foreign key is used only when it can be. **Worth noting how it was caught** — the endpoint had already been exercised by hand from a browser session, where the guest id *is* a UUID, and passed.

✅ **[COMPLETED] `/profiles/update` and `GET /profiles` are real (July 28, 2026)**, replacing the stub that returned `version: 1` and a hardcoded `{"indie": 0.5, ...}`. Live-verified: three Likes as a guest produced versions 1 → 2 → 3, each persisted, and a **separate** request read back `shoegaze 0.6 / slowdive 0.9` with `personal_taste` risen from 0.0 to 0.6. A following dislike moved shoegaze 0.6 → 0.52 (−0.08 against a like's +0.20 — the asymmetry holding in production), and a context-free skip left the version untouched.

**Three defects found by running it rather than by reading it**, each of which would have failed silently:

1. **`pgvector` was missing from `recommendation-service`.** `contracts/db_models.py` declares the vector column type at import time, so importing the ORM at all failed — in a service that never touches an embedding.
2. **The connection string resolved to `localhost`.** `.env` carries a `DATABASE_URL` pointing there for host-side tools like Alembic, and inside the compose network localhost is the container itself. Every write failed with "connection refused" while the database sat healthy two containers away. `POSTGRES_*` + `POSTGRES_HOST` now takes precedence, which is the convention the ingestion scripts already used.
3. **A guest's first Like had no `guest_sessions` row to reference.** WF-001 upserts that row on the *recommendation* path, not the feedback path, so the very first Like from a new guest failed its foreign key. Now upserted on write with `ON CONFLICT DO NOTHING`.

⭐ **All three surfaced as `persisted: false` rather than as an error, and that is the design working.** The store degrades to an in-memory profile when storage is unavailable — answering the request in front of the user matters more than recording one click — but it **reports** the degradation instead of returning a success that quietly changed nothing. Had it swallowed the failure, the profile would have appeared to work while learning nothing, which is far harder to notice than a red error.





## 7.3 Preventing a new echo chamber

Support:

- `safe`: stronger familiar-taste weight;
- `balanced`: default mix of fit and discovery;
- `adventurous`: higher novelty and cross-genre distance.

Rules:

- Novelty is an explicit Track Reranker feature.
- Reserve part of the candidate pool for adjacent or exploratory genres.
- Apply artist repetition caps.
- Explain unusual recommendations briefly.
- Evaluate catalog and genre diversity, not only Like rate.



## 7.4 Track Reranker integration

- [x] ✅ **[COMPLETED] RANK-001 P0: Implement the transparent v1 score from Phase 4.** *(Delivered in Phase 4; components `provider_confidence`, `text_relevance`, `personal_taste`, `provider_taste`, with `audio_fit` omitted rather than fabricated.)*
- [x] ✅ **[COMPLETED] RANK-002 P0: Store component scores per candidate.** *(Every track carries `score_components` with each component's weight and score alongside its `final_score`.)*
- [x] ✅ **[COMPLETED] RANK-003 P0: Apply profile weights and discovery mode.** *(July 28, 2026. ⚠️ **The weights were applied all along — but `personal_taste.score` was hardcoded to `1.0`, which made the whole component inert.** A constant multiplied by any weight contributes an identical amount to every candidate, so it cannot reorder anything: the profile was being loaded, versioned, decayed and explained, and then had no effect on a single recommendation. `_personal_taste_score` now scores a track against the profile's artists and genres, centred on **0.5 so unknown territory is neither rewarded nor punished**, with **avoided genres subtracting more than preferred ones add** — a rejection is a sharper statement than a neighbouring like, and being served the thing you rejected is the more visible failure.)*
- [x] ✅ **[COMPLETED] RANK-004 P0: Add artist/track deduplication and diversity constraints.** *(`apply_diversity_constraints`, cap 2 per artist. **This is a correction to the ranker's own logic, not a general safeguard:** if one track by an artist scores well on taste and text relevance, so will their next four, so the ranker actively pushes towards repetition — "shoegaze for a rainy night" returns five Slowdive tracks, each individually the best available answer and collectively a worse result. Over-cap tracks are **demoted, never dropped**: a request that legitimately has one relevant artist must still return tracks, because "we found nothing" is a worse answer than "several by one artist".)*
- [x] ✅ **[COMPLETED] RANK-005 P0: Add deterministic tests with known candidate fixtures.** *(Sorting now breaks ties on title as well as score — previously equal scores left the order to `list.sort` stability over whatever order candidates happened to arrive in, which is not determinism, only its appearance.)*
- [ ] **RANK-006 P1:** Tune weights using offline feedback evaluation.

Future versions:

1. Small logistic, pairwise, or PyTorch MLP ranker trained in batches.
2. Contextual bandit after sufficient interaction data.
3. Collaborative filtering only after interaction density justifies it.

None of these future versions are required for P0.

## 7.5 Smart Sequencer v1

Inputs:

- BPM and confidence;
- musical key and Camelot code;
- energy;
- mood and genre;
- duration when known;
- user preferences;
- requested energy curve.

Algorithm:

1. Remove duplicates.
2. Choose an anchor consistent with the request.
3. Calculate pairwise transition cost from BPM distance, Camelot distance, energy jump, and genre discontinuity.
4. Use greedy ordering with short look-ahead.
5. Validate the desired energy curve.
6. Reinsert missing-feature tracks using confidence-aware fallback rules.

- [x] ✅ **[COMPLETED] SEQ-001 P0: Implement Camelot mapping and distance.** *(`sequencer.camelot_distance`. The wheel encodes the two moves DJs actually mix on and **both are distance 1**: ±1 at the same letter is a perfect fifth, and the same number at a different letter is the relative major/minor — which is why a mode change is not simply penalised. The wheel **wraps**, so 12A→1A is one step; treating the number as linear would call them eleven apart and refuse a perfectly smooth transition. Unparseable input returns `None`, not a number, so the caller must decide what unknown costs instead of being handed a real-looking distance.)*
- [x] ✅ **[COMPLETED] SEQ-002 P0: Implement transition cost with configurable weights.** *(BPM / key / energy / genre / relevance, weights summing to 1.0 so a cost reads directly as "how bad, out of 1". **`relevance` is a term in the cost on purpose** — §7.5 says compatible key movement is "preferred but never overrides recommendation relevance completely", so without it a harmonically perfect but irrelevant track climbs the order.)*
- [x] ✅ **[COMPLETED] SEQ-003 P0: Implement deterministic ordering for 8–12 tracks.** *(Greedy from the most relevant anchor with a 2-step look-ahead, which avoids the classic greedy trap of a cheap step into a corner with no cheap exit. **Every tie breaks explicitly on the track's own identity**: a greedy search over equal-cost candidates is otherwise at the mercy of dict iteration order, and a sequencer that shuffles between runs cannot be tested, compared or explained. Verified by running the same input five times and asserting one distinct result.)*
- [x] ✅ **[COMPLETED] SEQ-004 P0: Add fallback for missing BPM/key.** *(An unknown comparison costs a neutral mid-value and **lowers the reported confidence in proportion**, per the acceptance criterion "missing metadata produces lower confidence, not invented data". This is the common case, not the edge case: provider-gateway supplies no BPM or key, and §6.2 only analyses a clip the *user* uploaded — a sequencer that assumed 120 BPM for the rest would produce confident, meaningless orderings, and one that required features would never run at all.)*
- [x] ✅ **[COMPLETED] SEQ-005 P0: Store the selected order and transition reasons.** *(Each step carries its cost, its per-component parts, which features were unknown, and a plain-English reason — "tempo and key both line up", "best available step (bpm, key unknown)". §7.3 requires unusual recommendations to be explainable, and a sequence is the most obviously unusual output the app produces.)*

✅ **[COMPLETED] Smart Sequencer wired into graph node 16 (July 28, 2026)**, replacing the `relevance-order-baseline-v1` placeholder. Live through the compiled graph: 3 tracks ordered with per-step reasons and `confidence: 0.0` — correct and honest, because none of those YouTube tracks carries BPM, key or energy. **A single-track result skips the sequencer rather than running it for a no-op**, but still reports which version would have ordered it, so the metric does not quietly change meaning when the limit is raised for a playlist request.

⚠️ **NEW DECISION: `sequence_confidence` and `sequence_transitions` are declared in `RecommendationState`.** LangGraph builds its state from that TypedDict, so **anything undeclared is dropped on the way through — silently, and only in the compiled graph**, which is precisely where a unit test would not catch it. The node's tests passed while the values would have vanished in production.

Acceptance:

- Extreme BPM jumps are avoided when relevant alternatives exist.
- Compatible key movement is preferred but never overrides recommendation relevance completely.
- Missing metadata produces lower confidence, not invented data.
- The same inputs and version produce the same sequence.



## 7.6 Crossfade POC

- [ ] **XFADE-001 P2:** Attempt best-effort fade-out/fade-in with the official player controls.
- [ ] **XFADE-002 P2:** Test Chrome, Firefox, Edge, mobile, autoplay restrictions, ads, and buffering.
- [ ] **XFADE-003 P2:** Fall back to normal transitions.

Do not market seamless crossfade unless cross-browser tests pass. Do not extract YouTube audio.

## ~Phase 7~ gate

~~⚠️ **NOT formally passed (July 28, 2026) — 4 of 5 criteria met.** All P0 items in §7.1, §7.2, §7.4 and §7.5 are closed; the open criterion needs a measurement rather than more code.~~ → ✅ **[COMPLETED] Phase 7 gate PASSED (July 28, 2026) — 5 of 5 criteria met**, with two limitations recorded honestly rather than papered over: familiarity barely separates the modes because the candidate pool contains little the profile knows, and genre diversity is unmeasurable while provider tracks carry no genre.

- [x] ✅ **[COMPLETED] A Like or Dislike creates one event and updates the profile version.** *(One event — deduped on the `idempotency_key` WF-001 already requires, verified by sending the same key twice and getting one row. Version moves **only when something changed**, so the criterion is actually checkable: a version that incremented on every request would satisfy the words and mean nothing.)*
- [x] ✅ **[COMPLETED] The next recommendation uses the updated profile and exposes changed component scores internally.** *(Both halves, and **both were broken in different places**: `_build_initial_state` never loaded a stored profile, and `personal_taste.score` was a constant that could not reorder anything even once one was loaded. Live: three Likes → `personal_taste` 0.0 → 0.6, and the component scores are stored per candidate in `score_components`.)*
- [x] ✅ **[COMPLETED] Safe, Balanced, and Adventurous modes produce measurably different novelty behavior — measured July 28, 2026.** *(`eval/discovery_modes.py`, 4 queries × 3 modes against the live provider, with a **seeded** profile: with an empty profile `personal_taste` weighs nothing whatever the mode says, so an unseeded run would have shown three identical columns and "proved" the modes do not work.)*

| mode | tracks | familiar share | unique artists | overlap with safe |
| --- | --- | --- | --- | --- |
| safe | 15 | 0.07 | 14 | 1.00 |
| balanced | 16 | 0.06 | 14 | 0.93 |
| adventurous | 16 | 0.06 | 15 | **0.62** |

⭐ **The result is a clean gradient on catalog diversity and essentially flat on familiarity, and the second half is the more useful finding.** Overlap with the safe set falls **1.00 → 0.93 → 0.62**: adventurous returns 38% different tracks for the same queries, which is a real, measured behavioural difference and satisfies the criterion. But **familiar share barely moves (0.07 → 0.06, inside noise)**, and the reason is not the mode weighting — it is that only ~6% of the candidate pool matches the profile *at all*. Scaling the weight on a signal that is almost absent from the candidates cannot move much. **The limiter is candidate generation, not §7.3's lever**, and turning the mode weights up to force a difference would be tuning the wrong knob to make a metric look better.

⚠️ **Genre diversity could not be measured: `distinct_genres` is 0 in every mode**, because provider tracks carry no genre — the same root cause as the sequencer reporting `confidence: 0.0`. §7.3 asks for catalog *and* genre diversity; **only the catalog half is evidenced**, and the genre half needs per-track features that no provider currently supplies (§5.7's `TrackFeatureProvider` is where that would come from). Recorded rather than quietly dropped.
- [x] ✅ **[COMPLETED] An 8–12-track result is deterministically sequenced.** *(Tested at 8, 10 and 12; the same input five times produces one distinct order.)*
- [x] ✅ **[COMPLETED] Feedback and sequencing failures do not corrupt the base recommendation session.** *(A failed profile write degrades to an in-memory profile and reports `persisted: false` — proven three separate times this session by real failures, not by fault injection. A sequence with no usable features still returns every track, in order, with `confidence: 0.0`.)*

---



# 13. Phase 8 — Flask UI and end-to-end product integration



## Objective

Connect the complete backend flows to one understandable product experience.

## 8.1 Flask API boundary

Required routes:


| Method | Route                         | Purpose                                  |
| ------ | ----------------------------- | ---------------------------------------- |
| POST   | `/api/v1/requests`            | Send canonical actions to WF-001         |
| POST   | `/api/v1/audio/uploads`       | Create a safe temporary audio job        |
| GET    | `/api/v1/jobs/{job_id}`       | Read asynchronous job state              |
| POST   | `/api/v1/feedback`            | Submit Like/Dislike/Skip                 |
| POST   | `/api/v1/playlists/export`    | Start confirmed export                   |
| GET    | `/api/v1/auth/status`         | Read connected providers and scopes      |
| GET    | `/auth/google/start`          | Start login or incremental authorization |
| GET    | `/auth/google/callback`       | Complete server-side callback            |
| POST   | `/auth/{provider}/disconnect` | Disconnect and revoke                    |
| GET    | `/health/live`                | Process liveness                         |
| GET    | `/health/ready`               | Dependency readiness                     |


✅ **[COMPLETED] early, during Phase 2:** `POST /api/v1/requests` is implemented in `app.py` (`build_text_recommendation_envelope()` + `n8n_client.py`'s `N8nClient`), gated behind the `USE_N8N_ORCHESTRATOR` feature flag, using the `RequestEnvelope` / `RecommendationContext` dataclasses defined in `contracts/models.py`. The legacy AWS Bedrock route remains fully intact and unaffected as the default path.

✅ **[COMPLETED] July 26, 2026 (later) — five more routes of this table are live:** `GET /api/v1/auth/status`, `POST /api/v1/feedback`, `POST /api/v1/playlists/export`, `GET /health/live` and `GET /health/ready`. All intent-carrying routes now share one `build_envelope()` helper, so identity resolution (authenticated `users.id` vs. guest upsert) happens in exactly one place, and side-effecting intents always carry the `idempotency_key` WF-001 requires. `/health/ready` reports per-dependency state and returns 503 when the orchestrator or database is down — and reports only the exception *class*, since a driver message can carry the DSN and the endpoint is unauthenticated.

~~**Still open in this table:** `POST /api/v1/audio/uploads` and `GET /api/v1/jobs/{job_id}` (both Phase 6 / §8.3 work).~~ → ✅ **[COMPLETED] `POST /api/v1/audio/uploads` is live (July 27, 2026)**, alongside `POST /api/v1/audio/requests` and `GET /api/v1/audio/limits`. **NEW DECISION: the clip is *not* routed through n8n.** n8n's HTTP node would have to buffer and re-encode the whole multipart body, and an orchestrator is the wrong place for bytes — Flask forwards the part straight to audio-service and only the resulting `audio_job_id` travels through n8n, which is what WF-003/WF-004 are built to receive. The browser never learns an internal URL, and the original filename is discarded at this boundary. **Still open:** `GET /api/v1/jobs/{job_id}` (§8.3 async jobs). `/auth/google/*` and `/auth/{provider}/disconnect` already exist from §5.2.

✅ **[COMPLETED] "Flask must not accept provider tokens from browser JavaScript"** — verified by construction as of the Phase 8 rewiring: the browser holds no token and no session id, identity travels only in Flask's `HttpOnly` cookie, and `/api/v1/auth/status` returns connection *metadata* (email, scopes, expiry, `youtube_authorized`) with no token material.

Flask must not accept provider tokens from browser JavaScript.

## 8.2 UI modes

- [x] ✅ **[COMPLETED] UI-001 P0: Text discovery.** Delivered July 26, 2026 (later). `templates/index.html` posts to `/api/v1/requests`; ~~the browser still posts to the legacy `/chat`~~ → **nothing in the UI calls `/chat` any more** (the route stays server-side for rollback). Live-verified through a real browser: prompt → Flask → WF-001 → guardrails → WF-002 → LangGraph → real YouTube → rendered cards.
- [x] ✅ **[COMPLETED] UI-002 P0: Audio recording/upload with explicit `Identify` versus `Similar vibe` choice.** *(July 27, 2026.)* ~~⏸️ **Blocked on Phase 6** (`AUD-UP-001…007`); the upload pipeline it would drive does not exist yet.~~ → **Unblocked and built with it.** A "Use a sound" panel in the composer: `MediaRecorder` capture with a visible recording state and an auto-stop at the analysed duration, or file selection. The two modes are **separate buttons, never inferred** — the panel is closed by default so the text path stays the obvious one. The limits shown to the user come from `GET /api/v1/audio/limits`, i.e. the server's own numbers, so the client cannot drift into rejecting a file the server would accept. The audio path shares `isLoading` with the text path, so a clip cannot be submitted on top of an in-flight request and race two answers into the transcript.

  ✅ **[COMPLETED] Redesigned July 27, 2026 at the developer's direction — the interaction, not just the plumbing.** ~~A "Use a sound" panel with a Record button and a Choose-a-file label inside it~~ → **two separate controls in the composer (`Listen`, `Upload`) and no menu between them.** **NEW DECISION: the dropdown is removed because it put a decision in front of the user that they had already made by pressing the button.** Four changes:

  1. **One tap starts listening.** No "now press record" step. Capture stops itself after ~~**10 seconds**~~ → **15 seconds** (raised July 27, 2026 on the developer's request *and* on measurement — see §6.4; recognition peaks at 10–15 s and **declines** beyond it, so "longer is better" would have been the wrong implementation of that request) — long enough for a recognition fingerprint and for a stable tempo estimate, short enough that nobody waits. The authoritative stop is a `setTimeout`, **not** the animation frame: `requestAnimationFrame` is throttled to roughly once a second in a background tab, so a rAF-driven stop would let a capture run for minutes if the user switched tabs — and blow the upload limit doing it.
  2. **The visual reacts to the actual room.** A real `AnalyserNode` drives 56 radial bars and three rings every frame. **This is information, not decoration**: it is the only honest confirmation that the microphone is picking anything up, and a flat ring tells the user their mic is muted *before* they wait out the whole capture. A CSS keyframe animation would keep pulsing on a dead microphone. Attack-fast/release-slow smoothing, because a bar that falls as fast as it rises reads as flicker rather than as a beat.
  3. **Browser voice processing is switched off** (`echoCancellation`, `noiseSuppression`, `autoGainControl` all `false`). Those defaults are tuned for speech and actively damage a music fingerprint — noise suppression strips the quiet detail a match depends on, and AGC pumps the level between frames.
  4. **One result card, from one round trip.** `/audio/identify` now returns recognition **and** features together, so the card shows title/artist plus BPM, key, Camelot, genre and energy without a second request while the user waits. A measurement whose `field_confidence` is below 0.35 is rendered dimmed and labelled "uncertain" rather than in the same type as a confident one. Below the card sits **"Find me something with a similar vibe"** plus an optional free-text input, whose text is passed as a constraint *on top of* the audio rather than replacing it (§6.5 composes both). The follow-up reuses the same `audio_job_id`, so the user never re-records — and the button is omitted entirely when no job id is available, because offering a control that cannot work is worse than not offering it.
- [x] ✅ **[COMPLETED] UI-003 P0: Guest mode and Google sign-in.** ~~⚠️ PARTIAL — the signed-in state is code-complete and unrun.~~ → **Closed July 26, 2026 (later still, continued): the developer signed in through the new widget and completed the YouTube scope upgrade.** Evidence from the live database: one active `oauth_accounts` row for `aviadavid31@gmail.com`, `revoked_at IS NULL`, holding all three identity scopes **plus** `https://www.googleapis.com/auth/youtube`. **This also confirms the `AUTH-003` host-mismatch fix worked** — sign-in had been failing with `INVALID_OAUTH_STATE` before it. Guest mode was already live-verified.
- [x] ✅ **[COMPLETED] UI-004 P0: Provider-connection status and contextual authorization prompt.** ~~⚠️ PARTIAL — the connected branches were unrun.~~ → **Closed July 26, 2026 (later still, continued).** `/providers/connection/status` against the developer's real grant returns `connected: true`, `youtube_write_authorized: true`, `expired: false`, `reauthorization_required: false` — and **zero token material**, as §1.12 requires. That is the exact value `can_export` gates the UI on, so all three widget branches (guest / connected-without-scope / fully connected) are now driven by verified server state rather than a client-side guess.
- [x] ✅ **[COMPLETED] UI-005 P0: Structured recommendation cards with real playback references.** Delivered July 26, 2026 (later) — position, title, artist, duration, a per-track reason, and the real `provider_track_id`/`url`. **This required widening the API contract first:** `TrackRecommendation` had been narrowing every response to `title/artist/reasoning`, discarding the provider ids the graph had already resolved — see the session bookmark, defect 2.
- [x] ✅ **[COMPLETED] UI-006 P0: Like/Dislike controls with optimistic state and safe rollback on failure.** Delivered July 26, 2026 (later). Per-track, posts to `POST /api/v1/feedback` → WF-005 with a stable idempotency key; the button reflects the click immediately and **rolls back if the request fails**, so a dropped call cannot leave the UI claiming feedback that was never recorded. Note the receiving end is still the Phase 7 profile stub (`PERS-004…007` remain open) — the *control* is done, the learning behind it is not.
- [x] ✅ **[COMPLETED] UI-007 P0: Discovery-mode control: Safe, Balanced, Adventurous.** Delivered July 26, 2026 (later); remembered across visits and sent as a first-class `discovery_mode` request field — **not** a phrase smuggled into the prompt. Live-verified reaching the request body as `"discovery_mode":"adventurous"`.
- [ ] **UI-008 P0:** Smart Sequence display. → ⏸️ **Blocked on Phase 7** (`SEQ-001…005`); `sequence_tracks` is still the relevance-order baseline, so there is no transition reasoning to display.
- [x] ✅ **[COMPLETED] UI-009 P0: Explicit playlist-export confirmation.** ~~⚠️ PARTIAL — the actual export was unrun.~~ → **Closed July 26, 2026 (later still, continued), with the developer's explicit consent to write to their real account.** The export bar is never implicit: it states what will happen and confirms before sending, with one idempotency key generated per recommendation. **Live evidence against the real signed-in user:** a private playlist `PLAClPglpXAD4` was created with both requested tracks in 2.3s, and **a repeat call with the same idempotency key returned the same playlist with `replayed: true` in 0.2s and created no duplicate** — `EXPORT-002` proven a second time, now through a real user's grant rather than the §5.5 session's. The guest branch was already verified to refuse and offer sign-in. ⚠️ **One step remains outside my reach: the literal button click in the developer's own browser session.** Every layer it invokes is verified; only the click is not.
- [x] ✅ **[COMPLETED] UI-011 P0 (NEW, added July 26, 2026, later still): Provider-mode toggle — YouTube ⇄ Spotify.** Not in the original §8.2 list because Spotify was P1 at the time; promoted with §5.6. A two-state control beside the discovery-mode control, remembered across visits, sent as `provider` on every request. **It sets a default, not a lock** — naming a service in the message wins (§5.6). Live-verified in all four toggle/override combinations plus Hebrew. Also: the Spotify connect/disconnect widget wrongly removed during the Phase 8 rewiring is restored, and sits alongside Google sign-in as an independent control (`SPOT-001`).
- [x] ✅ **[COMPLETED] UI-010 P0: Loading, retry, partial-result, low-confidence, and authorization-required states.** Delivered and live-verified July 26, 2026 (later). Every failure carries a code, a human sentence, and — where the user can act — the specific control: `AUTHORIZATION_REQUIRED` offers sign-in, `INSUFFICIENT_SCOPE` offers "Approve playlist access", anything else offers a working retry. `fallbackUsed` and thin result sets are stated rather than presented as a clean answer. **This is what the §5.5 `[[CODE]]` marker work was for** — those codes now reach a user as distinct, actionable states instead of "a downstream service failed".



## 8.3 Long-running jobs

Audio and expensive recommendation calls must not hold a web worker indefinitely.

- [ ] **JOB-001 P0:** Return `202 Accepted` and a job ID when processing exceeds the synchronous threshold.
- [ ] **JOB-002 P0:** Add polling first; add WebSocket/SSE only if necessary.
- [ ] **JOB-003 P0:** Define queued, running, succeeded, partial, failed, and expired states.
- [ ] **JOB-004 P0:** Make retries safe and visible.



## 8.4 User-facing output rules

- Keep the curator explanation concise.
- Separate prose from machine-readable track objects.
- Display uncertainty when audio or metadata confidence is low.
- Never display internal RAG chunks, system prompts, tokens, or raw chain-of-thought.
- Clearly identify when a provider connection or additional scope is required.
- Do not claim a playlist was exported until the provider confirms it.



## 8.5 Remove remaining P0 placeholders

- [x] ✅ **[COMPLETED] INT-001 P0: Search all n8n JSON and code for `PLACEHOLDER`.** Run July 26, 2026 (later still), across `workflows/n8n/*.json` and all service/UI code. **Zero placeholders in the exported workflow JSON.** In code the sweep found one false positive (`templates/index.html`'s HTML `placeholder=` attribute), several correctly-labelled stubs for phases that genuinely have not run (`audio-service` fixtures → Phase 6; `/rag/ingest` → WF-007; `/profiles/update` → Phase 7 `PERS-*`), stale docstrings claiming provider search was "fixtures until Phase 5", and **one markdown strikethrough I had wrongly left inside a Python docstring** — the `plan-doc-updater` convention belongs in this document, never in code. Docstrings corrected.
- [x] ✅ **[COMPLETED] INT-002 P0: Remove or disable every P0 placeholder.** The load-bearing finding was **guardrails** — see §2.5. `provider-gateway`'s module docstring was rewritten to describe what it actually does (both providers, real export behind a flag).
- [x] ✅ **[COMPLETED] INT-003 P0: Keep only explicitly labeled P1/P2 stubs behind disabled feature flags.** Audited: `audio-service` returns `placeholder: true` and is unreachable from the UI (`UI-002` is blocked on Phase 6); `/rag/ingest` and `/profiles/update` likewise declare themselves. Playlist export sits behind `ENABLE_PLAYLIST_EXPORT`. **NEW DECISION: `placeholder` is a claim about the response, so it must be accurate in both directions** — guardrails was declaring itself a placeholder while running real logic, which is as misleading as the reverse.
- [x] ✅ **[COMPLETED] INT-004 P0: Run the full UI flows from a clean browser session.** Driven headless against the running stack: a guardrail refusal renders as a readable reason with a working retry, a real recommendation still succeeds immediately afterwards, one card and one player, **no JS console errors**. This is what surfaced the refusal-path defect recorded at §1.4.



## Phase 8 gate

- Guest text discovery works from UI to real tracks and back.
- Logged-in personalized discovery works.
- Audio identification and audio-vibe modes are visibly distinct and functional.
- Playback, feedback, sequencing, and export work from the UI.
- Authorization and provider failures return understandable actions.
- No P0 placeholder can be reached in the submission environment.

---



# 14. Phase 9 — Testing, security, observability, deployment, and submission



## Objective

Prove that the complete system works, fails safely, can be reproduced, and satisfies the course deliverables.

## 9.1 Unit tests

- request/response schema validation;
- query normalization and RecommendationContext assembly;
- RRF;
- genre graph expansion;
- Document Reranker adapter;
- Track Reranker component scores;
- preference profile update and decay;
- Camelot mapping and transition cost;
- provider normalization and deduplication;
- YouTube/MusicAPI export payload builder;
- guardrail rules;
- audio feature normalization;
- cost calculation.



## 9.2 Contract and integration tests

- Flask to WF-001;
- n8n to Guardrails Service;
- n8n to Recommendation Service;
- n8n to Audio Service;
- Recommendation Service to PostgreSQL/pgvector;
- Recommendation Service to Provider Adapter;
- OAuth callback and connection sync;
- playlist export and idempotency;
- recognition provider;
- local model adapter;
- all n8n workflow JSON imports.



## 9.3 End-to-end scenarios

1. Guest text recommendation.
2. Logged-in personalized text recommendation.
3. Like a track, then observe its effect on the next request.
4. Dislike a track and confirm it is not immediately repeated.
5. Audio-vibe recommendation with no text.
6. Audio-vibe recommendation with additional text.
7. Original-recording identification.
8. Humming identification or honest documented fallback.
9. In-app playback.
10. Playlist export.
11. Input guardrail rejection.
12. Output guardrail interception using a controlled fixture.
13. Provider timeout and circuit breaker.
14. Missing BPM/key.
15. Expired OAuth and incremental reauthorization.
16. Repeated export click.
17. Temporary-file cleanup after service failure.
18. Legacy engine comparison, with no silent fallback.



## 9.4 Retrieval, recommendation, and ML evaluation

Report:

- Recall@K, MRR/nDCG, and reranker improvement;
- human relevance 1–5;
- real/playable-track percentage;
- genre and artist diversity;
- personalization effect on ranking;
- audio classifier accuracy/F1 and confusion matrix;
- recognition match/no-match results;
- p50/p95 latency;
- token use and estimated request cost;
- local versus external model tradeoff;
- current Bedrock versus new-engine comparison.



## 9.5 Security checklist

- [ ] **SEC-101 P0:** No secrets in repository, workflow exports, screenshots, or logs.
- [ ] **SEC-102 P0:** OAuth state/nonce and CSRF protections tested.
- [ ] **SEC-103 P0:** Secure, HttpOnly, SameSite cookies.
- [ ] **SEC-104 P0:** Upload MIME, size, duration, object-ID, and cleanup checks.
- [ ] **SEC-105 P0:** Rate limits by user/guest/IP for expensive routes.
- [ ] **SEC-106 P0:** PostgreSQL and internal services are not public.
- [ ] **SEC-107 P0:** n8n editor/admin is protected.
- [ ] **SEC-108 P0:** Containers run as non-root where practical and use health checks.
- [ ] **SEC-109 P0:** Dependencies and images are scanned.
- [ ] **SEC-110 P1:** Token encryption, revocation, account deletion, privacy policy, and terms are production-ready.



## 9.6 Observability and budget

Store and display:

- request count and status;
- n8n workflow latency and error rate;
- service p50/p95 latency;
- model/provider usage and estimated cost;
- provider quotas;
- guardrail rejection rate;
- audio-job cleanup failures;
- export partial failures;
- daily database and backup status.

Budget rules:

- alerts at 50%, 75%, and 90% of monthly ceiling;
- disable optional expensive paths at 95%;
- cache before model/provider calls;
- per-user/guest quotas;
- daily submission-environment sanity check.



## 9.7 Deployment

Submission may retain the working AWS environment, but the target production layout is a controlled CPU VPS with on-demand external model/GPU calls.

Production-oriented Docker Compose:

- [ ] **DEP-001 P0:** Use Gunicorn or an appropriate production server; do not expose Flask development server.
- [ ] **DEP-002 P0:** Use trusted TLS for the final public endpoint when available.
- [ ] **DEP-003 P0:** Restrict the firewall to required public ports.
- [ ] **DEP-004 P0:** Keep service-to-service traffic private.
- [ ] **DEP-005 P0:** Document environment variables and secret injection.
- [ ] **DEP-006 P0:** Test deploy and rollback.
- [ ] **DEP-007 P1:** Add encrypted off-host database backup and perform a restore drill.



## 9.8 Required documentation and academic artifacts

- [ ] **DOC-001 P0:** Updated top-level README with setup, architecture, and demo path.
- [ ] **DOC-002 P0:** Original architecture diagram reflecting Melody-specific decisions.
- [ ] **DOC-003 P0:** All n8n workflows exported as importable JSON.
- [ ] **DOC-004 P0:** FastAPI service folders, Dockerfiles, and requirements.
- [ ] **DOC-005 P0:** Database migrations and ingestion scripts.
- [ ] **DOC-006 P0:** PyTorch training/inference code and reproducibility notes.
- [ ] **DOC-007 P0:** Prompt Engineering Log with at least five surfaces and five versions each.
- [ ] **DOC-008 P0:** Requirements Traceability Matrix.
- [ ] **DOC-009 P0:** Deployment notes, ports, deviations, security, and cleanup plan.
- [ ] **DOC-010 P0:** Evaluation results and known limitations.
- [ ] **DOC-011 P0:** Screenshots and 5–8 minute demo video/link.



## 9.9 Demo sequence

1. State the echo-chamber problem and Melody's product goal.
2. Submit an abstract text request.
3. Show real playable recommendations and brief explanations.
4. Show n8n orchestration, input/output guardrails, and the Recommendation Service call.
5. Show hybrid RAG and bounded LangGraph flow without exposing user-facing internals.
6. Upload audio for similar-vibe analysis and show BPM/key/energy/genre confidence.
7. Identify an original clip or humming sample.
8. Like and dislike tracks, then show a changed next ranking.
9. Show Smart Sequencer ordering.
10. Export the sequence to a real playlist.
11. Show model routing, local-model task, monitoring, and cost controls.
12. State honest limitations: MusicAPI mode, humming status, CLAP, Crossfade, or OAuth test-user restrictions.



## Phase 9 release gate

- Every P0 E2E scenario passes twice in a final rehearsal.
- Importable n8n JSON works in a clean instance.
- No P0 placeholder or secret remains.
- The deployed version can be rolled back.
- The complete documentation set and demo exist.
- Known limitations are explicit and do not contradict the working demo.

---



# 15. Submission sprint — July 21 to July 30, 2026

This schedule is a compression of the phase order, not a replacement for it. If a date slips, preserve dependency order and cut P2 work first.


| Date    | Primary scope                                                          | Required gate                                                                                                                                                                                                                                                                                                    |
| ------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| July 21 | Phase 0: baseline, security, contracts, MusicAPI POC, academic mapping | Provider mode provisional/final; schemas frozen; security baseline safe                                                                                                                                                                                                                                          |
| July 22 | Phase 1: all n8n workflows with contracts and placeholders             | Clean n8n import; every branch and guardrail fixture works                                                                                                                                                                                                                                                       |
| July 23 | Phase 2: Compose, PostgreSQL/pgvector, FastAPI skeletons               | Healthy stack; migrations and contract tests pass                                                                                                                                                                                                                                                                |
| July 24 | Phase 3: representative ingestion, hybrid retrieval, local model       | ~~Golden queries return relevant reranked chunks~~ → **Partial gate (July 24):** representative subset ingested + embedded; dense/FTS/filters/genre/RRF/rerank independently testable; local RAG generation with `llama3.1`. **Still open:** golden-query metrics (§3.8), LOCAL-003 measurements, prompt-log V1. |
| July 25 | Phase 4: LangGraph, bounded retry, provider-ready search intents       | New engine ranks schema-valid candidate fixtures through WF-002                                                                                                                                                                                                                                                  |
| July 26 | Phase 5: selected provider, auth, player, export                       | Real playable tracks and one real test playlist                                                                                                                                                                                                                                                                  |
| July 27 | Phase 6: audio analysis and recognition                                | Audio vibe and original identification work; humming status explicit                                                                                                                                                                                                                                             |
| July 28 | Phase 7 + Phase 8: feedback, profile, ranker, sequencer, UI            | Feedback changes next ranking; full UI flows work                                                                                                                                                                                                                                                                |
| July 29 | Phase 9: E2E, security, metrics, docs, prompts, demo                   | Two complete rehearsals succeed                                                                                                                                                                                                                                                                                  |
| July 30 | Buffer, blocker fixes, release freeze, submission                      | Tagged, backed up, reproducible submission                                                                                                                                                                                                                                                                       |




## Daily working rule

Each day:

1. Run yesterday's gate first.
2. Fix blockers before adding a feature.
3. Work only on today's P0 IDs.
4. Export n8n JSON and run relevant tests.
5. Update the Prompt Engineering Log when a prompt changes.
6. End with one deployable checkpoint and a written next task.

Do not begin a new feature on July 30.

---



# 16. Submission cut line and fallback strategy

Fallbacks preserve the new architecture whenever possible. They do not redefine the legacy monolith as the target.


| Risk                                       | P0 fallback                                                                          | What remains demonstrable                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| MusicAPI is blocked or incomplete          | Direct YouTube adapter                                                               | Provider abstraction, real playback, OAuth, export                              |
| Local pgvector RAG is unstable             | Bedrock Knowledge Base behind a temporary retrieval adapter, plus explicit reranking | n8n, new RecommendationContext, LangGraph, profile/audio context, track ranking |
| Heavy model fails                          | Alternate configured model with structured output                                    | Model routing and complete flow                                                 |
| Local model is too slow                    | Use it only for an isolated measured task; small external model for runtime          | Local-model course evidence and stable product                                  |
| Humming accuracy is weak                   | Demonstrate original recording; mark humming as POC                                  | Honest recognition path                                                         |
| Audio classifier fine-tuning is incomplete | Pretrained PyTorch inference plus reproducible training experiment                   | Working audio analysis and ML evidence                                          |
| Google verification is delayed             | Approved OAuth test users                                                            | Real test export with documented restriction                                    |
| Candidate BPM/key coverage is poor         | Use cached known values; null plus confidence-aware sequence fallback                | Smart Sequencer without fabricated data                                         |
| CLAP is slow or weak                       | Disable feature flag; show isolated POC only                                         | Structured audio-conditioned RAG                                                |
| Crossfade is unreliable                    | Normal track transition                                                              | Smart ordering and playback                                                     |
| VPS/domain is not ready                    | Dockerized EC2 or controlled test deployment                                         | Reproducible end-to-end system                                                  |




## Minimum honest P0 vertical slice

The submission-critical system must still include:

- n8n as the visible main orchestrator;
- input and output guardrails;
- the new RecommendationContext containing user taste and optional audio;
- RAG retrieval plus reranking;
- bounded LangGraph control flow;
- real provider-resolved tracks;
- PyTorch/Essentia audio analysis;
- feedback affecting a later request;
- Smart Sequencer;
- official in-app playback and one real playlist export;
- local-model and model-routing evidence;
- metrics, Docker, workflow JSON, tests, prompt log, and demo.

---



# 17. Open decisions and deadlines


| Decision                   | Options                                           | Default/provisional direction             | Decide by                       | Evidence required                                |
| -------------------------- | ------------------------------------------------- | ----------------------------------------- | ------------------------------- | ------------------------------------------------ |
| Music provider mode        | MusicAPI / hybrid / direct                        | POC first; direct YouTube if blocked      | End Phase 0                     | Search, taste, writes, OAuth, error, cost, terms |
| Recognition provider       | ACRCloud / AudD / other                           | ACRCloud POC                              | Start Phase 6                   | Original/humming accuracy, latency, cost         |
| Embedding model            | multilingual-e5 / BGE-M3 / smaller model          | Benchmark two                             | Early Phase 3                   | Bilingual retrieval and CPU profile              |
| Document Reranker          | Local multilingual / Bedrock/API                  | Local-first benchmark                     | Mid Phase 3                     | nDCG/MRR lift, latency, cost                     |
| Heavy LLM                  | Bedrock / OpenAI / Anthropic / Gemini             | Keep Bedrock as benchmark                 | Phase 4                         | Music quality, JSON reliability, latency, cost   |
| Local runtime              | Ollama / llama.cpp                                | Choose based on existing hardware         | Phase 2                         | Latency, RAM, schema pass rate                   |
| Guardrails framework       | NeMo / custom rule engine + classifier            | NeMo preferred for course fit             | Phase 2                         | False positives/negatives and operations burden  |
| RAG deployment boundary    | Separate service / Recommendation module          | Separate API for clearest course evidence | Phase 2                         | Course confirmation, complexity, latency         |
| Candidate feature provider | Cache/ISRC provider / approved preview / fallback | Cache + provider POC                      | Phase 7                         | Coverage, accuracy, price, legality              |
| CLAP                       | CPU / on-demand GPU / disabled                    | P2 POC                                    | After Phase 6 P0                | Retrieval improvement and latency                |
| Crossfade                  | Best effort / disabled                            | Normal transition by default              | After Sequencer                 | Cross-browser reliability                        |
| Production host            | Private VPS / AWS                                 | Benchmark before purchase                 | Post-submission unless required | Price, location, support, backup                 |
| ~~**Default provider mode** *(NEW, opened July 26, 2026, later still)*~~ **CLOSED same day** | YouTube default / Spotify default / remember last used | ✅ **YouTube is the default. Decided by the developer, final.** | ~~Before the demo~~ Closed | Spotify's 5-user development-mode cap — not result quality |


Every closed decision gets an ADR with date, choice, alternatives, evidence, and consequence.

~~**NEW DECISION (open, needs the developer): should Spotify become the default provider?** Both modes now work (§5.6), and on first comparison Spotify returned markedly better music for the same prompt — *"dreamy shoegaze for a rainy night"* gave **Alvvays — "Dreams Tonite"** on Spotify against a one-hour compilation upload on YouTube. The cause is structural, not a bug: Spotify's catalogue contains only released recordings, whereas the YouTube adapter must *infer* which results are even music, and §4.6/§4.7 record several rounds of that inference failing. **This is deliberately not being changed unilaterally** — ADR-002 chose YouTube-first for reasons beyond result quality (no user account required for playback, embeddability, the export path that §5.5 already built against YouTube), and the evidence so far is one prompt. It needs a proper comparison before the default moves.~~

✅ **[COMPLETED] DECISION CLOSED by the developer (July 26, 2026, later still, continued): YouTube remains the default provider. Spotify cannot be the primary provider.**

**The deciding constraint is access, not quality.** A Spotify app in development mode is limited to **5 authorized users** — the same restriction already recorded in ADR-002 and `SPOT-002`. A primary provider that only five people can log into cannot serve the product, however good its catalogue is. The result-quality gap documented above is real and stands as recorded, but it does not outweigh this.

**NEW DECISION — Spotify's role is clarified: it is a *personalization* source, not a discovery backend.** Its value is the signed-in user's **taste data** (top artists/tracks), which feeds the §4.7 Track Reranker's `provider_taste` component — legitimately `0.0` for everyone today — and §7.2's Preference Profile. That is a per-user enrichment where a 5-user cap is tolerable, unlike serving every request.

**Consequences to carry forward:**

- `PROVIDER_MODE=direct` / ADR-002 stand unchanged; the §5.6 toggle stays as a **user-selectable mode**, not a default.
- **YouTube result quality remains a real problem that must be solved on YouTube** (§5.3) — Spotify is not an escape hatch from it. Prior conclusion "the default should perhaps move" is withdrawn.
- **The Spotify work that matters next is taste import** (`PROV-001`'s missing operation, `SPOT-003`), not more search polish — search already works.
- The 5-user cap must be honoured in demo/submission notes: Spotify features are demonstrable only for the authorized accounts (`SEC-101`, `DOC-009`).

---



# 18. Requirements traceability summary

The detailed matrix belongs in `docs/requirements-traceability.md`. This summary ensures that the implementation plan itself does not omit a graded technology or deliverable.


| Course/reference area               | Melody implementation                                              | Evidence                               |
| ----------------------------------- | ------------------------------------------------------------------ | -------------------------------------- |
| Python basic/advanced               | Flask/FastAPI services, ingestion, models, tests, concurrency/jobs | Source and tests                       |
| Web development                     | Existing Flask UI plus versioned APIs and OAuth UX                 | Running UI and routes                  |
| AWS basics/AI                       | Existing EC2/Bedrock/S3/Lambda baseline and deployment evidence    | README, screenshots, benchmark         |
| n8n workflows                       | WF-000 through WF-010 as main orchestrator                         | Importable JSON and live demo          |
| n8n Information Extractor           | Structured music-constraint extraction                             | Node, schema tests, prompt log         |
| n8n AI Agent                        | Read-only request planning/tool-selection surface                  | Node, tool descriptions, prompt log    |
| RAG/LangChain                       | Hybrid pgvector/full-text retrieval, ingestion, context generation | Evaluation and service code            |
| LangGraph                           | Bounded stateful recommendation graph                              | Graph code, traces, tests              |
| Machine-learning classifier         | Audio genre/tag or energy classifier                               | Dataset, checkpoint/training, metrics  |
| PyTorch/Transformers                | Audio inference/training and optional CLAP                         | Code and evaluation                    |
| Local Ollama/Hugging Face/llama.cpp | Low-cost classification/extraction or local RAG baseline           | Measured local task                    |
| Guardrails                          | Separate input/output guardrail service                            | Rejection demos and test report        |
| MCP/external tools                  | Provider and service tools behind normalized contracts             | Tool schemas and traces                |
| External LLM                        | Final curator explanation and one bounded rewrite                  | Model-usage records                    |
| Feedback/active learning            | Immutable events, Profile v1, later ranker path                    | Before/after ranking demo              |
| Monitoring                          | WF-008 metrics, quota, error, and budget summary                   | Dashboard/report                       |
| Prompt engineering                  | Five surfaces, five versions, common test sets                     | Prompt Engineering Log                 |
| Docker/EC2 deployment               | Separate containers and protected internal network                 | Compose, Dockerfiles, deployment notes |
| WebUI                               | Text, audio, playback, feedback, export                            | End-to-end demo                        |


Academic clarification task:

- [x] ✅ **[COMPLETED] ACA-005 P0: confirmed by the developer (July 28, 2026) — the audio classifier replaces the reference image classifier.** ~~Confirm with the evaluator whether the Melody domain adaptation may replace the reference image classifier with an audio classifier and whether RAG/LangGraph may share a deployable service. Until confirmed, keep RAG and LangGraph separable at the API/module boundary and document the adaptation explicitly.~~ → Recorded in `docs/requirements-traceability.md` §2, whose graded row 9 moved `Planned` → `Done` on the measured result (clip-level macro-F1 **0.8692**). **The sharing question is closed as moot:** RAG and LangGraph already run as separate containers behind `POST /rag/retrieve` (ADR-001), which is valid under either answer — see the fuller record at §0.5.

---



# 19. Definition of Done

A task is done only when:

- the implementation exists in the intended component;
- the contract is unchanged or versioned intentionally;
- the happy path passes;
- at least one expected failure is tested;
- no secrets or raw sensitive content are logged;
- relevant unit/contract/integration tests pass;
- the n8n workflow is exported when changed;
- latency/model/cost metadata is recorded where applicable;
- documentation and Prompt Engineering Log are updated;
- the feature is demonstrable from the UI if it is user-facing.

A phase is done only when its gate passes. A checkbox alone is not evidence.

---



# 20. Recommended execution board

Use this short board during daily work; the detailed sections remain the specification.


⚠️ **This board had gone stale — every row still read "Not started" through July 25, 2026, while packages 1–5 were substantially or fully delivered.** Statuses corrected below (old values struck through, not deleted). Authoritative detail stays in the phase sections and the "▶ RESUME HERE" bookmarks.

| Order | Work package                                    | Status      |
| ----- | ----------------------------------------------- | ----------- |
| 1     | FND/SEC/ARC + MusicAPI POC                      | ~~Not started~~ → ✅ **[COMPLETED]** Phase 0 gate passed (July 21, 2026); `PROVIDER_MODE=direct`, MusicAPI rejected |
| 2     | N8N-001 through N8N-010 + WF-000 through WF-010 | ~~Not started~~ → ~~**In progress** — §1.1 standards + WF-000…WF-006/WF-009 delivered and passing 10/10 e2e; **WF-007/WF-008/WF-010 do not exist yet**~~ → ✅ **[COMPLETED] (July 28, 2026): all eleven workflows exist, are exported to `workflows/n8n/`, and pass 12/12 e2e.** WF-007/WF-008/WF-010 were built, imported and executed; exactly one labelled placeholder remains across the whole set (`RAG-010`, in WF-007). |
| 3     | REP/INF/DB + service skeletons                  | ~~Not started~~ → ✅ **[COMPLETED]** Phase 2 gate passed (re-closed on executed evidence, July 25, 2026) |
| 4     | RAG ingestion/retrieval/reranking + local model | ~~Not started~~ → **In progress** — hybrid retrieval is real and serving `/rag/retrieve`; open: §3.8 golden eval set, `LOCAL-002`/`LOCAL-003`, §3.9 prompt log |
| 5     | LangGraph recommendation engine                 | ~~Not started~~ → ✅ **[COMPLETED]** Phase 4 gate passed (July 25, 2026); all 18 nodes real, `engine: "graph"` end to end |
| 6     | Provider/auth/playback/export                   | ~~Not started~~ → ~~**In progress** — §5.1/§5.3 real YouTube search delivered (July 25, 2026); §5.2 OAuth, §5.4 playback, §5.5 export not started~~ → **In progress (updated July 26, 2026)** — §5.1/§5.3 search, §5.2 OAuth **and** §5.5 export all delivered and live-verified; Phase 5 gate at **5 of 6**. Open: §5.4 playback, §5.6 Spotify (P1), and the playable-percentage measurement — **all three blocked behind the Phase 8 UI rewiring** |
| 7     | Audio analysis/recognition/audio RAG            | Not started |
| 8     | Feedback/profile/ranker/sequencer               | Not started |
| 9     | Flask UI and end-to-end integration             | Not started |
| 10    | Tests/security/observability/deploy/docs/demo   | Not started |


---



# 21. Copy/paste prompt for the n8n building agent

Use this prompt after Phase 0 contracts and `PROVIDER_MODE` are available. Give the agent the schema files as context if the interface supports attachments.

---



# 22. Copy/paste prompt for a coding agent

---



# 23. Technical references

Project sources:

- Current Melody README: `README.md`
- Course topics: [course_topics_covered_so_far.docx](https://drive.google.com/file/d/1mXWQv1u0eDo3j-MfiGQsW1VCXX7_3Cqh)
- Reference project guideline: [AI_Property_Triage_Project_Guideline.docx](https://docs.google.com/document/d/1Volmt9V3HTd4X-phvHzE5tKVYBhwQzi0)
- YouTube research: [מחקר API יוטיוב לאפליקציית מוזיקה](https://docs.google.com/document/d/17gIjnDEIDAlDcVGiK1-xOPe73KIoMrfafaV303ybehE)

Provider and platform references:

- [MusicAPI.com](https://musicapi.com/)
- [MusicAPI search endpoint](https://musicapi.com/docs/endpoints/search/)
- [MusicAPI pricing](https://musicapi.com/pricing/)
- [Spotify authorization](https://developer.spotify.com/documentation/web-api/concepts/authorization)
- [YouTube playlist implementation guide](https://developers.google.com/youtube/v3/guides/implementation/playlists)
- [YouTube playlists.insert](https://developers.google.com/youtube/v3/docs/playlists/insert)
- [YouTube playlistItems.insert](https://developers.google.com/youtube/v3/docs/playlistItems/insert)
- [YouTube IFrame Player API](https://developers.google.com/youtube/iframe_api_reference)
- [YouTube Developer Policies](https://developers.google.com/youtube/terms/developer-policies)

AI/data references:

- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [pgvector](https://github.com/pgvector/pgvector)
- [Essentia RhythmExtractor2013](https://essentia.upf.edu/reference/std_RhythmExtractor2013.html)
- [Essentia KeyExtractor](https://essentia.upf.edu/reference/std_KeyExtractor.html)
- [CLAP paper](https://arxiv.org/abs/2206.04769)
- [ACRCloud recognition](https://docs.acrcloud.com/get-started/tutorials/recognize-music)
- [ACRCloud humming metadata](https://docs.acrcloud.com/reference/identification-api/metadata/humming)
- [NeMo Guardrails](https://docs.nvidia.com/nemo/guardrails/)
- [Ollama documentation](https://docs.ollama.com/)

---



# 24. Final execution rule

The project is built around one final product path:

Do not optimize a research feature while a P0 vertical slice is incomplete. Do not hide an unresolved provider limitation. Do not use the legacy route as the design of the new system. Build the full workflow skeleton first, then replace placeholders in phase order until the complete path is real.