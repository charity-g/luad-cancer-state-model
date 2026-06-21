from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_graph_endpoint_returns_full_graph():
    r = client.get("/graph")
    assert r.status_code == 200
    body = r.json()
    assert len(body["nodes"]) >= 500
    assert len(body["edges"]) >= 1500


def test_query_endpoint_contract(force_fallback):
    from backend.agents.traverse_graph import cypher

    r = client.post("/query", json={"question": "Will inhibiting KRAS help?"})
    assert r.status_code == 200
    body = r.json()
    assert {"report", "cypher", "verdict", "subgraph", "cited_pathways"} <= set(body)
    assert cypher.is_read_only(body["cypher"])


def test_query_requires_question():
    r = client.post("/query", json={})
    assert r.status_code == 422  # FastAPI validation
