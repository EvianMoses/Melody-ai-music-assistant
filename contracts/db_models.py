"""SQLAlchemy 2.0 ORM models for the Melody core schema (Section 2.3).

Scope for this step (DB-002..DB-005): the core identity, preference,
track, and recommendation tables. Remaining tables from the plan
(feedback_events, recommendation_candidates, knowledge_*, audio_jobs,
playlist_exports, model_usage, jobs, audit_events, genre_*) are added later.

Conventions:
- UUID primary keys (DB-003), generated application-side (`uuid4`).
- Timezone-aware UTC timestamps (DB-003) via `TIMESTAMP(timezone=True)`.
- Provider IDs are never internal primary keys (Section 2.3 rules).
- pgvector `Vector` is imported and ready for `knowledge_chunks` (DB-002).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.types import DateTime, Uuid

# Embedding dimensionality for knowledge_chunks.
# Set to 384 for the selected retrieval model intfloat/multilingual-e5-small
# (see docs/adr/ADR-003-embedding-model.md). Was 768 for Gemini-style models.
EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    """Declarative base carrying the shared MetaData used by Alembic."""


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class CreatedAtMixin:
    """UTC created timestamp for append-only / immutable tables (DB-003)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TimestampMixin(CreatedAtMixin):
    """UTC created/updated columns shared across mutable tables (DB-003)."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(Base, TimestampMixin):
    """Identity, locale, account state, created/deleted timestamps."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[Optional[str]] = mapped_column(String(320), unique=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    account_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    preferences: Mapped[list["UserPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    guest_sessions: Mapped[list["GuestSession"]] = relationship(
        back_populates="migrated_user"
    )


class GuestSession(Base, TimestampMixin):
    """Expiring guest identity and migration-to-user reference."""

    __tablename__ = "guest_sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    migrated_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    migrated_user: Mapped[Optional["User"]] = relationship(
        back_populates="guest_sessions"
    )

    __table_args__ = (Index("ix_guest_sessions_expires_at", "expires_at"),)


class UserPreference(Base, TimestampMixin):
    """Materialized versioned preference profile (§7.2).

    One row per *version*, never an update in place. That makes the history of a
    profile inspectable — "why did this recommendation change?" is answerable by
    diffing two rows — and it is what `PERS-005`'s "version every profile
    update" means in storage terms.

    `user_id` is nullable so a **guest** can have a profile too (`PERS-003`).
    Feedback from someone who has not signed in is still feedback, and requiring
    an account before the app learns anything would make the first session
    permanently unpersonalized. On sign-in the guest profile is merged into the
    user's rather than discarded (`profile.merge_guest_into_user`).
    """

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    guest_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    discovery_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="balanced"
    )
    profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="preferences")

    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_user_preferences_user_version"),
        UniqueConstraint(
            "guest_session_id", "version", name="uq_user_preferences_guest_version"
        ),
        Index("ix_user_preferences_user_id", "user_id"),
        Index("ix_user_preferences_guest_session_id", "guest_session_id"),
        # A profile belongs to exactly one owner. Without this a row with both
        # ids set, or neither, is storable — and "whose profile is this?" stops
        # having an answer.
        CheckConstraint(
            "(user_id IS NOT NULL) <> (guest_session_id IS NOT NULL)",
            name="ck_user_preferences_single_owner",
        ),
    )


class OAuthAccount(Base, TimestampMixin):
    """Provider, encrypted token material/reference, scopes, expiry, revocation state.

    The 19th and last table of the Section 2.3 data model, deferred to Phase 5
    because that is where the encrypted-token-storage decision is made
    (ADR-007). Section 2.3's rule is absolute: *"OAuth token values are
    encrypted or stored in an approved secret store; never plaintext columns."*
    Both token columns therefore hold Fernet ciphertext produced by
    ``shared_lib.token_crypto`` -- never a raw token.
    """

    __tablename__ = "oauth_accounts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # The provider's stable subject id (Google's OIDC `sub`). Deliberately not
    # the email address, which a user can change.
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)

    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(Text)
    # Which encryption key sealed this row, so keys can be rotated without a
    # rewrite (see shared_lib/token_crypto.py and ADR-007).
    encryption_key_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Granted scopes, which drive the AUTH-005 incremental-upgrade decision.
    # The SQLite variant exists purely so the OAuth flow can be unit-tested
    # against an in-memory database; PostgreSQL still gets a real JSONB column.
    scopes: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_accounts_provider_identity"
        ),
        Index("ix_oauth_accounts_user_id", "user_id"),
        Index("ix_oauth_accounts_provider", "provider"),
    )


