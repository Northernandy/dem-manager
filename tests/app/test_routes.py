"""
Tests for the Flask application routes.

This module tests the API endpoints and routes of the Flask application.

Usage:
    pytest -xvs tests/app/test_routes.py
"""

import os
import json
import pytest
import tempfile
from pathlib import Path

# Import the Flask app
from app.app import app as flask_app


@pytest.fixture
def client():
    """Fixture to provide a test client for the Flask app."""
    flask_app.config['TESTING'] = True
    
    with flask_app.test_client() as client:
        yield client


class TestRoutes:
    """Test cases for Flask routes."""
    
    def test_index_route(self, client):
        """Test the main index route."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Brisbane Flood Visualization' in response.data
    
    def test_settings_route(self, client):
        """Test the settings page route."""
        response = client.get('/settings')
        assert response.status_code == 200
        assert b'DEM Management' in response.data
    
    def test_list_dems_api(self, client):
        """Test the API endpoint to list available DEMs."""
        response = client.get('/api/list-dems')
        assert response.status_code == 200
        
        # Parse the JSON response
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is True
        assert 'dems' in data
        
        # DEMs should be a list (even if empty)
        assert isinstance(data['dems'], list)
    
    def test_logs_route(self, client):
        """Test the logs viewer route."""
        response = client.get('/logs')
        assert response.status_code == 200
        assert b'Log Viewer' in response.data
    
    def test_get_app_logs_api(self, client):
        """Test the API endpoint to get application logs."""
        response = client.get('/api/get-app-logs')
        assert response.status_code == 200
        
        # Parse the JSON response
        data = json.loads(response.data)
        assert 'success' in data
        assert 'logs' in data
        
        # Logs should be a string
        assert isinstance(data['logs'], str)
    
    def test_system_info_api(self, client):
        """Test the API endpoint to get system information."""
        response = client.get('/api/system-info')
        assert response.status_code == 200
        
        # Parse the JSON response
        data = json.loads(response.data)
        assert 'success' in data
        assert data['success'] is True
        assert 'system_info' in data
        
        # Check that system info contains expected fields
        system_info = data['system_info']
        assert 'python_version' in system_info
        assert 'platform' in system_info
        assert 'memory_usage' in system_info
