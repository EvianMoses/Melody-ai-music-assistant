# Service call policies — timeouts, retries, and idempotency

> Phase 0 §0.3 deliverables `ARC-002` (timeouts and retry rules per service call)
> and `ARC-003` (which actions require an idempotency key).
>
> This document is the authoritative source for every hop in the request path.
> n8n node options, `shared_lib/http.py`, and Flask's `N8N_HTTP_TIMEOUT_SECONDS`
> must match the tables below. Where a value is not yet applied in code, the
> "Applied" column says so — the policy is defined here first, and Phase 1
> `N8N-006` is the task that configures the nodes.

## 1. Principles

1. **Every outbound call has an explicit timeout.** A missing timeout is a bug,
   not a default. A hung dependency must never hold an n8n execution or a Flask
   worker indefinitely.
2. **Retry only what is safe to repeat.** Read-only computation and idempotent
   upserts may be retried. External writes may not, unless an idempotency key
   makes the repeat provably harmless.
3. **Bounded attempts, exponential backoff, jitter.** Maximum 3 total attempts
   (initial + 2 retries) for any single call. Backoff `1s → 2s → 4s` with full
   jitter. No open-ended retry loops anywhere.
4. **The synchronous budget is 30 seconds.** `N8N_HTTP_TIMEOUT_SECONDS=30` is
   the Flask → n8n ceiling, so the whole WF-001 chain must fit inside it. Any
   call whose worst case exceeds the budget is marked **async-required** and is
   handed to the Phase 8 job path (`JOB-001`, `202 Accepted` + job ID).
5. **Guardrails fail closed.** If the Guardrails Service is unreachable or times
   out, the request is rejected — an unavailable safety check is not a passing
   safety check.
6. **Telemetry writes never fail the user.** Metrics and error-persistence calls
   are best-effort: they are retried once and then abandoned with a warning.
   They must not turn a successful recommendation into an error response.

## 2. Timeout and retry matrix

Timeouts are `connect / read` in seconds. "Attempts" is the total including the
first try.

### 2.1 Client edge

| Caller | Node / call | Target | Timeout | Attempts | Retry on | Applied |
| ------ | ----------- | ------ | ------- | -------- | -------- | ------- |
| Flask | `N8nClient.post` | WF-001 webhook | `5 / 30` | 1 | never — the envelope may carry a non-idempotent intent | ✅ `app.py` (`N8N_HTTP_TIMEOUT_SECONDS=30`) |

Flask does not retry. `feedback` and `playlist_export` envelopes have side
effects; a blind client retry would duplicate them. A user-visible retry is an
explicit user action, carrying the same `idempotency_key` (§4).

### 2.2 WF-001 — Main Request Router

| Node | Target | Timeout | Attempts | Retry on | Applied |
| ---- | ------ | ------- | -------- | -------- | ------- |
| `Input Guardrails` | `guardrails-service:8000/check/input` | `2 / 3` | 3 | connect error, `502/503/504` | ❌ not yet set on the node |
| `Resolve User or Guest` | PostgreSQL | `2 / 5` | 3 | connect error, deadlock, serialization failure | ❌ |
| `Load Connection Status` | WF-009 | `— / 10` | 1 | never at router level — WF-009 owns its own policy | ❌ |
| `Call 'WF-00x …'` (6 nodes) | sub-workflow | `— / 25` | 1 | never — the sub-workflow owns retries; a router-level retry would re-run its writes | ❌ |
| `Output Guardrails` | `guardrails-service:8000/check/output` | `2 / 3` | 3 | connect error, `502/503/504` | ❌ |
| `Record Request Metrics` | PostgreSQL | `2 / 5` | 2 | connect error | ❌ best-effort; failure is logged, not returned |

**Guardrail failure semantics.** Exhausted retries on `/check/input` return
`GUARDRAIL_UNAVAILABLE` and the request stops before any recommendation or
provider call. Exhausted retries on `/check/output` suppress the generated prose
and return the controlled review response — never the unchecked model output.