class Track(Base, TimestampMixin):
    """Canonical track identity with normalized metadata."""

    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    artist: Mapped[str] = mapped_column(String(512), nullable=False)
    album: Mapped[Optional[str]] = mapped_column(String(512))
    isrc: Mapped[Optional[str]] = mapped_column(String(32), unique=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    track_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    provider_ids: Mapped[list["TrackProviderId"]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_tracks_artist_title", "artist", "title"),)


class TrackProviderId(Base, TimestampMixin):
    """Provider-specific IDs, links, and confidence.

    Provider IDs are not internal primary keys (Section 2.3 rules): the PK is a
    surrogate UUID, while the provider identity is a unique constraint.
    """

    __tablename__ = "track_provider_ids"

    id: Mapped[uuid.UUID] = _uuid_pk()
    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_track_id: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    confidence: Mapped[Optional[float]] = mapped_column(Float)

    track: Mapped["Track"] = relationship(back_populates="provider_ids")

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_track_id", name="uq_track_provider_identity"
        ),
        Index("ix_track_provider_ids_track_id", "track_id"),
        Index("ix_track_provider_ids_provider", "provider"),
    )


class RecommendationSession(Base, TimestampMixin):
    """Request context, engine, result, fallback, latency, status."""

    __tablename__ = "recommendation_sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    guest_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="SET NULL")
    )
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    request_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    engine_used: Mapped[Optional[str]] = mapped_column(String(64))
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    fallback_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    __table_args__ = (
        Index("ix_recommendation_sessions_request_id", "request_id"),
        Index("ix_recommendation_sessions_user_id", "user_id"),
        Index("ix_recommendation_sessions_status", "status"),
    )


class RecommendationCandidate(Base, CreatedAtMixin):
    """Candidate identity, feature values, component scores, final rank."""

    __tablename__ = "recommendation_candidates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recommendation_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    track_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL")
    )
    feature_values: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    component_scores: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    final_rank: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (
        Index(
            "ix_recommendation_candidates_session_id", "recommendation_session_id"
        ),
        Index(
            "ix_recommendation_candidates_session_rank",
            "recommendation_session_id",
            "final_rank",
        ),
        Index("ix_recommendation_candidates_track_id", "track_id"),
    )


class FeedbackEvent(Base, CreatedAtMixin):
    """Immutable interaction events with session and candidate context."""

    __tablename__ = "feedback_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recommendation_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("recommendation_sessions.id", ondelete="SET NULL")
    )
    candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("recommendation_candidates.id", ondelete="SET NULL")
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    guest_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="SET NULL")
    )
    track_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    __table_args__ = (
        Index("ix_feedback_events_session_id", "recommendation_session_id"),
        Index("ix_feedback_events_candidate_id", "candidate_id"),
        Index("ix_feedback_events_user_id", "user_id"),
        Index("ix_feedback_events_event_type", "event_type"),
    )


class TrackAudioFeature(Base, TimestampMixin):
    """BPM, key, Camelot, energy, source, confidence, model version."""

    __tablename__ = "track_audio_features"

    id: Mapped[uuid.UUID] = _uuid_pk()
    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    bpm: Mapped[Optional[float]] = mapped_column(Float)
    musical_key: Mapped[Optional[str]] = mapped_column(String(16))
    camelot: Mapped[Optional[str]] = mapped_column(String(8))
    energy: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    __table_args__ = (
        UniqueConstraint(
            "track_id",
            "source",
            "model_version",
            name="uq_track_audio_features_version",
        ),
        Index("ix_track_audio_features_track_id", "track_id"),
    )


class GenreNode(Base, TimestampMixin):
    """Parent genres and subgenres."""

    __tablename__ = "genre_nodes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("genre_nodes.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="genre")
    description: Mapped[Optional[str]] = mapped_column(Text)
    node_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    __table_args__ = (
        Index("ix_genre_nodes_parent_id", "parent_id"),
        Index("ix_genre_nodes_name", "name"),
    )


class GenreEdge(Base, CreatedAtMixin):
    """Parent, related, influence, and similarity relations."""

    __tablename__ = "genre_edges"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("genre_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("genre_nodes.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint(
            "source_id", "target_id", "relation", name="uq_genre_edge_identity"
        ),
        Index("ix_genre_edges_source_id", "source_id"),
        Index("ix_genre_edges_target_id", "target_id"),
        Index("ix_genre_edges_relation", "relation"),
    )


class KnowledgeDocument(Base, TimestampMixin):
    """Source document and version metadata."""

    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(1024))
    uri: Mapped[Optional[str]] = mapped_column(String(2048))
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="1")
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_knowledge_documents_source", "source"),
        UniqueConstraint("source", "uri", "version", name="uq_knowledge_document_version"),
    )


