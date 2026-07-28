"""Recommendation service (Section 2.4 skeleton -> Phase 4 real engine).

Endpoints:
- POST /recommendations/run  -> invokes the compiled LangGraph (app/core/graph.py,
  §4.2 nodes 1-18)
- POST /profiles/update      -> apply one feedback event (§7.2)
- GET  /profiles             -> the caller's current profile
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core import profile, profile_store
from app.core.graph import recommendation_graph
from shared_lib import create_app

app = create_app("recommendation-service")


class TrackRecommendation(BaseModel):
    """A track item plus the playback references a client needs (§4.8).

    Superset of contracts/ai_recommendation_schema.json's track item: the
    frozen schema requires title/artist/reasoning and sets no
    ``additionalProperties: false``, so carrying the provider fields alongside
    them is contract-valid.

    These fields are not decoration. §4.8 requires "structured provider IDs
    separate from prose", and until this model carried them the graph resolved
    a real YouTube video for every track and then discarded the id, url and
    embeddability on the way out -- which made UI-005 (cards with real playback
    references) and PLAY-001/PLAY-005 unimplementable no matter what the UI did.
    They are optional so a track that never reached a provider still serializes.
    """

    title: str
    artist: str
    reasoning: str
    provider: Optional[str] = None
    provider_track_id: Optional[str] = None
    url: Optional[str] = None
    # None = unknown. False means the IFrame player will refuse the video and
    # the UI must fall back to a plain provider link (§PLAY-005).
    embeddable: Optional[bool] = None
    duration_seconds: Optional[int] = None
    # Playback order from the sequencer (§4.2 node 16), 1-based.
    position: Optional[int] = None


class RecommendationRunRequest(BaseModel):
    # Accepts either WF-001/WF-002's envelope shape
    # ({request_id, user_id, intent, locale, context: RecommendationContext})
    # or a flat fixture-style payload; extra keys are tolerated while the
    # contract stabilizes.
    model_config = ConfigDict(extra="allow")

    request_id: Optional[str] = None
    user_id: Optional[str] = None
    locale: Optional[str] = None
    user_text: str = ""
    discovery_mode: str = "balanced"
    context: dict[str, Any] = Field(default_factory=dict)


class RecommendationRunResponse(BaseModel):
    playlist_title: str
    playlist_description: str
    tracks: list[TrackRecommendation]
    engine: str = "fixture"
    placeholder: bool = True


def _unwrap_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the RecommendationContext, whichever shape the caller sent.

    This function exists because of a live defect (2026-07-26). The service was
    written expecting ``context`` to *be* a RecommendationContext, but WF-002
    forwards ``$json.envelope`` -- the whole ``RequestEnvelope``, whose real
    context sits at ``body.recommendation_context``. Nothing errored: every
    lookup below simply missed, so ``user_text`` resolved to ``""`` and every
    recommendation placed through n8n was generated from an *empty query*.
    A request for "dreamy shoegaze for a rainy night" came back with H.E.R.
    and a YouTube commentary channel under the title "Audio Discovery".

    It stayed invisible because the direct callers -- the smoke test, the
    REC-LEG harness, every manual probe -- send the flat shape, which works.
    Only the browser path goes through WF-002.

    Accepting both shapes here, rather than only correcting WF-002's mapping,
    keeps the same silent-miss from reappearing via WF-003/WF-004.
    """
    context = payload.get("context")
    if not isinstance(context, dict):
        return {}
    # A full RequestEnvelope: descend to the context it carries.
    body = context.get("body")
    if isinstance(body, dict):
        nested = body.get("recommendation_context")
        if isinstance(nested, dict):
            # `prompt` is the envelope's authoritative user text; the nested
            # context repeats it, but fall back to it if the copy is missing.
            return {**nested, "user_text": nested.get("user_text") or body.get("prompt") or ""}
        return {"user_text": body.get("prompt") or "", "locale": context.get("locale")}
    return context


