"""Job metadata for an uploaded clip (§6.1).

An "audio job" is a stored clip plus the little we know about it: who uploaded
it, what container it turned out to be, when it expires, and any features we
have already derived. It lives in a JSON sidecar next to the clip rather than in
the `audio_jobs` table.

**Why the sidecar and not the table** (deviation from the Phase 2 schema, taken
deliberately): the clip and its metadata have exactly the same fifteen-minute
lifetime, and cleanup must not depend on bookkeeping that can go missing. With a
sidecar, one directory sweep expires both, and a row can never outlive its bytes
or point at a file that is already gone. It also keeps audio-service free of a
database dependency it otherwise does not need, so its tests run offline like
every other service's. `audio_jobs` remains the right home once a job outlives
its clip -- which is what §8.3's async job queue will introduce.

Identity is recorded so `/audio/analyze` can check that the caller owns the job.
Object IDs are already 128-bit unguessable capabilities; the ownership check is
the second lock, so that a leaked ID in a log or referrer is not enough on its own.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from . import config, storage

logger = logging.getLogger("melody.audio.jobs")

_META_SUFFIX = ".json"


@dataclass
class AudioJob:
    audio_job_id: str
    container: str
    size_bytes: int
    created_at: float
    expires_at: float
    user_id: Optional[str] = None
    guest_id: Optional[str] = None
    state: str = "stored"
    duration_seconds: Optional[float] = None
    derived_features: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) >= self.expires_at

    def owned_by(self, user_id: Optional[str], guest_id: Optional[str]) -> bool:
        """Whether this caller may act on the job.

        A job with no recorded owner is treated as open: it was uploaded before
        identity was available, and refusing it would break the anonymous path
        the rest of the app supports. A job *with* an owner may only be used by
        that owner -- a signed-in user's clip never becomes reachable by a guest
        who happens to learn the ID.
        """
        if self.user_id is None and self.guest_id is None:
            return True
        if self.user_id is not None and user_id is not None:
            return self.user_id == user_id
        if self.guest_id is not None and guest_id is not None:
            return self.guest_id == guest_id
        return False

    def public_dict(self) -> dict[str, Any]:
        """The client-safe view: no owner identifiers, no storage paths."""
        return {
            "audio_job_id": self.audio_job_id,
            "container": self.container,
            "size_bytes": self.size_bytes,
            "duration_seconds": self.duration_seconds,
            "state": self.state,
            "expires_in_seconds": max(0, int(self.expires_at - time.time())),
        }


def _meta_path(audio_job_id: str):
    # Reuses storage's grammar check, so a malformed ID cannot reach the disk.
    return storage.path_for(audio_job_id).with_suffix(_META_SUFFIX)


def create(
    *,
    audio_job_id: str,
    container: str,
    size_bytes: int,
    duration_seconds: Optional[float],
    user_id: Optional[str],
    guest_id: Optional[str],
) -> AudioJob:
    now = time.time()
    job = AudioJob(
        audio_job_id=audio_job_id,
        container=container,
        size_bytes=size_bytes,
        created_at=now,
        expires_at=now + config.RETENTION_MINUTES * 60,
        user_id=user_id,
        guest_id=guest_id,
        duration_seconds=duration_seconds,
    )
    save(job)
    return job


def save(job: AudioJob) -> None:
    path = _meta_path(job.audio_job_id)
    path.write_text(json.dumps(asdict(job)), encoding="utf-8")


def load(audio_job_id: str) -> Optional[AudioJob]:
    try:
        path = _meta_path(audio_job_id)
    except storage.StorageError:
        return None
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AudioJob(**payload)
    except (json.JSONDecodeError, TypeError, OSError):
        # Corrupt sidecar: treat the job as gone rather than half-trusting it.
        logger.warning("audio_job_metadata_unreadable", extra={"object_id": audio_job_id})
        return None


def delete(audio_job_id: str) -> None:
    """Remove a job completely -- clip and metadata (AUD-UP-006)."""
    try:
        _meta_path(audio_job_id).unlink(missing_ok=True)
    except storage.StorageError:
        return
    storage.delete_object(audio_job_id)


def count_stored() -> int:
    """How many clips are currently in the approved temporary store.

    Counted from the sidecars rather than the audio files, so a clip whose
    bytes are gone but whose metadata lingers is not counted as present. Used by
    the WF-010 sweep endpoint to report before/after rather than just a delta --
    "removed 0" means something quite different when 0 remain than when 40 do.
    """
    if not config.STORAGE_DIR.is_dir():
        return 0
    return sum(1 for _ in config.STORAGE_DIR.glob(f"*{_META_SUFFIX}"))


def sweep_expired(now: Optional[float] = None) -> int:
    """Expire clips *and* their sidecars. Returns the number of jobs removed."""
    now = now or time.time()
    removed = 0
    if config.STORAGE_DIR.is_dir():
        for entry in list(config.STORAGE_DIR.glob(f"*{_META_SUFFIX}")):
            job = load(entry.stem)
            # An unreadable sidecar is swept on age alone, so corruption cannot
            # pin a clip in storage forever.
            expired = job.is_expired(now) if job else entry.stat().st_mtime <= (
                now - config.RETENTION_MINUTES * 60
            )
            if expired:
                delete(entry.stem)
                removed += 1
    # Second pass catches clips whose sidecar never landed (a crash between the
    # two writes), which the metadata loop above cannot see.
    removed += storage.sweep_expired(now)
    if removed:
        logger.info("audio_jobs_swept", extra={"removed": removed})
    return removed