class KnowledgeChunk(Base, CreatedAtMixin):
    """Chunk text, full-text data, metadata, embedding, ingestion version.

    - `embedding` uses the pgvector `Vector` type (DB-002) for ANN search.
    - `content_tsv` is a generated TSVECTOR for full-text search (DB-004).
    """

    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_tsv: Mapped[Optional[str]] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', chunk_text)", persisted=True),
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(EMBEDDING_DIM))
    ingestion_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="1"
    )
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_knowledge_chunks_document_id", "document_id"),
        # Full-text search (GIN over the generated tsvector).
        Index("ix_knowledge_chunks_content_tsv", "content_tsv", postgresql_using="gin"),
        # Vector ANN search (HNSW with cosine distance for text embeddings).
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class PlaylistExport(Base, TimestampMixin):
    """Provider, playlist ID, URL, idempotency key, partial-failure state."""

    __tablename__ = "playlist_exports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_playlist_id: Mapped[Optional[str]] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(2048))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # Same SQLite variant as OAuthAccount.scopes: provider-gateway's export
    # tests build these tables in an in-memory database, and JSONB cannot
    # render there. PostgreSQL still gets a real JSONB column.
    partial_failure: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite")
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_playlist_exports_idempotency_key"),
        Index("ix_playlist_exports_user_id", "user_id"),
        Index("ix_playlist_exports_provider", "provider"),
    )


class AudioJob(Base, TimestampMixin):
    """Temporary object reference, derived features, state, cleanup timestamp."""

    __tablename__ = "audio_jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    guest_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="SET NULL")
    )
    object_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    derived_features: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    cleanup_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_audio_jobs_state", "state"),
        Index("ix_audio_jobs_cleanup_at", "cleanup_at"),
        Index("ix_audio_jobs_user_id", "user_id"),
    )


class ModelUsage(Base, CreatedAtMixin):
    """Provider/model, tokens, latency, estimated cost, cache hit."""

    __tablename__ = "model_usage"

    id: Mapped[uuid.UUID] = _uuid_pk()
    request_id: Mapped[Optional[str]] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_model_usage_request_id", "request_id"),
        Index("ix_model_usage_provider_model", "provider", "model"),
    )


class Job(Base, TimestampMixin):
    """Asynchronous job state and safe error code."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    __table_args__ = (
        Index("ix_jobs_state", "state"),
        Index("ix_jobs_job_type", "job_type"),
    )


class AuditEvent(Base, CreatedAtMixin):
    """Security-sensitive actions without credential values."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(String(255))
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    __table_args__ = (
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_created_at", "created_at"),
    )


# ---------------------------------------------------------------------------
# Operations tables (N8N-REAL-004, WF-008 Monitoring and Budget).
#
# Section 2.3 froze nineteen tables and `oauth_accounts` was called the last of
# them. These two are additive, and the reason they exist is specific: WF-008 is
# required to read *real* usage and health, and two of the four things it must
# read had nowhere to be read from. `model_usage` already existed but nothing
# wrote to it; provider quota and the daily summary had no table at all, so the
# workflow would have had to invent its numbers -- which is the failure the
# whole placeholder policy exists to prevent.
# ---------------------------------------------------------------------------


class ProviderQuotaUsage(Base, CreatedAtMixin):
    """One row per quota-consuming provider call (N8N-REAL-004).

    YouTube's daily budget is the hard operational constraint in this system --
    10,000 units/day, with `search.list` at 100 and a playlist export at 50 per
    track. That was tracked only by a log line, so the number could be read by a
    human tailing `docker logs` and by nothing else. WF-008 needs it as data.

    Append-only, and deliberately not aggregated on write: a daily total that is
    incremented in place cannot answer "which method spent the budget", which is
    the question that actually changes a decision.
    """

    __tablename__ = "provider_quota_usage"

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # e.g. "search.list", "videos.list", "playlists.insert".
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    # Optional: recognition and export calls carry one; cached reads do not.
    request_id: Mapped[Optional[str]] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_provider_quota_usage_created_at", "created_at"),
        Index("ix_provider_quota_usage_provider_method", "provider", "method"),
    )


class OpsDailySummary(Base, TimestampMixin):
    """WF-008's `Store Daily Summary` output -- one row per UTC day.

    `summary_date` is unique so a re-run of the daily schedule updates the day
    rather than appending a second, contradictory version of it. That matters
    because the workflow is retryable: an alert that fired at 09:00 and a re-run
    at 09:05 must not leave two rows disagreeing about whether the budget
    threshold was crossed.
    """

    __tablename__ = "ops_daily_summary"

    id: Mapped[uuid.UUID] = _uuid_pk()
    summary_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Model cost, provider quota, error rate, latency, storage -- the whole
    # measured picture, kept as one document rather than a column per metric so
    # a new metric does not require a migration.
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    budget_percent: Mapped[Optional[float]] = mapped_column(Float)
    # "ok" | "notice" | "warning" | "critical" | "emergency" -- the 50/75/90/95
    # rules of §1.11.
    alert_level: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    alert_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("summary_date", name="uq_ops_daily_summary_date"),
        Index("ix_ops_daily_summary_date", "summary_date"),
    )
