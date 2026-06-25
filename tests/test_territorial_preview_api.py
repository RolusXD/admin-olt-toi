from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_zones_preview_returns_200_and_basic_shape():
    response = client.get("/api/v1/admin/territorial/zones/preview")
    assert response.status_code == 200

    data = response.json()
    assert "summaries" in data
    assert "catalog_proposals" in data
    assert "onus" in data


def test_get_naps_preview_returns_200_and_basic_shape():
    response = client.get("/api/v1/admin/territorial/naps/preview")
    assert response.status_code == 200

    data = response.json()
    assert "summaries" in data
    assert "catalog_proposals" in data
    assert "onus" in data


def test_get_territorial_audit_center_returns_200_and_basic_shape():
    response = client.get("/api/v1/admin/territorial/audit-center")
    assert response.status_code == 200

    data = response.json()
    assert "generated_at" in data
    assert "olt_summaries" in data
    assert "zone_state_summary" in data
    assert "nap_state_summary" in data
    assert "confidence_summary" in data
    assert "critical_issues" in data
    assert "recommendations" in data
