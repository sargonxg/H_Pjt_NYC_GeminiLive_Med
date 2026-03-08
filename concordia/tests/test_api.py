"""Integration tests for REST API endpoints."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestGraphEndpoint:
    def test_get_graph(self, client):
        r = client.get("/api/graph")
        assert r.status_code == 200
        d = r.json()
        assert "actors" in d
        assert "claims" in d
        assert "edges" in d


class TestHealthEndpoint:
    def test_health_check(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "healthy"
        assert "gemini_api" in d
        assert "graph_health" in d
        assert "active_cases" in d


class TestStatusEndpoint:
    def test_status(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        d = r.json()
        assert "title" in d
        assert "phase" in d
        assert "counts" in d
        assert "health" in d


class TestSetKeyEndpoint:
    def test_set_key(self, client):
        r = client.post("/api/set-key", json={"key": "test-key-123"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_set_key_empty(self, client):
        # Empty string is rejected with 400 (validation)
        r = client.post("/api/set-key", json={"key": ""})
        assert r.status_code == 400


class TestCasesEndpoints:
    def test_create_case(self, client):
        r = client.post("/api/cases", json={"title": "Test", "parties": ["Alice", "Bob"]})
        assert r.status_code == 200
        d = r.json()
        assert "case_id" in d
        assert len(d["parties"]) == 2
        assert d["parties"][0]["name"] == "Alice"
        assert d["parties"][0]["status"] == "active"
        assert d["parties"][1]["status"] == "waiting"

    def test_create_case_no_title(self, client):
        r = client.post("/api/cases", json={"parties": ["A", "B"]})
        assert r.status_code == 200

    def test_create_case_too_few_parties(self, client):
        r = client.post("/api/cases", json={"parties": ["Only One"]})
        assert r.status_code == 422

    def test_create_case_missing_parties(self, client):
        r = client.post("/api/cases", json={})
        assert r.status_code == 422

    def test_list_cases(self, client):
        client.post("/api/cases", json={"parties": ["A", "B"]})
        r = client.get("/api/cases")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    def test_get_case(self, client):
        cr = client.post("/api/cases", json={"title": "Detail Test", "parties": ["X", "Y"]})
        cid = cr.json()["case_id"]
        r = client.get(f"/api/cases/{cid}")
        assert r.status_code == 200
        d = r.json()
        assert d["case_id"] == cid
        assert "graph" in d
        assert "party_health" in d

    def test_get_case_404(self, client):
        r = client.get("/api/cases/nonexistent")
        assert r.status_code == 404

    def test_advance_case(self, client):
        cr = client.post("/api/cases", json={"parties": ["A", "B"]})
        cid = cr.json()["case_id"]
        r = client.post(f"/api/cases/{cid}/advance", json={})
        assert r.status_code == 200
        d = r.json()
        assert d["previous_phase"] == "intake_party_1"
        assert d["current_phase"] == "intake_party_2"

    def test_advance_case_404(self, client):
        r = client.post("/api/cases/nonexistent/advance", json={})
        assert r.status_code == 404


class TestUploadEndpoint:
    def test_upload_404_case(self, client):
        r = client.post("/api/cases/nonexistent/upload", json={
            "party_id": "p1", "text": "hello", "document_name": "doc"})
        assert r.status_code == 404

    def test_upload_404_party(self, client):
        cr = client.post("/api/cases", json={"parties": ["A", "B"]})
        cid = cr.json()["case_id"]
        r = client.post(f"/api/cases/{cid}/upload", json={
            "party_id": "nonexistent", "text": "hello"})
        assert r.status_code == 404


class TestStaticServing:
    def test_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "CONCORDIA" in r.text