### 2.3 WF-002 — Unified Recommendation

| Node | Target | Timeout | Attempts | Retry on | Applied |
| ---- | ------ | ------- | -------- | -------- | ------- |
| `Call Recommendation Service` | `recommendation-service:8000/recommendations/run` | `2 / 25` | 2 | connect error, `502/503/504` only | ❌ |
| `Persist Session and Candidates` | PostgreSQL | `2 / 5` | 3 | connect error, deadlock | ❌ |

The recommendation call is read-only with respect to external providers
(LangGraph performs no provider writes — see `ADR-001`), so one retry is safe.
It is *not* retried on `500`: a deterministic engine failure will fail again and
the second attempt only burns the model budget.

### 2.4 WF-003 / WF-004 — Audio paths

| Node | Target | Timeout | Attempts | Retry on | Applied |
| ---- | ------ | ------- | -------- | -------- | ------- |
| `Call Audio Analysis Service` | `audio-service:8000/audio/analyze` | `2 / 60` | 2 | connect error, `502/503/504` | ❌ **async-required** — 60s exceeds the 30s budget |
| `Call Recognition Service` | `audio-service:8000/audio/identify` | `2 / 15` | 2 | connect error, `502/503/504`, `429` with backoff | ❌ |
| `Call Recommendation Service` (WF-003) | `recommendation-service:8000/recommendations/run` | `2 / 25` | 2 | as §2.3 | ❌ |

Recognition providers are rate-limited third parties, so `429` is retryable
there with backoff. Both audio paths must invoke WF-010 cleanup on success *and*
on exhausted failure; a timeout must not orphan a temporary object.

### 2.5 WF-005 — Feedback

| Node | Target | Timeout | Attempts | Retry on | Applied |
| ---- | ------ | ------- | -------- | -------- | ------- |
| `Insert Immutable Feedback Event` | PostgreSQL | `2 / 5` | 3 | connect error, deadlock | ❌ |
| `Update Materialized Profile` | `recommendation-service:8000/profiles/update` | `2 / 10` | 2 | connect error, `502/503/504` | ❌ |

Both are retry-safe only because they are keyed (§4.2): the insert is
deduplicated on the feedback event key, and the profile update is a
deterministic recomputation from stored events, not a blind increment.

### 2.6 WF-006 — Playlist export (external write)

| Node | Target | Timeout | Attempts | Retry on | Applied |
| ---- | ------ | ------- | -------- | -------- | ------- |
| `Check Existing Idempotent Export` | PostgreSQL | `2 / 5` | 3 | connect error | ❌ |
| `Create Playlist` | `provider-gateway:8000/providers/playlists` | `2 / 20` | 1 | **never automatically** | ❌ |
| `Insert Tracks in Order` | provider-gateway (per item) | `2 / 10` | 2 | `429`, `503` only, per item | ❌ |
| `Store Export Result` | PostgreSQL | `2 / 5` | 3 | connect error | ❌ |

`Create Playlist` is the one call that must never retry on its own. A timeout is
ambiguous — the playlist may exist. Recovery is: re-enter WF-006 with the same
`idempotency_key`, let `Check Existing Idempotent Export` resolve the prior
result, and only then decide. Item insertion *is* retryable per item because
adding the same video to the same playlist is checked against the recorded
`added` list before each attempt.

### 2.7 WF-000 — Common Error Handler

| Node | Target | Timeout | Attempts | Retry on | Applied |
| ---- | ------ | ------- | -------- | -------- | ------- |
| `Persist Error Event` | PostgreSQL (`audit_events`) | `2 / 5` | 2 | connect error | ❌ |
| `Schedule Retry` | caller workflow | per caller's declared maximum | ≤ caller max | only classes marked retryable in §3 | ❌ |

WF-000 must never route its own failures back into WF-000. If error persistence
fails, log locally and return the error envelope anyway.

## 3. Error classification

