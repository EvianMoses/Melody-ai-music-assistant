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

⚠️ **Read this before the entries: building Version 1 changed the surface list,
because two of the five surfaces did not exist as described (2026-07-28).**

The §3.9 exercise was meant to be transcription. Auditing the codebase to
transcribe the prompts found that the table in §1 described a system that was
partly aspirational:

| Surface as documented | What is actually there |
| --------------------- | ---------------------- |
| PE-1 `Extract Music Constraints` node in WF-002 | **Does not exist.** No Information Extractor node exists in any workflow. Constraint extraction is deterministic Python (`normalize_input`, `extract_negations`), not an LLM node |
| PE-2 `Recommendation Planning Agent` in WF-002 | **Wrong workflow and wrong prompt.** The AI Agent is `Classify Ambiguous Intent` in **WF-001**, and its prompt was untouched n8n template boilerplate |
| PE-3 RAG generation in `test_generation.py` | **File deleted** with the Ollama removal (ADR-006 amendment). The surviving grounded-generation surface is the evaluation harness prompt |
| PE-4 Guardrails prompts | Correct: the rails are deterministic, **not prompted** |
| PE-5 Local-model system prompt | **Surface removed** with Ollama. Re-mapped to the curator explanation — the product's most important prompt, previously the "optional" PE-6 |

**NEW DECISION: the surface list is corrected to match the system, rather than
the system bent to match the list.** A prompt log describing nodes that do not
exist is worse than no log, because it reads as evidence.

---

### PE-1 — n8n Information Extractor

**Status: NOT IMPLEMENTED. No version can be logged, because the surface does not
exist.**

Searched every workflow in `workflows/n8n/` for
`@n8n/n8n-nodes-langchain.informationExtractor` and for a node named
`Extract Music Constraints`: **zero matches**. The `docs/requirements-traceability.md`
row citing it was inaccurate and has been corrected.

**What does the job today, and does it well:** structured constraint extraction
is deterministic Python in `recommendation-service/app/core/graph_nodes.py` —
`normalize_input` pulls positive and negative constraints from
`explicit_constraints`, and `extract_negations` parses bilingual free-text
negation. For this task that is arguably *better* than an LLM node (no latency,
no cost, nothing invented, unit-tested) — but it is **not** an n8n Information
Extractor, and the graded area names that node specifically.

**Open decision for the developer:** either build a real Information Extractor
node in WF-002 to satisfy the graded requirement, or record the deterministic
extractor as a deliberate substitution and argue it. This log will not pretend
the node exists either way.

---

### PE-2 — n8n AI Agent (`Classify Ambiguous Intent`, WF-001)

Model: `gpt-5-mini` via n8n's managed AI gateway.
Location: `workflows/n8n/MELODY — WF-001 — Main Request Router.json`.
Feeds: `Route by Intent`, a Switch on Melody's six intents.

#### Version 1 — inherited template boilerplate *(as found, never authored)*

```
You classify a user message into exactly one intent label from: faq, billing,
technical, account, sales, feedback. Respond with only the single lowercase label.
```

**Targeted failure from the previous version:** none — this was never written for
this product. It is n8n starter-template text that survived into the router.

**Evaluation: catastrophic, established by inspection rather than a test set.**
The node feeds `Route by Intent`, which accepts exactly `text_recommendation`,
`audio_vibe_recommendation`, `audio_identification`, `feedback`,
`playlist_export`, `auth_connection_sync`. This prompt can only emit
`faq | billing | technical | account | sales | feedback`.

| Outcome | Consequence |
| ------- | ----------- |
| 5 of its 6 labels | No Switch branch matches, so the request falls out as **Unroutable Intent** |
| `feedback` | The one accidental overlap — and it means *customer-support feedback*, so an ambiguous music request could route into **WF-005's like/dislike loop** and be recorded as a rating of nothing |

**Why nobody noticed:** the node sits on the false branch of `Explicit Intent
Available?`, and Flask always sends an explicit intent, so it had almost certainly
never executed. The same shape as §8.5's three mute refusal branches and the
hardcoded `off_topic = False`: **a surface unreachable in practice is a surface
nobody checks.**

#### Version 2 — written for this product *(2026-07-28, current)*

