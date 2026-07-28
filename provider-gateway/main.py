"""Provider gateway (Section 2.4 skeleton -> Phase 5 §5.1/§5.3/§5.6 real search).

Endpoints:
- POST /providers/search    -> real search on either approved provider, chosen
  per request by the caller's `provider` field: YouTube Data API v3
  (app/youtube_adapter.py) or Spotify Web API (app/spotify_adapter.py, §5.6).
  Direct mode per ADR-002; cached (§PROV-004/§YT-006).
- POST /providers/playlists -> real YouTube playlist export (§5.5), behind the
  ENABLE_PLAYLIST_EXPORT flag. Not implemented for Spotify.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from app import cache, db, google_token, spotify_adapter, youtube_adapter, youtube_playlist
from contracts.db_models import PlaylistExport
from shared_lib import AppError, create_app

app = create_app("provider-gateway")

# PROVIDER_MODE=direct (ADR-002): YouTube primary, Spotify limited.
_SUPPORTED_PROVIDERS = ("youtube", "spotify")

# Both adapters expose search(query, limit) -> list[NormalizedTrack-shaped dict]
# and raise a ProviderError with the same code vocabulary, so the endpoint does
# not branch on provider beyond this lookup.
_SEARCH_ADAPTERS = {
    "youtube": youtube_adapter,
    "spotify": spotify_adapter,
}

_PROVIDER_ERROR_STATUS = {
    "QUOTA_EXCEEDED": 403,
    "RATE_LIMITED": 429,
    "PROVIDER_UNAVAILABLE": 503,
    # Write-path codes (§5.5). AUTHORIZATION_REQUIRED means "connect an
    # account"; REAUTHORIZATION_REQUIRED means "the grant died, reconnect";
    # INSUFFICIENT_SCOPE means "connected, but never approved playlist access"
    # -- the UI's cue to send the user to /auth/google/upgrade (AUTH-005).
    "AUTHORIZATION_REQUIRED": 401,
    "REAUTHORIZATION_REQUIRED": 401,
    "INSUFFICIENT_SCOPE": 403,
    "MISSING_ITEM": 422,
}


class NormalizedTrack(BaseModel):
    provider: str
    provider_track_id: str
    title: str
    artist: str
    url: str
    confidence: float
    # Additive enrichment from videos.list (§5.3). All optional so an
    # unenriched result -- or a future adapter that can't supply them --
    # still satisfies the contract recommendation-service consumes.
    duration_seconds: Optional[int] = None
    # None = unknown. False = the IFrame player won't work, so the UI must
    # fall back to a plain provider link (§PLAY-005).
    embeddable: Optional[bool] = None
    duration_in_track_range: Optional[bool] = None
    # §PROV-005: where each normalized field came from.
    field_sources: dict[str, Any] = Field(default_factory=dict)


class ProviderSearchRequest(BaseModel):
    query: str
    provider: str = "youtube"
    limit: int = 5


class ProviderSearchResponse(BaseModel):
    provider: str
    results: list[NormalizedTrack]
    placeholder: bool = True


class PlaylistExportRequest(BaseModel):
    provider: str = "youtube"
    track_ids: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = None
    # Phase 5 §5.5: identifies whose OAuth grant to export with. WF-006 forwards
    # it from the envelope; it must be the real users.id, not a guest id.
    user_id: Optional[str] = None
    name: str = "Melody Export"
    description: str = ""
    request_id: Optional[str] = None


class PlaylistExportResponse(BaseModel):
    ok: bool = True
    provider: str
    playlist_id: str
    url: str
    status: str  # "completed" | "partial"
    added: list[str] = Field(default_factory=list)
    failed: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: Optional[str] = None
    # True when this request matched an existing key and no provider call was
    # made -- the repeated-click case (EXPORT-002).
    replayed: bool = False


class ConnectionStatusRequest(BaseModel):
    user_id: Optional[str] = None
    provider: str = "google"


@app.post("/providers/search", response_model=ProviderSearchResponse)
async def providers_search(request: ProviderSearchRequest) -> ProviderSearchResponse:
    provider = request.provider.lower()
    if provider not in _SUPPORTED_PROVIDERS:
        raise AppError(
            f"Unsupported provider '{request.provider}'.",
            code="UNSUPPORTED_PROVIDER",
            status_code=400,
        )
    # §5.6: Spotify search is live as of 2026-07-26. Both adapters expose the
    # same `search(query, limit)` signature, the same NormalizedTrack shape and
    # the same ProviderError code vocabulary, so dispatch is a lookup and the
    # error mapping below is shared.
    adapter = _SEARCH_ADAPTERS[provider]

    cached = cache.get(provider, request.query, request.limit)
    if cached is not None:
        results = cached
    else:
        try:
            results = await adapter.search(request.query, request.limit)
        except (youtube_adapter.ProviderError, spotify_adapter.ProviderError) as exc:
            raise AppError(
                exc.message,
                code=exc.code,
                status_code=_PROVIDER_ERROR_STATUS.get(exc.code, 502),
            ) from exc
        cache.set(provider, request.query, request.limit, results)

    return ProviderSearchResponse(
        provider=provider,
        results=[NormalizedTrack(**r) for r in results],
        placeholder=False,
    )


def _export_enabled() -> bool:
    """§ARC-004 master switch for external provider *writes*. Declared in
    .env.example and docs/feature-flags.md since Phase 0 but never referenced in
    code until now; default stays false so no unconfigured write is reachable."""
    return (os.getenv("ENABLE_PLAYLIST_EXPORT") or "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _provider_error_to_app_error(exc: youtube_adapter.ProviderError) -> AppError:
    return AppError(
        exc.message,
        code=exc.code,
        status_code=_PROVIDER_ERROR_STATUS.get(exc.code, 502),
    )


@app.post("/providers/playlists", response_model=PlaylistExportResponse)
async def providers_playlists(request: PlaylistExportRequest) -> PlaylistExportResponse:
    """EXPORT-001/002/003: create a real YouTube playlist, idempotently.

    This service owns the whole claim-key -> call-provider -> record-result
    transaction (rather than n8n splitting it across nodes), so a repeated click
    cannot create a second playlist and a crash cannot leave a claimed-but-
    unexecuted key. The idempotency key itself is generated by the Flask client
    and enforced upstream by WF-001/N8N-009 (§ARC-003).
    """
    if not _export_enabled():
        raise AppError(
            "Playlist export is disabled.",
            code="FEATURE_DISABLED",
            status_code=503,
        )

    provider = request.provider.lower()
    if provider != "youtube":
        raise AppError(
            f"Playlist export is not implemented for provider '{provider}'.",
            code="PROVIDER_NOT_IMPLEMENTED",
            status_code=501,
        )
    if not request.user_id:
        raise AppError(
            "Playlist export requires a signed-in user.",
            code="AUTHORIZATION_REQUIRED",
            status_code=401,
        )
    if not request.idempotency_key:
        raise AppError(
            "idempotency_key is required for playlist export.",
            code="VALIDATION_ERROR",
            status_code=422,
        )

    with db.session() as session:
        # 1. Replay check FIRST -- before any provider call, which is the whole
        #    point: the previous ordering called YouTube first and could create
        #    a duplicate playlist before the unique constraint was consulted.
        existing = session.execute(
            select(PlaylistExport).where(
                PlaylistExport.idempotency_key == request.idempotency_key
            )
        ).scalar_one_or_none()

        if existing is not None and existing.provider_playlist_id:
            return PlaylistExportResponse(
                provider=existing.provider,
                playlist_id=existing.provider_playlist_id,
                url=existing.url or "",
                status=existing.status,
                added=list((existing.partial_failure or {}).get("added", [])),
                failed=list((existing.partial_failure or {}).get("failed", [])),
                idempotency_key=request.idempotency_key,
                replayed=True,
            )

        # 2. Claim the key (or adopt an existing unfinished claim).
        record = existing
        if record is None:
            record = PlaylistExport(
                provider=provider,
                idempotency_key=request.idempotency_key,
                status="pending",
            )
            try:
                record.user_id = uuid.UUID(str(request.user_id))
            except (ValueError, TypeError):
                pass  # user_id is validated below by the token lookup anyway
            session.add(record)
            session.commit()

        # 3. Resolve a usable token, checking scope before spending any quota.
        try:
            grant = await google_token.get_grant(
                session, request.user_id, require_youtube_write=True
            )
        except youtube_adapter.ProviderError as exc:
            record.status = "failed"
            record.partial_failure = {"reason": exc.code}
            session.commit()
            raise _provider_error_to_app_error(exc) from exc

        # 4. Perform the external write.
        try:
            result = await youtube_playlist.export_playlist(
                access_token=grant.access_token,
                name=request.name,
                track_ids=request.track_ids,
                description=request.description,
            )
        except youtube_adapter.ProviderError as exc:
            record.status = "failed"
            record.partial_failure = {"reason": exc.code}
            session.commit()
            raise _provider_error_to_app_error(exc) from exc

        # 5. Record the outcome (EXPORT-003: history + provider playlist URL).
        record.provider_playlist_id = result["playlist_id"]
        record.url = result["url"]
        record.status = result["status"]
        record.partial_failure = {"added": result["added"], "failed": result["failed"]}
        session.commit()

        return PlaylistExportResponse(
            provider=provider,
            playlist_id=result["playlist_id"],
            url=result["url"],
            status=result["status"],
            added=result["added"],
            failed=result["failed"],
            idempotency_key=request.idempotency_key,
        )


@app.post("/providers/connection/status")
async def providers_connection_status(request: ConnectionStatusRequest) -> dict[str, Any]:
    """Connection metadata for WF-009 (§1.12).

    Returns provider/scopes/expiry/reauthorization state and **never** token
    material -- §1.12: "raw tokens must never pass through client-visible n8n
    output."
    """
    if not request.user_id:
        return {"connected": False, "provider": request.provider, "reason": "NO_USER"}
    with db.session() as session:
        return google_token.connection_status(session, request.user_id)
