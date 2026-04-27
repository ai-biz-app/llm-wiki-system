"""Tests for ingestion routes."""
import pytest


def test_ingest_url_endpoint_exists(client):
    """Verify the ingest URL endpoint is accessible."""
    response = client.post("/api/ingest/url", json={"url": "https://example.com"})
    # Should accept the request (don't validate processing)
    assert response.status_code in [200, 202, 422]  # 422 if validation fails


def test_ingest_requires_url_field(client):
    """Verify URL field is required."""
    response = client.post("/api/ingest/url", json={})
    assert response.status_code == 422  # Validation error
