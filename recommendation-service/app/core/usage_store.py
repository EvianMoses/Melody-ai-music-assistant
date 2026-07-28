"""Persistence for §4.9 model-usage records (N8N-REAL-004).

`model_usage` has existed since the Phase 2 schema and **nothing ever wrote to
it**. Per-call provider/model/token/cost data lived only in a `logger.info` line,
which made it recoverable by scraping `docker logs` (which is exactly what
`eval/rec_leg_comparison.py` does) and unavailable to anything else -- including
WF-008, whose whole job is to read real usage and budget.

This module closes that gap. It is deliberately separate from `graph_nodes.py`:
nodes produce metrics as part of their state update and stay testable without a
database, and the single place that knows about rows is here.

**Failure policy: best effort, and loudly logged.** A monitoring write must never
fail a recommendation the user is waiting on -- the cost of a lost row is an
incomplete report, and the cost of the alternative is a broken answer. Failures
are logged with a stack trace, never swallowed silently.

Only nodes that actually called a paid model are recorded. A node that ran no
model has nothing to say about cost, and inserting a zero-token row for it would
make "how many model calls did this request make?" unanswerable from the table.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger("melody.recommendation.usage_store")

_engine = None
_session_factory = None


def _database_url() -> str:
    """Same resolution order as `profile_store._database_url`.

    `POSTGRES_*` first, `DATABASE_URL` only as a fallback: `.env` carries a
    `DATABASE_URL` pointing at localhost for host-side tools, and inside the
    compose network localhost is this container.
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
    global _engine, _session_factory
    if _session_factory is not None:
        return _session_factory
    url = _database_url()
    if not url:
        return None
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        _engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    except Exception:
        logger.warning("usage_store_unavailable", exc_info=True)
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


def reset_for_tests(factory: Optional[Any] = None) -> None:
    """Swap the factory (tests inject their own, or None to disable)."""
    global _session_factory, _engine
    _session_factory = factory
    if factory is None:
        _engine = None


def _is_model_call(entry: dict[str, Any]) -> bool:
    """Whether this node metric describes a real model call.

    A model name alone is not enough: nodes record the model they *would* use
    even when they skipped or failed before calling it. Token counts are the
    evidence that a call actually happened and money was actually spent.
    """
    if not entry.get("model"):
        return False
    return any(
        entry.get(field) is not None
        for field in ("input_tokens", "output_tokens", "estimated_cost_usd")
    )


def record_node_metrics(
    node_metrics: dict[str, Any],
    *,
    request_id: str = "",
    provider: str = "anthropic",
) -> int:
    """Persist every metric entry that represents a paid model call.

    Returns the number of rows written -- 0 when the database is unavailable,
    when nothing in this request called a model, or on failure. Never raises.
    """
    if not node_metrics:
        return 0

    rows = [
        {
            # Generated here rather than left to the column default. The
            # PostgreSQL table has `gen_random_uuid()`, but a raw INSERT gets no
            # help from the ORM's Python-side default, so any dialect without
            # that server default -- SQLite, which the offline tests use --
            # fails on a NOT NULL id. Supplying it makes the statement portable
            # instead of silently PostgreSQL-only.
            "id": str(uuid.uuid4()),
            "request_id": (request_id or None),
            "provider": provider,
            "model": entry.get("model") or "unknown",
            "prompt_tokens": entry.get("input_tokens"),
            "completion_tokens": entry.get("output_tokens"),
            "total_tokens": (
                (entry.get("input_tokens") or 0) + (entry.get("output_tokens") or 0)
                if entry.get("input_tokens") is not None
                or entry.get("output_tokens") is not None
                else None
            ),
            "latency_ms": (
                int(entry["latency_ms"]) if entry.get("latency_ms") is not None else None
            ),
            "estimated_cost": entry.get("estimated_cost_usd"),
            "cache_hit": bool(entry.get("cache_hit", False)),
        }
        for entry in node_metrics.values()
        if isinstance(entry, dict) and _is_model_call(entry)
    ]
    if not rows:
        return 0

    try:
        from sqlalchemy import text as sql_text

        with _session() as session:
            if session is None:
                return 0
            session.execute(
                sql_text(
                    "INSERT INTO model_usage (id, request_id, provider, model, "
                    "prompt_tokens, completion_tokens, total_tokens, latency_ms, "
                    "estimated_cost, cache_hit) VALUES (:id, :request_id, "
                    ":provider, :model, :prompt_tokens, :completion_tokens, "
                    ":total_tokens, :latency_ms, :estimated_cost, :cache_hit)"
                ),
                rows,
            )
            session.commit()
            return len(rows)
    except Exception:  # noqa: BLE001 - deliberate: see module docstring
        logger.warning("model_usage_persist_failed", exc_info=True)
        return 0
