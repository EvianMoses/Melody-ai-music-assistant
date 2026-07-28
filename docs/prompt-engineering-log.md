# Prompt Engineering Log

> Phase 0 §0.5 deliverable `ACA-003` — define five prompt-engineering surfaces and
> a five-version evaluation log for each. This file defines the **surfaces, test
> sets, and log structure**. Filling in Version 1 for each surface is the separate
> Phase 3 §3.9 gate item; reaching Version 5 is `DOC-007`.
>
> Rule from Section 15: update this log on the same day a prompt changes. A prompt
> edited in n8n or in a service without a log entry is an undocumented change.

## 1. Surfaces

Six surfaces; PE-1 through PE-5 are required, PE-6 is optional.

| ID | Component | Where the prompt lives | Primary measure | Status |
| -- | --------- | ---------------------- | --------------- | ------ |
| PE-1 | n8n Information Extractor — music constraint extraction | `Extract Music Constraints` node, `workflows/n8n/WF-002 — Text Recommendation.json` | Schema accuracy and **missing-field honesty** (does it leave absent values absent?) | Not started |
| PE-2 | n8n AI Agent — read-only request planning and tool descriptions | `Recommendation Planning Agent` node, WF-002 | Correct tool selection, no unnecessary calls, no attempt to reach a write tool | Not started |
| PE-3 | RAG context-grounded generation | `rag-service/scripts/test_generation.py` (system + `<context>` template) | Grounding rate, usable evidence references, zero invention | V0 exists in code, unlogged |
| PE-4 | Guardrails input/output prompts | `guardrails-service/main.py` | False positive and false negative rate on a labelled set | Not started (rails are currently deterministic, not prompted) |
| PE-5 | Local-model system prompt | Ollama `llama3.1` call in `test_generation.py`; later the LOCAL-002 adapter | On-topic rate, schema pass rate, latency | V0 exists in code, unlogged |
| PE-6 *(optional)* | Final curator explanation | Phase 4 §4.8, Recommendation Service | Musical quality, concision, track-grounding | Planned |

## 2. Shared test sets

Each surface has its **own fixed test set of at least 10 cases**, reused unchanged
across all five versions. Changing the test set mid-log invalidates the
comparison — if a case must be added, it is appended and the version at which it
appeared is recorded.

Every test set must include, at minimum:

- 4 ordinary in-domain cases (the happy path);
- 2 cases where the correct answer is **partial or absent** — this is what
  measures honesty rather than fluency;
- 2 bilingual cases (Hebrew and English) where the surface is user-facing;
- 1 adversarial case (prompt injection, off-topic, or a request for internal
  state);
- 1 boundary case (empty input, maximum length, or conflicting constraints).

Test sets live in `docs/prompt-tests/PE-<n>-cases.md` (or a JSON fixture where the
surface is machine-scored) and are committed before Version 1 is evaluated.

## 3. Per-version log format

Every version of every surface uses this exact structure. Five versions per
surface is the requirement; a version that produced no measurable change is still
recorded, with that finding as its result.

```markdown
### PE-<n> — Version <v>

- **Date:**
- **Targeted failure from the previous version:**   (V1: state the initial hypothesis instead)
- **Change made:**                                   (one sentence — what actually differs)
- **Full prompt:**
  ```
  <the complete prompt text, verbatim — not a summary>
  ```
- **Test set:** `docs/prompt-tests/PE-<n>-cases.md` (N cases, unchanged since V<x>)
- **Results:**

  | Metric | V<v-1> | V<v> | Δ |
  | ------ | ------ | ---- | - |
  | <primary measure> |  |  |  |
  | <secondary measure> |  |  |  |
  | latency p50 (ms) |  |  |  |

- **Regressions observed:**    (state "none" only if the full set was re-run)
- **Failing cases remaining:** (case IDs, not prose)
- **Next target:**
```

The final version of each surface additionally records a **design
justification**: why this prompt is the one that ships, and what it deliberately
does not attempt.

## 4. Measurement rules

1. **Same model, same parameters, one variable.** A prompt change and a model
   change in the same version makes the delta unattributable. If the model must
   change, that is its own version with the prompt held constant.
2. **Re-run the whole set, every version.** Spot-checking the cases that failed
   last time hides regressions on the ones that passed.
3. **Record the failure, not just the score.** "82%" is not actionable; "fails
   both Hebrew cases and the empty-input boundary" is.
4. **Honesty metrics outrank fluency metrics.** For PE-1 and PE-3, a version that
   scores lower on coverage but stops inventing absent values is the better
   version, and the log must say so explicitly.
5. **Guardrail surfaces are scored both ways.** PE-4 reports false positives and
   false negatives separately; a single accuracy number hides which direction the
   rail fails in, and the two have very different costs.
6. **Latency is a result, not a footnote.** A prompt that doubles token count for
   a marginal quality gain is recorded as a tradeoff, since Section 9.6 budgets
   token use per request.

## 5. Version log

*(Entries are appended below as each version is evaluated. Empty until §3.9
Version 1 work begins.)*

### PE-1 — n8n Information Extractor

_No versions logged yet._

### PE-2 — n8n AI Agent

_No versions logged yet._

### PE-3 — RAG context-grounded generation

_No versions logged yet. A Version 0 prompt exists in
`rag-service/scripts/test_generation.py` and must be transcribed verbatim as
Version 1 before it is modified._

### PE-4 — Guardrails input/output

_No versions logged yet. The current rails are deterministic string rules rather
than prompts; Version 1 begins when the Phase 3/4 framework decision introduces a
prompted classifier._

### PE-5 — Local-model system prompt

_No versions logged yet. As with PE-3, the in-code prompt is transcribed as
Version 1 before any change._

### PE-6 — Final curator explanation *(optional)*

_Planned for Phase 4 §4.8._
