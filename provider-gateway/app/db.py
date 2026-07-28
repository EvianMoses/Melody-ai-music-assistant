"""Database access for provider-gateway (Phase 5 §5.5).

This service had no database dependency until playlist export: it now reads the
user's encrypted grant from ``oauth_accounts`` and owns the idempotent write to
``playlist_exports``.

The engine is created lazily so the service still starts -- and `/providers/search`
still works -- when the database is unreachable. Search needs only an API key,
so a database outage must not take the whole gateway down with it.
"""

from __future__ import annotations

import os
from typing import Optional

_engine = None
_session_factory = None


def normalize_database_url(url: str) -> str:
    """Force the psycopg (v3) dialect, matching migrations/env.py and app.py."""
    for prefix, repl in (
        ("postgresql+psycopg2://", "postgresql+psycopg://"),
        ("postgresql://", "postgresql+psycopg://"),
        ("postgres://", "postgresql+psycopg://"),
    ):
        if url.startswith(prefix):
            return repl + url[len(prefix):]
    return url


def _from_postgres_vars() -> Optional[str]:
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    if not (user and password):
        return None

    from urllib.parse import quote_plus

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", user)
    return (
        f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )


def _resolve_database_url() -> str:
    """POSTGRES_* when compose sets POSTGRES_HOST, else DATABASE_URL.

    The ordering is deliberate and not the obvious one. docker-compose.yml loads
    the whole ``.env`` into the container -- including a ``DATABASE_URL`` whose
    host is ``localhost``, correct for a host-run process and useless inside the
    network -- and then sets ``POSTGRES_HOST: postgres`` on top. So an explicitly
    set POSTGRES_HOST is the signal that we are in the compose network and must
    assemble the URL from the parts, exactly as the comment in docker-compose.yml
    describes ("Scripts build DATABASE_URL from POSTGRES_* + this host").
    """
    if os.getenv("POSTGRES_HOST"):
        assembled = _from_postgres_vars()
        if assembled:
            return assembled

    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return normalize_database_url(explicit)

    assembled = _from_postgres_vars()
    if assembled:
        return assembled

    raise RuntimeError(
        "No database configuration found. Set DATABASE_URL, or POSTGRES_USER/"
        "POSTGRES_PASSWORD (plus POSTGRES_HOST inside the compose network)."
    )


def get_session_factory():
    global _engine, _session_factory
    if _session_factory is None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        _engine = create_engine(_resolve_database_url(), future=True, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=_engine, future=True)
    return _session_factory


def session():
    """A new ORM session. Callers use it as a context manager."""
    return get_session_factory()()


def reset_for_tests(factory: Optional[object] = None) -> None:
    """Swap the factory (tests inject an in-memory SQLite one)."""
    global _session_factory, _engine
    _session_factory = factory
    if factory is None:
        _engine = None
