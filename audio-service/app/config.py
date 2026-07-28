"""Explicit audio-pipeline limits (§6.1).

The plan requires the initial constraints to be *configuration values*, not
constants buried in handler code: "maximum upload size, maximum processed
duration, allowed formats, and retention minutes". They are read from the
environment once at import so a deployment can tighten them without a rebuild,
and so a test can state the limit it is exercising instead of guessing it.

Every value here is a safety boundary. Widening one is a deliberate act.
"""

from __future__ import annotations

import os
from pathlib import Path

_MIB = 1024 * 1024


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    """Read a positive int, falling back to the default on anything unusable.

    A malformed limit must never become an *absent* limit: an unparseable
    ``AUDIO_MAX_UPLOAD_BYTES`` falls back to the documented default rather than
    disabling the check.
    """
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    items = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    return items or default


# AUD-UP-002 — server-side size limit. 15 MiB comfortably holds a 30 s clip in
# any allowed format, including uncompressed WAV (~5 MB at 44.1 kHz stereo).
MAX_UPLOAD_BYTES: int = _int_env("AUDIO_MAX_UPLOAD_BYTES", 15 * _MIB, minimum=1024)

# AUD-UP-002 — we never *analyse* more than this, however long the upload is.
# Recognition and feature extraction both work from a short excerpt, so a long
# file is truncated rather than rejected.
MAX_DURATION_SECONDS: int = _int_env("AUDIO_MAX_DURATION_SECONDS", 30)

# Formats we are willing to decode. `webm` and `mp4` matter as much as the
# classical formats: they are what a browser's MediaRecorder actually produces,
# so omitting them would break recording (AUD-UP-001) while looking correct.
ALLOWED_FORMATS: tuple[str, ...] = _csv_env(
    "AUDIO_ALLOWED_FORMATS",
    ("wav", "mp3", "flac", "m4a", "mp4", "ogg", "webm"),
)

# AUD-UP-006 — how long a stored clip may survive before the sweeper deletes it.
RETENTION_MINUTES: int = _int_env("AUDIO_RETENTION_MINUTES", 15)

# AUD-UP-004 — approved temporary storage. A directory, never user-controlled:
# object names are generated server-side (see storage.new_object_id).
STORAGE_DIR: Path = Path(
    (os.getenv("AUDIO_STORAGE_DIR") or "").strip() or "/tmp/melody-audio"
)

# Analysis working format. Mono 22.05 kHz is the standard librosa working rate:
# ample for BPM/key/energy, and a quarter of the samples of 44.1 kHz stereo.
ANALYSIS_SAMPLE_RATE: int = _int_env("AUDIO_ANALYSIS_SAMPLE_RATE", 22_050)

# Hard ceiling on how long FFmpeg may run for one clip, so a malformed file
# cannot pin a worker open indefinitely.
FFMPEG_TIMEOUT_SECONDS: int = _int_env("AUDIO_FFMPEG_TIMEOUT_SECONDS", 30)

FFMPEG_BINARY: str = (os.getenv("AUDIO_FFMPEG_BINARY") or "").strip() or "ffmpeg"
FFPROBE_BINARY: str = (os.getenv("AUDIO_FFPROBE_BINARY") or "").strip() or "ffprobe"


def as_dict() -> dict[str, object]:
    """The effective limits, for `/health/ready` and for tests to assert on."""
    return {
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_duration_seconds": MAX_DURATION_SECONDS,
        "allowed_formats": list(ALLOWED_FORMATS),
        "retention_minutes": RETENTION_MINUTES,
        "analysis_sample_rate": ANALYSIS_SAMPLE_RATE,
    }
