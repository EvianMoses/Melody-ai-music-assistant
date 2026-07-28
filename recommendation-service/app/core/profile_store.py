"""Persistence for Preference Profile v1 (§7.2, PERS-005).

Kept apart from `profile.py` on purpose: the update *rules* are pure functions
over dicts and are tested without a database, while everything that knows about
rows lives here. That split is what lets `PERS-006`'s like/dislike/decay/
conflict/migration tests run offline like every other service's.

**Append-only.** Each update writes a new row rather than mutating one, so a
profile's history is inspectable — "why did this recommendation change?" is
answerable by diffing two versions. Reading means taking the highest version for
an owner.

**Absence is not failure.** If the database is unreachable the caller still gets
a usable profile: feedback is a secondary concern to answering the request in
front of the user, and a recommendation that works without personalization is
far better than an error. Failures are logged and surfaced as `persisted:
false`, never swallowed silently.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from typing import Any, Optional

from .profile import Profile

logger = logging.getLogger("melody.recommendation.profile_store")

_engine = None
_session_factory = None


def _database_url() -> str:
    """Build the connection URL, preferring the per-part variables.

    `POSTGRES_*` comes first and `DATABASE_URL` is only the fallback, which is
    the opposite of the obvious ordering and is deliberate: `.env` carries a
    `DATABASE_URL` pointing at **localhost** for host-side tools like Alembic,
    and inside the compose network localhost is the container itself. Preferring
    it made every profile write fail with "connection refused" while the
    database was healthy two containers away. Compose sets `POSTGRES_HOST:
    postgres` for exactly this reason, and the ingestion scripts already build
    their URL the same way.
    """
    user = os.getenv("POSTGRES_USER", "")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST", "")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "")
    if user and database and host:
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"

    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return ""


def _factory():
    """Build the session factory once, lazily.

    Lazy because the service must start and serve `/recommendations/run` even
    when the database is down -- the graph does not need it, and refusing to
    boot would take the whole recommendation path with it.
    """
    global _engine, _session_factory
    if _session_factory is not None:
        return _session_factory
    url = _database_url()
    if not url:
        return None
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        _engine = create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    except Exception:
        logger.warning("profile_store_unavailable", exc_info=True)
        return None
    return _session_factory


@contextmanager
def _session():
    factory = _factory()
    if factory is None:
        yield None
        return
    session = factory()
    try:
        yield session
    finally:
        session.close()


def available() -> bool:
    return _factory() is not None


def _as_uuid(value: Any) -> Optional[uuid.UUID]:
    """Accept a UUID, a UUID string, or anything else and return None.

    Guest ids in this system are not always UUIDs -- Flask falls back to a
    session id -- so a non-UUID is an ordinary case, not an error.
    """
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def load(*, user_id: Any = None, guest_id: Any = None) -> Profile:
    """Latest profile for an owner, or an empty one. Never raises."""
    owner_user, owner_guest = _as_uuid(user_id), _as_uuid(guest_id)
    if owner_user is None and owner_guest is None:
        return Profile()

    try:
        from contracts.db_models import UserPreference
        from sqlalchemy import select

        with _session() as session:
            if session is None:
                return Profile()
            stmt = select(UserPreference)
            stmt = (
                stmt.where(UserPreference.user_id == owner_user)
                if owner_user
                else stmt.where(UserPreference.guest_session_id == owner_guest)
            )
            row = session.execute(
                stmt.order_by(UserPreference.version.desc()).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return Profile()
            loaded = Profile.from_dict(row.profile)
            # The column is authoritative for the version -- the JSON copy is a
            # convenience, and if the two ever disagree the row wins.
            loaded.version = row.version
            loaded.discovery_mode = row.discovery_mode or loaded.discovery_mode
            return loaded
    except Exception:
        logger.warning("profile_load_failed", exc_info=True)
        return Profile()


GUEST_SESSION_TTL_DAYS = 30


def _ensure_guest_session(session, guest_uuid: uuid.UUID) -> bool:
    """Make sure a `guest_sessions` row exists for this id.

    The profile row carries a foreign key to `guest_sessions`, and a guest who
    has only ever given feedback has no reason to have one yet -- WF-001 upserts
    it on the *recommendation* path, not the feedback path. Without this, the
    first Like from a guest fails its foreign key and the profile silently never
    persists, which is exactly what the first live test of this endpoint showed.

    `ON CONFLICT DO NOTHING` so two concurrent first-likes cannot race.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text

    session.execute(
        text(
            "INSERT INTO guest_sessions (id, expires_at) VALUES (:id, :expires) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": str(guest_uuid),
            "expires": datetime.now(timezone.utc) + timedelta(days=GUEST_SESSION_TTL_DAYS),
        },
    )
    return True


def save(profile: Profile, *, user_id: Any = None, guest_id: Any = None) -> bool:
    """Append a new version. Returns whether it was persisted.

    A guest whose id is not a UUID cannot be stored -- there is nothing to hang
    a foreign key on -- and that is reported honestly rather than being made to
    look like a successful write.
    """
    owner_user, owner_guest = _as_uuid(user_id), _as_uuid(guest_id)
    if owner_user is None and owner_guest is None:
        return False

    try:
        from contracts.db_models import UserPreference

        with _session() as session:
            if session is None:
                return False
            if owner_user is None:
                _ensure_guest_session(session, owner_guest)
            session.add(
                UserPreference(
                    user_id=owner_user,
                    guest_session_id=None if owner_user else owner_guest,
                    version=profile.version,
                    discovery_mode=profile.discovery_mode,
                    profile=profile.to_dict(),
                )
            )
            session.commit()
            return True
    except Exception:
        # Includes the unique-constraint case: two concurrent updates racing on
        # the same version. Losing one feedback event is acceptable; failing the
        # user's request over it is not.
        logger.warning("profile_save_failed", exc_info=True)
        return False