```
You classify a music-assistant request into exactly one intent label from:
text_recommendation, audio_vibe_recommendation, audio_identification,
feedback, playlist_export, auth_connection_sync.

- text_recommendation: the user describes music they want in words.
- audio_vibe_recommendation: the user wants music similar to an audio clip.
- audio_identification: the user asks what a clip IS (name the song).
- feedback: the user is rating or reacting to a track already shown
  (liked it, disliked it, skip).
- playlist_export: the user asks to save or export tracks to a playlist.
- auth_connection_sync: the user asks about connecting or disconnecting a
  music account.

Requests may be in English or Hebrew; classify the intent, not the language.
If the request is ambiguous, choose text_recommendation, which is the safe
default for a music assistant. Respond with only the single lowercase label
and nothing else.
```

**Changes, and why each:**

1. **The label set now matches the Switch.** That is the whole defect; the rest is
   refinement.
2. **One line of definition per label**, because `audio_vibe_recommendation` and
   `audio_identification` both take an audio clip and differ only in what the
   user wants to know — the single genuinely hard call in this taxonomy.
3. **A bilingual instruction**, since a fifth of real requests are Hebrew and the
   language is not the intent.
4. **A stated safe default.** A classifier with no fallback produces an
   unroutable request, which a user experiences as an error; defaulting to
   `text_recommendation` degrades onto the product's main path instead.

**Measured:** `smoke_test_e2e.py` **12/12** after the change, including the
unknown-intent rejection case. ⚠️ **Not yet measured on a 10-case set** — the
branch is deliberately hard to reach, and building a fixture that forces
ambiguous-intent routing is the honest next step for Version 3.

---

### PE-3 — RAG context-grounded generation

Location: `eval/rag_eval.py::generate_answers`. Model: `claude-haiku-4-5`.

⚠️ **Surface relocated.** The original PE-3 lived in
`rag-service/scripts/test_generation.py`, **deleted** when Ollama was removed
(ADR-006 amendment). The grounded-generation prompt that survives is the one the
Ragas evaluation uses — a genuine surface: it answers golden-set questions from
retrieved context, and its output is scored for faithfulness.

#### Version 1 — first formulation *(2026-07-28)*

```
You are a music knowledge assistant. Answer the question using ONLY the context
provided. If the context does not support an answer, say so plainly rather than
inventing one.

Context:
{context}

Question: {query}

Answer:
```

**Measured on the 25-query golden set** (Ragas, `claude-haiku-4-5` as judge):

| Metric | Version 1 |
| ------ | --------- |
| faithfulness | 0.7863 |
| response relevancy | 0.6119 |
| Hebrew response relevancy | **0.00 on all four Hebrew queries** |

**The failure, and it is instructive.** The refusal clause fired on *language
mismatch* rather than on missing information. `he-01` scored context precision
**1.0** and context recall **1.0** — retrieval had found exactly the right chunk
— and the answer still said the context did not contain the information. `he-03`
refused while explicitly writing *"the context does contain information about
Grunge from the 1990s"*.

**This was very nearly reported as a product failure.** The system under test was
fine; the evaluation prompt was broken.

#### Version 2 — language-aware *(current)*

```
You are a music knowledge assistant. Answer the question using ONLY the context
provided. If the context does not support an answer, say so plainly rather than
inventing one.

The knowledge base is written in English. A question asked in another language
is normal and must still be answered from that English context -- a language
difference is NOT a reason to refuse. Reply in the same language the question
was asked in.

Context:
{context}

Question: {query}

Answer:
```

**Targeted failure:** cross-language refusal on grounded context.

| Metric | V1 | V2 | Δ |
| ------ | -- | -- | - |
| faithfulness | 0.7863 | **0.8483** | +0.062 |
| response relevancy | 0.6119 | **0.7407** | +0.129 |
| Hebrew relevancy (per query) | 0.00 / 0.00 / 0.00 / 0.00 | **0.78 / 0.00 / 0.82 / 0.00** | 2 of 4 recovered |

**Honest reading of the two still at 0.00:** they are genuine *retrieval*
failures, not prompt failures — `he-02` and `he-04` both scored Recall@5 **0.0**,
so the model correctly declined to answer from irrelevant context. Fixing those
is retrieval work.

---

### PE-4 — Guardrails input/output

**Status: deliberately not a prompted surface. Nothing to log, and that is the
correct state rather than a gap.**

`guardrails-service/main.py` implements every §2.5 rule as deterministic Python:
prompt-injection patterns, length limits, off-topic classification, language
support, and the output rules (internal leakage, ad-free claims, fabricated
BPM/key, missing provider ids). 17 tests.

**NEW DECISION: keep them deterministic.** A guardrail is a *policy* boundary,
and three properties matter more here than flexibility: it cannot be argued out
of a decision by the text it is inspecting; it costs no latency on the request
path; and its false-positive and false-negative rates are exactly reproducible.
An LLM rail trades all three for coverage of rules nobody has written yet.

