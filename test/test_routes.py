import pytest
from starlette.testclient import TestClient
from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_frontend_serves(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Prisme" in r.text


def test_css_serves(client):
    r = client.get("/css/styles.css")
    assert r.status_code == 200


def test_js_serves(client):
    r = client.get("/js/app.js")
    assert r.status_code == 200
    r = client.get("/js/ui.js")
    assert r.status_code == 200


def test_schema_endpoint(client):
    r = client.get("/api/schema")
    assert r.status_code == 200
    data = r.json()
    assert "generic_anomaly" in data
    assert "configuration" in data
    assert data["generic_anomaly"]["row_count"] > 100_000


def test_export_csv(client):
    r = client.get("/api/export?sql=SELECT anomaly_kuid FROM generic_anomaly LIMIT 5&format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "anomaly_kuid" in r.text


def test_export_xlsx(client):
    r = client.get("/api/export?sql=SELECT anomaly_kuid FROM generic_anomaly LIMIT 5&format=xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]


def test_export_rejects_delete(client):
    r = client.get("/api/export?sql=DELETE FROM generic_anomaly&format=csv")
    assert r.status_code == 400


def test_execute_rejects_without_conversation(client):
    r = client.post("/api/execute", json={"conversation_id": "fake", "sql": "SELECT 1"})
    assert r.status_code == 404
