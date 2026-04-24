"""
Tests for health check endpoints.
"""

import pytest
from fastapi import status


class TestHealthCheck:
    """Test cases for health check endpoints."""
    
    def test_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "payment-reconciliation"
    
    def test_database_health_check(self, client):
        """Test database connectivity health check."""
        response = client.get("/health/db")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
