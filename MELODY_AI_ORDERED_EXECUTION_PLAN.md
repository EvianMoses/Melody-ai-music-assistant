# Melody AI — Ordered Execution and Build Plan

> Primary execution document for building the next version of Melody in dependency order.
>
> This file supersedes the execution order in `MELODY_AI_IMPLEMENTATION_PLAN.md`. The older file may remain as an architecture and product reference, but task execution should follow this document.

## Document status

| Field | Value |
|---|---|
| Project | Melody — AI-Powered Music Discovery Assistant |
| Owner | Solo developer |
| Plan date | July 21, 2026 |
| Submission deadline | July 30, 2026 |
| Current baseline | Flask + AWS Bedrock Agent + Bedrock Knowledge Base + OpenSearch Serverless + S3 + Lambda + Spotify |
| Target system | n8n-orchestrated, multimodal, personalized music recommendation system |
| Primary playback/export direction | YouTube-first, behind a provider interface |
| Provider decision | MusicAPI.com must be evaluated immediately; final mode may be MusicAPI, hybrid, or direct APIs |
| Status | Approved architecture converted into an ordered implementation plan |

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

The first implementation surface is the n8n architecture, but only after a short Phase 0 that freezes the baseline, fixes exposed-secret risks, defines the shared request contracts, and performs the MusicAPI decision experiment.

The first n8n deliverable is not a single legacy text path. It is the complete final workflow skeleton with placeholder service calls where implementation is not ready yet.

~~~text
Phase 0: freeze, secure, define contracts, test MusicAPI
    ↓
Phase 1: build the complete n8n workflow architecture
    ↓
Phase 2: implement database and service foundations
    ↓
Phase 3: build the knowledge and RAG foundation
    ↓
Phase 4: build the new LangGraph recommendation engine
    ↓
Phase 5: implement the selected provider/auth/playback route
    ↓
Phase 6: add audio identification and audio-conditioned recommendation
    ↓
Phase 7: add feedback, personalization, and Smart Sequencer
    ↓
Phase 8: complete the UI and end-to-end product flows
    ↓
Phase 9: test, secure, deploy, document, and demonstrate
~~~

---

# 2. Non-negotiable architecture

## 2.1 Target request path

The target recommendation path is new. It is not the existing Bedrock recommendation path with an n8n wrapper.

~~~mermaid
flowchart TD
    UI["Flask Web UI"] --> N8N["n8n Orchestrator"]
    N8N --> Guard["Guardrails Service"]
    N8N --> Profile["User Profile"]
    N8N --> Audio["Audio Service"]
    N8N --> Rec["Recommendation Service / LangGraph"]
    Rec --> RAG["Hybrid RAG"]
    Rec --> Provider["Music Provider Adapter"]
    Rec --> Rank["Personal Ranker + Sequencer"]
    Provider --> Play["Playable Provider IDs"]
    Rank --> N8N
    N8N --> UI
~~~

Every recommendation may use this complete context:

~~~text
user text
+ user identity or guest identity
+ materialized user taste profile
+ optional connected-provider taste signals
+ optional audio-analysis features
+ current discovery mode and constraints
= RecommendationContext
~~~

## 2.2 Component boundaries

| Component | Owns | Must not own |
|---|---|---|
| Flask Web App | UI, session cookie, upload UX, embedded player, feedback controls, OAuth start/callback UX | RAG logic, personal ranking logic, provider-specific recommendation logic |
| n8n | Request orchestration, validation, guardrail calls, routing, retries, side effects, persistence coordination, export, monitoring | Embedding math, audio DSP, complex ranking algorithms |
| Recommendation Service | LangGraph state, bounded control flow, provider search intents, track ranking, sequencing, explanation | OAuth callbacks, playlist writes, feedback writes |
| RAG Service | Hybrid retrieval, genre expansion, RRF, document reranking, retrieval confidence, evidence packaging | Provider writes, final personal ranking, OAuth |
| Audio Service | File validation, conversion, BPM, key, energy, genre/tags, embeddings | Music-provider authentication, final recommendation generation |
| Guardrails Service | Input policy, output grounding checks, prompt-injection and unsupported-claim checks | Music discovery, ranking, provider search |
| Provider Adapter Layer | Search, identity resolution, taste import, playlist operations, normalized provider data | RAG, user preference learning, final prose |
| PostgreSQL + pgvector | Durable users, profiles, feedback, tracks, knowledge, vectors, jobs, usage, exports | Workflow branching |
| Local Model Runtime | Cheap classification, structured extraction, local inference demonstrations | Authentication and deterministic operations |

## 2.3 Role of the existing AWS/Bedrock implementation

The existing AWS route is retained only as:

- a known-good rollback while development is incomplete;
- a quality and latency benchmark;
- an optional, explicitly logged emergency fallback behind a feature flag.

It is not the target recommendation architecture. It must not define the new request schema, personalization logic, audio path, provider layer, or workflow structure.

Required feature flags:

~~~text
RECOMMENDATION_ENGINE=new|legacy
ALLOW_LEGACY_FALLBACK=true|false
PROVIDER_MODE=musicapi|hybrid|direct
CLAP_ENABLED=true|false
~~~

Any legacy fallback must be recorded in `recommendation_sessions.engine_used`; never switch silently.

---

# 3. Canonical contracts to freeze before workflow construction

These contracts are drafted in Phase 0 and used by every later phase. Pydantic/JSON Schema becomes the executable source of truth in Phase 2.

## 3.1 Request envelope

~~~json
{
  "api_version": "v1",
  "request_id": "uuid",
  "idempotency_key": "optional-uuid",
  "intent": "text_recommendation",
  "user": {
    "user_id": "uuid-or-null",
    "guest_id": "uuid-or-null",
    "locale": "he-IL"
  },
  "input": {
    "text": "Warm, melancholy music with organic instrumentation",
    "audio_job_id": null,
    "track_ids": [],
    "feedback": null,
    "export": null
  },
  "context": {
    "discovery_mode": "balanced",
    "conversation_id": "uuid",
    "connected_providers": ["youtube"],
    "client_timestamp": "ISO-8601"
  }
}
~~~

Allowed `intent` values:

- `text_recommendation`
- `audio_vibe_recommendation`
- `audio_identification`
- `feedback`
- `playlist_export`
- `auth_connection_sync`

## 3.2 RecommendationContext

~~~json
{
  "request_id": "uuid",
  "text": "optional user text",
  "user_profile": {
    "genre_weights": {},
    "mood_weights": {},
    "artist_weights": {},
    "energy_preference": null,
    "novelty_preference": "balanced",
    "profile_version": 1
  },
  "provider_taste": {
    "liked_tracks": [],
    "artists": [],
    "playlists": [],
    "source": []
  },
  "audio_features": {
    "bpm": null,
    "key": null,
    "scale": null,
    "camelot": null,
    "energy": null,
    "genres": [],
    "embedding_id": null,
    "confidence": {}
  },
  "constraints": {
    "language": "he",
    "result_count": 10,
    "discovery_mode": "balanced",
    "excluded_tracks": [],
    "excluded_artists": []
  }
}
~~~

Fields may be empty, but the schema and keys remain stable. A text request and an audio request enter the same recommendation engine after their context has been assembled.

## 3.3 Success response envelope

~~~json
{
  "ok": true,
  "request_id": "uuid",
  "job_id": "uuid-or-null",
  "intent": "text_recommendation",
  "data": {
    "recommendation_session_id": "uuid",
    "summary": "Curator explanation",
    "tracks": [],
    "sequence": [],
    "audio_analysis": null,
    "identification": null,
    "export": null
  },
  "meta": {
    "engine": "new",
    "provider_mode": "direct",
    "latency_ms": 0,
    "fallback_used": false,
    "warnings": []
  }
}
~~~

## 3.4 Error envelope

~~~json
{
  "ok": false,
  "request_id": "uuid",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "User-safe message",
    "retryable": false,
    "details": {}
  }
}
~~~

Never include stack traces, tokens, provider secrets, raw model reasoning, or internal URLs in a client response.

## 3.5 Music Provider Adapter contract

Every provider implementation must normalize to these operations:

~~~text
connect_user(provider, callback_context)
disconnect_user(provider, user_id)
get_connection_status(user_id)
get_user_taste(user_id, provider)
search_tracks(query, filters, limit)
resolve_track(identity_fields)
get_track(track_id)
get_playback_reference(track_id)
create_playlist(user_id, name, description, privacy, idempotency_key)
add_tracks_to_playlist(user_id, playlist_id, track_ids)
revoke_connection(user_id, provider)
~~~

Normalized track fields:

~~~json
{
  "canonical_track_id": "uuid-or-null",
  "provider": "youtube",
  "provider_track_id": "video-id",
  "title": "Track title",
  "artist": "Artist",
  "album": null,
  "isrc": null,
  "duration_ms": null,
  "artwork_url": null,
  "playback": {
    "type": "youtube_iframe",
    "reference": "video-id"
  },
  "metadata_confidence": 0.0,
  "source": "provider-search"
}
~~~

---

# 4. Phase dependency map

