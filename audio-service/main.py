"""Audio Service — upload, analysis and identification (§6.1–§6.4).

Endpoints:
    POST   /audio/uploads       store a clip, return an audio_job_id  (§6.1)
    POST   /audio/analyze       BPM / key / Camelot / energy + genre  (§6.2, §6.3)
    POST   /audio/identify      recognition adapter                   (§6.4)
    DELETE /audio/jobs/{id}     explicit disposal
    GET    /audio/limits        the effective configured constraints

The Phase 2 skeleton returned fixture features for anything that looked like
audio. What changed here is not just "real analysis": the *validation* was the
larger defect. It accepted a file when the declared MIME type **or** the
filename extension looked like audio, and both are supplied by the caller, so
naming a file `.wav` was enough to get in. Detection now comes from the bytes
(`app/sniffing.py`), and the file never leaves the storage boundary in
`app/storage.py`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from fastapi import File, Form, Request, UploadFile
from pydantic import BaseModel

from shared_lib import AppError, create_app

from app import acrcloud, config, features, jobs, storage, transcode, uploads

logger = logging.getLogger("melody.audio")

# How often the background sweeper runs. Independent of the retention window:
# checking more often than clips expire costs one directory listing and bounds
# how long expired bytes linger past their deadline.
_SWEEP_INTERVAL_SECONDS = 60


def _readiness() -> bool:
    """Ready only if FFmpeg can actually be invoked.

    Without it every clip fails to decode, so reporting ready would send traffic
    to a service that cannot do its one job. The result is cached once it
    succeeds: readiness is polled every 15 s by the container healthcheck and
    `ffmpeg -version` is a process spawn, not a free call.
    """
    if getattr(app.state, "ffmpeg_ok", False):
        return True
    ok = transcode.ffmpeg_available()
    app.state.ffmpeg_ok = ok
    return ok


app = create_app("audio-service", readiness=_readiness)


@app.on_event("startup")
async def _start_sweeper() -> None:
    storage.ensure_storage_dir()

    async def _loop() -> None:
        while True:
            await asyncio.sleep(_SWEEP_INTERVAL_SECONDS)
            try:
                # Blocking filesystem work off the event loop.
                await asyncio.to_thread(jobs.sweep_expired)
            except Exception:  # never let the sweeper die on one bad clip
                logger.exception("audio_sweep_error")

    app.state.sweeper = asyncio.create_task(_loop())


@app.on_event("shutdown")
async def _stop_sweeper() -> None:
    task = getattr(app.state, "sweeper", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    audio_job_id: str
    container: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    expires_in_seconds: int
    truncated: bool = False


class AudioFeatures(BaseModel):
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    camelot: Optional[str] = None
    energy: Optional[float] = None
    # None means "no genre", whether because no model is loaded or because the
    # model abstained -- `genre_model.reason` distinguishes the two (§6.3).
    genre: Optional[str] = None
    source: str
    confidence: float
    model_version: str
    genre_model: dict[str, Any] = {}
    # Per-field confidence: a clip can have an unmistakable tempo and an
    # ambiguous key, and collapsing that into one number would hide it from
    # §6.5's "down-weight uncertain features" rule (AUD-RAG-002).
    field_confidence: dict[str, float] = {}
    analyzed_seconds: Optional[float] = None


class AnalyzeResponse(BaseModel):
    audio_job_id: Optional[str] = None
    features: AudioFeatures
    placeholder: bool = False


class IdentifyResponse(BaseModel):
    matched: bool
    track: dict[str, Any]
    confidence: float
    # Recognition and analysis in one response, because the UI's result card
    # shows both and a second round trip would double the wait for a user who
    # is standing there watching. Features are reused from the job when it has
    # already been analysed rather than decoded twice.
    features: Optional[AudioFeatures] = None
    low_confidence: bool = False
    # Ranked alternatives with their own confidences. Populated even when
    # nothing cleared the threshold -- that is when they matter most.
    candidates: list[dict[str, Any]] = []
    # False once a real provider answers; True only while none is configured.
    placeholder: bool = True
    reason: Optional[str] = None
    provider: Optional[str] = None


# ---------------------------------------------------------------------------
# §6.1 — upload
# ---------------------------------------------------------------------------


@app.post("/audio/uploads", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(default=None),
    guest_id: Optional[str] = Form(default=None),
) -> UploadResponse:
    """Store one clip and return the ID the rest of the system refers to it by.

    The client gets back an opaque ID and never learns a path or filename. The
    original filename is discarded entirely at this point -- it is both
    attacker-controlled and personal, and nothing downstream needs it
    (AUD-UP-007).
    """
    read = await uploads.read_and_validate(file)

    object_id = storage.new_object_id()
    stored = storage.write_object(object_id, read.data, read.container)

    # Probe after storing: ffprobe needs a path, and a failed probe must not
    # lose an otherwise valid clip -- duration simply stays unknown.
    probed = transcode.probe(stored.path)
    duration = probed.duration_seconds

    try:
        job = jobs.create(
            audio_job_id=object_id,
            container=read.container,
            size_bytes=stored.size_bytes,
            duration_seconds=duration,
            user_id=uploads.coerce_identity(user_id),
            guest_id=uploads.coerce_identity(guest_id),
        )
    except OSError as exc:
        # AUD-UP-006: cleanup on failure. Bytes we cannot track are bytes we
        # cannot expire, so they must not survive this request.
        storage.delete_object(object_id)
        raise AppError(
            "Could not store the audio clip.", code="INTERNAL_ERROR", status_code=500
        ) from exc

    return UploadResponse(
        audio_job_id=job.audio_job_id,
        container=job.container,
        size_bytes=job.size_bytes,
        duration_seconds=duration,
        expires_in_seconds=max(0, int(job.expires_at - job.created_at)),
        # Stated rather than silent: a 4-minute song is analysed from its first
        # 30 seconds and the caller should know the verdict is partial.
        truncated=bool(duration and duration > config.MAX_DURATION_SECONDS),
    )


@app.delete("/audio/jobs/{audio_job_id}")
async def dispose(audio_job_id: str) -> dict[str, Any]:
    """Delete a clip before its expiry. Idempotent, and never reveals existence."""
    jobs.delete(audio_job_id)
    return {"ok": True, "audio_job_id": audio_job_id, "deleted": True}


@app.get("/audio/limits")
async def limits() -> dict[str, Any]:
    """The effective constraints, so the UI can enforce the same numbers."""
    return config.as_dict()


# ---------------------------------------------------------------------------
# §6.2 — analysis
# ---------------------------------------------------------------------------


def _resolve_job(
    audio_job_id: str, user_id: Optional[str], guest_id: Optional[str]
) -> jobs.AudioJob:
    job = jobs.load(audio_job_id)
    if job is None or job.is_expired():
        raise AppError(
            "That audio clip has expired or is unavailable.",
            code="NOT_FOUND",
            status_code=404,
        )
    if not job.owned_by(user_id, guest_id):
        # Deliberately the same shape as "not found": whether a job exists is
        # not something a non-owner gets to learn.
        raise AppError(
            "That audio clip has expired or is unavailable.",
            code="NOT_FOUND",
            status_code=404,
        )
    return job


async def _analyze_path(path) -> features.AnalysisResult:
    """Run the DSP off the event loop and map its failures to client errors.

    Each failure mode gets its own code because they call for different actions:
    a missing DSP stack is ours to fix (503), an undecodable file is the
    caller's (415), and an expired clip means upload again (404). Letting any of
    them fall through to the generic handler would report all three as
    INTERNAL_ERROR.
    """
    try:
        # librosa/FFmpeg are CPU-bound and blocking; keep them off the event loop.
        return await asyncio.to_thread(features.analyze_file, path)
    except features.AnalysisUnavailable as exc:
        logger.error("audio_analysis_unavailable")
        raise AppError(
            "Audio analysis is temporarily unavailable.",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
        ) from exc
    except transcode.TranscodeError as exc:
        raise AppError(str(exc), code="UNSUPPORTED_MEDIA_TYPE", status_code=415) from exc


async def _analyze_stored(job: jobs.AudioJob) -> features.AnalysisResult:
    try:
        path = storage.read_object(job.audio_job_id)
    except storage.StorageError as exc:
        raise AppError(
            "That audio clip has expired or is unavailable.",
            code="NOT_FOUND",
            status_code=404,
        ) from exc
    return await _analyze_path(path)


@app.post("/audio/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: Request,
    file: Optional[UploadFile] = File(default=None),
    audio_job_id: Optional[str] = Form(default=None),
    user_id: Optional[str] = Form(default=None),
    guest_id: Optional[str] = Form(default=None),
) -> AnalyzeResponse:
    """Extract real features from a stored job, or from a direct upload.

    Accepts multipart *or* JSON, because the two callers differ: the browser
    posts a file, while n8n (WF-003) has only an `audio_job_id` and sends JSON.
    Declaring `File`/`Form` alone made every JSON call fail with 422 even when
    it carried a valid job ID.
    """
    if audio_job_id is None and request.headers.get("content-type", "").startswith(
        "application/json"
    ):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            value = payload.get("audio_job_id")
            audio_job_id = str(value) if value else None
            user_id = user_id or payload.get("user_id")
            guest_id = guest_id or payload.get("guest_id")

    user_id = uploads.coerce_identity(user_id)
    guest_id = uploads.coerce_identity(guest_id)

    if audio_job_id:
        job = _resolve_job(audio_job_id, user_id, guest_id)
        result = await _analyze_stored(job)
        # Cache on the job so a second call (identify, then vibe-match) does not
        # decode the same clip twice inside one 15-minute window.
        job.derived_features = result.as_dict()
        job.state = "analyzed"
        jobs.save(job)
        return AnalyzeResponse(audio_job_id=audio_job_id, features=AudioFeatures(**result.as_dict()))

    if file is None:
        raise AppError(
            "Provide either an audio file or an audio_job_id.",
            code="VALIDATION_ERROR",
            status_code=422,
        )

    # Direct upload: store, analyse, and dispose immediately. The clip is not
    # kept, because nothing was given an ID to come back for it with.
    read = await uploads.read_and_validate(file)
    object_id = storage.new_object_id()
    stored = storage.write_object(object_id, read.data, read.container)
    try:
        result = await _analyze_path(stored.path)
    finally:
        # Runs on success, failure and cancellation alike (AUD-UP-006).
        storage.delete_object(object_id)
    return AnalyzeResponse(audio_job_id=None, features=AudioFeatures(**result.as_dict()))


# ---------------------------------------------------------------------------
# §6.4 — identification via ACRCloud (ADR-004). Degrades to a stated gap, never
# to a fabricated match, when no credentials are present.
# ---------------------------------------------------------------------------


@app.post("/audio/identify", response_model=IdentifyResponse)
async def identify(
    request: Request,
    file: Optional[UploadFile] = File(default=None),
    audio_job_id: Optional[str] = Form(default=None),
    user_id: Optional[str] = Form(default=None),
    guest_id: Optional[str] = Form(default=None),
) -> IdentifyResponse:
    """Recognize a clip via ACRCloud, and return its features in the same answer.

    Three outcomes, deliberately distinct, because collapsing them is how a user
    is told "we couldn't recognize your song" for a feature that never ran:

    * `placeholder: true`  — no provider configured. A stated gap.
    * `matched: false`     — the provider ran and recognized nothing. A real answer.
    * `matched: true`      — with a score, and `low_confidence` when it is marginal.

    Features come back regardless of whether recognition succeeded: BPM, key and
    genre are useful on their own, and they are what the "similar vibe" follow-up
    runs on. They are read from the job's cache when it has already been
    analysed, so the common record → identify → similar flow decodes once.
    """
    if audio_job_id is None and request.headers.get("content-type", "").startswith(
        "application/json"
    ):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            if payload.get("audio_job_id"):
                audio_job_id = str(payload["audio_job_id"])
            # Identity has to be read here too, not just in /audio/analyze.
            # Omitting it made the ownership check see no caller at all, so a
            # guest's own clip -- uploaded with their guest_id -- was refused
            # with NOT_FOUND, which WF-004 then reported as UPSTREAM_ERROR.
            user_id = user_id or payload.get("user_id")
            guest_id = guest_id or payload.get("guest_id")

    job: Optional[jobs.AudioJob] = None
    temporary_object: Optional[str] = None

    if audio_job_id:
        job = _resolve_job(
            audio_job_id,
            uploads.coerce_identity(user_id),
            uploads.coerce_identity(guest_id),
        )
        try:
            clip_path = storage.read_object(job.audio_job_id)
        except storage.StorageError as exc:
            # Metadata outlived the bytes -- same user-facing state as expiry.
            raise AppError(
                "That audio clip has expired or is unavailable.",
                code="NOT_FOUND",
                status_code=404,
            ) from exc
    elif file is not None:
        read = await uploads.read_and_validate(file)
        temporary_object = storage.new_object_id()
        clip_path = storage.write_object(temporary_object, read.data, read.container).path
    else:
        raise AppError(
            "Provide either an audio file or an audio_job_id.",
            code="VALIDATION_ERROR",
            status_code=422,
        )

    try:
        features_dict = (job.derived_features if job else None) or {}
        if not features_dict:
            try:
                analysis = await _analyze_path(clip_path)
                features_dict = analysis.as_dict()
                if job is not None:
                    job.derived_features = features_dict
                    job.state = "analyzed"
                    jobs.save(job)
            except AppError:
                # Analysis failing must not take recognition down with it --
                # they are independent answers and either is useful alone.
                logger.warning("identify_analysis_failed")
                features_dict = {}

        # ACRCloud wants a short PCM excerpt, not an arbitrary container. The
        # analysis WAV is already mono, resampled and duration-capped, so
        # converting once serves both purposes.
        recognition = await _recognize(clip_path)
    finally:
        if temporary_object:
            storage.delete_object(temporary_object)

    return IdentifyResponse(
        matched=recognition.matched,
        track=recognition.track,
        confidence=recognition.confidence,
        features=AudioFeatures(**features_dict) if features_dict else None,
        low_confidence=recognition.low_confidence,
        candidates=recognition.candidates,
        # `placeholder` is a claim about the response: true only while no
        # provider exists to ask. A configured provider answering "no match" is
        # a real result, not a placeholder.
        placeholder=not recognition.configured,
        reason=recognition.reason,
        provider=recognition.provider if recognition.configured else None,
    )


async def _recognize(clip_path) -> acrcloud.Recognition:
    """Convert to the excerpt ACRCloud expects, then ask it."""
    if not acrcloud.is_configured():
        return acrcloud.Recognition(
            configured=False, matched=False, confidence=0.0, reason="not_configured"
        )
    with tempfile.TemporaryDirectory(prefix="melody-recognize-") as workdir:
        excerpt = Path(workdir) / "excerpt.wav"
        try:
            await asyncio.to_thread(transcode.to_analysis_wav, clip_path, excerpt)
        except transcode.TranscodeError:
            return acrcloud.Recognition(True, False, 0.0, reason="undecodable")

        result = await acrcloud.identify(excerpt, data_type=acrcloud.DATA_TYPE_AUDIO)
        if result.matched or not result.configured:
            return result

        # A hum shares no spectral fingerprint with the recording it is a hum
        # of, so the humming index is a genuinely separate search -- one the
        # recording index can never satisfy. Retried only on a miss: a miss is
        # already the slow path, so the second request costs nothing anybody is
        # waiting on in the common case.
        if result.reason in ("no_match", "below_threshold", "junk_metadata_only"):
            hummed = await acrcloud.identify(
                excerpt, data_type=acrcloud.DATA_TYPE_HUMMING
            )
            if hummed.matched:
                # Marked so the UI can say "sounds like you were humming",
                # and so the POC can tell the two indexes apart in its results.
                return replace(hummed, provider="acrcloud:humming")
            # Keep the *audio* verdict when both miss: it is the one that
            # searched the index the clip most likely belongs to.
            logger.info("acrcloud_humming_fallback_missed", extra={"reason": hummed.reason})
        return result


@app.get("/audio/recognition/status")
async def recognition_status() -> dict[str, Any]:
    """Whether recognition is usable, and if not, precisely what is missing.

    Exists because `3001 Missing/Invalid Access Key` is ACRCloud's answer to a
    wrong key, a wrong host *and* a wrong product's credentials alike, so the
    only way to tell them apart from outside is to report what we hold.
    Lengths, never values.
    """
    return acrcloud.describe_configuration()