| Class | Examples | Retryable | Canonical code |
| ----- | -------- | --------- | -------------- |
| Transport | connect refused/reset, DNS failure | ✅ | `UPSTREAM_ERROR` |
| Timeout on a read-only call | recommendation/RAG/guardrail read timeout | ✅ | `UPSTREAM_TIMEOUT` |
| Timeout on an external write | playlist create/insert timeout | ❌ (idempotent re-entry only) | `UPSTREAM_TIMEOUT` |
| Upstream unavailable | `502`, `503`, `504` | ✅ | `SERVICE_UNAVAILABLE` |
| Rate limited | `429` | ✅ with backoff, honour `Retry-After` | `RATE_LIMITED` |
| Validation | `400`, `422`, unknown enum, body too large | ❌ | `VALIDATION_ERROR` |
| Authorization | `401`, `403`, missing OAuth scope | ❌ — needs user action | `AUTHORIZATION_REQUIRED` |
| Not found / gone | `404`, removed provider item | ❌ | `NOT_FOUND` |
| Conflict | `409`, duplicate idempotency key | ❌ — return the prior result | `CONFLICT` |
| Guardrail decision | input blocked, output not grounded | ❌ — a decision, not a failure | `INPUT_REJECTED` / `OUTPUT_BLOCKED` |
| Deterministic server error | `500` from our own service | ❌ | `INTERNAL_ERROR` |

Codes align with `shared_lib/errors.py::_HTTP_CODE_NAMES`. Retry decisions are
made on the class, never on the message text.

## 4. Idempotency (ARC-003)

### 4.1 Actions that require a client-supplied key

An `idempotency_key` is **required** on the request envelope for any intent that
causes an externally visible or immutable side effect.

| Intent / action | Key required | Uniqueness scope | Enforcement |
| --------------- | ------------ | ---------------- | ----------- |
| `playlist_export` | ✅ required | `(user_id, provider, key)` | `UNIQUE playlist_exports.idempotency_key` (already in the schema) |
| `feedback` | ✅ required | `(user_or_guest_id, session_id, track_id, action)` | dedup check in WF-005 before insert |
| `auth_connection_sync` (token write) | ✅ required | `(user_id, provider, key)` | WF-009 upsert on the connection row |
| audio job creation | ✅ required | `(user_or_guest_id, key)` | one temporary object per key |

A request in this set that arrives **without** a key is rejected with
`VALIDATION_ERROR`. The field already exists on the envelope
(`contracts/models.py::RequestEnvelope.idempotency_key`) but is currently
optional in code — enforcing it per this table is Phase 1 `N8N-009`.

### 4.2 Actions that do not require a client key

`text_recommendation`, `audio_vibe_recommendation`, and `audio_identification`
are read-only with respect to external systems. Repeating one costs money and
latency but corrupts nothing. They still persist a session row, keyed naturally
by `request_id`, so a duplicate delivery updates rather than duplicates.

### 4.3 Key rules

- **Generated by the client** (Flask), not by n8n — an n8n-generated key changes
  on retry and defeats the purpose.
- **Format:** UUIDv4 string, opaque to the server. Never derived from user text.
- **Lifetime:** 24 hours. A repeat within the window returns the stored result
  with the original status; after expiry the key is free to be reused.
- **Stored with the outcome, not just the attempt.** A key recorded before the
  provider confirms would make a failed export look completed.
- **Same key, different payload** ⇒ `CONFLICT`. Idempotency means "repeat of the
  same request", not "overwrite the previous one".

## 5. Open follow-ups

- **Phase 1 `N8N-006`** applies §2 to every n8n node; every ❌ in the "Applied"
  column closes there.
- **Phase 1 `N8N-009`** enforces §4.1 key requirements in WF-001 validation.
- **Phase 8 `JOB-001`** moves `/audio/analyze` (and any recommendation call that
  measures beyond the 30s budget) onto the async job path.
- **Phase 5 `PROV-003`** adds circuit breakers on top of these per-call retries,
  so a persistently failing provider stops being called at all.