| Phase | Required input | Main output | Unlocks |
|---|---|---|---|
| 0. Foundation and decisions | Current repository and accounts | Frozen contracts, security baseline, provider ADR | n8n build |
| 1. Complete n8n skeleton | Contracts and provider mode | Importable workflow JSON with placeholders | Service implementation |
| 2. Data and service foundation | Workflow contracts | PostgreSQL and healthy FastAPI services | RAG and real persistence |
| 3. Knowledge and RAG | Database and service skeleton | Evaluated hybrid retrieval | LangGraph recommendation |
| 4. Recommendation engine | RAG and provider interface | New multimodal-ready recommendation API | Provider/audio integration |
| 5. Provider/auth/playback | Provider ADR and recommendation intents | Real playable tracks and export | Complete product results |
| 6. Audio intelligence | Audio service skeleton and engine context | Identification and audio-conditioned recommendations | Multimodal demo |
| 7. Personalization and sequencing | Feedback tables and real candidates | Feedback-aware ranking and ordered playlist | Personalized demo |
| 8. UI and end-to-end integration | All P0 services | Complete user flows | Release testing |
| 9. Release and submission | Complete P0 flows | Tested deployable submission | Final demo |

---

# 5. Phase 0 — Foundation, security, contracts, and provider decision

## Objective

Create a safe starting point and resolve the provider architecture early enough that YouTube and Spotify work is not duplicated.

## 0.1 Freeze and measure the current baseline

- [ ] **FND-001 P0:** Create a new implementation branch.
- [ ] **FND-002 P0:** Tag or otherwise record the known-good existing version.
- [ ] **FND-003 P0:** Record one successful text recommendation with request, response, latency, and screenshots.
- [ ] **FND-004 P0:** Inventory current Flask routes, AWS resources, Bedrock IDs, Lambda tools, Spotify functions, environment variables, and deployed URLs.
- [ ] **FND-005 P0:** Back up prompts, Bedrock schemas, n8n exports, source knowledge, and configuration templates without secrets.

This is rollback and benchmarking work. It does not preserve the legacy recommendation logic as the new design.

## 0.2 Immediate security repair

- [ ] **SEC-001 P0:** Revoke or rotate the Spotify authorization that appeared in logs.
- [ ] **SEC-002 P0:** Remove logging of access tokens, refresh tokens, authorization headers, cookies, and uploaded audio.
- [ ] **SEC-003 P0:** Scan the working tree and relevant Git history for committed secrets.
- [ ] **SEC-004 P0:** Add or repair `.env.example` with variable names only.
- [ ] **SEC-005 P0:** Add a centralized log-redaction filter.
- [ ] **SEC-006 P0:** Confirm that internal service ports are not exposed to the public internet.

## 0.3 Freeze v1 contracts and boundaries

- [ ] **ARC-001 P0:** Save the request, response, error, RecommendationContext, and normalized-track schemas under `contracts/`.
- [ ] **ARC-002 P0:** Define explicit timeouts and retry rules per service call.
- [ ] **ARC-003 P0:** Define which actions require an idempotency key.
- [ ] **ARC-004 P0:** Define the feature flags listed in Section 2.3.
- [ ] **ARC-005 P0:** Create an architecture ADR stating that n8n orchestrates, LangGraph recommends, and provider adapters isolate external APIs.

## 0.4 MusicAPI.com proof of concept — early decision gate

MusicAPI.com is neither deferred nor assumed. It must earn its role through a short experiment.

### Required tests

- [ ] **PROV-POC-001 P0:** Create a trial project and record available plan limits and credentials required.
- [ ] **PROV-POC-002 P0:** Connect a test user to YouTube/YouTube Music if supported.
- [ ] **PROV-POC-003 P0:** Connect a test user to Spotify if supported and available.
- [ ] **PROV-POC-004 P0:** Search tracks and playlists; verify normalized IDs, artist/title quality, artwork, duration, and ISRC when available.
- [ ] **PROV-POC-005 P0:** Retrieve user-library or taste signals and identify exactly which signals exist per provider.
- [ ] **PROV-POC-006 P0:** Create a test playlist and add tracks on every claimed P0 platform.
- [ ] **PROV-POC-007 P0:** Test disconnect, token refresh, expired authorization, insufficient scope, rate limit, and provider outage behavior.
- [ ] **PROV-POC-008 P0:** Confirm what MusicAPI supplies for playback: embedded player, provider link/ID, or actual media. Do not treat provider IDs as raw audio access.
- [ ] **PROV-POC-009 P0:** Measure request latency and count calls needed for one recommendation and one export.
- [ ] **PROV-POC-010 P0:** Calculate submission usage and realistic first-100-user monthly cost.
- [ ] **PROV-POC-011 P0:** Review terms, data retention, user consent, and whether platform-specific user authorization is still required.

### Decision outcomes

Choose one and create `docs/adr/ADR-002-music-provider-mode.md`:

| Mode | Select when | Architecture |
|---|---|---|
| `musicapi` | Search, taste, playlist writes, error handling, cost, and reliability all pass | All provider operations go through MusicAPI; official playback mechanism remains compliant |
| `hybrid` | MusicAPI is strong for auth/data but a direct API is better for a critical operation | Adapter routes each operation to the chosen backend |
| `direct` | P0 capability, cost, reliability, or terms fail | Direct YouTube-first API; optional direct Spotify adapter |

### Hard rule

MusicAPI's unified authentication does not remove the need to test real user consent, platform permissions, or provider restrictions. YouTube playlist creation and item insertion require authorized OAuth operations in the official API, and Spotify user resources are scope-controlled OAuth resources. The POC must confirm how MusicAPI represents and manages those requirements.

### Timebox

If account approval or a missing capability blocks the POC for more than two focused hours during the submission sprint:

1. Record the blocker.
2. Choose provisional `direct` YouTube mode for P0.
3. Keep the adapter contract unchanged.
4. Continue the POC after the submission-critical path is safe.

## 0.5 Academic requirement mapping

- [ ] **ACA-001 P0:** Create `docs/requirements-traceability.md`.
- [ ] **ACA-002 P0:** Map n8n, LangChain/RAG, LangGraph, PyTorch classifier, local model runtime, external LLM, guardrails, Docker, AWS/EC2, and WebUI to specific Melody components.
- [ ] **ACA-003 P0:** Define five prompt-engineering surfaces and a five-version evaluation log for each.
- [ ] **ACA-004 P0:** Document any approved adaptation from the reference real-estate scenario to the Melody music domain.

## Phase 0 artifacts

~~~text
contracts/request.schema.json
contracts/response.schema.json
contracts/error.schema.json
contracts/recommendation-context.schema.json
contracts/normalized-track.schema.json
docs/adr/ADR-001-orchestration-boundaries.md
docs/adr/ADR-002-music-provider-mode.md
docs/evaluation/baseline.md
docs/requirements-traceability.md
.env.example
~~~

## Phase 0 gate

Phase 0 is complete when:

- the current system can be restored;
- exposed authorization is rotated and token logging is removed;
- the five canonical schemas are reviewed;
- `PROVIDER_MODE` has a documented selected or provisional value;
- the new target route is explicitly distinguished from the legacy benchmark.

---

# 6. Phase 1 — Build the complete n8n workflow architecture

## Objective

Build the full workflow topology before the services are complete. Every branch must exist, use stable contracts, and return a valid mocked response when its downstream service is still a placeholder.

This is the first major implementation phase and the first prompt to give the n8n building agent.

## 1.1 n8n global standards

- [ ] **N8N-001 P0:** Create a project/folder for Melody workflows.
- [ ] **N8N-002 P0:** Configure credentials by reference; never place secret values in Code, Set, or HTTP nodes.
- [ ] **N8N-003 P0:** Use consistent workflow names: `MELODY — WF-### — Name`.
- [ ] **N8N-004 P0:** Add `request_id` to every execution.
- [ ] **N8N-005 P0:** Use pinned schemas and reject unknown critical enum values.
- [ ] **N8N-006 P0:** Define per-node timeouts and bounded retries with exponential backoff only for safe/retryable calls.
- [ ] **N8N-007 P0:** Route every error to `WF-000 Common Error Handler`.
- [ ] **N8N-008 P0:** Add execution metadata: workflow version, provider mode, engine, latency, and fallback state.
- [ ] **N8N-009 P0:** Use idempotency keys for playlist export and any other external write.
- [ ] **N8N-010 P0:** Export all workflows into `workflows/n8n/`.

## 1.2 Workflow topology

~~~mermaid
flowchart TD
    R["WF-001 Main Router"] --> T["WF-002 Recommendation"]
    R --> I["WF-003 Audio Identify"]
    R --> V["WF-004 Audio Vibe"]
    R --> F["WF-005 Feedback"]
    R --> E["WF-006 Playlist Export"]
    T --> G["WF-000 Error Handler"]
    I --> G
    V --> G
    F --> G
    E --> G
~~~

Supporting workflows:

- `WF-007 Knowledge Ingestion`
- `WF-008 Monitoring and Budget`
- `WF-009 Provider Connection Sync`
- `WF-010 Temporary File Cleanup`

## 1.3 WF-000 — Common Error Handler

### Trigger

- Error Trigger for unhandled n8n failures.
- Execute Workflow input for explicit application errors.

### Node order

