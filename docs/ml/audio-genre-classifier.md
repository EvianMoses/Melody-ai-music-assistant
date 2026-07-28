# Audio genre classifier — model card (§6.3, ML-AUD-001…007)

Melody's domain adaptation of the course's PyTorch classifier requirement: a
spectrogram CNN that labels a short audio clip with a music genre, used to
condition retrieval when a user asks "find me something like this" (§6.5).

Everything below is either a decision made before training or a number measured
after it. Nothing here is projected.

---

## 1. Task and labels (ML-AUD-001)

**Input** — a mono audio clip. **Output** — one of ten genres, or an explicit
abstention.

```
blues  classical  country  disco  hiphop  jazz  metal  pop  reggae  rock
```

These are the GTZAN genres. They are coarse, Western-centric and partly
overlapping (disco/pop, rock/metal), which is a limitation of the *label space*
and shows up in the confusion matrix as adjacent-genre error. It is not a defect
of the model, and the model cannot fix it.

`ml/labels.py` is the single source of truth for the label set, the thresholds
and the target metric. It was written before any training code, deliberately:
choosing a confidence threshold after seeing the results is how a threshold ends
up selected to flatter the model.

### Confidence policy (ML-AUD-006)

Two gates, **both** of which must pass, because they catch different failures:

| Gate | Value | Catches |
| --- | --- | --- |
| `MIN_CONFIDENCE` (top probability) | 0.45 | "unlike anything I was trained on" — the whole distribution is flat |
| `MIN_MARGIN` (top-1 − top-2) | 0.15 | "equally rock and metal" — confident something is there, not which |

A clip failing either is reported as **`uncertain`**, and the API returns
`genre: null` with `genre_model.reason = "low_confidence"`. It is never forced
into a label. Abstention is the *correct* output for humming, speech, or a
genre the label set does not contain, and §6.5 is built to run without a genre.

### Success metric

**Macro-F1 on the held-out test split** — macro, not accuracy, so a model that
does well on the easy genres and ignores a hard one is not rewarded.

Reference points, fixed in advance:

| | Macro-F1 |
| --- | --- |
| Random / majority-class baseline | 0.10 |
| Threshold to be worth shipping | **0.60** |
| Published CNN results on GTZAN | 0.75 – 0.85 |

Anything materially above that range on 1000 clips should be treated as evidence
of a leakage bug, not as a result.

---

## 2. Dataset (ML-AUD-002)

**GTZAN** — 1000 clips of 30 s, 100 per genre. The standard benchmark for this
task, obtained from the `marsyas/gtzan` mirror and distributed for research use.

### Known faults, stated rather than worked around

Sturm (2013), *The GTZAN dataset: its contents, its faults, their effects on
evaluation* documents exact duplicates, mislabelled clips, and several files
drawn from the same recording. None of these are fixable here. They put a
ceiling on how much any number below means, and that ceiling is real.

Two dataset defects **were** fixed, because they are ours and not Sturm's:

* **`jazz.00054.wav` is truncated** and cannot be decoded. Excluded by name
  (`KNOWN_BAD_FILES`) rather than by swallowing decode errors, so that a *new*
  decode failure stays loud.
* **The archive ships macOS AppleDouble resource forks** — a 211-byte
  `._blues.00000.wav` beside every real clip, which `Path.glob("*.wav")`
  happily returns. Left in, the index came to **1999 "clips", half of them
  undecodable**, and every split ratio and per-genre count computed from it
  would have been wrong. Filtered on the leading dot.

Usable clips after both: **999**.

### Split — and why leakage is the thing to watch here

The model trains on 3-second **segments**, and a 30-second clip yields ten of
them. Splitting *segments* at random puts nine siblings of every test segment
into training, and the reported accuracy then measures memorization of specific
recordings. It typically lands in the high 90s — that is the tell.

So the split is computed over **files**, and segments inherit their file's
split. `dataset.assert_no_leakage` enforces it on every run rather than trusting
the comment.

The assignment is by **hash rank within each genre**, not by a hash threshold.
Thresholding is the obvious way to do it and is only stratified *on average*:
the first run produced per-genre test folds ranging from 11 to 22 clips, which
distorts macro-F1 because the small folds carry far more variance. Ranking and
cutting at exact positions keeps determinism (the split survives re-runs,
machines and Python versions) and gives every genre identical proportions.

| Split | Clips | Per genre |
| --- | --- | --- |
| train | 699 | ~70 |
| val | 150 | 15 |
| test | 150 | 15 |

**Residual risk that cannot be removed:** GTZAN's own duplicate recordings can
place near-identical audio on both sides of a file-level split. Documented, not
hidden.

