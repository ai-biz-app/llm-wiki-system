"""Pytest fixtures and configuration."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def sample_wiki_content():
    """Sample markdown content for testing."""
    return """# Test Page

This is a test wiki page.

## Section 1

Content here.

## Section 2

- Item 1
- Item 2
- Item 3
"""