| # | Node name | n8n type | Responsibility |
|---:|---|---|---|
| 1 | `Error Trigger / Subworkflow Input` | Error Trigger / Execute Workflow Trigger | Receive workflow, node, request ID, error, and retry metadata |
| 2 | `Normalize Error` | Code | Map internal/provider errors to the canonical error schema |
| 3 | `Redact Sensitive Values` | Code | Remove tokens, cookies, headers, uploaded content, stack traces, and internal URLs |
| 4 | `Is Retryable?` | IF | Branch only when error class and operation are safe to retry |
| 5 | `Schedule Retry` | Wait + Execute Workflow | Retry within the caller's defined maximum; never retry non-idempotent writes blindly |
| 6 | `Persist Error Event` | PostgreSQL or placeholder | Store safe error code, request ID, component, and latency |
| 7 | `Alert Required?` | IF | Alert only for repeated provider failure, security event, budget guard, or health failure |
| 8 | `Return Error Envelope` | Set | Return the user-safe canonical error object |

### Acceptance criteria

- A simulated timeout returns `UPSTREAM_TIMEOUT` without secrets.
- A validation error is not retried.
- A provider `429` follows the configured bounded retry policy.
- A playlist write is not duplicated.

## 1.4 WF-001 — Main Request Router

### Purpose

Receive every app action through one stable external contract, enforce guardrails, resolve identity, and route to a complete subworkflow.

### Node order

| # | Node name | n8n type | Responsibility |
|---:|---|---|---|
| 1 | `Melody API Webhook` | Webhook | Receive the canonical request envelope from Flask |
| 2 | `Initialize Execution` | Set | Add server timestamp, workflow version, start time, and request ID if absent |
| 3 | `Validate Request Schema` | Code or JSON Schema validation | Validate API version, intent, identity, body limits, and required fields |
| 4 | `Input Guardrails` | HTTP Request | Call `POST /check/input` with text and context metadata |
| 5 | `Input Allowed?` | IF | Reject invalid, off-topic, abusive, or prompt-injection input with a localized response |
| 6 | `Resolve User or Guest` | PostgreSQL / placeholder | Resolve `user_id` or create/validate `guest_id` |
| 7 | `Load Connection Status` | Execute Workflow | Invoke WF-009 or a placeholder to load connected providers and scopes |
| 8 | `Explicit Intent Available?` | IF | Prefer deterministic UI intent when present |
| 9 | `Classify Ambiguous Intent` | AI Agent or Text Classifier | Use a small/local model only when the client did not send a reliable explicit mode |
| 10 | `Route by Intent` | Switch | Route to WF-002, WF-003, WF-004, WF-005, WF-006, or WF-009 |
| 11 | `Execute Selected Workflow` | Execute Workflow | Wait for the chosen subworkflow result |
| 12 | `Normalize Subworkflow Result` | Set/Code | Map all results to the canonical success/error envelope |
| 13 | `Output Guardrails` | HTTP Request | Validate grounding, track existence fields, and unsupported claims |
| 14 | `Output Allowed?` | IF | Return safe output or flag a controlled review/fallback response |
| 15 | `Record Request Metrics` | PostgreSQL / placeholder | Store latency, workflow, engine, model, provider mode, fallback, and status |
| 16 | `Respond to Webhook` | Respond to Webhook | Return canonical JSON to Flask |

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

## 1.5 WF-002 — Unified Recommendation

### Purpose

Create a recommendation using text, user taste, and optional audio features. This workflow replaces the concept of a text-only recommendation path.

### Input

Canonical request plus optional `audio_job_id` and loaded identity.

### Node order

| # | Node name | n8n type | Responsibility |
|---:|---|---|---|
| 1 | `Recommendation Input` | Execute Workflow Trigger | Receive router context |
| 2 | `Load Materialized Taste Profile` | PostgreSQL / placeholder | Load weighted preferences and discovery mode |
| 3 | `Load Provider Taste Signals` | HTTP/Execute Workflow / placeholder | Fetch cached liked tracks, artists, and playlist signals when authorized |
| 4 | `Load Audio Features` | PostgreSQL / placeholder | Load analysis if `audio_job_id` is present |
| 5 | `Assemble RecommendationContext` | Code | Merge text, profile, provider taste, audio, exclusions, and constraints |
| 6 | `Extract Music Constraints` | Information Extractor | Produce structured mood, genre, era, instrumentation, energy, and novelty constraints without inventing absent values |
| 7 | `Recommendation Planning Agent` | AI Agent | Produce a structured read-only request plan; it may inspect capability, genre-taxonomy, and connection-status tools, but receives no external write tools |
| 8 | `Call Recommendation Service` | HTTP Request | Deterministically call `POST /recommendations/run` with the complete context and optional validated plan |
| 9 | `Recommendation Valid?` | IF | Require real provider candidates, scores, and valid schema |
| 10 | `Optional Explicit Legacy Fallback` | IF + HTTP | Only if feature flag allows and failure is eligible; record fallback |
| 11 | `Persist Session and Candidates` | PostgreSQL / placeholder | Store input context, selected tracks, scores, models, latency, and engine |
| 12 | `Return Recommendation Result` | Set | Return structured tracks, sequence, explanation, and metadata |

### Placeholder behavior in Phase 1

Until the Recommendation Service exists, Node 8 calls a mock endpoint or Set node that returns 3–5 clearly marked mock tracks matching the response schema. Mock data must never be presented as a completed production recommendation.

### Acceptance criteria

- A text-only request creates a complete RecommendationContext.
- An audio-conditioned request contains both audio features and user taste.
- Guest mode works with an empty profile.
- The workflow does not invent provider track IDs in non-mock mode.

## 1.6 WF-003 — Audio Identification

### Node order

| # | Node name | Type | Responsibility |
|---:|---|---|---|
| 1 | `Identification Input` | Execute Workflow Trigger | Receive temporary file reference and identity |
| 2 | `Validate File Job` | HTTP/PostgreSQL / placeholder | Confirm ownership, MIME, size, duration, and unexpired reference |
| 3 | `Call Recognition Provider` | HTTP Request | Send the clip through the recognition adapter |
| 4 | `Match Confidence Gate` | IF | Separate confident, low-confidence, and no-match results |
| 5 | `Resolve Canonical Track` | HTTP Request / placeholder | Match title/artist/external IDs through Provider Adapter |
| 6 | `Find Playable Reference` | HTTP Request / placeholder | Resolve a YouTube or selected-provider playback ID |
| 7 | `Persist Minimal Result` | PostgreSQL / placeholder | Store derived match metadata and confidence, not raw audio |
| 8 | `Request File Deletion` | Execute Workflow | Invoke WF-010 |
| 9 | `Return Identification` | Set | Return match or honest retry guidance |

### Acceptance criteria

- Confident, low-confidence, and no-match fixtures reach the correct branches.
- Temporary files are deleted on both success and failure.
- Raw audio is not stored in execution logs.

## 1.7 WF-004 — Audio Vibe Recommendation

### Node order

| # | Node name | Type | Responsibility |
|---:|---|---|---|
| 1 | `Audio Vibe Input` | Execute Workflow Trigger | Receive file reference, optional text, and identity |
| 2 | `Validate File Job` | HTTP/PostgreSQL / placeholder | Confirm ownership and upload constraints |
| 3 | `Call Audio Analysis Service` | HTTP Request | Call `POST /audio/analyze` |
| 4 | `Analysis Confidence Gate` | IF | Continue with reliable fields and attach warnings for uncertain fields |
| 5 | `Store Derived Features` | PostgreSQL / placeholder | Store versioned features and confidence |
| 6 | `Create Recommendation Request` | Code | Add `audio_job_id`, retain user text, and set intent for unified recommendation |
| 7 | `Execute WF-002 Recommendation` | Execute Workflow | Run the same personal recommendation engine with audio context |
| 8 | `Request File Deletion` | Execute Workflow | Invoke WF-010 |
| 9 | `Return Audio-Conditioned Result` | Set | Return analysis plus recommendations |

### Acceptance criteria

- The audio features are passed into WF-002 instead of becoming a separate shallow recommendation engine.
- User taste remains present in the final context.
- Uncertain BPM/key values are not fabricated.

## 1.8 WF-005 — Feedback and Preference Update

### Node order

| # | Node name | Type | Responsibility |
|---:|---|---|---|
| 1 | `Feedback Input` | Execute Workflow Trigger | Receive session, track, action, and identity |
| 2 | `Validate Ownership and Action` | PostgreSQL / placeholder | Confirm session belongs to user/guest and action is allowed |
| 3 | `Deduplicate Event` | PostgreSQL / placeholder | Apply event idempotency/deduplication rule |
| 4 | `Insert Immutable Feedback Event` | PostgreSQL / placeholder | Store like, dislike, skip, play, or export event |
| 5 | `Update Materialized Profile` | HTTP Request / placeholder | Apply Profile v1 weighted update |
| 6 | `Return Current Feedback State` | Set | Return action state and new profile version |

### Acceptance criteria

- Duplicate clicks do not create unintended duplicate events.
- A Like and Dislike update profile weights in opposite directions.
- The next WF-002 call loads the new profile version.

## 1.9 WF-006 — Provider-Agnostic Playlist Export

### Node order