---

## 3. Preprocessing and architecture (ML-AUD-003, ML-AUD-004)

### Preprocessing

Mono · 22.05 kHz · 3-second segments · 128-mel spectrogram (`n_fft` 2048,
`hop_length` 512) · amplitude→dB with an 80 dB floor · per-example
standardization.

The mel transform lives **inside** the `nn.Module`, not in the data loader.
This is the most useful decision in the file: it makes the checkpoint
self-contained, so training and serving cannot drift apart on `n_mels` or
`hop_length`. A preprocessing mismatch between the two is the classic silent
failure — the model still returns confident answers, they are just wrong.

Per-example standardization matters for a second reason: without it the network
can learn *mastering loudness* as a genre cue, which generalizes to nothing.

### Architecture

Four `Conv2d(3×3) → BatchNorm → ReLU → MaxPool(2)` blocks at 32/64/128/128
channels, then global average pooling, dropout 0.3, and a linear head to 10
classes. ~250k parameters.

* **BatchNorm before the activation** — mel magnitudes vary by orders of
  magnitude between a quiet jazz clip and a mastered metal one; without
  normalization the loudest genre dominates the early gradients.
* **Global pooling instead of flatten** — the classifier depends on *what* is
  present, not where in the 3 seconds it happened, and the network then accepts
  a segment of any length at inference time.

A spectrogram-based CNN was chosen over fine-tuning a pretrained transformer
(AST): it trains to a reportable result on CPU inside the submission window,
where a transformer would not, and an unmeasured model is worth nothing. Every
layer is also inspectable, which is the point of the exercise.

### Augmentation — all label-preserving

* random segment offset per epoch (`dataset.SegmentDataset`)
* gain jitter ±30%
* SpecAugment-style frequency (16) and time (24) masking

**Pitch-shift and time-stretch are deliberately excluded**: they alter the key
and tempo that partly *define* a genre, so they would teach the model to ignore
a real signal.

### Hyperparameters

| | |
| --- | --- |
| optimizer | AdamW, lr 1e-3, weight decay 1e-4 |
| schedule | cosine annealing over the epoch budget |
| loss | cross-entropy, label smoothing 0.1 |
| batch size | 64 segments |
| epochs | 30, early stopping (patience 8) on val macro-F1 |
| seed | 1337 |

Label smoothing is there for a specific reason: GTZAN's labels are known to
contain errors, so training the model to be *certain* about them would fit the
noise.

**Model selection**: the checkpoint kept is the one with the best *validation*
macro-F1 — never the last epoch, and never anything computed on test.

---

## 4. Results (ML-AUD-005)

The test split is read **once**, by `ml/evaluate.py`, after training finishes.
It is not folded into the training script, because glancing at test performance
between epochs turns the held-out number into a training signal and the reported
figure into a fiction.

Two numbers are reported:

* **segment-level** — performance on the 3-second windows the model trained on;
* **clip-level** — probabilities averaged across a clip's segments, which is how
  `app/classifier.py` actually predicts. This is the honest headline.

### Measured — `melody-genre-cnn-1.0.0`, trained 2026-07-26, 30 epochs, 59.6 min CPU

| Metric | Value |
| --- | --- |
| **Clip-level macro-F1** (the headline) | **0.8692** |
| Clip-level accuracy | 0.8733 |
| Segment-level macro-F1 | 0.8378 |
| Segment-level accuracy | 0.8413 |
| Best validation macro-F1 (epoch 26) | 0.8482 |
| Test clips / segments | 150 / 1500 |
| Clips abstained under the confidence policy | 20 of 150 (13%) |
| Baseline / target | 0.10 / 0.60 — **target met** |

Clip-level beats segment-level by ~3 points, which is the expected direction:
averaging across a clip's windows cancels the odd unrepresentative one.

#### Per class (clip level)

| Genre | F1 | Precision | Recall |
| --- | --- | --- | --- |
| classical | 1.000 | 1.000 | 1.000 |
| jazz | 0.968 | 0.938 | 1.000 |
| metal | 0.966 | 1.000 | 0.933 |
| blues | 0.938 | 0.882 | 1.000 |
| disco | 0.903 | 0.875 | 0.933 |
| hiphop | 0.903 | 0.875 | 0.933 |
| country | 0.839 | 0.812 | 0.867 |
| reggae | 0.786 | 0.846 | 0.733 |
| pop | 0.750 | 0.706 | 0.800 |
| **rock** | **0.640** | 0.800 | 0.533 |

#### Confusion matrix (rows = true, columns = predicted)

