"""
Test main FastAPI application endpoints.

Tests the basic functionality of the FastAPI application including
health checks and root endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

# Create test client
client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns basic information."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["message"] == "Media Planning Platform API"
    assert "version" in data
    assert "docs" in data


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "media-planner-api"
    assert "version" in data


def test_api_ping():
    """Test the API ping endpoint."""
    response = client.get("/api/v1/ping")
    assert response.status_code == 200

    data = response.json()
    assert data["message"] == "pong"


def test_api_status():
    """Test the API status endpoint."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data
    assert "environment" in data


def test_docs_endpoints():
    """Test that documentation endpoints are accessible."""
    # Test Swagger UI
    response = client.get("/api/docs")
    assert response.status_code == 200

    # Test ReDoc
    response = client.get("/api/redoc")
    assert response.status_code == 200

    # Test OpenAPI JSON
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
