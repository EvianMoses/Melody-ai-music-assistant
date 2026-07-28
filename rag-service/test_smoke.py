from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import main
from genre_graph import GenreGraph

client = TestClient(main.app)


class _FakeEmbeddingModel:
    def encode(self, *_args, **_kwargs):
        class _Vec:
            def tolist(self_inner):
                return [0.1, 0.2, 0.3]

        return _Vec()


class _FakeCrossEncoder:
    def predict(self, pairs):
        return [1.0 - i * 0.1 for i in range(len(pairs))]


def _fake_dense_search(_session, _query_vector, _pool, _filters):
    return [("chunk-1", "Indie folk blends acoustic instrumentation.", "doc-1", "genre")]


def _fake_fulltext_search(_session, _or_query, _pool, _filters):
    return [("chunk-2", "Warm production emphasizes reverb-laden vocals.", "doc-2", "genre")]


def test_health_live():
    assert client.get("/health/live").json() == {"status": "ok"}


def test_retrieve_real_pipeline(monkeypatch):
    monkeypatch.setattr(main, "_get_engine", lambda: create_engine("sqlite:///:memory:"))
    monkeypatch.setattr(main, "_get_embedding_model", lambda: _FakeEmbeddingModel())
    monkeypatch.setattr(main, "_get_cross_encoder", lambda: _FakeCrossEncoder())
    monkeypatch.setattr(main, "_get_genre_graph", lambda: GenreGraph())
    monkeypatch.setattr(main, "dense_search", _fake_dense_search)
    monkeypatch.setattr(main, "fulltext_search", _fake_fulltext_search)

    response = client.post("/rag/retrieve", json={"query": "warm indie folk"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "warm indie folk"
    assert len(body["chunks"]) == 2
    assert body["placeholder"] is False
    assert 0.0 <= body["retrieval_confidence"] <= 1.0


def test_retrieve_blank_query_returns_empty():
    response = client.post("/rag/retrieve", json={"query": "   "})
    assert response.status_code == 200
    body = response.json()
    assert body["chunks"] == []
    assert body["retrieval_confidence"] == 0.0


def test_ingest_disabled_without_token():
    response = client.post("/rag/ingest", json={"source": "test", "documents": []})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INGESTION_DISABLED"
