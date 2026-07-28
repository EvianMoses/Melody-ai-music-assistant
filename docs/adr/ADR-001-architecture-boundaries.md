# ADR-001: Architecture boundaries — n8n orchestrates, LangGraph recommends, adapters isolate

- **Status:** Accepted
- **Date:** 2026-07-24
- **Phase / tasks:** Phase 0 — §0.3 Freeze v1 contracts and boundaries (`ARC-005`)
- **Relates to:** Section 2.2 (component boundaries), ADR-002 (provider mode), ADR-003 (embedding model)

## Context

Melody's baseline was a Flask monolith that called a Bedrock Agent, which in turn
called Lambda tools and Spotify. Orchestration, retrieval, ranking, and provider
access all lived behind one opaque agent call. That shape made three things
impossible: showing where a decision was made, testing any stage in isolation,
and swapping a provider or a model without touching everything else.

The target system introduces three new runtimes at once — n8n, a LangGraph
recommendation engine, and a set of FastAPI services. Without an explicit rule
about who owns what, they will re-merge into the same monolith with more moving
parts: retrieval logic will leak into n8n Code nodes, OAuth will leak into the
graph, and provider-specific fields will leak into the recommendation contract.

This ADR fixes the boundary before the phases that would blur it.

## Decision

Three responsibilities, three owners, and no overlap.

### 1. n8n orchestrates — it does not compute

n8n owns request flow: validation, guardrail invocation, identity resolution,
routing, bounded retries, persistence coordination, side effects, export, and
monitoring. Every user action enters through one webhook (WF-001) and leaves
through one canonical envelope.

n8n must **not** own embedding math, audio DSP, or ranking algorithms. A Code
node that computes a score is a boundary violation, not a shortcut.

### 2. LangGraph recommends — it reads, it never writes

The Recommendation Service owns bounded stateful control flow: query
construction, retrieval orchestration, the confidence gate, track ranking,
sequencing, and the grounded explanation. Its control flow is a compiled graph
with a structurally enforced bound (`rewrite_count <= 1`), not an open-ended
agent loop.

The graph performs **reads only**. It emits *provider search intents* — a
description of the music wanted — and receives normalized candidates back. It
never creates a playlist, never writes feedback, never touches OAuth. Those side
effects belong to n8n, which can retry and deduplicate them under an idempotency
key.

### 3. Provider adapters isolate — external shape stops at the boundary

Every external music platform is reached through one normalized adapter contract
(search, identity resolution, taste import, playlist operations). YouTube,
Spotify, and any future backend produce the same normalized track fields and the
same error codes.

No YouTube video ID format, Spotify scope name, or MusicAPI response shape may
appear in the Recommendation Service or RAG Service contracts. `PROVIDER_MODE`
selects the backend; nothing upstream of the adapter knows which one won.

### Corollary: the legacy AWS route is a benchmark, not a fallback design

The Bedrock path is retained as a rollback, a quality/latency benchmark, and an
optional emergency fallback behind `ENABLE_LEGACY_BEDROCK_FALLBACK`. It does not
define the new request schema, personalization logic, audio path, or workflow
structure, and any use of it is recorded in `recommendation_sessions.engine_used`.

## Rationale

1. **Each stage becomes independently testable.** A retrieval regression is
   reproducible against the RAG Service alone; a routing bug is reproducible in
   n8n with fixtures. In the monolith both looked like "the agent gave a bad
   answer."
2. **Side effects concentrate where retries are safe.** n8n already owns
   idempotency keys, bounded retry, and the error handler (WF-000). Keeping
   writes there means a retried recommendation can never duplicate a playlist.
3. **Bounded control flow is a hard requirement, not a preference.** An agent
   that may loop is an unbounded cost and latency risk before a submission
   deadline. Enforcing the bound in graph topology makes it structural rather
   than prompt-dependent.
4. **Provider risk is contained.** ADR-002 rejected MusicAPI after the POC. That
   decision cost one adapter implementation instead of a rewrite precisely
   because the boundary was assumed from the start.
5. **The boundary is also the course evidence.** n8n, LangGraph, RAG, guardrails,
   and the local model runtime are separately graded areas; keeping them
   separately deployable makes each one demonstrable on its own.

## Alternatives considered

- **LangGraph orchestrates everything, n8n is a thin webhook.** Rejected: n8n is
  a graded deliverable and the visible orchestrator, and moving side effects into
  the graph would put non-idempotent writes inside a retryable compute path.
- **n8n orchestrates *and* recommends (AI Agent nodes do the ranking).** Rejected:
  ranking and sequencing need unit tests, versioned scoring components, and
  deterministic replay. Workflow JSON is a poor host for that, and the component
  scores would not be storable per candidate.
- **One combined RAG + recommendation service.** Tempting for latency, and
  explicitly left open by the plan's "RAG deployment boundary" decision. Rejected
  for now: separate services give the clearest course evidence and let retrieval
  be evaluated without the graph. Kept reversible — they communicate over HTTP
  with a stable contract, so merging later is a deployment change, not a rewrite.
- **Provider calls directly from the recommendation engine.** Rejected: it would
  put OAuth token handling inside the graph and leak provider-specific fields
  into the recommendation contract, undoing the isolation this ADR exists for.

## Consequences

- Cross-service calls cost network hops; §2 of `docs/service-call-policies.md`
  budgets them explicitly (30s synchronous ceiling, per-call timeouts).
- Any new capability must be assigned an owner before implementation. "Where does
  this go?" is answered by Section 2.2 plus this ADR, not by convenience.
- The Recommendation Service can be developed and tested against normalized
  candidate fixtures before Phase 5 delivers real provider data — the Phase 4
  gate depends on this.
- A future decision to merge RAG into the recommendation runtime requires
  superseding this ADR, not silently importing the module.
