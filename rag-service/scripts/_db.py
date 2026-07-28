"""Shared database-URL resolution for rag-service maintenance scripts.

Why this exists: building ``DATABASE_URL`` by interpolating ``${POSTGRES_PASSWORD}``
in docker-compose is fragile — Docker Compose lets host shell environment
variables override ``.env`` during interpolation, which silently injected a wrong
password into one-off ``docker compose run`` containers.

This resolver is deterministic. Precedence:
1. An explicit ``override`` argument.
2. Discrete ``POSTGRES_*`` components (the source of truth). ``POSTGRES_HOST`` is
   ``postgres`` inside the compose network and defaults to ``localhost`` for
   host-run scripts. The password is URL-encoded, so special characters are safe.
3. A pre-set ``DATABASE_URL`` (normalized to the psycopg v3 dialect).

``.env`` is loaded with python-dotenv when available (host runs); inside the
containers the values arrive via compose ``env_file``, so no file is needed there.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in (REPO_ROOT / ".env", Path("/app/.env"), Path.cwd() / ".env"):
        if candidate.is_file():
            load_dotenv(dotenv_path=candidate, override=False)


def _normalize(url: str) -> str:
    """Force the psycopg (v3) dialect so scripts and Alembic agree."""
    for prefix, repl in (
        ("postgresql+psycopg2://", "postgresql+psycopg://"),
        ("postgresql://", "postgresql+psycopg://"),
        ("postgres://", "postgresql+psycopg://"),
    ):
        if url.startswith(prefix):
            return repl + url[len(prefix):]
    return url


def resolve_database_url(override: Optional[str] = None) -> str:
    if override:
        return _normalize(override)

    _load_dotenv()

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    if user and password:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", user)
        return (
            f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{database}"
        )

    url = os.getenv("DATABASE_URL")
    if url:
        return _normalize(url)

    raise RuntimeError(
        "No database configuration found. Set POSTGRES_USER/POSTGRES_PASSWORD "
        "(and POSTGRES_HOST for the compose network) or DATABASE_URL, e.g. "
        "postgresql+psycopg://user:pass@localhost:5432/melody."
    )
