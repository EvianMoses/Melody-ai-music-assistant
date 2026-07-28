# ADR-005: n8n deployment mode — self-hosted, not n8n Cloud

- **Status:** Accepted
- **Date:** 2026-07-25
- **Phase / tasks:** Phase 1 §1.1 (n8n global standards), Phase 2 `INF-002`, Phase 9 `SEC-106` / `DEP-003` / `DEP-004`
- **Relates to:** ADR-001 (architecture boundaries)

## Context

Melody's workflows were originally built in **n8n Cloud**, while every backend
service runs in Docker Compose on the developer's machine. This was discovered on
2026-07-25, after Section 2.6 had already wired the workflows to service URLs.

The wiring uses Docker-internal hostnames — all eight service calls target names
like `http://guardrails-service:8000/check/input` and
`http://recommendation-service:8000/recommendations/run`, and six n8n Postgres
nodes connect to the host `postgres`. **These names resolve only inside the
`melody-net` bridge network.** n8n Cloud runs on n8n's own infrastructure and has
no route to them, nor to the developer's `localhost`.

So the Section 2.6 wiring could not have executed successfully from n8n Cloud,
regardless of how the workflows were written.

The stated end state for the project is a **single VPS running the whole
application**, which forces the question now rather than at deployment time.

## Decision

**Self-host n8n as a Docker Compose service on the same private network as the
rest of Melody.** n8n Cloud is not used.

The `n8n` service already exists in `docker-compose.yml` (added under `INF-002`)
on the `melody-net` network with a persistent `n8n_data` volume, a stable
`N8N_ENCRYPTION_KEY`, and a healthcheck. Workflows move across as JSON exports
from `workflows/n8n/`.

In the target VPS topology, **n8n needs no publicly exposed port at all**:

| Hop | Address | Exposure |
| --- | ------- | -------- |
| Browser → Flask | `:80` / `:443` | the only public surface |
| Flask → n8n | `http://n8n:5678` | private network |
| n8n → services | `http://<service>:8000` | private network |
| n8n / services → Postgres | `postgres:5432` | private network |

## Rationale

1. **n8n Cloud would require exposing PostgreSQL to the public internet.** Six
   workflow nodes talk to the database directly, so a cloud-hosted n8n means
   opening the database port outward. That directly violates `SEC-106`
   (*"PostgreSQL and internal services are not public"*, P0) and would expose the
   `oauth_accounts` table of user tokens that Phase 5 introduces. This single
   point decides the ADR; the remaining reasons only reinforce it.
2. **It matches the declared end state.** The goal is everything on one VPS. The
   same Compose file that runs locally deploys there unchanged — that is the
   point of containerising it.
3. **Cost.** Self-hosting the Community edition is free under n8n's fair-code
   Sustainable Use License, which permits personal and internal use such as a
   student project. n8n Cloud is a paid subscription after its trial.
4. **One less external dependency before a deadline.** A cloud outage, trial
   expiry, or plan change on submission day is a risk with no upside here.
5. **Latency.** A single recommendation makes several service calls. Routing each
   one out to the public internet and back adds round trips that a private
   network does not have.
6. **Reproducibility is graded.** `DOC-003`, `DOC-004`, and the Phase 1 gate all
   assume workflow JSON that imports into a clean n8n instance, and Section 9.7
   expects a production-oriented Compose deployment.

## Alternatives considered

- **n8n Cloud + a tunnel (ngrok / Cloudflare Tunnel) to local services.**
  Rejected: it still publishes internal services, free-tier tunnel hostnames
  rotate on restart (breaking every workflow URL), and it adds a moving part that
  must be running for any demo to work.
- **n8n Cloud + services deployed to the existing EC2 instance.** Workable and
  closer to production, but it still requires the database to be reachable from
  outside unless every Postgres node is refactored into service endpoints, and it
  pulls Phase 9 deployment work forward into the build sprint.
- **Keep Cloud for authoring, self-host for running.** Rejected: two copies of
  every workflow, drifting independently, each needing separate verification.

## Consequences

- The workflows must be imported into the self-hosted instance, and credentials
  (`Melody Postgres`, and the OpenAI credential used by `Classify Ambiguous
  Intent`) recreated there. Credentials are referenced **by name**, not by id,
  which keeps this straightforward.
- `WF-009 Provider Connection Sync` still exists only in the Cloud account and
  must be exported before that account is abandoned, or it is lost (`N8N-010`).
- Claims in the plan that Section 2.6 wiring was verified end to end are
  **corrected**, not preserved — they could not have held from Cloud.
- Operational duties (updates, backup of the `n8n_data` volume) become the
  project's own. Backing up that volume belongs with `DEP-007`.
- Two follow-ups this surfaced, both tracked in the plan rather than fixed here:
  - `docker-compose.yml` pins `n8nio/n8n:latest`; a specific tag is needed for a
    reproducible submission.
  - `N8N_BASIC_AUTH_ACTIVE` was removed in n8n 1.x in favour of the built-in
    owner account, so `INF-002`'s "protected editor access" now rests on that
    account plus the fact that the port is not published in the VPS topology.
- The Flask app has a root `Dockerfile` but is **not** a Compose service yet; the
  VPS end state needs it added so the whole system starts with one command.
