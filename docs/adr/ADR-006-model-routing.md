# ADR-006: Model routing — local model for classification, Claude Haiku 4.5 for generation

- **Status:** Accepted
- **Date:** 2026-07-25
- **Phase / tasks:** Phase 3 §3.7 (`LOCAL-001`…`LOCAL-004`), Phase 4 §4.8–4.9, Section 17 open decisions ("Heavy LLM", "Local runtime")
- **Relates to:** ADR-001 (architecture boundaries), ADR-003 (embedding model), ADR-005 (n8n deployment mode)

## Context

The local runtime (`llama3.1` 8B Q4_K_M via Ollama, 4.9 GB) was too slow to be
usable. Measured on the development machine on 2026-07-25:

| Task | Output tokens | Wall time | Throughput |
| ---- | ------------- | --------- | ---------- |
| Curator-style prose | 80 | **17.4 s** | 11.9 tok/s |
| Intent classification | 20 | **2.6 s** | 12.6 tok/s |

**Throughput is essentially constant (~12 tok/s); only the token count of the
task varies.** The model is not slow in general — it is slow at *generating
text*. A realistic curator explanation (~400–500 tokens) would take 35–45
seconds here, and several times that on the CPU VPS that Section 9.7 names as
the target production host. A 20–50 token structured classification is 2–4
seconds, which is workable.

This is the scenario Section 16 already anticipated: *"Local model is too slow →
Use it only for an isolated measured task; small external model for runtime."*

## Decision

**Split the work by output size, not by importance.**

1. **The local model owns cheap, short, structured tasks** — intent
   classification for ambiguous requests and structured music-constraint
   extraction. Output is 20–50 tokens of JSON. This matches the Section 2.2
   boundary for the Local Model Runtime: *"Cheap classification, structured
   extraction, local inference demonstrations."*
2. **An external API owns the two expensive moments** — the final curator
   explanation (§4.8) and ~~the single bounded low-confidence rewrite (§4.5)~~
   → **NEW DECISION (2026-07-25, see "Update" below): the rewrite stays
   deterministic/rule-based, not an LLM call.** §4.8 already states *"The
   expensive model is used only here."*
3. **The selected external model is `claude-haiku-4-5`, called through the
   direct Anthropic API** (not Amazon Bedrock).
4. **The existing `rag-service/scripts/test_generation.py` (llama3.1) is
   retained as the measured local-inference demonstration**, satisfying the
   course's local-runtime requirement — but it is *not* on the request path.

## Rationale

**Why Haiku 4.5 rather than a larger model.** The developer has already tested
both Sonnet 4.6 (via Bedrock) and Haiku 4.5 on this workload and reports good
results from both. That empirical evidence outweighs any theoretical argument.
The curator explanation is a *grounded writing* task — the RAG stage has already
gathered and reranked the evidence, so the model is asked to write two or three
sentences per track from material it is handed, not to reason from scratch.
Cost per recommendation (~3,000 input + ~500 output tokens):

| Model | Input / output per MTok | Per request | Per 1,000 requests |
| ----- | ----------------------- | ----------- | ------------------ |
| **Claude Haiku 4.5** | $1 / $5 | **~$0.0055** | **~$5.50** |
| Claude Sonnet 5 | $3 / $15 | ~$0.011 | ~$11 |
| Claude Opus 5 | $5 / $25 | ~$0.018 | ~$18 |

Prompt caching reduces this further, since the system prompt and genre context
are stable across requests.

**Why the direct API rather than Bedrock.** The stated goal is to move off AWS
onto an economical VPS (ADR-005). The direct API needs one environment variable
— an API key — and works from any host with no IAM roles, no region
configuration, and no AWS SDK. Bedrock is partner-operated with separate
pricing. Bedrock nevertheless **remains the quality benchmark** required by
`REC-LEG-001`/`REC-LEG-002`; this decision concerns the new engine's runtime
path, not the comparison baseline.

**Why there is no migration cost.** The heavy-model call **does not exist in
code yet** — `recommendation-service` returns fixtures. This is a greenfield
choice, not a rewrite.

**Why a smaller local model.** Dropping from an 8B to a 3B-class model for the
classification job roughly halves the resident memory (~4.9 GB → ~2.5 GB), which
matters directly for VPS sizing. At 20–50 output tokens the quality difference
on a constrained classification task is minimal.