def _build_initial_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Map WF-002's RecommendationContext envelope (or a flat fixture-style
    payload) onto the initial ``RecommendationState`` the graph consumes."""
    context = _unwrap_context(payload)

    explicit_constraints: dict[str, Any] = {}
    constraints_src = context.get("constraints")
    if isinstance(constraints_src, dict):
        explicit_constraints.update({k: v for k, v in constraints_src.items() if v is not None})
    exclusions = context.get("exclusions")
    if exclusions:
        explicit_constraints["avoid"] = exclusions

    discovery_mode = (
        context.get("discovery_mode") or payload.get("discovery_mode", "balanced")
    )

    # §7.2 / Phase 7 gate: "the next recommendation uses the updated profile".
    # A caller-supplied profile still wins -- WF-002 may already have one, and a
    # test fixture must stay authoritative -- but when nothing is supplied the
    # stored profile is loaded here. Without this the engine accepted a profile
    # it was handed and never once read the one it had been building, so every
    # Like was recorded and then ignored.
    # Named `taste_profile`, not `profile`: `profile` is the module imported at
    # the top of this file, and a local of the same name shadows it. Harmless
    # today because this function never calls the module -- and a trap the first
    # time somebody adds a line that does.
    taste_profile = context.get("taste_profile") or payload.get("user_profile")
    if not taste_profile:
        stored = profile_store.load(
            user_id=payload.get("user_id") or context.get("user_id"),
            guest_id=payload.get("guest_id") or context.get("guest_id"),
        )
        # An empty profile is left as None so the graph injects its guest
        # default, rather than being handed a profile that claims a version of 0.
        taste_profile = stored.to_graph_profile(discovery_mode) if stored.version else None

    return {
        "request_id": payload.get("request_id") or context.get("request_id") or "",
        "user_id": payload.get("user_id"),
        "user_text": context.get("user_text") or payload.get("user_text", ""),
        "discovery_mode": discovery_mode,
        # §5.6 provider mode selected in the UI. A default the request text can
        # override -- see graph_nodes.resolve_provider.
        "provider": context.get("provider") or payload.get("provider"),
        "language": context.get("locale") or payload.get("locale"),
        "region": payload.get("region"),
        "audio_features": context.get("audio_features") or payload.get("audio_features") or {},
        "user_profile": taste_profile,
        "explicit_constraints": explicit_constraints,
    }


class ProfileUpdateRequest(BaseModel):
    """Identity may be a signed-in user *or* a guest.

    ``user_id`` was previously required, which rejected every guest request with
    a 422 — but guest mode is a P0 requirement (WF-002: "Guest mode works with an
    empty profile"), and WF-001 sends ``user_id: null`` for an unauthenticated
    visitor. At least one of the two identifiers must be present.
    """

    user_id: Optional[str] = None
    guest_id: Optional[str] = None
    signals: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_an_identity(self) -> "ProfileUpdateRequest":
        if not self.user_id and not self.guest_id:
            raise ValueError("either user_id or guest_id is required")
        return self

    @property
    def subject_id(self) -> str:
        """The identifier the profile is keyed on."""
        return self.user_id or self.guest_id or ""


class ProfileUpdateResponse(BaseModel):
    user_id: Optional[str] = None
    guest_id: Optional[str] = None
    version: int
    discovery_mode: str
    weights: dict[str, float]
    # The interpretable profile itself (§7.2), so a caller can see *what*
    # changed and not just that a number went up.
    profile: dict[str, Any] = Field(default_factory=dict)
    explanation: list[str] = Field(default_factory=list)
    # Whether the new version reached the database. Reported rather than
    # assumed: a guest whose id is not a UUID has no `guest_sessions` row to
    # hang a profile on, and pretending that write happened would make the
    # next recommendation's behaviour inexplicable.
    persisted: bool = False
    # False as of Phase 7 — this endpoint stopped being a stub.
    placeholder: bool = False


@app.post("/recommendations/run", response_model=RecommendationRunResponse)
async def run_recommendation(request: RecommendationRunRequest) -> RecommendationRunResponse:
    initial_state = _build_initial_state(request.model_dump())
    final_state = await recommendation_graph.ainvoke(initial_state)

    tracks = [
        TrackRecommendation(
            title=t.get("title", ""),
            artist=t.get("artist", ""),
            reasoning=t.get("reasoning", ""),
            provider=t.get("provider"),
            provider_track_id=t.get("provider_track_id"),
            url=t.get("url"),
            embeddable=t.get("embeddable"),
            duration_seconds=t.get("duration_seconds"),
            position=t.get("position"),
        )
        for t in final_state.get("sequenced_tracks", [])
    ]
    return RecommendationRunResponse(
        playlist_title=final_state.get("playlist_title") or "Your Melody Mix",
        playlist_description=final_state.get("curator_explanation") or "",
        tracks=tracks,
        engine="graph",
        placeholder=False,
    )


@app.post("/profiles/update", response_model=ProfileUpdateResponse)
async def update_profile(request: ProfileUpdateRequest) -> ProfileUpdateResponse:
    """Apply one feedback event to the caller's profile (§7.2, PERS-004/005).

    Real as of Phase 7, replacing the deterministic weighted-profile stub: load
    the latest version, apply the signal through the pure update rules, append a
    new version. The write is append-only, so the history of a profile stays
    inspectable.

    Never raises on a storage problem: answering the user's next request matters
    more than recording this click, so a failed write degrades to an in-memory
    profile and says so via `persisted`.
    """
    current = profile_store.load(user_id=request.user_id, guest_id=request.guest_id)
    signal = profile.FeedbackSignal.from_dict(request.signals or {})
    discovery_mode = (request.signals or {}).get("discovery_mode")

    before = current.version
    updated = profile.update(current, signal, discovery_mode=discovery_mode)

    persisted = False
    if updated.version != before:
        persisted = profile_store.save(
            updated, user_id=request.user_id, guest_id=request.guest_id
        )

    shaped = updated.to_graph_profile(discovery_mode)
    return ProfileUpdateResponse(
        user_id=request.user_id,
        guest_id=request.guest_id,
        version=updated.version,
        discovery_mode=shaped["discovery_mode"],
        weights=shaped["weights"],
        profile=updated.to_dict(),
        explanation=profile.explain(updated),
        persisted=persisted,
    )


@app.get("/profiles", response_model=ProfileUpdateResponse)
async def read_profile(
    user_id: Optional[str] = None, guest_id: Optional[str] = None
) -> ProfileUpdateResponse:
    """The caller's current profile, without changing it.

    The recommendation path reads this so the *next* recommendation reflects the
    last Like — which is the Phase 7 gate criterion, and was impossible before
    because nothing ever loaded a stored profile.
    """
    current = profile_store.load(user_id=user_id, guest_id=guest_id)
    shaped = current.to_graph_profile()
    return ProfileUpdateResponse(
        user_id=user_id,
        guest_id=guest_id,
        version=current.version,
        discovery_mode=shaped["discovery_mode"],
        weights=shaped["weights"],
        profile=current.to_dict(),
        explanation=profile.explain(current),
        persisted=profile_store.available(),
    )
