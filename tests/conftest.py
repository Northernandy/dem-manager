"""
Test configuration and fixtures for the Brisbane Flood Visualization project.

This module provides pytest fixtures and configuration for all tests.
"""

import os
import sys
import pytest
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test')

# Define constants used across tests
TEST_DATA_DIR = os.path.join(project_root, 'data', 'test')
DEM_DIR = os.path.join(project_root, 'data', 'geo')
SMALL_BBOX_BRISBANE = (152.95, -27.5, 153.05, -27.4)  # Small area around Brisbane CBD


@pytest.fixture(scope="session")
def test_data_dir():
    """Fixture to provide the test data directory."""
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    return TEST_DATA_DIR


@pytest.fixture(scope="session")
def dem_dir():
    """Fixture to provide the DEM directory."""
    os.makedirs(DEM_DIR, exist_ok=True)
    os.makedirs(os.path.join(DEM_DIR, 'metadata'), exist_ok=True)
    return DEM_DIR


@pytest.fixture(scope="function")
def clean_test_files(test_data_dir, dem_dir):
    """Fixture to clean up test files before and after tests."""
    # Clean up before test
    _cleanup_test_files(test_data_dir, dem_dir)
    
    # Run the test
    yield
    
    # Clean up after test
    _cleanup_test_files(test_data_dir, dem_dir)


def _cleanup_test_files(test_data_dir, dem_dir):
    """Helper function to clean up test files."""
    # Remove test files from data/test directory
    for file in os.listdir(test_data_dir):
        if file.startswith('test_'):
            try:
                os.remove(os.path.join(test_data_dir, file))
            except Exception as e:
                logger.warning(f"Could not remove {file}: {e}")
    
    # Remove test files from data/geo directory
    for file in os.listdir(dem_dir):
        if file.startswith('test_'):
            try:
                os.remove(os.path.join(dem_dir, file))
            except Exception as e:
                logger.warning(f"Could not remove {file}: {e}")
    
    # Remove test metadata files
    metadata_dir = os.path.join(dem_dir, 'metadata')
    if os.path.exists(metadata_dir):
        for file in os.listdir(metadata_dir):
            if file.startswith('test_'):
                try:
                    os.remove(os.path.join(metadata_dir, file))
                except Exception as e:
                    logger.warning(f"Could not remove metadata file {file}: {e}")
