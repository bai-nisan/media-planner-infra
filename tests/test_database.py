"""
Tests for database bridge functionality and endpoints.

Tests the AI workflow database bridge with read-only access patterns.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.services.database import DatabaseBridge, get_database_bridge
from main import app


class TestDatabaseBridge:
    """Test cases for DatabaseBridge class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db_bridge = DatabaseBridge()

    @patch("app.services.database.create_client")
    def test_client_initialization(self, mock_create_client):
        """Test Supabase client initialization."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client

        # Force client creation
        client = self.db_bridge.client

        # Verify client was created with correct parameters
        mock_create_client.assert_called_once_with(
            self.db_bridge.settings.SUPABASE_URL, self.db_bridge.settings.SUPABASE_KEY
        )
        assert client == mock_client

    @patch("app.services.database.create_client")
    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_create_client):
        """Test successful database health check."""
        mock_client = Mock()
        mock_auth = Mock()
        mock_auth.get_user.return_value = {"user": "test"}
        mock_client.auth = mock_auth
        mock_create_client.return_value = mock_client

        health_status = await self.db_bridge.health_check()

        assert health_status["status"] == "healthy"
        assert health_status["database"] == "connected"
        assert "timestamp" in health_status
        assert health_status["message"] == "Database connection successful"

    @patch("app.services.database.create_client")
    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_create_client):
        """Test failed database health check."""
        mock_client = Mock()
        mock_auth = Mock()
        mock_auth.get_user.side_effect = Exception("Connection failed")
        mock_client.auth = mock_auth
        mock_create_client.return_value = mock_client

        health_status = await self.db_bridge.health_check()

        assert health_status["status"] == "unhealthy"
        assert health_status["database"] == "disconnected"
        assert "error" in health_status
        assert health_status["message"] == "Database connection failed"

    @patch("app.services.database.create_client")
    def test_get_campaign_context_success(self, mock_create_client):
        """Test successful campaign context retrieval."""
        mock_client = Mock()
        mock_table = Mock()
        mock_response = Mock()
        mock_response.data = [
            {
                "id": "camp123",
                "name": "Test Campaign",
                "budget": 10000,
                "status": "active",
                "target_audience": "adults",
                "objectives": ["awareness"],
                "channels": ["google", "meta"],
                "created_at": "2024-01-01",
                "tenant_id": "tenant123",
            }
        ]

        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table
        mock_create_client.return_value = mock_client

        # Clear cache first
        self.db_bridge.get_campaign_context.cache_clear()

        context = self.db_bridge.get_campaign_context("camp123", "tenant123")

        assert context is not None
        assert context["campaign_id"] == "camp123"
        assert context["name"] == "Test Campaign"
        assert context["budget"] == 10000
        assert context["tenant_id"] == "tenant123"

        # Verify correct table and query calls
        mock_client.table.assert_called_with("campaigns")
        mock_table.select.assert_called_with("*")
        mock_table.eq.assert_any_call("id", "camp123")
        mock_table.eq.assert_any_call("tenant_id", "tenant123")

    @patch("app.services.database.create_client")
    def test_get_campaign_context_not_found(self, mock_create_client):
        """Test campaign context retrieval when campaign not found."""
        mock_client = Mock()
        mock_table = Mock()
        mock_response = Mock()
        mock_response.data = []

        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table
        mock_create_client.return_value = mock_client

        # Clear cache first
        self.db_bridge.get_campaign_context.cache_clear()

        context = self.db_bridge.get_campaign_context("nonexistent")

        assert context is None

    @patch("app.services.database.create_client")
    def test_get_workflow_history(self, mock_create_client):
        """Test workflow history retrieval."""
        mock_client = Mock()
        mock_table = Mock()
        mock_response = Mock()
        mock_response.data = [
            {
                "id": "exec123",
                "workflow_type": "campaign_analysis",
                "status": "completed",
                "input_data": {"campaign_id": "camp123"},
                "output_data": {"score": 85},
                "execution_time": 120,
                "created_at": "2024-01-01",
            }
        ]

        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table
        mock_create_client.return_value = mock_client

        history = self.db_bridge.get_workflow_history("campaign_analysis", 5)

        assert len(history) == 1
        assert history[0]["execution_id"] == "exec123"
        assert history[0]["workflow_type"] == "campaign_analysis"
        assert history[0]["status"] == "completed"

        # Verify correct query calls
        mock_client.table.assert_called_with("workflow_executions")
        mock_table.eq.assert_called_with("workflow_type", "campaign_analysis")
        mock_table.order.assert_called_with("created_at", desc=True)
        mock_table.limit.assert_called_with(5)

    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        # This test ensures cache_clear methods exist and can be called
        try:
            self.db_bridge.clear_cache()
            # If no exception is raised, test passes
            assert True
        except Exception as e:
            pytest.fail(f"Cache clearing failed: {str(e)}")


class TestDatabaseEndpoints:
    """Test cases for database API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

    @patch("app.services.database.get_database_bridge")
    @pytest.mark.asyncio
    async def test_database_health_endpoint_healthy(self, mock_get_bridge):
        """Test database health endpoint with healthy status."""
        mock_bridge = Mock()
        mock_bridge.health_check.return_value = {
            "status": "healthy",
            "database": "connected",
            "message": "Database connection successful",
        }
        mock_get_bridge.return_value = mock_bridge

        response = self.client.get("/api/v1/database/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    @patch("app.services.database.get_database_bridge")
    def test_campaign_context_endpoint_success(self, mock_get_bridge):
        """Test campaign context endpoint with successful retrieval."""
        mock_bridge = Mock()
        mock_bridge.get_campaign_context.return_value = {
            "campaign_id": "camp123",
            "name": "Test Campaign",
            "budget": 10000,
        }
        mock_get_bridge.return_value = mock_bridge

        response = self.client.get("/api/v1/database/campaign-context/camp123")

        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == "camp123"
        assert data["name"] == "Test Campaign"

    @patch("app.services.database.get_database_bridge")
    def test_campaign_context_endpoint_not_found(self, mock_get_bridge):
        """Test campaign context endpoint when campaign not found."""
        mock_bridge = Mock()
        mock_bridge.get_campaign_context.return_value = None
        mock_get_bridge.return_value = mock_bridge

        response = self.client.get("/api/v1/database/campaign-context/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "Campaign not found" in data["detail"]

    @patch("app.services.database.get_database_bridge")
    def test_workflow_history_endpoint(self, mock_get_bridge):
        """Test workflow history endpoint."""
        mock_bridge = Mock()
        mock_bridge.get_workflow_history.return_value = [
            {
                "execution_id": "exec123",
                "workflow_type": "campaign_analysis",
                "status": "completed",
            }
        ]
        mock_get_bridge.return_value = mock_bridge

        response = self.client.get(
            "/api/v1/database/workflow-history/campaign_analysis?limit=5"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["execution_id"] == "exec123"

    @patch("app.services.database.get_database_bridge")
    def test_clear_cache_endpoint(self, mock_get_bridge):
        """Test cache clearing endpoint."""
        mock_bridge = Mock()
        mock_bridge.clear_cache.return_value = None
        mock_get_bridge.return_value = mock_bridge

        response = self.client.post("/api/v1/database/cache/clear")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Database cache cleared successfully"
