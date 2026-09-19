"""Tests for health endpoint and FastAPI app."""

import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["app_name"] == "S*EntryTrace"
    assert data["status"] == "ok"
    assert "mvt" in data
    assert "adb" in data


def test_health_mvt_available(client):
    resp = client.get("/health")
    data = resp.json()
    assert data["mvt"]["available"] is True
    assert data["mvt"]["version"] is not None


def test_health_adb_section(client):
    resp = client.get("/health")
    data = resp.json()
    assert "available" in data["adb"]
