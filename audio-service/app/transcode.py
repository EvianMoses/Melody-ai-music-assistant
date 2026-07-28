"""FFmpeg decode/convert boundary (AUD-UP-005).

"Convert through an argument-safe FFmpeg call without shell interpolation."

Every invocation here passes an argument *list* to `subprocess.run` with the
default `shell=False`. No string is ever formatted into a command line, so a
filename containing `; rm -rf /` is just a filename -- and in any case the only
paths that reach this module come from `storage.path_for`, which generates them.

Two further boundaries, because "no shell" is not by itself enough:

* `-t <seconds>` caps the *decoded* duration, so a 3-hour upload costs the same
  as a 30-second one (AUD-UP-002). Note it precedes `-i`, which makes FFmpeg
  stop reading input rather than decode everything and discard the tail.
* `timeout=` caps wall-clock time, because a malformed container can make
  FFmpeg spin without producing output.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config

logger = logging.getLogger("melody.audio.transcode")


class TranscodeError(RuntimeError):
    """FFmpeg could not decode the input, or is not installed."""


@dataclass(frozen=True)
class ProbeResult:
    duration_seconds: Optional[float]
    codec: Optional[str]
    sample_rate: Optional[int]
    channels: Optional[int]


def ffmpeg_available() -> bool:
    """Whether FFmpeg can actually be invoked -- used by `/health/ready`.

    Worth a readiness check rather than an import-time assert: the service can
    still serve health and reject uploads honestly without FFmpeg, and a
    container that exits on a missing binary is harder to diagnose than one
    that reports `ffmpeg: false`.
    """
    try:
        proc = subprocess.run(
            [config.FFMPEG_BINARY, "-version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def probe(source: Path) -> ProbeResult:
    """Read stream metadata with ffprobe. Never raises for a bad file."""
    args = [
        config.FFPROBE_BINARY,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels:format=duration",
        "-of", "json",
        str(source),
    ]
    try:
        proc = subprocess.run(
            args, capture_output=True, timeout=config.FFMPEG_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ProbeResult(None, None, None, None)
    if proc.returncode != 0:
        return ProbeResult(None, None, None, None)
    try:
        payload = json.loads(proc.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return ProbeResult(None, None, None, None)

    streams = payload.get("streams") or [{}]
    stream = streams[0] if streams else {}
    duration_raw = (payload.get("format") or {}).get("duration")
    try:
        duration = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None
    try:
        sample_rate = int(stream["sample_rate"]) if stream.get("sample_rate") else None
    except (TypeError, ValueError):
        sample_rate = None
    return ProbeResult(
        duration_seconds=duration,
        codec=stream.get("codec_name"),
        sample_rate=sample_rate,
        channels=stream.get("channels"),
    )


def to_analysis_wav(source: Path, destination: Path) -> Path:
    """Decode any allowed container to mono PCM WAV at the analysis rate.

    Downstream feature extraction then has exactly one input shape to handle,
    which is why the container zoo stops here rather than leaking into §6.2.
    """
    args = [
        config.FFMPEG_BINARY,
        "-nostdin",              # never block waiting on stdin
        "-v", "error",
        "-t", str(config.MAX_DURATION_SECONDS),  # before -i: stop *reading* early
        "-i", str(source),
        "-vn",                   # ignore any video stream (webm/mp4 may carry one)
        "-ac", "1",              # mono
        "-ar", str(config.ANALYSIS_SAMPLE_RATE),
        "-f", "wav",
        "-y",
        str(destination),
    ]
    try:
        proc = subprocess.run(
            args, capture_output=True, timeout=config.FFMPEG_TIMEOUT_SECONDS, check=False
        )
    except subprocess.TimeoutExpired as exc:
        # AUD-UP-006: cleanup on timeout. A partial WAV must not be analysed.
        destination.unlink(missing_ok=True)
        raise TranscodeError("Audio conversion timed out.") from exc
    except OSError as exc:
        raise TranscodeError("Audio conversion is unavailable.") from exc

    if proc.returncode != 0 or not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        # FFmpeg's stderr can echo the input path, so it is logged, never returned.
        logger.warning(
            "ffmpeg_decode_failed",
            extra={"returncode": proc.returncode,
                   "stderr": proc.stderr.decode("utf-8", "replace")[:400]},
        )
        raise TranscodeError("The audio file could not be decoded.")
    return destination