| # | Node name | Type | Responsibility |
|---:|---|---|---|
| 1 | `Export Input` | Execute Workflow Trigger | Receive provider, ordered track IDs, name, privacy, and idempotency key |
| 2 | `Validate Export Ownership` | PostgreSQL / placeholder | Confirm recommendation session and selected tracks |
| 3 | `Check Existing Idempotent Export` | PostgreSQL / placeholder | Return prior success when the same key was already completed |
| 4 | `Check Provider Connection and Scope` | Execute Workflow | Invoke WF-009 |
| 5 | `Authorization Sufficient?` | IF | Return `AUTHORIZATION_REQUIRED` with an authorization action when scope is missing |
| 6 | `Resolve Provider Track IDs` | HTTP Request / placeholder | Ensure each canonical track maps to the chosen provider |
| 7 | `Create Playlist` | HTTP Request | Use Provider Adapter based on `PROVIDER_MODE` |
| 8 | `Insert Tracks in Order` | Loop Over Items + HTTP Request | Add selected tracks, preserving Smart Sequencer order |
| 9 | `Handle Partial Failure` | IF/Code | Record added and failed items; retry only safe failed operations |
| 10 | `Store Export Result` | PostgreSQL / placeholder | Store provider playlist ID, URL, status, and idempotency key |
| 11 | `Return Export Result` | Set | Return success, partial success, or actionable failure |

### Acceptance criteria

- Repeated clicks with the same key create one playlist.
- Track order is preserved.
- Missing OAuth scope never causes a blind retry loop.
- Partial failure is visible and recoverable.

## 1.10 WF-007 — Knowledge Ingestion

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

~~~text
workflows/n8n/WF-000-common-error-handler.json
workflows/n8n/WF-001-main-request-router.json
workflows/n8n/WF-002-unified-recommendation.json
workflows/n8n/WF-003-audio-identification.json
workflows/n8n/WF-004-audio-vibe-recommendation.json
workflows/n8n/WF-005-feedback.json
workflows/n8n/WF-006-playlist-export.json
workflows/n8n/WF-007-knowledge-ingestion.json
workflows/n8n/WF-008-monitoring-budget.json
workflows/n8n/WF-009-provider-connection-sync.json
workflows/n8n/WF-010-temporary-file-cleanup.json
docs/n8n/workflow-contracts.md
docs/n8n/credentials-and-environment.md
~~~

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

## Objective

Replace Phase 1 placeholders with real persistence and healthy service boundaries before implementing complex AI logic.

## 2.1 Repository structure

- [ ] **REP-001 P0:** Create the incremental target folders without moving unrelated working code.

~~~text
Melody/
├── app.py
├── templates/
├── static/
├── contracts/
├── services/
│   ├── recommendation/
│   ├── rag/
│   ├── audio/
│   ├── guardrails/
│   └── provider_gateway/
├── db/
│   ├── migrations/
│   ├── seeds/
│   └── models/
├── workflows/
│   └── n8n/
├── infra/
│   ├── docker-compose.yml
│   ├── caddy/
│   └── backup/
├── data_prep/
├── data/
├── docs/
│   ├── adr/
│   ├── architecture/
│   ├── evaluation/
│   ├── n8n/
│   ├── prompts/
│   └── demo/
├── tests/
│   ├── contract/
│   ├── integration/
│   └── e2e/
├── .env.example
├── MELODY_AI_ORDERED_EXECUTION_PLAN.md
└── README.md
~~~

## 2.2 Docker Compose foundation

- [ ] **INF-001 P0:** Add `postgres-pgvector`.
- [ ] **INF-002 P0:** Add `n8n` with persistent volume and protected editor access.
- [ ] **INF-003 P0:** Add `recommendation-service`.
- [ ] **INF-004 P0:** Add independently deployable `rag-service` so the RAG and LangGraph responsibilities remain visible and separately testable.
- [ ] **INF-005 P0:** Add `audio-service`.
- [ ] **INF-006 P0:** Add `guardrails-service`.
- [ ] **INF-007 P0:** Add `provider-gateway` when provider logic is not implemented directly inside n8n.
- [ ] **INF-008 P0:** Add `ollama` or a `llama.cpp` model server for the local-model requirement and cheap routing tasks.
- [ ] **INF-009 P1:** Add Redis only if asynchronous-job measurement proves it is necessary.
- [ ] **INF-010 P0:** Add health checks, dependency ordering, restart policies, named networks, and resource limits.

Initial services:

~~~text
melody-web
n8n
recommendation-service
rag-service
audio-service
guardrails-service
provider-gateway
postgres-pgvector
ollama-or-llamacpp
~~~

## 2.3 Database migrations

- [ ] **DB-001 P0:** Initialize Alembic.
- [ ] **DB-002 P0:** Enable `vector` and required PostgreSQL extensions.
- [ ] **DB-003 P0:** Create UUID-based identities and UTC timestamps.
- [ ] **DB-004 P0:** Add indexes for request ID, user ID, provider IDs, feedback session, vector search, full-text search, and idempotency keys.
- [ ] **DB-005 P0:** Add migration upgrade/downgrade smoke tests.

Required tables:

| Table | Required fields/purpose |
|---|---|
| `users` | Identity, locale, account state, created/deleted timestamps |
| `guest_sessions` | Expiring guest identity and migration-to-user reference |
| `oauth_accounts` | Provider, encrypted token material/reference, scopes, expiry, revocation state |
| `user_preferences` | Materialized versioned preference profile |
| `feedback_events` | Immutable interaction events with session and candidate context |
| `recommendation_sessions` | Request context, engine, result, fallback, latency, status |
| `recommendation_candidates` | Candidate identity, feature values, component scores, final rank |
| `tracks` | Canonical identity with normalized metadata |
| `track_provider_ids` | Provider-specific IDs, links, and confidence |
| `track_audio_features` | BPM, key, Camelot, energy, source, confidence, model version |
| `genre_nodes` | Parent genres and subgenres |
| `genre_edges` | Parent, related, influence, and similarity relations |
| `knowledge_documents` | Source document and version metadata |
| `knowledge_chunks` | Chunk text, full-text data, metadata, embedding, ingestion version |
| `playlist_exports` | Provider, playlist ID, URL, idempotency key, partial-failure state |
| `audio_jobs` | Temporary object reference, derived features, state, cleanup timestamp |
| `model_usage` | Provider/model, tokens, latency, estimated cost, cache hit |
| `jobs` | Asynchronous job state and safe error code |
| `audit_events` | Security-sensitive actions without credential values |

Rules:

- Provider IDs are not internal primary keys.
- Embeddings, audio features, profiles, prompts, and rankers are versioned.
- Raw audio is temporary and is not stored in the database.
- OAuth token values are encrypted or stored in an approved secret store; never plaintext columns.
- Deletion requirements are implemented as true deletion where promised to the user.

## 2.4 FastAPI service skeletons

Each service must include:

- Pydantic models generated from or validated against `contracts/`.
- `/health/live` and `/health/ready`.
- request-ID propagation.
- structured redacted logging.
- explicit dependency timeouts.
- user-safe error mapping.
- unit test and Dockerfile.

Endpoints:

| Service | Endpoint | Phase 2 behavior |
|---|---|---|
| Recommendation | `POST /recommendations/run` | Validated fixture response |
| Recommendation | `POST /profiles/update` | Deterministic weighted-profile stub |
| RAG | `POST /rag/retrieve` | Validated fixture evidence package |
| RAG | `POST /rag/ingest` | Disabled except for authenticated internal ingestion tests |
| Audio | `POST /audio/analyze` | Validate a test file and return fixture features |
| Audio | `POST /audio/identify` | Recognition-adapter fixture |
| Guardrails | `POST /check/input` | Initial rules and topic/prompt-injection checks |
| Guardrails | `POST /check/output` | Initial schema and unsupported-claim checks |
| Provider Gateway | `POST /providers/search` | Selected adapter fixture |
| Provider Gateway | `POST /providers/playlists` | Disabled fixture until Phase 5 |

## 2.5 Guardrails foundation

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

- [ ] **N8N-REAL-001 P0:** Connect identity/profile nodes to PostgreSQL.
- [ ] **N8N-REAL-002 P0:** Connect WF-000 error persistence.
- [ ] **N8N-REAL-003 P0:** Connect WF-001 input/output guardrail nodes.
- [ ] **N8N-REAL-004 P0:** Connect WF-008 to real usage and health tables.
- [ ] **N8N-REAL-005 P0:** Run contract tests between n8n and every service skeleton.

## Phase 2 gate

- `docker compose up` starts every required service.
- All readiness endpoints pass.
- Database migrations apply to an empty database.
- A profile, feedback event, recommendation session, and vector test row can be written and read.
- n8n calls the real guardrails and service fixture endpoints with the final contracts.
- No placeholder database nodes remain in WF-000, WF-001, WF-005, WF-008, or WF-009.

---

# 8. Phase 3 — Knowledge preparation, local models, and hybrid RAG

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

## 3.2 Dataset inventory and legal/source metadata

- [ ] **RAG-001 P0:** Inventory every dataset, scraper output, genre document, review collection, and current AWS source.
- [ ] **RAG-002 P0:** Record source, license/usage status, retrieval domain, and allowed runtime use.
- [ ] **RAG-003 P0:** Remove empty text, exact duplicates, near duplicates, and malformed metadata.
- [ ] **RAG-004 P0:** Define stable source-document IDs and ingestion versions.
- [ ] **RAG-005 P0:** Preserve the original source reference for evaluation and internal grounding.

## 3.3 Chunking and ingestion

