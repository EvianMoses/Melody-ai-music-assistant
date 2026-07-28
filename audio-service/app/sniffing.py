"""Container detection from the bytes themselves (AUD-UP-003).

The plan is explicit: "Detect actual MIME/container type; do not trust filename
extension." The Phase 2 skeleton did exactly what it forbids -- it accepted a
file if `content_type` *or* the filename extension looked like audio, both of
which are attacker-supplied strings. `evil.wav` with a `audio/wav` header and a
PE executable inside passed.

This module reads the leading bytes and matches real container signatures. The
declared type is used for one thing only: an early, cheap rejection before we
read the body. The stored decision always comes from `sniff`.

No third-party dependency: the signatures we need are short and stable, and
`libmagic` would add a system package for a dozen byte comparisons.
"""

from __future__ import annotations

from typing import Optional

# Enough to cover every signature below, including the ID3 tag case.
SNIFF_BYTES = 64


def _is_mp3(head: bytes) -> bool:
    if head.startswith(b"ID3"):
        return True
    # A bare MPEG audio frame: 11 sync bits, then a version/layer nibble that is
    # not the "reserved" pattern. 0xFFE0 masking avoids matching plain 0xFFFF
    # padding, which is common in unrelated binaries.
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        version = (head[1] >> 3) & 0x03
        layer = (head[1] >> 1) & 0x03
        return version != 0x01 and layer != 0x00
    return False


def _isobmff_brand(head: bytes) -> Optional[str]:
    """Return the container name for an ISO base-media file, else None.

    m4a and mp4 share a structure: a size-prefixed `ftyp` box at offset 4 whose
    major brand names the flavour. We keep them distinct because only some
    brands are audio, and reporting `mp4` for a video file is honest.
    """
    if len(head) < 12 or head[4:8] != b"ftyp":
        return None
    brand = head[8:12]
    if brand in (b"M4A ", b"M4B ", b"M4P "):
        return "m4a"
    if brand[:3] in (b"mp4", b"iso", b"avc") or brand in (b"dash", b"qt  "):
        return "mp4"
    # Unknown brand, but structurally an ISOBMFF file. Let FFmpeg have the last
    # word rather than guessing: report the generic container.
    return "mp4"


def sniff(head: bytes) -> Optional[str]:
    """Identify the container from its leading bytes, or None if unrecognized.

    Returns a short container name matching `config.ALLOWED_FORMATS`.
    """
    if not head:
        return None

    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "wav"
    if head.startswith(b"fLaC"):
        return "flac"
    if head.startswith(b"OggS"):
        return "ogg"
    # EBML -- both .webm and .mkv. MediaRecorder's audio output is a WebM/Opus
    # stream, so this is the single most important signature for recording.
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    if head.startswith(b"FORM") and head[8:12] == b"AIFF":
        return "aiff"

    brand = _isobmff_brand(head)
    if brand:
        return brand
    # Checked last: the MPEG sync pattern is only two bytes, so a stricter
    # signature must win over it wherever both could match.
    if _is_mp3(head):
        return "mp3"
    return None


def looks_declared_audio(content_type: Optional[str], filename: Optional[str]) -> bool:
    """Cheap pre-read screen on the *declared* type.

    Deliberately permissive and deliberately not authoritative -- it exists to
    reject an obvious `text/plain` before we spend bandwidth reading the body.
    `sniff` makes the real decision.
    """
    declared = (content_type or "").lower()
    if declared.startswith("audio/") or declared.startswith("video/"):
        return True
    # Browsers sometimes send application/octet-stream for a recorded blob, and
    # some send nothing at all. Neither is grounds for rejection on its own.
    if declared in ("", "application/octet-stream", "binary/octet-stream"):
        return True
    return False