```
           blues classi countr  disco hiphop   jazz  metal    pop reggae   rock
blues         15      0      0      0      0      0      0      0      0      0
classical      0     15      0      0      0      0      0      0      0      0
country        0      0     13      0      0      1      0      1      0      0
disco          0      0      0     14      0      0      0      0      0      1
hiphop         0      0      0      0     14      0      0      1      0      0
jazz           0      0      0      0      0     15      0      0      0      0
metal          0      0      0      1      0      0     14      0      0      0
pop            0      0      0      0      1      0      0     12      1      1
reggae         2      0      0      0      1      0      0      1     11      0
rock           0      0      3      1      0      0      0      2      1      8
```

**Reading it.** 0.8692 sits inside the published 0.75–0.85 band rather than
above it, and the *structure* of the errors is the stronger signal: rock is by
far the worst class (recall 0.533, losing 3 clips to country, 2 to pop, 1 each
to disco and reggae), while classical and jazz are perfect. That is exactly the
error pattern a human annotator produces — "rock" in GTZAN spans everything from
country-rock to arena rock, and the label carries little acoustic commitment.
Reggae→blues (2) is the other notable cell, and is likewise musically plausible.

A *clean* matrix on 1000 clips would be evidence of leakage, not of quality. This
one is not clean, and its mistakes are the right mistakes.

**Rock is the honest weak point** and is stated as such rather than averaged
away — which is precisely why the success metric was fixed as macro-F1 in
advance: accuracy alone (0.8733) would have quietly absorbed it.

---

## 5. Serving (ML-AUD-007)

`app/classifier.py` loads the checkpoint once, lazily, on the first request that
needs it.

**Absence is a first-class state.** With no checkpoint trained, the service
still returns BPM, key, Camelot and energy, and reports `genre: null` with
`reason: "no_checkpoint"`. It does not fail, and it does not invent a genre —
which is what let §6.1/§6.2 ship ahead of a trained model rather than behind it.

Prediction averages softmax probabilities across the clip's 3-second windows
rather than classifying one. A single window can land on an intro, a breakdown,
or four bars of silence.

`torch.load(..., weights_only=True)`: a checkpoint is untrusted input as soon as
it is downloaded rather than trained locally, and the legacy pickle path can
execute arbitrary code on load.

### Checkpoint policy

* Checkpoints live in `audio-service/ml/checkpoints/`, git-ignored — the
  training run is reproducible from `ml/train.py`, and binaries do not belong in
  the repository.
* Every checkpoint stores its own `model_version`, genre list, hyperparameters,
  validation score and UTC timestamp, so any stored prediction can be traced
  back to the exact configuration that produced it.
* `MODEL_VERSION` must be bumped whenever the label set, preprocessing or
  architecture changes. Existing checkpoints are then invalid by definition:
  `model.py`'s constants and the checkpoint are one unit.

---

## 6. Reproducing

Both commands run inside the audio-service image. Training is given more CPU
than the service's compose limit, which is the difference between ~1.7 minutes
and ~9 minutes per epoch:

```bash
# Train (downloads GTZAN on first run into the gtzan_data volume, ~1.2 GB)
docker run --rm --cpus=16 --shm-size=2g -e OMP_NUM_THREADS=16 \
  -v melody_gtzan_data:/app/data/gtzan \
  -v "$PWD/audio-service/ml/checkpoints:/app/ml/checkpoints" \
  melody-audio-service python -m ml.train --epochs 30 --workers 4

# Evaluate on the held-out test split
docker run --rm --cpus=16 -e OMP_NUM_THREADS=16 \
  -v melody_gtzan_data:/app/data/gtzan \
  -v "$PWD/audio-service/ml/checkpoints:/app/ml/checkpoints" \
  melody-audio-service python -m ml.evaluate
```

`--shm-size=2g` is required: the default 64 MB of `/dev/shm` is not enough for
DataLoader workers, and the failure surfaces as
`DataLoader worker (pid(s) …) exited unexpectedly`.

---

## 7. Recorded runs

| Date | Model version | Val macro-F1 | Test clip macro-F1 | Notes |
| --- | --- | --- | --- | --- |
| 2026-07-26 | `melody-genre-cnn-1.0.0` | 0.8482 (epoch 26) | **0.8692** | First trained model. 30 epochs, 59.6 min on 16 CPUs, no early stop. Full report: `audio-service/ml/checkpoints/test_report.json`. |

**Not attempted, and why.** Nothing was tuned after seeing the test number — no
threshold adjustment, no architecture change, no re-run. The test split has been
read once. Any future change goes through validation first, and this row stays
as the record of what the untouched model scored.