- [ ] **RAG-006 P0:** Chunk genre Markdown by headings and semantic sections.
- [ ] **RAG-007 P0:** Chunk reviews by coherent passages, not fixed character count alone.
- [ ] **RAG-008 P0:** Attach domain, source, artist, album, genre, language, era, and version metadata when present.
- [ ] **RAG-009 P0:** Create and populate `genre_nodes` and `genre_edges`.
- [ ] **RAG-010 P0:** Stage ingestion before publishing a version.
- [ ] **RAG-011 P0:** Run WF-007 smoke queries before marking a version active.

## 3.4 Embedding-model decision

Benchmark at least two feasible multilingual models, for example multilingual-e5 and BGE-M3 or a smaller equivalent.

Evaluate:

- Hebrew and English retrieval quality;
- CPU latency and RAM;
- embedding dimension and storage;
- license and redistribution terms;
- compatibility with local Hugging Face inference.

- [ ] **RAG-EMB-001 P0:** Build 20 bilingual retrieval queries.
- [ ] **RAG-EMB-002 P0:** Benchmark candidates on the same indexed subset.
- [ ] **RAG-EMB-003 P0:** Record the decision in `ADR-003-embedding-model.md`.

## 3.5 Hybrid retrieval pipeline

Implement in this order:

1. Dense vector retrieval.
2. PostgreSQL full-text retrieval.
3. Exact-name and metadata filters.
4. One-hop genre graph expansion.
5. Reciprocal Rank Fusion.
6. Document reranking over approximately 20 initial chunks.
7. Select 5–8 chunks for expensive generation.

Starting RRF implementation:

~~~text
rrf_score(document) = Σ 1 / (k + rank_in_result_list)
~~~

Treat `k`, candidate counts, and final chunk counts as evaluation parameters, not permanent truths.

## 3.6 Document Reranker

The Document Reranker is separate from the Track Reranker.

Input:

~~~text
normalized retrieval query + knowledge chunks
~~~

Output:

~~~text
relevance score + ordered chunk IDs + model version + latency
~~~

- [ ] **RAG-RERANK-001 P0:** Benchmark a multilingual local reranker.
- [ ] **RAG-RERANK-002 P0:** Compare against a no-reranker baseline.
- [ ] **RAG-RERANK-003 P0:** Keep an API reranker as an optional measured alternative, not an implicit dependency.

## 3.7 Local model runtime

Use Ollama or llama.cpp for at least one real, measured project responsibility:

- intent classification for ambiguous requests;
- structured music-constraint extraction;
- simple query normalization;
- local RAG answer baseline;
- low-cost prompt experiment.

Do not use a local model for deterministic validation, OAuth, database writes, or sequencing.

- [ ] **LOCAL-001 P0:** Select a small local model compatible with available CPU/RAM.
- [ ] **LOCAL-002 P0:** Expose it behind a stable internal adapter.
- [ ] **LOCAL-003 P0:** Measure latency, memory, and output-schema pass rate.
- [ ] **LOCAL-004 P0:** Document the exact task it owns in the final system.

## 3.8 Golden evaluation set

Create at least 25–40 queries covering:

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

| Surface | Component | Primary measure |
|---|---|---|
| PE-1 | n8n Information Extractor | Schema accuracy and missing-field honesty |
| PE-2 | n8n AI Agent/tool descriptions | Correct tool selection and no unnecessary calls |
| PE-3 | RAG context-grounded generation | Grounding, useful citations/evidence, no invention |
| PE-4 | Input/output Guardrails prompts | False positive and false negative rate |
| PE-5 | Local-model system prompt | On-topic rate, schema pass rate, latency |
| PE-6 optional | Final curator explanation | Musical quality, concision, and track-grounding |

For each version:

1. Save the full prompt.
2. Use the same minimum 10-case test set.
3. Record the targeted failure from the previous version.
4. Record outputs or structured evaluation results.
5. Measure improvement and regressions.
6. End with the final prompt and design justification.

## Phase 3 artifacts

~~~text
services/rag/retrieval/
services/rag/reranking/document_reranker.py
data_prep/ingest_knowledge.py
data_prep/build_genre_graph.py
docs/evaluation/rag-golden-set.jsonl
docs/evaluation/rag-baseline.md
docs/prompts/prompt-engineering-log.md
docs/adr/ADR-003-embedding-model.md
~~~

## Phase 3 gate

- A representative knowledge subset is versioned in PostgreSQL/pgvector.
- Dense, full-text, filters, genre expansion, RRF, and reranking are independently testable.
- Golden queries return relevant chunks with recorded metrics.
- The selected local model performs one real task with measured results.
- Prompt-log Version 1 exists for at least five surfaces.

---

# 9. Phase 4 — New LangGraph recommendation engine

## Objective

Create the actual new recommendation system that combines user text, personal taste, provider taste, and optional audio features.

## 4.1 LangGraph state

~~~text
request_id
user_query
audio_features
user_profile
provider_taste
constraints
retrieval_query
genre_chunks
review_chunks
expanded_genres
fused_chunks
reranked_chunks
retrieval_confidence
rewrite_count
search_intents
provider_candidates
ranked_tracks
sequence
final_answer
warnings
usage_metrics
~~~

## 4.2 Required graph nodes

Implement and test in this order:

1. `validate_context`
2. `normalize_input`
3. `load_or_accept_user_profile`
4. `build_retrieval_query`
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

Example:

~~~json
{
  "queries": [
    {
      "text": "warm intimate indie folk acoustic melancholic",
      "genres": ["indie folk"],
      "exclude_artists": [],
      "target_energy": 0.35,
      "novelty": "balanced"
    }
  ],
  "target_candidate_count": 30
}
~~~

The model may describe desired music, but the Provider Adapter supplies real IDs and metadata.

## 4.7 Track Reranker v1

The Track Reranker is separate from the Document Reranker.

Initial transparent score:

~~~text
score =
  0.30 * semantic_fit +
  0.20 * genre_fit +
  0.15 * user_preference +
  0.10 * audio_feature_fit +
  0.10 * novelty +
  0.05 * energy_fit +
  0.05 * bpm_fit +
  0.05 * metadata_confidence
~~~

When no audio input exists, redistribute or normalize the available weights; do not set missing signals to fabricated values.

Store every component score for explainability and future learning.

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

## 4.9 Model routing

~~~text
deterministic validation, storage, OAuth, sequencing -> code
embeddings and reranking -> local specialized models
ambiguous intent or structured extraction -> small/local model
complex cross-genre reasoning and final explanation -> heavy external model
~~~

For every model call store provider, model, input/output token counts if available, latency, estimated cost, cache hit, request ID, and success/failure.

## 4.10 Legacy comparison and cutover

- [ ] **REC-LEG-001 P0:** Run at least 10 shared prompts through the existing Bedrock route and the new route.
- [ ] **REC-LEG-002 P0:** Compare retrieval relevance, playable-track rate, latency, cost, diversity, and explanation quality.
- [ ] **REC-LEG-003 P0:** Make the new engine default only after the Phase 5 real-provider gate and Phase 8 UI gate pass.
- [ ] **REC-LEG-004 P1:** Remove automatic legacy fallback after release stability is established.

## Phase 4 gate

- `POST /recommendations/run` accepts the full RecommendationContext.
- Text-only, profile-aware, and audio-feature-fixture tests all pass.
- The graph performs at most one rewrite.
- Provider search intents are stable; normalized candidate fixtures pass the same adapter contract that Phase 5 will use for real tracks.
- Track component scores and model usage are stored for fixture-based contract tests.
- `sequence_tracks` uses a versioned deterministic relevance-order baseline until Phase 7 replaces it with the Smart Sequencer.
- WF-002 uses the real Recommendation Service; its service-call placeholder is removed, while the provider fixture remains explicitly labeled and traced to Phase 5.
- The new engine is distinguishable from the legacy benchmark in logs and test metadata, but public cutover waits for real-provider and UI gates.

---

# 10. Phase 5 — Provider implementation, authentication, playback, and export

## Objective

Implement the provider mode selected in Phase 0 and return real, playable track identities without coupling the recommendation engine to MusicAPI, YouTube, or Spotify.

## 5.1 Implement the chosen provider mode

- [ ] **PROV-001 P0:** Implement every adapter operation required by the selected Phase 0 mode.
- [ ] **PROV-002 P0:** Add normalized error codes for authorization, quota, rate limit, missing item, unavailable item, and provider outage.
- [ ] **PROV-003 P0:** Add provider-level timeouts, circuit breakers, and safe retries.
- [ ] **PROV-004 P0:** Cache stable metadata and repeated searches with explicit TTLs.
- [ ] **PROV-005 P0:** Store the data source and confidence for every normalized field.
- [ ] **PROV-006 P0:** Add contract tests that run unchanged across MusicAPI and direct adapters.

## 5.2 Google identity and YouTube authorization

- [ ] **AUTH-001 P0:** Use Google OpenID Connect for basic application identity.
- [ ] **AUTH-002 P0:** Use Authorization Code Flow on the server.
- [ ] **AUTH-003 P0:** Validate `state`, `nonce`, callback origin, and session binding.
- [ ] **AUTH-004 P0:** Request basic identity scopes first.
- [ ] **AUTH-005 P0:** Request YouTube write scopes incrementally only when export is selected.
- [ ] **AUTH-006 P0:** Encrypt stored tokens or token references.
- [ ] **AUTH-007 P1:** Add disconnect, revocation, and user-data deletion flows.

