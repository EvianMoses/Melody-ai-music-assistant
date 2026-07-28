"""Canonical Phase 2 request contracts for Flask → n8n (WF-001).

Field keys remain stable even when values are empty (Section 3.1 / 3.2).
Implemented with dataclasses so the Flask path has no extra dependency;
FastAPI services can later mirror these shapes with Pydantic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class Intent(str, Enum):
    TEXT_RECOMMENDATION = "text_recommendation"
    AUDIO_VIBE_RECOMMENDATION = "audio_vibe_recommendation"
    AUDIO_IDENTIFICATION = "audio_identification"
    FEEDBACK = "feedback"
    PLAYLIST_EXPORT = "playlist_export"
    AUTH_CONNECTION_SYNC = "auth_connection_sync"


class DiscoveryMode(str, Enum):
    SAFE = "safe"
    BALANCED = "balanced"
    ADVENTUROUS = "adventurous"


# §5.6 provider modes the UI toggle can select. Kept as a tuple rather than an
# Enum to match `provider` fields already typed as plain strings across the
# services and the n8n workflows.
SUPPORTED_PROVIDERS = ("youtube", "spotify")
DEFAULT_PROVIDER = "youtube"


@dataclass
class Identity:
    """Resolved or provisional identity carried on every request."""

    user_id: Optional[str] = None
    guest_id: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "guest_id": self.guest_id,
            "session_id": self.session_id,
        }


@dataclass
class MusicConstraints:
    """Structured music constraints extracted or supplied by the client."""

    mood: Optional[str] = None
    genre: Optional[str] = None
    era: Optional[str] = None
    instrumentation: Optional[str] = None
    energy: Optional[float] = None
    novelty: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecommendationContext:
    """Stable context object assembled before the recommendation engine runs.

    Text and audio paths share this schema after context assembly (Section 3.2).
    Empty containers are intentional — keys must always be present.
    """

    request_id: str
    user_text: str = ""
    audio_job_id: Optional[str] = None
    discovery_mode: DiscoveryMode = DiscoveryMode.BALANCED
    locale: str = "en"
    taste_profile: dict[str, Any] = field(default_factory=dict)
    provider_taste_signals: dict[str, Any] = field(default_factory=dict)
    audio_features: dict[str, Any] = field(default_factory=dict)
    exclusions: list[str] = field(default_factory=list)
    constraints: MusicConstraints = field(default_factory=MusicConstraints)
    connected_providers: list[str] = field(default_factory=list)
    # §5.6: which provider should answer this request ("youtube" | "spotify").
    # The UI's mode toggle sets it; naming a provider in `user_text` overrides
    # it downstream. Distinct from `connected_providers`, which says what the
    # user has *authorized*, not what they asked for.
    provider: str = "youtube"

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_text": self.user_text,
            "audio_job_id": self.audio_job_id,
            "discovery_mode": self.discovery_mode.value,
            "locale": self.locale,
            "taste_profile": self.taste_profile,
            "provider_taste_signals": self.provider_taste_signals,
            "audio_features": self.audio_features,
            "exclusions": list(self.exclusions),
            "constraints": self.constraints.to_dict(),
            "connected_providers": list(self.connected_providers),
            "provider": self.provider,
        }


@dataclass
class RequestBody:
    """Intent-specific payload nested inside the request envelope."""

    prompt: str = ""
    recommendation_context: Optional[RecommendationContext] = None
    audio_job_id: Optional[str] = None
    feedback: Optional[dict[str, Any]] = None
    playlist: Optional[dict[str, Any]] = None
    provider: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "recommendation_context": (
                self.recommendation_context.to_dict()
                if self.recommendation_context is not None
                else None
            ),
            "audio_job_id": self.audio_job_id,
            "feedback": self.feedback,
            "playlist": self.playlist,
            "provider": self.provider,
        }


@dataclass
class RequestEnvelope:
    """Canonical envelope sent from Flask to WF-001 (Section 3.1)."""

    request_id: str
    intent: Intent
    identity: Identity
    body: RequestBody
    api_version: str = "v1"
    locale: str = "en"
    idempotency_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_version": self.api_version,
            "request_id": self.request_id,
            "intent": self.intent.value,
            "identity": self.identity.to_dict(),
            "locale": self.locale,
            "body": self.body.to_dict(),
            "idempotency_key": self.idempotency_key,
        }


@dataclass
class ClientRequestPayload:
    """Minimal inbound body accepted by POST /api/v1/requests in this step."""

    prompt: Optional[str] = None
    user_query: Optional[str] = None
    question: Optional[str] = None
    message: Optional[str] = None
    locale: Optional[str] = None
    discovery_mode: Optional[DiscoveryMode] = None
    provider: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClientRequestPayload":
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")

        mode_raw = data.get("discovery_mode")
        discovery_mode: Optional[DiscoveryMode] = None
        if mode_raw is not None and mode_raw != "":
            try:
                discovery_mode = DiscoveryMode(str(mode_raw).lower())
            except ValueError as error:
                raise ValueError(
                    "discovery_mode must be one of: safe, balanced, adventurous."
                ) from error

        provider_raw = data.get("provider")
        provider: Optional[str] = None
        if provider_raw is not None and provider_raw != "":
            provider = str(provider_raw).strip().lower()
            if provider not in SUPPORTED_PROVIDERS:
                raise ValueError(
                    f"provider must be one of: {', '.join(SUPPORTED_PROVIDERS)}."
                )

        return cls(
            prompt=_optional_str(data.get("prompt")),
            user_query=_optional_str(data.get("user_query")),
            question=_optional_str(data.get("question")),
            message=_optional_str(data.get("message")),
            locale=_optional_str(data.get("locale")),
            discovery_mode=discovery_mode,
            provider=provider,
        )

    def resolved_prompt(self) -> str:
        for value in (self.prompt, self.user_query, self.question, self.message):
            if value and value.strip():
                return value.strip()
        return ""


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)
