from fastapi.testclient import TestClient

from app.core import llm_adapter, provider_client, rag_client
from main import app
from test_graph_nodes import (
    _fake_llm_success,
    _fake_provider_search_ok,
    _fake_rag_retrieve_ok,
)

client = TestClient(app)


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_recommendations_run_real_graph(monkeypatch):
    # engine="graph" now runs the real §4.2 pipeline; external seams
    # (rag-service, provider-gateway, Anthropic) are monkeypatched so the
    # endpoint test stays fast/offline (see test_graph_nodes.py for the
    # node-level unit tests these fakes are shared with).
    monkeypatch.setattr(rag_client, "retrieve", _fake_rag_retrieve_ok)
    monkeypatch.setattr(provider_client, "search", _fake_provider_search_ok)
    monkeypatch.setattr(llm_adapter, "generate_curator_explanation", _fake_llm_success)

    response = client.post("/recommendations/run", json={"user_text": "warm indie folk"})
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "graph"
    assert body["placeholder"] is False
    assert body["playlist_title"]
    assert len(body["tracks"]) == 1
    assert {"title", "artist", "reasoning"} <= body["tracks"][0].keys()
    assert body["tracks"][0]["reasoning"]


# Regression test for the defect found live on 2026-07-26: WF-002 forwards the
# whole RequestEnvelope as `context`, not a RecommendationContext, so every
# lookup missed and the graph ran on an empty query. Nothing raised -- the only
# symptom was irrelevant recommendations, and only on the browser path.
def test_wf002_envelope_shape_reaches_the_graph():
    from main import _build_initial_state

    envelope = {
        "api_version": "v1",
        "request_id": "req-1",
        "intent": "text_recommendation",
        "identity": {"guest_id": "g-1", "session_id": "s-1", "user_id": None},
        "locale": "he",
        "body": {
            "prompt": "dreamy shoegaze for a rainy night",
            "recommendation_context": {
                "request_id": "req-1",
                "user_text": "dreamy shoegaze for a rainy night",
                "discovery_mode": "adventurous",
                "locale": "he",
                "exclusions": ["Slowdive"],
            },
        },
        "idempotency_key": None,
    }
    state = _build_initial_state(
        {"request_id": "req-1", "user_id": None, "locale": "he", "context": envelope}
    )
    assert state["user_text"] == "dreamy shoegaze for a rainy night"
    assert state["discovery_mode"] == "adventurous"
    assert state["language"] == "he"
    assert state["explicit_constraints"]["avoid"] == ["Slowdive"]


def test_flat_context_shape_still_works():
    """The direct callers (smoke test, REC-LEG harness) send this shape."""
    from main import _build_initial_state

    state = _build_initial_state(
        {"request_id": "r", "context": {"user_text": "warm indie folk", "discovery_mode": "safe"}}
    )
    assert state["user_text"] == "warm indie folk"
    assert state["discovery_mode"] == "safe"


def test_profiles_update_stub():
    response = client.post("/profiles/update", json={"user_id": "u-123"})
    assert response.status_code == 200
    assert response.json()["user_id"] == "u-123"


def test_request_id_propagates():
    response = client.get("/health/live", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"
