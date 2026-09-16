import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"]["total_tickets"] == 500
    assert "llm_provider" in data

def test_query_endpoint():
    resp = client.post("/query", json={"query": "How many tickets are currently open?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "open_tickets_count" in data["results"][0]
    assert data["results"][0]["open_tickets_count"] == 111
    assert "summary" in data
    assert data["execution_time_ms"] >= 0

def test_query_endpoint_empty():
    resp = client.post("/query", json={"query": "   "})
    assert resp.status_code == 400

def test_anomalies_endpoint():
    resp = client.get("/anomalies?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_anomalies"] > 0
    assert len(data["anomalies"]) <= 10
    assert "by_severity" in data

def test_anomalies_filter_critical():
    resp = client.get("/anomalies?severity=CRITICAL")
    assert resp.status_code == 200
    data = resp.json()
    for a in data["anomalies"]:
        assert a["severity"] == "CRITICAL"

def test_analytics_summary_endpoint():
    resp = client.get("/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "kpis" in data
    assert "categories" in data
    assert "top_agents" in data

def test_dashboard_ui():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "DOTMappers" in resp.text
    assert "Support Ticket Intelligence" in resp.text
