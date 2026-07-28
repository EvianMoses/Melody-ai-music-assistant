"""Genre classifier inference inside the Audio Service (ML-AUD-007).

The model is loaded once, lazily, on the first request that needs it, and
**absence is a first-class state**. If no checkpoint has been trained yet the
service still analyses BPM, key and energy and reports `genre: null` with a
reason -- it does not fail, and it does not invent a genre. That is what lets
§6.1/§6.2 ship ahead of a trained model instead of behind it.

Prediction averages softmax probabilities across the clip's 3-second segments
rather than classifying one window. A single window can land on an intro, a
breakdown or four bars of silence; averaging is both more accurate and closer to
what a listener means by "what genre is this". `evaluate.py` reports the
clip-level score computed the same way, so the number we publish is the number
this path produces.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("melody.audio.classifier")

CHECKPOINT_PATH = Path(__file__).resolve().parents[1] / "ml" / "checkpoints" / "genre_cnn.pt"

_lock = threading.Lock()
_state: dict[str, Any] = {"loaded": False, "model": None, "metadata": {}, "reason": None}


@dataclass
class GenrePrediction:
    genre: Optional[str]
    confidence: float
    margin: float
    model_version: Optional[str]
    available: bool
    reason: Optional[str] = None
    top: dict[str, float] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "genre": self.genre,
            "confidence": self.confidence,
            "margin": self.margin,
            "model_version": self.model_version,
            "available": self.available,
            "reason": self.reason,
            "top": self.top or {},
        }


def _ensure_loaded() -> dict[str, Any]:
    """Load the checkpoint once. Thread-safe; failures are cached, not retried.

    A missing or unreadable checkpoint is not going to fix itself between
    requests, and retrying the load on every clip would add a filesystem probe
    and an exception to every analysis for no benefit.
    """
    if _state["loaded"]:
        return _state
    with _lock:
        if _state["loaded"]:
            return _state
        _state["loaded"] = True
        if not CHECKPOINT_PATH.is_file():
            _state["reason"] = "no_checkpoint"
            logger.info("genre_classifier_absent", extra={"path": str(CHECKPOINT_PATH)})
            return _state
        try:
            from ml.model import load_checkpoint  # noqa: PLC0415 - deferred like the DSP stack

            model, metadata = load_checkpoint(CHECKPOINT_PATH)
            _state["model"] = model
            _state["metadata"] = metadata
            logger.info(
                "genre_classifier_loaded",
                extra={"model_version": metadata.get("model_version")},
            )
        except Exception as exc:  # torch missing, corrupt file, shape mismatch
            _state["reason"] = "load_failed"
            logger.warning("genre_classifier_load_failed", extra={"error": type(exc).__name__})
    return _state


def available() -> bool:
    return _ensure_loaded()["model"] is not None


def predict(samples, sample_rate: int) -> GenrePrediction:
    """Classify a mono waveform. `samples` is a 1-D numpy array or torch tensor."""
    state = _ensure_loaded()
    model = state["model"]
    if model is None:
        return GenrePrediction(
            genre=None,
            confidence=0.0,
            margin=0.0,
            model_version=None,
            available=False,
            reason=state.get("reason") or "unavailable",
        )

    import torch  # noqa: PLC0415

    from ml.labels import GENRES, decide  # noqa: PLC0415
    from ml.model import SAMPLE_RATE, SEGMENT_SAMPLES  # noqa: PLC0415

    waveform = torch.as_tensor(samples, dtype=torch.float32).flatten()
    if sample_rate != SAMPLE_RATE:
        import torchaudio  # noqa: PLC0415

        waveform = torchaudio.functional.resample(waveform, sample_rate, SAMPLE_RATE)

    # Non-overlapping windows. A clip shorter than one window is padded rather
    # than refused -- the confidence policy will abstain if there is too little
    # signal to be sure, which is the right way for it to fail.
    segments = []
    for start in range(0, max(1, waveform.numel() - SEGMENT_SAMPLES + 1), SEGMENT_SAMPLES):
        segment = waveform[start : start + SEGMENT_SAMPLES]
        if segment.numel() < SEGMENT_SAMPLES:
            segment = torch.nn.functional.pad(segment, (0, SEGMENT_SAMPLES - segment.numel()))
        segments.append(segment)
    if not segments:
        padded = torch.nn.functional.pad(waveform, (0, SEGMENT_SAMPLES - waveform.numel()))
        segments.append(padded)

    with torch.no_grad():
        probabilities = torch.softmax(model(torch.stack(segments)), dim=1).mean(dim=0)

    distribution = {genre: float(probabilities[i]) for i, genre in enumerate(GENRES)}
    label, confidence, margin = decide(distribution)
    ranked = sorted(distribution.items(), key=lambda item: item[1], reverse=True)[:3]

    return GenrePrediction(
        # `decide` returns the string "uncertain"; the API reports it as a null
        # genre so no caller can mistake it for a genre named "uncertain".
        genre=None if label == "uncertain" else label,
        confidence=confidence,
        margin=margin,
        model_version=state["metadata"].get("model_version"),
        available=True,
        reason="low_confidence" if label == "uncertain" else None,
        top={name: round(value, 4) for name, value in ranked},
    )
