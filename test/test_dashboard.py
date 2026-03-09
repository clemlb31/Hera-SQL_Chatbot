import pytest
from starlette.testclient import TestClient
from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_dashboard_returns_kpis(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "total_anomalies" in data
    assert "hotfix_count" in data
    assert "typology_count" in data
    assert data["total_anomalies"] > 100_000
    assert data["typology_count"] == 264


def test_dashboard_top_business_objects(client):
    r = client.get("/api/dashboard")
    data = r.json()
    top = data["top_business_objects"]
    assert len(top) <= 5
    assert all("label" in item and "count" in item for item in top)
    # Should be sorted descending
    counts = [item["count"] for item in top]
    assert counts == sorted(counts, reverse=True)


def test_dashboard_top_typologies(client):
    r = client.get("/api/dashboard")
    data = r.json()
    top = data["top_typologies"]
    assert len(top) <= 5
    assert all("label" in item and "count" in item for item in top)


def test_dashboard_events(client):
    r = client.get("/api/dashboard")
    data = r.json()
    events = data["events"]
    assert len(events) > 0
    labels = [e["label"] for e in events]
    assert len(labels) > 0  # At least one event type exists
