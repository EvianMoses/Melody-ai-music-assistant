# ADR-004 — Recognition provider

**Status:** Accepted — **live and measured** (2026-07-27)
**Date:** 2026-07-27
**Relates to:** §6.4 (`REC-ID-001…006`), Phase 6 gate

## Context

Melody needs to answer "what is this song?" from a short microphone capture.
This is **fingerprint recognition** and is not the same problem as the audio
feature extraction in §6.2 — the plan is explicit that the two must not be
confused. Feature extraction says a clip is 128 BPM in G minor; recognition says
it is a specific commercial recording.

Recognition cannot be built here. It requires a fingerprint index over tens of
millions of commercial recordings, which is a licensing and infrastructure
problem, not a modelling one. So the decision is which provider to call.

## Decision

**ACRCloud**, via its Audio & Video Recognition `/v1/identify` endpoint.

Implemented in `audio-service/app/acrcloud.py`.

### Why

* It is the only major provider covering **both** original-recording matching
  and humming/query-by-humming, and humming is a named Phase 6 gate criterion.
  AudD does original recordings well and has no humming path at all.
* It returns **external IDs** (ISRC, Spotify, YouTube, Deezer) alongside the
  metadata. This is what `REC-ID-004` is asking about, and it matters more than
  it looks: a recognized track can be handed straight to Provider Adapter by ID
  instead of being re-searched by title, which is both faster and far more
  accurate — title search is exactly where §5.3's result-quality problems live.
* Self-hosted alternatives (Dejavu, audfprint) were not considered seriously:
  they fingerprint a catalogue *you already hold*, which is the part we do not
  have.

### Confidence thresholds (`REC-ID-005`)

Fixed **before** any measurement, so they cannot be tuned afterwards to flatter
a result. ACRCloud returns `score` 0–100, a fingerprint-match strength rather
than a probability.

| Band | Behaviour |
| --- | --- |
| `score ≥ 80` | Stated as a match |
| `60 ≤ score < 80` | Shown, explicitly flagged uncertain (`low_confidence`) |
| `score < 60` | **No track is named at all** |

The middle band exists because it is real: a noisy phone capture of a genuine
match often lands in the 60s, and discarding it is as wrong as presenting it as
certain. Below 60 nothing is named, because a confidently wrong answer is worse
than no answer — the user cannot tell it is wrong.

### Four outcomes, kept distinct

This is the structural decision, and it is the reason the adapter is shaped the
way it is:

| State | Meaning |
| --- | --- |
| `placeholder: true` | No provider configured. A stated gap. |
| `matched: false, reason: "no_match"` | The provider ran and recognized nothing. A real answer. |
| `matched: false, reason: "auth_rejected"` | **Our** configuration is wrong. |
| `matched: true` | With a score, and `low_confidence` when marginal. |

Collapsing these is how a user gets told "we couldn't recognize your song" about
a feature that never ran, or about a wrong API key. The UI renders all four
differently.

## Activation

The account is on **`identify-ap-southeast-1.acrcloud.com`**, found by probing.
This was not guesswork avoidance for its own sake: ACRCloud issues a per-project
regional endpoint, and a valid key aimed at the wrong region answers the same
`3001 Missing/Invalid Access Key` as a bad key. Every other region rejects this
key; `ap-southeast-1` answered `1001 No result` for a sine wave, which is the
correct answer and proves the key is accepted there.

`GET /audio/recognition/status` reports which of the three settings are present
and their lengths, never their values, so this stays diagnosable.

## POC results (REC-ID-001, 002, 003) — 2026-07-27

62 requests. `ml/recognition_poc.py`, raw output in
`audio-service/ml/checkpoints/recognition_poc.json`.

### Catalogue coverage

**11 of 12 (91.7%)** randomly sampled GTZAN clips are in ACRCloud's index.

This is the control that makes everything below meaningful. A clip that is
simply *not indexed* fails identically to one the noise destroyed, so the
degradation curve is computed over the 11 in-catalogue clips only. **The first
version of this POC omitted that control, and its noise figures were worthless
as a result** — it reported 10/10 on "noisy" clips and would have been written
up as evidence of robustness.

### Degradation curve (in-catalogue clips only)

White noise added at increasing sigma with the music attenuated — a crude stand-in
for a phone at increasing distance.

| Condition | Noise σ / gain | Matched | Rate |
| --- | --- | --- | --- |
| clean | — | 11/11 | **100%** |
| light | 0.02 / 0.55 | 10/11 | 90.9% |
| moderate | 0.06 / 0.40 | 9/11 | 81.8% |
| heavy | 0.12 / 0.25 | 4/11 | 36.4% |
| severe | 0.20 / 0.15 | 0/11 | **0%** |

**The useful finding is where it breaks, not that it works.** Recognition holds
up well through moderate degradation and then falls off a cliff between
moderate and heavy. That is the product-relevant boundary: a phone on a table in
a quiet room will match; a phone in a pocket in a loud bar will not, and it will
say so rather than guess.

### False positives — the failure that matters most

**0 of 3** synthetic no-match clips (tone, sweep, white noise) produced a match.
Adding the out-of-catalogue clip and the humming stand-ins, that is **0 false
positives across 7 genuine no-match opportunities**. A confident wrong answer is
the one failure a user cannot detect, and the provider did not produce one.

### Latency

Median **3.84 s**, p95 **4.88 s**, max 5.48 s — end to end including our own
FFmpeg conversion. This is slow enough to need the "Working it out…" state the
UI already shows, and comfortably inside WF-004's 30 s timeout.

### Cost

62 requests for this run. ACRCloud bills per recognition request, so the cost
driver is user volume, not clip length. Not modelled further here: with one
recognition per user action, the free tier covers demo and development use.

### Humming — still not evidenced

The humming stand-ins are **synthesized monophonic melodies, not human humming**,
and all 3 returned no match. This is not evidence about ACRCloud's humming
capability, for two independent reasons: the clips are not real humming, and
query-by-humming is a separately-enabled ACRCloud service rather than something
the standard `/v1/identify` endpoint answers.

**Per the Phase 6 gate's own wording — "humming is marked complete only if it
passes the POC threshold" — humming stays not complete.** Closing it would
require real hummed recordings and the humming service enabled on the project.

## Consequences

* Original-recording identification is **done and measured**. `REC-ID-001…006`
  are all closed.
* Humming remains open, and is now open for a *specific, actionable* reason
  rather than a general one.
* The 91.7% catalogue coverage is a ceiling on the feature, not a bug: some
  recordings are not indexed anywhere. The UI's "no match" state is therefore a
  normal outcome that will be seen in practice, which is why it is designed as
  a real state with its own copy rather than as an error.
* If per-request cost becomes a problem at volume, the adapter sits behind a
  `Recognition` dataclass — a provider swap touches nothing outside
  `app/acrcloud.py`.