If MusicAPI owns the external OAuth exchange, Melody must still validate its own application session and securely map the returned provider connection to the correct user.

## 5.3 YouTube-first discovery

YouTube is video-centric and does not provide a reliable official watch-history feed for this product. Build taste from signals the authorized API actually exposes, such as relevant liked music videos, subscriptions, user-selected playlists, and Melody's own feedback.

- [ ] **YT-001 P0:** Search with music-oriented filters and transparent official-content heuristics.
- [ ] **YT-002 P0:** Prefer official artist channels, topic channels, official audio, or official music videos when confidence is adequate.
- [ ] **YT-003 P0:** Normalize artist/title from noisy video metadata and store confidence.
- [ ] **YT-004 P0:** Deduplicate alternate uploads, live versions, covers, and remixes without incorrectly merging distinct recordings.
- [ ] **YT-005 P0:** Record quota cost for every API method.
- [ ] **YT-006 P0:** Cache repeat searches and metadata lookups.

## 5.4 Playback

- [ ] **PLAY-001 P0:** Render the official YouTube IFrame Player using returned video IDs.
- [ ] **PLAY-002 P0:** Handle unavailable, region-blocked, embedding-disabled, and removed videos.
- [ ] **PLAY-003 P0:** Do not download, isolate, proxy, or modify YouTube audio.
- [ ] **PLAY-004 P0:** Do not promise ad-free playback or assume OAuth implies YouTube Premium behavior.
- [ ] **PLAY-005 P0:** Provide a normal provider link when embedding is unavailable.

## 5.5 Playlist export

For direct YouTube mode:

1. `playlists.insert` creates the playlist after explicit confirmation.
2. `playlistItems.insert` adds each video in Smart Sequencer order.
3. OAuth authorization and quota are checked before writes.
4. Idempotency prevents duplicate playlists.

For MusicAPI or hybrid mode, the Provider Adapter must produce the same externally visible result and failure states.

- [ ] **EXPORT-001 P0:** Replace all WF-006 provider placeholders.
- [ ] **EXPORT-002 P0:** Test success, partial failure, expired authorization, insufficient scope, quota error, and repeated click.
- [ ] **EXPORT-003 P0:** Store export history and provider playlist URL.

## 5.6 Optional Spotify

- [ ] **SPOT-001 P1:** Keep Spotify login optional.
- [ ] **SPOT-002 P1:** Revalidate current development-mode, endpoint, and user-limit restrictions before depending on any feature.
- [ ] **SPOT-003 P1:** Implement search/taste/export only through the normalized adapter.
- [ ] **SPOT-004 P1:** Never log or expose Spotify tokens.

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

- Search returns real normalized tracks with playable references.
- At least 90% of selected demo tracks are playable in the target test region; unavailable results are replaced or clearly handled.
- OAuth is incremental and session-bound.
- A playlist can be created and populated for a test user without duplication.
- WF-006 and WF-009 contain no P0 provider placeholders.
- MusicAPI/direct implementation details do not leak into Recommendation Service contracts.

---

# 11. Phase 6 — Audio identification and audio-conditioned recommendation

## Objective

Implement two distinct user actions:

1. Identify this recording or humming.
2. Recommend music with a similar vibe.

Do not confuse recognition with audio-feature extraction.

## 6.1 Upload and recording pipeline

- [ ] **AUD-UP-001 P0:** Add browser recording and file upload with explicit mode selection.
- [ ] **AUD-UP-002 P0:** Enforce client hints and server-side size/duration limits.
- [ ] **AUD-UP-003 P0:** Detect actual MIME/container type; do not trust filename extension.
- [ ] **AUD-UP-004 P0:** Store under a random server-side object ID in approved temporary storage.
- [ ] **AUD-UP-005 P0:** Convert through an argument-safe FFmpeg call without shell interpolation.
- [ ] **AUD-UP-006 P0:** Add cleanup on success, failure, timeout, and scheduled expiry.
- [ ] **AUD-UP-007 P0:** Never log raw bytes, local temporary paths, or original filenames.

Initial constraints must be explicit configuration values, for example maximum upload size, maximum processed duration, allowed formats, and retention minutes.

## 6.2 Audio analysis service

Tool allocation:

| Need | Tool |
|---|---|
| Decode/convert | FFmpeg |
| Waveform and spectrogram | torchaudio/PyTorch |
| BPM | Essentia `RhythmExtractor2013` |
| Key and scale | Essentia `KeyExtractor` |
| Camelot conversion | Deterministic code |
| Energy | Signal features and/or small model |
| Genre/tags | Pretrained or fine-tuned PyTorch model |
| Audio embedding | PyTorch/Hugging Face model |
| Audio-text shared embedding | CLAP POC, nonblocking |

Required `POST /audio/analyze` output:

~~~json
{
  "job_id": "uuid",
  "bpm": 92.4,
  "bpm_confidence": 0.81,
  "key": "A",
  "scale": "minor",
  "key_confidence": 0.72,
  "camelot": "8A",
  "energy": 0.34,
  "genres": [
    {"name": "indie folk", "score": 0.64}
  ],
  "embedding_id": "optional-reference",
  "duration_processed": 18.2,
  "model_versions": {},
  "warnings": []
}
~~~

## 6.3 PyTorch classifier deliverable

The audio genre/tag or energy model is Melody's domain adaptation of the course's PyTorch classifier requirement.

- [ ] **ML-AUD-001 P0:** Define labels, confidence behavior, and success metric.
- [ ] **ML-AUD-002 P0:** Inventory or create a legally usable labeled dataset and split it into train/validation/test without leakage.
- [ ] **ML-AUD-003 P0:** Use an appropriate pretrained audio model or spectrogram-based network; training from scratch is not required.
- [ ] **ML-AUD-004 P0:** Document preprocessing, augmentation, training loop, hyperparameters, and model version.
- [ ] **ML-AUD-005 P0:** Report accuracy/F1 and confusion matrix on the held-out test set.
- [ ] **ML-AUD-006 P0:** Return `uncertain` or low-confidence scores rather than a forced label.
- [ ] **ML-AUD-007 P0:** Package inference in the Audio Service and save reproducible training instructions/checkpoint policy.

If the submission window is too short for meaningful fine-tuning, use a pretrained model for the P0 inference path and present the reproducible fine-tuning experiment honestly as partial work. Do not report unmeasured accuracy.

## 6.4 Recognition provider decision

ACRCloud is the leading candidate, but it must pass a POC for both original recordings and humming.

- [ ] **REC-ID-001 P0:** Create a test set of clean original clips, noisy clips, humming clips, and no-match clips.
- [ ] **REC-ID-002 P0:** Test ACRCloud or the selected provider using the same set.
- [ ] **REC-ID-003 P0:** Measure match rate, false positives, latency, limits, and cost.
- [ ] **REC-ID-004 P0:** Verify which external IDs are returned and how they map through Provider Adapter.
- [ ] **REC-ID-005 P0:** Define confidence thresholds for match, low confidence, and no match.
- [ ] **REC-ID-006 P0:** Record the decision in `ADR-004-recognition-provider.md`.

Required `POST /audio/identify` output:

~~~json
{
  "matched": true,
  "title": "Track title",
  "artist": "Artist",
  "confidence": 0.91,
  "is_humming_match": false,
  "external_ids": {},
  "provider": "provider-name",
  "warnings": []
}
~~~

## 6.5 Audio-conditioned RAG integration

Baseline multimodal path:

~~~text
audio clip
  -> BPM/key/energy/genre/embedding
  -> confidence-weighted structured features
  -> RecommendationContext with user text and user profile
  -> LangGraph retrieval and provider search
  -> personal Track Reranker and Smart Sequencer
~~~

- [ ] **AUD-RAG-001 P0:** Map audio features to normalized query constraints.
- [ ] **AUD-RAG-002 P0:** Down-weight uncertain features.
- [ ] **AUD-RAG-003 P0:** Test audio-only, audio-plus-text, and audio-plus-personal-profile contexts.
- [ ] **AUD-RAG-004 P0:** Verify that audio context changes retrieval/ranking in a measurable way.
- [ ] **AUD-RAG-005 P0:** Replace all P0 WF-004 placeholders.

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

- An uploaded clip is safely processed and deleted.
- BPM, key, energy, and genre/tag outputs include confidence and model versions.
- Original-recording identification returns a match or an honest failure.
- Humming is marked complete only if it passes the POC threshold.
- Audio vibe input enters the same recommendation engine with user taste preserved.
- WF-003 and WF-004 have no P0 placeholders.

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

- [ ] **PERS-001 P0:** Make feedback events immutable.
- [ ] **PERS-002 P0:** Define deduplication and repeated-action behavior.
- [ ] **PERS-003 P0:** Permit guest feedback and migrate it on sign-in where appropriate.

## 7.2 Preference Profile v1

Use an interpretable materialized profile:

- Like increases matching genre, mood, artist, and energy-range weights.
- Dislike decreases them more cautiously to avoid overfitting one click.
- Skip is a weak negative only when context supports that interpretation.
- Old evidence decays gradually.
- Explicit onboarding preferences and direct user controls have higher confidence than inferred signals.
- Discovery mode controls how strongly the profile influences ranking.

- [ ] **PERS-004 P0:** Implement deterministic profile update logic.
- [ ] **PERS-005 P0:** Version every profile update.
- [ ] **PERS-006 P0:** Add unit tests for like, dislike, decay, conflict, and guest migration.
- [ ] **PERS-007 P0:** Replace WF-005 profile placeholder.

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

