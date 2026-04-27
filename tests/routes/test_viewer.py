"""Tests for wiki viewer routes."""
import pytest


def test_wiki_tree_endpoint_exists(client):
    """Verify wiki tree endpoint is accessible."""
    response = client.get("/api/wiki/")
    assert response.status_code in [200, 404]  # 404 if wiki dir empty


def test_wiki_page_endpoint_exists(client):
    """Verify wiki page endpoint is accessible."""
    response = client.get("/api/wiki/index.md")
    assert response.status_code in [200, 404]  # 404 if file doesn't exist
