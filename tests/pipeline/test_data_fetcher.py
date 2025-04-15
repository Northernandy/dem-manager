"""
Tests for the data_fetcher module.

This module tests the DataFetcher's ability to:
1. Fetch BOM data
2. Fetch SEQ Water data
3. Manage data directories

Usage:
    pytest -xvs tests/pipeline/test_data_fetcher.py
"""

import os
import pytest
import logging
from pathlib import Path
from datetime import datetime

# Import the DataFetcher class
from src.pipeline.data_fetcher import DataFetcher

# Get logger
logger = logging.getLogger('test')


@pytest.fixture
def data_fetcher(test_data_dir):
    """Fixture to provide a DataFetcher instance."""
    return DataFetcher(data_dir=test_data_dir)


class TestDataFetcher:
    """Test cases for the DataFetcher class."""
    
    def test_init_default_dir(self):
        """Test that DataFetcher initializes with default directory."""
        fetcher = DataFetcher()
        expected_dir = Path(__file__).parent.parent.parent / 'data' / 'raw'
        assert fetcher.data_dir == expected_dir
    
    def test_init_custom_dir(self, test_data_dir):
        """Test that DataFetcher initializes with custom directory."""
        fetcher = DataFetcher(data_dir=test_data_dir)
        assert fetcher.data_dir == test_data_dir
    
    def test_fetch_bom_data(self, data_fetcher, clean_test_files):
        """Test fetching BOM data."""
        station_id = "040913"
        start_date = "2023-01-01"
        end_date = "2023-01-31"
        
        file_path = data_fetcher.fetch_bom_data(station_id, start_date, end_date)
        
        # Check that the file was created
        assert os.path.exists(file_path)
        
        # Check that the filename is correct
        expected_filename = f"bom_{station_id}_{start_date}_to_{end_date}.csv"
        assert os.path.basename(file_path) == expected_filename
    
    def test_fetch_bom_data_default_dates(self, data_fetcher, clean_test_files):
        """Test fetching BOM data with default dates."""
        station_id = "040913"
        
        file_path = data_fetcher.fetch_bom_data(station_id)
        
        # Check that the file was created
        assert os.path.exists(file_path)
        
        # Check that the filename contains today's date
        today = datetime.now().strftime('%Y-%m-%d')
        assert today in os.path.basename(file_path)
    
    def test_fetch_seqwater_data(self, data_fetcher, clean_test_files):
        """Test fetching SEQ Water data."""
        dam_id = "wivenhoe"
        data_type = "level"
        start_date = "2023-01-01"
        end_date = "2023-01-31"
        
        file_path = data_fetcher.fetch_seqwater_data(dam_id, data_type, start_date, end_date)
        
        # Check that the file was created
        assert os.path.exists(file_path)
        
        # Check that the filename is correct
        expected_filename = f"seqwater_{dam_id}_{data_type}_{start_date}_to_{end_date}.csv"
        assert os.path.basename(file_path) == expected_filename
    
    def test_fetch_dem_data(self, data_fetcher, clean_test_files):
        """Test fetching DEM data."""
        region = "Brisbane CBD"
        resolution = "10m"
        
        file_path = data_fetcher.fetch_dem_data(region, resolution)
        
        # Check that the file was created
        assert os.path.exists(file_path)
        
        # Check that the filename is correct
        expected_filename = f"dem_brisbane_cbd_{resolution}.tif"
        assert os.path.basename(file_path) == expected_filename