- [ ] **RANK-001 P0:** Implement the transparent v1 score from Phase 4.
- [ ] **RANK-002 P0:** Store component scores per candidate.
- [ ] **RANK-003 P0:** Apply profile weights and discovery mode.
- [ ] **RANK-004 P0:** Add artist/track deduplication and diversity constraints.
- [ ] **RANK-005 P0:** Add deterministic tests with known candidate fixtures.
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

- [ ] **SEQ-001 P0:** Implement Camelot mapping and distance.
- [ ] **SEQ-002 P0:** Implement transition cost with configurable weights.
- [ ] **SEQ-003 P0:** Implement deterministic ordering for 8–12 tracks.
- [ ] **SEQ-004 P0:** Add fallback for missing BPM/key.
- [ ] **SEQ-005 P0:** Store the selected order and transition reasons.

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

## Phase 7 gate

- A Like or Dislike creates one event and updates the profile version.
- The next recommendation uses the updated profile and exposes changed component scores internally.
- Safe, Balanced, and Adventurous modes produce measurably different novelty behavior.
- An 8–12-track result is deterministically sequenced.
- Feedback and sequencing failures do not corrupt the base recommendation session.

---

# 13. Phase 8 — Flask UI and end-to-end product integration

## Objective

Connect the complete backend flows to one understandable product experience.

## 8.1 Flask API boundary

