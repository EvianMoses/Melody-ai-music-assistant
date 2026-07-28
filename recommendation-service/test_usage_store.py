"""Offline tests for §4.9 model-usage persistence (N8N-REAL-004).

SQLite in memory, no docker and no network -- same rule as every other service's
suite. What is asserted is the behaviour that matters for WF-008: only real model
calls become rows, the numbers survive the round trip intact, and a broken
database costs a row rather than a request.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import usage_store
from contracts.db_models import Base, ModelUsage


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine, tables=[ModelUsage.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    usage_store.reset_for_tests(factory)
    yield factory
    usage_store.reset_for_tests(None)


def _rows(factory):
    with factory() as session:
        return session.execute(
            text(
                "SELECT request_id, provider, model, prompt_tokens, "
                "completion_tokens, total_tokens, latency_ms, estimated_cost "
                "FROM model_usage ORDER BY model"
            )
        ).all()


def test_records_a_real_model_call(session_factory):
    written = usage_store.record_node_metrics(
        {
            "generate_grounded_explanation": {
                "latency_ms": 2410.5,
                "model": "claude-haiku-4-5",
                "status": "ok",
                "input_tokens": 1289,
                "output_tokens": 161,
                "estimated_cost_usd": 0.002094,
            }
        },
        request_id="req-1",
    )

    assert written == 1
    row = _rows(session_factory)[0]
    assert row.request_id == "req-1"
    assert row.provider == "anthropic"
    assert row.model == "claude-haiku-4-5"
    assert row.prompt_tokens == 1289
    assert row.completion_tokens == 161
    # Derived, not supplied by the node -- the sum must be right or the cost
    # report double-counts.
    assert row.total_tokens == 1450
    assert row.latency_ms == 2410
    assert float(row.estimated_cost) == pytest.approx(0.002094)


def test_nodes_that_called_no_model_are_not_recorded(session_factory):
    """The load-bearing case.

    Every node emits a metric entry, and most of them never touch a model. If
    those became rows, "how many model calls did this request make?" -- the
    question WF-008 exists to answer -- would be unanswerable from the table.
    """
    written = usage_store.record_node_metrics(
        {
            "validate_context": {"latency_ms": 0.4, "status": "ok"},
            "retrieve_genres": {"latency_ms": 812.0, "status": "ok", "detail": "5 chunks"},
            "rank_tracks": {"latency_ms": 3.1, "status": "ok"},
        },
        request_id="req-2",
    )

    assert written == 0
    assert _rows(session_factory) == []


def test_a_named_model_without_tokens_is_not_a_call(session_factory):
    """A node that failed before reaching the API names its model but spent
    nothing. Recording it would invent a call that never happened."""
    written = usage_store.record_node_metrics(
        {
            "generate_grounded_explanation": {
                "latency_ms": 120.0,
                "model": "claude-haiku-4-5",
                "status": "error",
                "detail": "credit balance too low",
            }
        },
        request_id="req-3",
    )

    assert written == 0
    assert _rows(session_factory) == []


def test_multiple_model_calls_in_one_request_are_all_recorded(session_factory):
    written = usage_store.record_node_metrics(
        {
            "rewrite_query": {
                "latency_ms": 900.0,
                "model": "llama3.1",
                "status": "ok",
                "input_tokens": 40,
                "output_tokens": 20,
                "estimated_cost_usd": 0.0,
            },
            "generate_grounded_explanation": {
                "latency_ms": 2000.0,
                "model": "claude-haiku-4-5",
                "status": "ok",
                "input_tokens": 1000,
                "output_tokens": 100,
                "estimated_cost_usd": 0.0018,
            },
            "rank_tracks": {"latency_ms": 2.0, "status": "ok"},
        },
        request_id="req-4",
    )

    assert written == 2
    assert [r.model for r in _rows(session_factory)] == [
        "claude-haiku-4-5",
        "llama3.1",
    ]


def test_empty_metrics_is_a_no_op(session_factory):
    assert usage_store.record_node_metrics({}, request_id="req-5") == 0
    assert usage_store.record_node_metrics(None, request_id="req-5") == 0


def test_unavailable_database_costs_a_row_not_a_request(monkeypatch):
    """The failure policy, asserted rather than assumed: with no database
    configured the call returns 0 and does not raise, so /recommendations/run
    still answers.

    `_database_url` is monkeypatched rather than just clearing the factory. The
    first version of this test cleared the factory and asserted 0 -- and passed
    on a laptop while **failing inside the container**, where POSTGRES_* really
    is configured, so clearing the factory just made the next call build a live
    connection and write a real row into the development database. Patching the
    URL is what actually reproduces "no database", in any environment.
    """
    monkeypatch.setattr(usage_store, "_database_url", lambda: "")
    usage_store.reset_for_tests(None)
    assert (
        usage_store.record_node_metrics(
            {
                "generate_grounded_explanation": {
                    "model": "claude-haiku-4-5",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "estimated_cost_usd": 0.0001,
                    "latency_ms": 5.0,
                }
            },
            request_id="req-6",
        )
        == 0
    )


def test_a_failing_session_does_not_raise(monkeypatch):
    """A database that accepts a connection and then rejects the write is the
    realistic outage, and it must be as harmless as no database at all."""

    class _Boom:
        def __call__(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, *a, **kw):
            raise RuntimeError("connection reset")

        def close(self):
            pass

    usage_store.reset_for_tests(_Boom())
    try:
        assert (
            usage_store.record_node_metrics(
                {
                    "generate_grounded_explanation": {
                        "model": "claude-haiku-4-5",
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "estimated_cost_usd": 0.0001,
                        "latency_ms": 5.0,
                    }
                },
                request_id="req-7",
            )
            == 0
        )
    finally:
        usage_store.reset_for_tests(None)
