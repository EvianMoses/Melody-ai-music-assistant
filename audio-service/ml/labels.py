"""Label set, confidence policy and success metric (ML-AUD-001).

Written before any training code, deliberately: "what counts as correct" and
"when do we refuse to answer" are decisions, not outcomes, and deciding them
after seeing the numbers is how a model ends up with a threshold chosen to
flatter it.

**Labels.** The ten GTZAN genres. They are coarse, Western-centric and partly
overlapping (disco/pop, rock/metal), which is a real limitation of the label
space rather than of the model -- recorded here so the confusion matrix is read
with it in mind.

**Confidence.** Two gates, both of which must pass, because they catch different
failures:

* `MIN_CONFIDENCE` -- the top probability. Catches "this is unlike anything I
  was trained on", where the whole distribution is flat.
* `MIN_MARGIN` -- top-1 minus top-2. Catches "this is equally rock and metal",
  where the model is confident *something* is there but not which.

A clip failing either is reported as `uncertain` with no genre (ML-AUD-006).
Refusing is the correct output for a hummed melody or a spoken-word clip, and
the recommendation path is built to run without a genre (§6.5, AUD-RAG-002).

**Success metric.** Macro-F1 on the held-out test split -- macro, not accuracy,
so a model that does well on the easy genres and ignores a hard one is not
rewarded. Reference points, fixed in advance:

* random / majority-class baseline: ~0.10
* the threshold at which this is worth shipping: **0.60**
* published CNN results on GTZAN sit around 0.75-0.85, and anything materially
  above that on 1000 clips should be treated as a leakage bug, not a triumph.
"""

from __future__ import annotations

GENRES: tuple[str, ...] = (
    "blues",
    "classical",
    "country",
    "disco",
    "hiphop",
    "jazz",
    "metal",
    "pop",
    "reggae",
    "rock",
)

LABEL_TO_INDEX = {name: index for index, name in enumerate(GENRES)}

# Reported alongside every prediction, and part of the checkpoint filename, so a
# stored feature row can always be traced to the model that produced it.
MODEL_VERSION = "melody-genre-cnn-1.0.0"

MIN_CONFIDENCE = 0.45
MIN_MARGIN = 0.15

UNCERTAIN = "uncertain"

# Fixed before training (see above).
BASELINE_MACRO_F1 = 0.10
TARGET_MACRO_F1 = 0.60


def decide(probabilities: dict[str, float]) -> tuple[str, float, float]:
    """Apply the confidence policy to a probability distribution.

    Returns ``(label, confidence, margin)`` where `label` is `UNCERTAIN` when
    either gate fails. The confidence and margin are returned either way, so a
    caller that wants the raw signal can still see it -- refusing to *label*
    is not the same as refusing to report.
    """
    if not probabilities:
        return UNCERTAIN, 0.0, 0.0
    ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    top_label, top_probability = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_probability - runner_up

    if top_probability < MIN_CONFIDENCE or margin < MIN_MARGIN:
        return UNCERTAIN, round(top_probability, 4), round(margin, 4)
    return top_label, round(top_probability, 4), round(margin, 4)
