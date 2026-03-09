import pytest
from starlette.testclient import TestClient
from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_suggestions_returns_results(client):
    r = client.get("/api/suggestions?q=tiers")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    texts = [item["text"] for item in data]
    assert any("tiers" in t.lower() for t in texts)


def test_suggestions_table_match(client):
    r = client.get("/api/suggestions?q=generic")
    data = r.json()
    assert any(item["text"] == "generic_anomaly" and item["category"] == "table" for item in data)


def test_suggestions_column_match(client):
    r = client.get("/api/suggestions?q=control")
    data = r.json()
    assert any(item["category"] == "colonne" for item in data)


def test_suggestions_max_10(client):
    r = client.get("/api/suggestions?q=a")
    data = r.json()
    assert len(data) <= 10


def test_suggestions_min_length(client):
    r = client.get("/api/suggestions?q=x")
    assert r.status_code == 422  # Validation error: min_length=2


def test_suggestions_no_match(client):
    r = client.get("/api/suggestions?q=xyzzyplugh")
    data = r.json()
    assert len(data) == 0
