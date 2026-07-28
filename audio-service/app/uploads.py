"""Reading an upload safely (AUD-UP-002, AUD-UP-003).

Kept apart from the route handlers because the order of the checks is the whole
point, and it is easy to reorder into something that looks equivalent and is not:

1. screen the *declared* type -- cheap, and rejects the obvious before we read;
2. read the body **in chunks with a running cap**, so an oversized upload is
   abandoned mid-stream rather than buffered whole and measured afterwards;
3. sniff the actual container from the bytes;
4. check that container against the allowlist.

Step 2 is the one that matters most: `await file.read()` followed by a length
check is the natural way to write this and it means a 2 GB upload is already in
memory by the time it is rejected. `MAX_UPLOAD_BYTES + 1` is the exact amount we
are willing to hold to *prove* a file is too large.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import UploadFile

from shared_lib import AppError

from . import config, sniffing

_CHUNK = 64 * 1024


@dataclass(frozen=True)
class ReadUpload:
    data: bytes
    container: str


async def read_and_validate(file: UploadFile) -> ReadUpload:
    if not sniffing.looks_declared_audio(file.content_type, file.filename):
        raise AppError(
            "That file does not look like audio.",
            code="UNSUPPORTED_MEDIA_TYPE",
            status_code=415,
        )

    limit = config.MAX_UPLOAD_BYTES
    buffer = bytearray()
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > limit:
            # Stop reading immediately; the client is told the limit so it can
            # trim the clip, which is actionable in a way "too large" is not.
            raise AppError(
                f"Audio file is larger than the {limit // (1024 * 1024)} MB limit.",
                code="PAYLOAD_TOO_LARGE",
                status_code=413,
            )

    if not buffer:
        raise AppError(
            "The uploaded file was empty.", code="VALIDATION_ERROR", status_code=422
        )

    container = sniffing.sniff(bytes(buffer[: sniffing.SNIFF_BYTES]))
    if container is None:
        raise AppError(
            "Unrecognized audio format.",
            code="UNSUPPORTED_MEDIA_TYPE",
            status_code=415,
        )
    if container not in config.ALLOWED_FORMATS:
        # Detected correctly, but not a format we accept -- a distinct case from
        # "unrecognized", and worth saying so.
        raise AppError(
            f"{container} files are not supported. Allowed: "
            + ", ".join(config.ALLOWED_FORMATS)
            + ".",
            code="UNSUPPORTED_MEDIA_TYPE",
            status_code=415,
        )
    return ReadUpload(bytes(buffer), container)


def coerce_identity(value: Optional[str]) -> Optional[str]:
    """Normalize an identity field: blank and the string "null" mean absent."""
    text = (value or "").strip()
    if not text or text.lower() in ("null", "none", "undefined"):
        return None
    return text[:128]
