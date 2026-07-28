"""Temporary clip storage keyed by a server-generated object ID (§6.1).

Covers AUD-UP-004 (random server-side object ID), AUD-UP-006 (cleanup on
success, failure, timeout and scheduled expiry) and AUD-UP-007 (never log raw
bytes, temporary paths, or original filenames).

Two rules hold everything together:

* **The client never names a file.** Object IDs are generated here from
  `secrets`, and `path_for` refuses anything that is not one of ours. A caller
  passing a user-supplied string cannot escape the storage root, because the
  string never reaches the filesystem unless it matches the ID grammar.
* **Nothing identifying is logged.** The original filename is attacker-
  controlled *and* personal (people name recordings after themselves), the
  absolute path exposes deployment layout, and the bytes are the payload. Only
  the object ID, byte count and container appear in logs.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from . import config

logger = logging.getLogger("melody.audio.storage")

# 32 hex chars = 128 bits. Unguessable, and a strict grammar so `path_for` can
# reject anything that did not come out of `new_object_id`.
_OBJECT_ID_RE = re.compile(r"^[0-9a-f]{32}$")

# Written alongside the clip so the sweeper and `/audio/analyze` know the
# container without re-sniffing, and so a crashed upload leaves no orphan.
_SUFFIX = ".bin"


class StorageError(RuntimeError):
    """Raised when a stored object cannot be located or read."""


@dataclass(frozen=True)
class StoredObject:
    """A clip on disk. `object_id` is the only part safe to hand to a client."""

    object_id: str
    path: Path
    container: str
    size_bytes: int


def new_object_id() -> str:
    return secrets.token_hex(16)


def ensure_storage_dir() -> Path:
    # 0o700: the clip is a user's recording, readable only by the service user.
    config.STORAGE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    return config.STORAGE_DIR


def path_for(object_id: str) -> Path:
    """Resolve an object ID to its path, refusing anything we did not generate.

    This is the single choke point between an identifier and the filesystem.
    Validating the grammar (rather than sanitizing the string) means traversal
    sequences, absolute paths and NUL bytes are rejected outright instead of
    being rewritten into something that might still escape.
    """
    if not _OBJECT_ID_RE.match(object_id or ""):
        raise StorageError("Unknown audio object.")
    return config.STORAGE_DIR / f"{object_id}{_SUFFIX}"


def write_object(object_id: str, data: bytes, container: str) -> StoredObject:
    ensure_storage_dir()
    path = path_for(object_id)
    # Exclusive create: a colliding ID is a bug worth failing on, never an
    # overwrite of somebody else's clip.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    except BaseException:
        # AUD-UP-006: cleanup on failure. A half-written clip is not left behind.
        delete_object(object_id)
        raise
    logger.info(
        "audio_object_stored",
        extra={"object_id": object_id, "container": container, "size_bytes": len(data)},
    )
    return StoredObject(object_id, path, container, len(data))


def read_object(object_id: str) -> Path:
    path = path_for(object_id)
    if not path.is_file():
        # Expired, swept, or never existed -- all indistinguishable to a client,
        # and deliberately so.
        raise StorageError("Audio clip is no longer available.")
    return path


def delete_object(object_id: str) -> bool:
    """Delete a stored clip. Idempotent: deleting twice is not an error."""
    try:
        path = path_for(object_id)
    except StorageError:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        logger.warning("audio_object_delete_failed", extra={"object_id": object_id})
        return False
    logger.info("audio_object_deleted", extra={"object_id": object_id})
    return True


def _stored_objects() -> Iterator[Path]:
    if not config.STORAGE_DIR.is_dir():
        return
    for entry in config.STORAGE_DIR.iterdir():
        if entry.is_file() and entry.suffix == _SUFFIX:
            yield entry


def sweep_expired(now: Optional[float] = None) -> int:
    """Delete clips older than the retention window. Returns the count removed.

    Scheduled expiry (AUD-UP-006) is deliberately based on the file's own mtime
    rather than a database column: if the DB row is lost, or a request dies
    between writing the file and committing the row, the bytes still expire.
    Storage cleanup must not depend on bookkeeping that can go missing.
    """
    cutoff = (now or time.time()) - config.RETENTION_MINUTES * 60
    removed = 0
    for entry in _stored_objects():
        try:
            if entry.stat().st_mtime <= cutoff:
                entry.unlink()
                removed += 1
        except FileNotFoundError:
            continue
        except OSError:
            logger.warning("audio_sweep_failed", extra={"object_id": entry.stem})
    if removed:
        logger.info("audio_sweep_removed", extra={"removed": removed})
    return removed