The §1 note — *"Version 1 begins when the Phase 3/4 framework decision introduces
a prompted classifier"* — stands. That decision has not been taken, so this
section stays empty on purpose.

⚠️ Worth recording: §8.5 found `off_topic` **hardcoded to `False`** here, so the
category appeared in every response and the check did nothing. Deterministic does
not mean correct; it means testable — and a test is what caught it.

---

### PE-5 — Final curator explanation

Location: `recommendation-service/app/core/llm_adapter.py::SYSTEM_PROMPT`.
Model: `claude-haiku-4-5` (ADR-006).

⚠️ **Promoted from the optional PE-6.** The original PE-5 was the Ollama
local-model prompt, whose surface no longer exists. The curator explanation is
the product's most user-visible prompt — it writes the prose every recommendation
is delivered in — and it already carries a real version history driven by a
defect found in production output.

#### Version 1 — as first shipped *(Phase 4, 2026-07-25)*

```
You are Melody's curator. Write a short, warm explanation of a track selection
using only the supplied evidence and tracks.
Rules (do not violate these):
- No unsupported biographies or factual claims about artists or tracks.
- No raw retrieval mechanics (scores, ranks, 'RRF', 'cross-encoder', chunk ids) in prose.
- One or two sentences per track, grounded in the evidence or the track's own metadata.
- playlist_title is short and evocative; playlist_description is 1-3 sentences.
```

Paired with a user turn that passed `state["warnings"]` verbatim under a
`Known caveats:` heading.

**Measured failure, found in a real `REC-LEG-001` comparison run** rather than in
testing: the Hebrew low-confidence case produced prose containing
*"אף שהביטחון בשלוף הוא נמוך"* — literally *"even though the confidence in the
retrieval is low"* — leaked to the user. §4.8 forbids exactly this.

**The rule was present and was obeyed to the letter.** The model printed no score
and never wrote "RRF". It **paraphrased** the internal warning string into
natural language instead.

#### Version 2 — jargon banned at the source *(2026-07-25, current)*

Two changes, and the ordering is the point:

1. **The input changed, not only the instruction.** `_user_safe_caveats()` now
   translates known signals into pre-written plain-language phrases, and
   `state["warnings"]` — exception messages, field names, "retrieval confidence
   was low" — **never reaches the model at all**. The adapter parameter was
   renamed `warnings` → `user_safe_caveats` so the bug cannot return by someone
   passing the raw list back in.
2. **The prompt gained an explicit anti-paraphrase rule**, as defence in depth:

```
- Never use internal/technical terms like 'retrieval', 'confidence score',
  'rewrite', 'query', or similar system jargon, even when translating a caveat
  -- write the way a human music curator would talk to a friend, in whatever
  language the user wrote in.
- 'Known caveats' below are already pre-approved, plain-language phrasing --
  use them as-is or lightly adapt them; do not add technical detail back in.
```

**Targeted failure:** internal jargon reaching user prose, in any language.

**Measured:** three regression tests assert no `_INTERNAL_JARGON` term reaches the
adapter; live-verified under the exact triggering condition (a forced rewrite on
an off-domain query), producing prose with no mention of confidence, retrieval or
rewriting. 141 offline tests green.

**Lesson worth keeping:** *a prompt rule that forbids a vocabulary does not forbid
the concept.* The durable fix was removing the jargon from the input; the prompt
rule is the second line of defence, not the first.

---

### PE-6 — *(retired)*

Absorbed into PE-5. The curator explanation was never really optional — it is the
only prose a user ever reads.

---

## 6. Honest status against `DOC-007`

`DOC-007` requires **five surfaces with five versions each**. This log delivers
Version 1 (and, where a defect forced it, Version 2) for the surfaces that exist:

| Surface | Versions logged | Measured on a ≥10-case set? |
| ------- | --------------- | --------------------------- |
| PE-1 Information Extractor | **0 — surface does not exist** | — |
| PE-2 AI Agent | 2 | No — smoke suite only (12/12) |
| PE-3 RAG generation | 2 | **Yes** — 25-query golden set + Ragas |
| PE-4 Guardrails | 0 by design (deterministic) | 17 unit tests |
| PE-5 Curator explanation | 2 | Regression tests + live verification |

**Remaining for `DOC-007`:** Versions 3–5 on PE-2, PE-3 and PE-5, and a decision
on PE-1. Only PE-3 currently has a shared ≥10-case test set behind it; extending
that discipline to PE-2 and PE-5 is the next real step, not writing more prompt
variants.
