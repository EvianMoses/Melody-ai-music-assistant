"""Real audio feature extraction: BPM, key, Camelot, energy (§6.2).

The Phase 2 skeleton returned `bpm: 120.0, musical_key: "A minor"` for every
file. This module measures them.

**Tool deviation from the §6.2 table, recorded deliberately.** The plan names
Essentia for `RhythmExtractor2013` and `KeyExtractor`. librosa is used instead:
Essentia publishes no reliable wheel for Python 3.12 (the runtime the rest of
the stack is pinned to), so adopting it would mean either a source build in the
image or downgrading every service's Python. librosa's `beat_track` covers the
same ground, and key detection is Krumhansl-Schmuckler either way -- it is a
published algorithm, not a library feature, and is implemented explicitly below
so the method is inspectable rather than delegated.

Everything returned carries a confidence, per the Phase 6 gate ("BPM, key,
energy, and genre/tag outputs include confidence and model versions"). The
confidences are *measured*, not assigned:

* **tempo** -- how regular the detected beats are. A steady four-on-the-floor
  gives near-identical inter-beat intervals; rubato piano does not.
* **key** -- the margin between the best-correlating key profile and the runner
  up. A clip that fits A minor and C major almost equally well is honestly
  ambiguous, and says so rather than picking one at 0.9.
* **energy** -- high by construction: RMS is a direct measurement, not an
  inference. It is reported anyway so every field has the same shape.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import classifier, config, transcode

logger = logging.getLogger("melody.audio.features")

MODEL_VERSION = "melody-dsp-1.0.0"
SOURCE = "librosa-dsp"

_PITCH_CLASSES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Krumhansl-Kessler key profiles: the average listener-rated fit of each pitch
# class within a key, from the 1982 probe-tone experiments. Correlating a clip's
# chroma against all 24 rotations is the standard key-finding method.
_MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)

# Camelot wheel. The numbers are what DJs mix by: same number = relative
# major/minor, adjacent numbers = a fifth apart, so ±1 or a letter flip is a
# smooth transition. §7.4's sequencer needs exactly this, which is why it is
# stored alongside the key rather than derived at read time.
_CAMELOT_MAJOR = {
    "C": "8B", "G": "9B", "D": "10B", "A": "11B", "E": "12B", "B": "1B",
    "F#": "2B", "C#": "3B", "G#": "4B", "D#": "5B", "A#": "6B", "F": "7B",
}
_CAMELOT_MINOR = {
    "A": "8A", "E": "9A", "B": "10A", "F#": "11A", "C#": "12A", "G#": "1A",
    "D#": "2A", "A#": "3A", "F": "4A", "C": "5A", "G": "6A", "D": "7A",
}


class AnalysisUnavailable(RuntimeError):
    """The DSP stack is not installed in this environment."""


@dataclass
class AnalysisResult:
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    camelot: Optional[str] = None
    energy: Optional[float] = None
    genre: Optional[str] = None
    source: str = SOURCE
    confidence: float = 0.0
    model_version: str = MODEL_VERSION
    field_confidence: dict[str, float] = field(default_factory=dict)
    analyzed_seconds: Optional[float] = None
    # The classifier's own version and abstention reason, kept apart from the
    # DSP `model_version`: they are two different models and the gate requires
    # each output to name the one that produced it.
    genre_model: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "bpm": self.bpm,
            "musical_key": self.musical_key,
            "camelot": self.camelot,
            "energy": self.energy,
            "genre": self.genre,
            "source": self.source,
            "confidence": self.confidence,
            "model_version": self.model_version,
            "field_confidence": self.field_confidence,
            "analyzed_seconds": self.analyzed_seconds,
            "genre_model": self.genre_model,
        }


def _load_dsp():
    """Import numpy/librosa on first use.

    Deferred rather than imported at module scope so the upload, storage and
    validation tests run on a plain Python install: librosa pulls numba and
    llvmlite, and requiring them to test a MIME sniffer would be absurd. It also
    keeps a ~3 s import off service startup for a service that may never be
    asked to analyse anything.
    """
    try:
        import librosa  # noqa: PLC0415
        import numpy  # noqa: PLC0415

        return numpy, librosa
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise AnalysisUnavailable(
            "Audio analysis dependencies are not installed."
        ) from exc


def available() -> bool:
    try:
        _load_dsp()
        return True
    except AnalysisUnavailable:
        return False


# ---------------------------------------------------------------------------
# Individual measurements
# ---------------------------------------------------------------------------


def _estimate_tempo(np, librosa, samples, sample_rate: int) -> tuple[Optional[float], float]:
    """Return (bpm, confidence) from beat tracking.

    Confidence is the regularity of the detected beat grid: the coefficient of
    variation of inter-beat intervals, inverted. This is a genuine measure of
    whether "a tempo" exists in the clip at all -- ambient pads and speech
    produce scattered onsets and score near zero, which is the correct answer
    for them.
    """
    onset_env = librosa.onset.onset_strength(y=samples, sr=sample_rate)
    if not onset_env.size or float(np.max(onset_env)) <= 0.0:
        return None, 0.0

    tempo, beats = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sample_rate, units="time"
    )
    bpm = float(np.atleast_1d(tempo)[0])
    if bpm <= 0:
        return None, 0.0

    if len(beats) < 4:
        # A tempo was reported, but from too few beats to trust. Report it with
        # low confidence instead of discarding a possibly-correct estimate.
        return round(bpm, 2), 0.2

    intervals = np.diff(np.asarray(beats, dtype=float))
    mean_interval = float(np.mean(intervals))
    if mean_interval <= 0:
        return round(bpm, 2), 0.2
    variation = float(np.std(intervals)) / mean_interval
    # cv of 0 -> 1.0; cv of 0.25 or worse -> 0. Real tracks with a steady pulse
    # land around 0.01-0.05; free-time material is well past 0.25.
    confidence = max(0.0, min(1.0, 1.0 - variation / 0.25))
    return round(bpm, 2), round(confidence, 3)


def _estimate_key(np, librosa, samples, sample_rate: int) -> tuple[Optional[str], Optional[str], float]:
    """Return (key name, camelot, confidence) via Krumhansl-Schmuckler.

    Chroma is CQT-based (pitch-aligned bins) rather than STFT-based, which
    matters for low-register content where linear FFT bins smear adjacent
    semitones together.
    """
    chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate)
    if not chroma.size:
        return None, None, 0.0
    # Average over time: we want the clip's overall tonal centre, not a
    # frame-by-frame reading.
    profile = np.mean(chroma, axis=1)
    if float(np.sum(profile)) <= 0:
        return None, None, 0.0
    profile = profile / np.linalg.norm(profile)

    major = np.asarray(_MAJOR_PROFILE, dtype=float)
    minor = np.asarray(_MINOR_PROFILE, dtype=float)

    scores: list[tuple[float, str, str]] = []
    for shift in range(12):
        rotated = np.roll(profile, -shift)
        for template, mode in ((major, "major"), (minor, "minor")):
            correlation = float(np.corrcoef(rotated, template)[0, 1])
            if correlation == correlation:  # guard against NaN on flat input
                scores.append((correlation, _PITCH_CLASSES[shift], mode))
    if not scores:
        return None, None, 0.0

    scores.sort(key=lambda item: item[0], reverse=True)
    best_score, tonic, mode = scores[0]
    runner_up = scores[1][0] if len(scores) > 1 else 0.0

    # Two independent requirements, multiplied: the winner must fit well *and*
    # beat the alternative. A clip that matches everything at 0.9 is as
    # uninformative as one that matches nothing.
    fit = max(0.0, min(1.0, best_score))
    margin = max(0.0, min(1.0, (best_score - runner_up) / 0.35))
    confidence = round(fit * margin, 3)

    camelot = (_CAMELOT_MAJOR if mode == "major" else _CAMELOT_MINOR).get(tonic)
    return f"{tonic} {mode}", camelot, confidence


def _estimate_energy(np, librosa, samples, sample_rate: int) -> tuple[Optional[float], float]:
    """Return (energy 0-1, confidence).

    Energy in the sense recommendation needs is perceived intensity, not raw
    amplitude, so this combines loudness with spectral brightness: a quiet track
    full of high-frequency movement reads as more energetic than a loud drone,
    which matches how people describe music.
    """
    rms = librosa.feature.rms(y=samples)
    if not rms.size:
        return None, 0.0
    mean_rms = float(np.mean(rms))
    if mean_rms <= 0:
        return 0.0, 0.5

    # dBFS, then mapped over the -40..0 dB range people actually hear music in.
    db = 20.0 * float(np.log10(max(mean_rms, 1e-6)))
    loudness = max(0.0, min(1.0, (db + 40.0) / 40.0))

    centroid = librosa.feature.spectral_centroid(y=samples, sr=sample_rate)
    # Normalized against 4 kHz: bright percussive material sits above it, warm
    # or bass-led material below.
    brightness = max(0.0, min(1.0, float(np.mean(centroid)) / 4000.0))

    energy = round(0.65 * loudness + 0.35 * brightness, 3)
    # Direct measurement of the signal, so confidence is high -- but not 1.0:
    # the loudness/brightness weighting is a modelling choice, not a fact.
    return energy, 0.8


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def analyze_file(source: Path) -> AnalysisResult:
    """Decode `source` and measure its features.

    `source` is always a path produced by `storage.path_for`, never anything a
    client named.
    """
    np, librosa = _load_dsp()

    with tempfile.TemporaryDirectory(prefix="melody-analysis-") as workdir:
        wav_path = Path(workdir) / "analysis.wav"
        transcode.to_analysis_wav(source, wav_path)
        samples, sample_rate = librosa.load(
            str(wav_path), sr=config.ANALYSIS_SAMPLE_RATE, mono=True
        )
        # The TemporaryDirectory removes the decoded copy on exit, including on
        # failure -- the converted audio is as sensitive as the upload
        # (AUD-UP-006).

    duration = float(len(samples)) / float(sample_rate) if sample_rate else 0.0
    if duration < 1.0:
        # Below about a second there is no tempo to find and the chroma average
        # is dominated by one note. Refusing is more useful than three numbers
        # that all mean nothing.
        return AnalysisResult(
            confidence=0.0,
            field_confidence={"tempo": 0.0, "key": 0.0, "energy": 0.0},
            analyzed_seconds=round(duration, 3),
        )

    bpm, tempo_confidence = _estimate_tempo(np, librosa, samples, sample_rate)
    key_name, camelot, key_confidence = _estimate_key(np, librosa, samples, sample_rate)
    energy, energy_confidence = _estimate_energy(np, librosa, samples, sample_rate)

    # §6.3. Never fatal: a clip still gets BPM/key/energy when no checkpoint has
    # been trained, and the caller is told why the genre is absent.
    genre_prediction = classifier.predict(samples, sample_rate)

    field_confidence = {
        "tempo": tempo_confidence,
        "key": key_confidence,
        "energy": energy_confidence,
    }
    # The genre only joins the confidence set when a model actually produced
    # one. Folding an unavailable classifier in as 0.0 would drag the headline
    # to zero and misreport perfectly good DSP measurements as untrustworthy.
    if genre_prediction.available:
        field_confidence["genre"] = genre_prediction.confidence

    # The headline number is the *weakest* field, not the average: a caller
    # reading only `confidence` must not be told 0.6 when the key is a guess.
    overall = round(min(field_confidence.values()), 3)

    logger.info(
        "audio_analyzed",
        extra={"duration": round(duration, 2), "bpm": bpm, "confidence": overall},
    )
    return AnalysisResult(
        bpm=bpm,
        musical_key=key_name,
        camelot=camelot,
        energy=energy,
        genre=genre_prediction.genre,
        confidence=overall,
        field_confidence=field_confidence,
        analyzed_seconds=round(duration, 3),
        genre_model=genre_prediction.as_dict(),
    )
