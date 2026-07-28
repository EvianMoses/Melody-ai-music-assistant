# Feature flags

> Phase 0 §0.3 deliverable `ARC-004` — the concrete flag set required by
> Section 2.3 of `MELODY_AI_ORDERED_EXECUTION_PLAN.md`, which named the
> requirement ("Required feature flags:") without listing the flags.
>
> Every flag is an environment variable, declared in `.env.example`, read once at
> process start, and never toggled per request by a model or by user input.

## Rules

1. **Boolean parsing is uniform.** `1 / true / yes / on` (case-insensitive) are
   true; everything else, including unset, is false. `app.py` already parses
   `USE_N8N_ORCHESTRATOR` this way and is the reference implementation.
2. **Defaults are the safe value, not the convenient one.** A flag that is unset
   in a fresh environment must not enable an external write, an expensive model
   path, or a placeholder.
3. **A flag decision that changes a result is recorded.** Any request served
   through a non-default path writes the reason into
   `recommendation_sessions.engine_used` and the execution metadata (`N8N-008`).
   Section 2.3 is explicit: never switch silently.
4. **Flags gate behaviour, not secrets.** Absence of a credential is a
   configuration error, not an off switch.
5. **Kill switches are one-way under pressure.** The budget guard (§ Budget)
   may turn optional paths *off* automatically; nothing turns them back on
   automatically.

## Flag set

### Orchestration and engine

| Flag | Default | Owner | Effect |
| ---- | ------- | ----- | ------ |
| `USE_N8N_ORCHESTRATOR` | `true` | Flask | Gates `POST /api/v1/requests`. When false the route returns `SERVICE_UNAVAILABLE`; legacy `/chat` and `/ask` are unaffected. Already implemented in `app.py`. |
| `RECOMMENDATION_ENGINE` | `legacy` | Flask / WF-002 | Which engine is the *default* for a recommendation: `legacy` (Bedrock Agent) or `langgraph` (the new Recommendation Service). Stays `legacy` until the Phase 5 real-provider gate and the Phase 8 UI gate both pass (`REC-LEG-003`). |
| `ENABLE_LEGACY_BEDROCK_FALLBACK` | `false` | WF-002 | Permits the *emergency* fallback described in Section 2.3: when the new engine fails an eligible failure class, WF-002 may re-run the request through Bedrock. Every fallback writes `engine_used='legacy_fallback'`. Off by default so a fallback is never accidental. `REC-LEG-004` removes this flag after release stability. |

### Providers

| Flag | Default | Owner | Effect |
| ---- | ------- | ----- | ------ |
| `PROVIDER_MODE` | `direct` | Provider Gateway | `direct` \| `musicapi` \| `hybrid`. Closed by ADR-002 as `direct` (YouTube primary). The other values remain parseable so the adapter contract stays honest, but selecting them without an implemented adapter is a startup error, not a silent no-op. |
| `ENABLE_SPOTIFY_ADAPTER` | `false` | Provider Gateway | Spotify is limited to the 5 authorized development users (ADR-002). Off by default so the core experience never depends on it. P1. |
| `ENABLE_PLAYLIST_EXPORT` | `false` | WF-006 | Master switch for external provider **writes**. Off until Phase 5 delivers real OAuth and idempotent export. While off, WF-006 returns `FEATURE_DISABLED` rather than calling the provider. |

### Audio and ML

| Flag | Default | Owner | Effect |
| ---- | ------- | ----- | ------ |
| `ENABLE_AUDIO_IDENTIFICATION` | `false` | WF-003 | Gates the recognition-provider call (Phase 6). Off until `ADR-004` selects a provider, so no request reaches an unconfigured third party. |
| `ENABLE_CLAP` | `false` | Audio Service | P2 proof of concept only. Section 12 requires it to be disable-able without touching the structured audio-feature path. |
| `ENABLE_CROSSFADE` | `false` | Flask UI | P2. Must stay off unless the cross-browser tests in `XFADE-002` pass; the plan forbids marketing seamless crossfade otherwise. |

### Cost and safety

| Flag | Default | Owner | Effect |
| ---- | ------- | ----- | ------ |
| `ENABLE_EXPENSIVE_MODEL_PATHS` | `true` | Recommendation Service | The budget kill switch from §1.11. At 95% of the monthly ceiling WF-008 sets this false, which disables the curator explanation's heavy model and the bounded rewrite — the deterministic core (retrieval, ranking, sequencing, export) keeps working. |
| `ALLOW_PLACEHOLDER_NODES` | `false` | all | Phase 1 §1.14 requires that no placeholder is reachable in the submission environment. With this false, any node or endpoint still returning fixture data must fail loudly instead of returning mock tracks. `INT-002` verifies this. |
| `LOG_LEVEL` | `INFO` | all services | Already read by `shared_lib/app_factory.py`. `DEBUG` is never valid in the submission environment — redaction is enforced by the log filter, but debug volume defeats review. |

## Budget interaction

`WF-008 Monitoring and Budget` is the only automated writer of a flag value, and
it may only ever move `ENABLE_EXPENSIVE_MODEL_PATHS` from true to false. Restoring
it is a deliberate human action after the budget window resets. This preserves
the Section 1.11 rule: at 95%, disable optional expensive paths, not the
deterministic core.

## Submission environment expectations

The values that must hold for the final demo, once the corresponding gates pass:

```
USE_N8N_ORCHESTRATOR=true
RECOMMENDATION_ENGINE=langgraph        # only after Phase 5 + Phase 8 gates
ENABLE_LEGACY_BEDROCK_FALLBACK=false   # no silent fallback during the demo
PROVIDER_MODE=direct
ENABLE_PLAYLIST_EXPORT=true            # only after Phase 5 gate
ALLOW_PLACEHOLDER_NODES=false
```

`ENABLE_SPOTIFY_ADAPTER`, `ENABLE_CLAP`, and `ENABLE_CROSSFADE` may remain false;
Section 16 lists each as an honest, stated limitation rather than a blocker.