Required routes:

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/v1/requests` | Send canonical actions to WF-001 |
| POST | `/api/v1/audio/uploads` | Create a safe temporary audio job |
| GET | `/api/v1/jobs/{job_id}` | Read asynchronous job state |
| POST | `/api/v1/feedback` | Submit Like/Dislike/Skip |
| POST | `/api/v1/playlists/export` | Start confirmed export |
| GET | `/api/v1/auth/status` | Read connected providers and scopes |
| GET | `/auth/google/start` | Start login or incremental authorization |
| GET | `/auth/google/callback` | Complete server-side callback |
| POST | `/auth/{provider}/disconnect` | Disconnect and revoke |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Dependency readiness |

Flask must not accept provider tokens from browser JavaScript.

## 8.2 UI modes

- [ ] **UI-001 P0:** Text discovery.
- [ ] **UI-002 P0:** Audio recording/upload with explicit `Identify` versus `Similar vibe` choice.
- [ ] **UI-003 P0:** Guest mode and Google sign-in.
- [ ] **UI-004 P0:** Provider-connection status and contextual authorization prompt.
- [ ] **UI-005 P0:** Structured recommendation cards with real playback references.
- [ ] **UI-006 P0:** Like/Dislike controls with optimistic state and safe rollback on failure.
- [ ] **UI-007 P0:** Discovery-mode control: Safe, Balanced, Adventurous.
- [ ] **UI-008 P0:** Smart Sequence display.
- [ ] **UI-009 P0:** Explicit playlist-export confirmation.
- [ ] **UI-010 P0:** Loading, retry, partial-result, low-confidence, and authorization-required states.

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

- [ ] **INT-001 P0:** Search all n8n JSON and code for `PLACEHOLDER`.
- [ ] **INT-002 P0:** Remove or disable every P0 placeholder.
- [ ] **INT-003 P0:** Keep only explicitly labeled P1/P2 stubs behind disabled feature flags.
- [ ] **INT-004 P0:** Run the full UI flows from a clean browser session.

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

~~~text
caddy
melody-web
n8n
recommendation-service
audio-service
guardrails-service
provider-gateway
postgres-pgvector
ollama-or-llamacpp
backup-job
~~~

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

| Date | Primary scope | Required gate |
|---|---|---|
| July 21 | Phase 0: baseline, security, contracts, MusicAPI POC, academic mapping | Provider mode provisional/final; schemas frozen; security baseline safe |
| July 22 | Phase 1: all n8n workflows with contracts and placeholders | Clean n8n import; every branch and guardrail fixture works |
| July 23 | Phase 2: Compose, PostgreSQL/pgvector, FastAPI skeletons | Healthy stack; migrations and contract tests pass |
| July 24 | Phase 3: representative ingestion, hybrid retrieval, local model | Golden queries return relevant reranked chunks |
| July 25 | Phase 4: LangGraph, bounded retry, provider-ready search intents | New engine ranks schema-valid candidate fixtures through WF-002 |
| July 26 | Phase 5: selected provider, auth, player, export | Real playable tracks and one real test playlist |
| July 27 | Phase 6: audio analysis and recognition | Audio vibe and original identification work; humming status explicit |
| July 28 | Phase 7 + Phase 8: feedback, profile, ranker, sequencer, UI | Feedback changes next ranking; full UI flows work |
| July 29 | Phase 9: E2E, security, metrics, docs, prompts, demo | Two complete rehearsals succeed |
| July 30 | Buffer, blocker fixes, release freeze, submission | Tagged, backed up, reproducible submission |

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

| Risk | P0 fallback | What remains demonstrable |
|---|---|---|
| MusicAPI is blocked or incomplete | Direct YouTube adapter | Provider abstraction, real playback, OAuth, export |
| Local pgvector RAG is unstable | Bedrock Knowledge Base behind a temporary retrieval adapter, plus explicit reranking | n8n, new RecommendationContext, LangGraph, profile/audio context, track ranking |
| Heavy model fails | Alternate configured model with structured output | Model routing and complete flow |
| Local model is too slow | Use it only for an isolated measured task; small external model for runtime | Local-model course evidence and stable product |
| Humming accuracy is weak | Demonstrate original recording; mark humming as POC | Honest recognition path |
| Audio classifier fine-tuning is incomplete | Pretrained PyTorch inference plus reproducible training experiment | Working audio analysis and ML evidence |
| Google verification is delayed | Approved OAuth test users | Real test export with documented restriction |
| Candidate BPM/key coverage is poor | Use cached known values; null plus confidence-aware sequence fallback | Smart Sequencer without fabricated data |
| CLAP is slow or weak | Disable feature flag; show isolated POC only | Structured audio-conditioned RAG |
| Crossfade is unreliable | Normal track transition | Smart ordering and playback |
| VPS/domain is not ready | Dockerized EC2 or controlled test deployment | Reproducible end-to-end system |

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

| Decision | Options | Default/provisional direction | Decide by | Evidence required |
|---|---|---|---|---|
| Music provider mode | MusicAPI / hybrid / direct | POC first; direct YouTube if blocked | End Phase 0 | Search, taste, writes, OAuth, error, cost, terms |
| Recognition provider | ACRCloud / AudD / other | ACRCloud POC | Start Phase 6 | Original/humming accuracy, latency, cost |
| Embedding model | multilingual-e5 / BGE-M3 / smaller model | Benchmark two | Early Phase 3 | Bilingual retrieval and CPU profile |
| Document Reranker | Local multilingual / Bedrock/API | Local-first benchmark | Mid Phase 3 | nDCG/MRR lift, latency, cost |
| Heavy LLM | Bedrock / OpenAI / Anthropic / Gemini | Keep Bedrock as benchmark | Phase 4 | Music quality, JSON reliability, latency, cost |
| Local runtime | Ollama / llama.cpp | Choose based on existing hardware | Phase 2 | Latency, RAM, schema pass rate |
| Guardrails framework | NeMo / custom rule engine + classifier | NeMo preferred for course fit | Phase 2 | False positives/negatives and operations burden |
| RAG deployment boundary | Separate service / Recommendation module | Separate API for clearest course evidence | Phase 2 | Course confirmation, complexity, latency |
| Candidate feature provider | Cache/ISRC provider / approved preview / fallback | Cache + provider POC | Phase 7 | Coverage, accuracy, price, legality |
| CLAP | CPU / on-demand GPU / disabled | P2 POC | After Phase 6 P0 | Retrieval improvement and latency |
| Crossfade | Best effort / disabled | Normal transition by default | After Sequencer | Cross-browser reliability |
| Production host | Private VPS / AWS | Benchmark before purchase | Post-submission unless required | Price, location, support, backup |

Every closed decision gets an ADR with date, choice, alternatives, evidence, and consequence.

---

# 18. Requirements traceability summary

The detailed matrix belongs in `docs/requirements-traceability.md`. This summary ensures that the implementation plan itself does not omit a graded technology or deliverable.

| Course/reference area | Melody implementation | Evidence |
|---|---|---|
| Python basic/advanced | Flask/FastAPI services, ingestion, models, tests, concurrency/jobs | Source and tests |
| Web development | Existing Flask UI plus versioned APIs and OAuth UX | Running UI and routes |
| AWS basics/AI | Existing EC2/Bedrock/S3/Lambda baseline and deployment evidence | README, screenshots, benchmark |
| n8n workflows | WF-000 through WF-010 as main orchestrator | Importable JSON and live demo |
| n8n Information Extractor | Structured music-constraint extraction | Node, schema tests, prompt log |
| n8n AI Agent | Read-only request planning/tool-selection surface | Node, tool descriptions, prompt log |
| RAG/LangChain | Hybrid pgvector/full-text retrieval, ingestion, context generation | Evaluation and service code |
| LangGraph | Bounded stateful recommendation graph | Graph code, traces, tests |
| Machine-learning classifier | Audio genre/tag or energy classifier | Dataset, checkpoint/training, metrics |
| PyTorch/Transformers | Audio inference/training and optional CLAP | Code and evaluation |
| Local Ollama/Hugging Face/llama.cpp | Low-cost classification/extraction or local RAG baseline | Measured local task |
| Guardrails | Separate input/output guardrail service | Rejection demos and test report |
| MCP/external tools | Provider and service tools behind normalized contracts | Tool schemas and traces |
| External LLM | Final curator explanation and one bounded rewrite | Model-usage records |
| Feedback/active learning | Immutable events, Profile v1, later ranker path | Before/after ranking demo |
| Monitoring | WF-008 metrics, quota, error, and budget summary | Dashboard/report |
| Prompt engineering | Five surfaces, five versions, common test sets | Prompt Engineering Log |
| Docker/EC2 deployment | Separate containers and protected internal network | Compose, Dockerfiles, deployment notes |
| WebUI | Text, audio, playback, feedback, export | End-to-end demo |

Academic clarification task:

- [ ] **ACA-005 P0:** Confirm with the evaluator whether the Melody domain adaptation may replace the reference image classifier with an audio classifier and whether RAG/LangGraph may share a deployable service. Until confirmed, keep RAG and LangGraph separable at the API/module boundary and document the adaptation explicitly.

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

| Order | Work package | Status |
|---:|---|---|
| 1 | FND/SEC/ARC + MusicAPI POC | Not started |
| 2 | N8N-001 through N8N-010 + WF-000 through WF-010 | Not started |
| 3 | REP/INF/DB + service skeletons | Not started |
| 4 | RAG ingestion/retrieval/reranking + local model | Not started |
| 5 | LangGraph recommendation engine | Not started |
| 6 | Provider/auth/playback/export | Not started |
| 7 | Audio analysis/recognition/audio RAG | Not started |
| 8 | Feedback/profile/ranker/sequencer | Not started |
| 9 | Flask UI and end-to-end integration | Not started |
| 10 | Tests/security/observability/deploy/docs/demo | Not started |

---

# 21. Copy/paste prompt for the n8n building agent

Use this prompt after Phase 0 contracts and `PROVIDER_MODE` are available. Give the agent the schema files as context if the interface supports attachments.

~~~text
You are building the complete n8n orchestration layer for Melody, an AI music discovery application.

Goal:
Create the full final workflow topology now, even when downstream services are not implemented. Unavailable services must use explicit deterministic placeholder nodes that follow the final contracts. Do not build only the old Bedrock text route.

Target recommendation context:
user text + user/guest identity + materialized user taste + optional connected-provider taste + optional audio analysis + discovery constraints.

Architecture boundaries:
- n8n owns validation, guardrail calls, identity/profile loading, routing, service calls, persistence coordination, retries, export, cleanup, and monitoring.
- Recommendation Service/LangGraph owns bounded control flow, provider search intents, candidate ranking, sequencing, and explanation.
- RAG Service owns hybrid retrieval, genre expansion, RRF, document reranking, and evidence packaging.
- Audio Service owns BPM, key, energy, genre/tags, and audio embeddings.
- Guardrails Service owns input and output policy checks.
- Provider Adapter owns provider-specific search, identity, taste, playback references, and playlist writes.
- Feedback and playlist writes must remain outside LangGraph.
- The existing Bedrock route is only an explicitly logged optional fallback behind a feature flag. It is not the target flow.

Global rules:
1. Never place credentials or token values in workflow nodes or exported JSON.
2. Propagate request_id through every node and response.
3. Use one canonical success envelope and one canonical error envelope.
4. Add explicit timeouts and bounded retries only for retryable/idempotent calls.
5. Route all errors to WF-000 Common Error Handler.
6. Use idempotency keys for playlist creation and track insertion recovery.
7. Do not log raw audio, cookies, authorization headers, access tokens, or refresh tokens.
8. Prefer deterministic Switch/IF routing. Use a small AI classifier only when explicit UI intent is absent.
9. Include visible input and output guardrail calls.
10. Include an Information Extractor node for structured music constraints.
11. Include a read-only n8n AI Agent planning surface with clearly defined capability, genre-taxonomy, and connection-status tools, but do not give it external write tools or responsibility for the final HTTP call.
12. Label every stub PLACEHOLDER — <service>, return deterministic schema-valid fixture data, and include placeholder=true.
13. Export every workflow as importable JSON.

Create these workflows:
- MELODY — WF-000 — Common Error Handler
- MELODY — WF-001 — Main Request Router
- MELODY — WF-002 — Unified Recommendation
- MELODY — WF-003 — Audio Identification
- MELODY — WF-004 — Audio Vibe Recommendation
- MELODY — WF-005 — Feedback and Preference Update
- MELODY — WF-006 — Provider-Agnostic Playlist Export
- MELODY — WF-007 — Knowledge Ingestion
- MELODY — WF-008 — Monitoring and Budget
- MELODY — WF-009 — Provider Connection Sync
- MELODY — WF-010 — Temporary File Cleanup

WF-001 required order:
Webhook -> initialize execution -> validate schema -> input guardrails -> allow/reject -> resolve user/guest -> load provider connection status -> explicit intent check -> ambiguous intent classifier only if needed -> Switch by intent -> execute subworkflow -> normalize result -> output guardrails -> allow/safe fallback -> record metrics -> respond.

WF-002 required order:
input -> load materialized profile -> load authorized provider taste -> load optional audio features -> assemble RecommendationContext -> Information Extractor -> read-only AI planning agent -> call Recommendation Service -> validate result -> optional explicit legacy fallback -> persist session/candidates -> return.

WF-003 required order:
input -> validate temporary audio job -> recognition provider -> confidence gate -> canonical track resolution -> playable reference -> persist minimal result -> cleanup -> return.

WF-004 required order:
input -> validate temporary audio job -> Audio Service -> confidence gate -> store derived features -> construct unified recommendation request -> execute WF-002 -> cleanup -> return analysis plus recommendations.

WF-005 required order:
input -> validate ownership/action -> deduplicate -> insert immutable event -> update materialized profile -> return profile version.

WF-006 required order:
input -> validate session/tracks -> idempotency lookup -> connection/scope check -> authorization branch -> resolve provider IDs -> create playlist -> loop and insert ordered tracks -> partial-failure handling -> persist -> return.

WF-007 required order:
manual/schedule trigger -> changed sources -> source validation -> clean/canonicalize -> semantic chunking -> embeddings -> staged upsert -> full-text index -> smoke queries -> publish or rollback ingestion version -> report.

WF-008 required order:
schedule -> model usage -> provider quotas -> n8n errors/latency -> disk/database/backup health -> budget calculation -> threshold actions -> alert -> daily summary.

WF-009 required order:
input -> validate user and OAuth state reference -> provider status -> refresh if required -> persist encrypted connection metadata/reference -> return scopes/expiry/reauthorization state.

WF-010 required order:
input/schedule -> resolve explicit temporary object IDs -> verify approved temporary store -> delete -> mark cleaned -> send failures to WF-000. Never accept arbitrary filesystem paths.

Deliver in this order:
1. A compact architecture summary.
2. Required environment-variable and credential names only.
3. The workflows, one at a time, beginning with WF-000 and WF-001.
4. For each workflow: node table, exact connections, expressions, input/output examples, placeholder list, and test cases.
5. Importable workflow JSON.
6. A final test matrix proving every WF-001 branch, error path, guardrail branch, and idempotency behavior.

Stop and ask for input only if a missing choice changes the external contract or requires paid credentials. Otherwise use named placeholders and continue.
~~~

---

# 22. Copy/paste prompt for a coding agent

~~~text
Read README.md and MELODY_AI_ORDERED_EXECUTION_PLAN.md.

Work only on task <TASK-ID> or the explicitly named adjacent task group.

Before editing:
1. Inspect the current implementation, contracts, tests, and related n8n workflow JSON.
2. State the task inputs, outputs, dependencies, and acceptance criteria.
3. Confirm which placeholders this task replaces.

Implementation rules:
- Preserve the canonical contracts or version them explicitly.
- Keep n8n, LangGraph, Audio, Guardrails, Provider Adapter, and database responsibilities separated.
- Treat the legacy Bedrock route as benchmark/fallback only.
- Never add or log secrets.
- Do not invent track IDs, BPM, key, provider success, or model metrics.
- Add proportionate unit/contract/integration tests.
- Update n8n JSON export when a workflow changes.
- Update the prompt log when a prompt changes.

At completion report:
- files changed;
- placeholders removed;
- tests and commands run;
- acceptance criteria results;
- remaining risks or open decisions;
- next logical task ID.

Do not mark the task complete when tests or the phase gate fail.
~~~

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

~~~text
Flask UI
  -> n8n validation, guardrails, identity, and routing
  -> user profile + optional provider taste + optional audio features
  -> new LangGraph recommendation engine
  -> hybrid RAG and document reranking
  -> real candidates through Music Provider Adapter
  -> personal Track Reranker and Smart Sequencer
  -> output guardrails and persistence
  -> playable response, feedback, and confirmed export
~~~

Do not optimize a research feature while a P0 vertical slice is incomplete. Do not hide an unresolved provider limitation. Do not use the legacy route as the design of the new system. Build the full workflow skeleton first, then replace placeholders in phase order until the complete path is real.