## What this does *not* cover: audio

**No LLM participates in audio analysis.** BPM and musical key are signal
processing (Essentia `RhythmExtractor2013` / `KeyExtractor`); genre and tags are
an *audio* machine-learning model (mel-spectrogram → PyTorch CNN, `ML-AUD-001`…
`ML-AUD-007`); recognition is a third-party service (ACRCloud, ADR-004). An LLM
consumes text tokens and has no path to a waveform — §6.6 already records this:
*"CLAP is a true audio-text retrieval enhancement, not a BPM/key extractor and
not a song-recognition service."*

The LLM touches audio only **after** the fact: it receives the *derived values*
(`bpm=128`, `key=A minor`, `genre=deep house, confidence 0.71`) as text and
writes prose about them. The model choice in this ADR therefore has no bearing
on the audio pipeline.

## Alternatives considered

- **Keep llama3.1 8B for generation.** Rejected on the measurement above: 35–45
  seconds per explanation locally, minutes on the target VPS.
- **Sonnet 5 for generation.** Held in reserve. Twice the cost of Haiku with no
  evidence yet that this task needs it. Revisit if a golden-set evaluation
  (§3.8) shows a quality gap.
- **On-demand GPU for local generation.** Rejected for the submission window:
  it reintroduces exactly the per-hour infrastructure cost the VPS move exists
  to avoid, for a task an API answers for fractions of a cent.
- **Bedrock for the new engine too.** Rejected — it keeps the AWS dependency the
  project is deliberately shedding, while Bedrock's value as a *benchmark* is
  preserved either way.

## Update (2026-07-25): node 11 (`rewrite_query`) stays deterministic, not LLM-based

**Confirmed with the developer during Phase 4 §4.2 nodes 5–18 implementation:**
node 11 (`rewrite_query`, the single bounded low-confidence retry, §4.5) does
**not** call `claude-haiku-4-5` or any model. It is rule-based: relax exactly
one constraint in priority order (drop the year range → widen the candidate
pool → enable genre expansion), same effect as an LLM-authored rewrite (§4.5
requires only "one structured rewrite explaining which constraint is relaxed
or clarified"), at zero added latency/cost on the low-confidence path and with
no extra code needed before node 11's turn in the build order.

This narrows the "Decision" section above: only **one** heavy-model call site
exists in the graph — node 17 (`generate_grounded_explanation`, §4.8) — not
two. Everything else in this ADR (model choice, pricing, adapter requirement,
`ANTHROPIC_API_KEY` requirement) is unchanged and applies to that single call
site. Implemented and live-verified 2026-07-25 (`claude-haiku-4-5` returns a
grounded `playlist_title`/`playlist_description`/per-track `reasoning` from
real RAG evidence — see the Phase 4 session bookmark in
`MELODY_AI_ORDERED_EXECUTION_PLAN.md`).

If a future session wants the rewrite to be LLM-generated after all (e.g. a
golden-eval run shows the rule-based relaxation picks the wrong constraint
too often), revisit this note rather than silently reintroducing the call.

## Consequences

- `ANTHROPIC_API_KEY` becomes a required secret for the recommendation path and
  must be added to `.env.example` (names only) and to the VPS secret injection
  documented under `DEP-005`.
- **Every model call goes through an adapter**, not a direct SDK call at the
  call site, so switching models is a configuration change. §4.9 already
  requires recording provider, model, token counts, latency, estimated cost, and
  success/failure per call — that record is what makes a later model change an
  evidence-based decision rather than a guess.
- `LOCAL-004` is **corrected**: it assigned the local model the "local RAG
  answer baseline", which is a *generation* task and contradicts the Section 2.2
  boundary. The local model's production job becomes classification/extraction;
  the RAG-answer script stays as the measured demonstration.
- `LOCAL-001` needs revisiting to select the 3B-class model; `LOCAL-002` (stable
  internal adapter) and `LOCAL-003` (latency/memory/schema measurements) remain
  open, though the table above is the first entry of the `LOCAL-003` record.
- A budget ceiling and the 50/75/90/95 % alerts in `WF-008` should be sized
  against the per-request figure above rather than a guess.
- If the API is unreachable at request time, the recommendation path fails —
  the guardrails and error envelopes already cover this, and
  `ENABLE_LEGACY_BEDROCK_FALLBACK` remains the documented escape hatch.
