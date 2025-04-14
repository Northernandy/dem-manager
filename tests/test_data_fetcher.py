"""
Tests for the data_fetcher module.
"""

import os
import unittest
from pathlib import Path
from datetime import datetime
from src.pipeline.data_fetcher import DataFetcher

class TestDataFetcher(unittest.TestCase):
    """Test cases for the DataFetcher class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for test data
        self.test_data_dir = Path("test_data")
        os.makedirs(self.test_data_dir, exist_ok=True)
        
        # Initialize the DataFetcher with the test directory
        self.fetcher = DataFetcher(data_dir=self.test_data_dir)
        
    def tearDown(self):
        """Clean up after each test."""
        # Remove test files
        for file in self.test_data_dir.glob("*"):
            os.remove(file)
        
        # Remove test directory
        os.rmdir(self.test_data_dir)
        
    def test_init_default_dir(self):
        """Test that DataFetcher initializes with default directory."""
        fetcher = DataFetcher()
        expected_dir = Path(__file__).parent.parent / 'data' / 'raw'
        self.assertEqual(fetcher.data_dir, expected_dir)
        
    def test_init_custom_dir(self):
        """Test that DataFetcher initializes with custom directory."""
        custom_dir = Path("custom_data_dir")
        fetcher = DataFetcher(data_dir=custom_dir)
        self.assertEqual(fetcher.data_dir, custom_dir)
        
    def test_fetch_bom_data(self):
        """Test fetching BOM data."""
        station_id = "040913"
        start_date = "2023-01-01"
        end_date = "2023-01-31"
        
        file_path = self.fetcher.fetch_bom_data(station_id, start_date, end_date)
        
        # Check that the file was created
        self.assertTrue(os.path.exists(file_path))
        
        # Check that the filename is correct
        expected_filename = f"bom_{station_id}_{start_date}_to_{end_date}.csv"
        self.assertEqual(os.path.basename(file_path), expected_filename)
        
    def test_fetch_bom_data_default_dates(self):
        """Test fetching BOM data with default dates."""
        station_id = "040913"
        
        file_path = self.fetcher.fetch_bom_data(station_id)
        
        # Check that the file was created
        self.assertTrue(os.path.exists(file_path))
        
        # Check that the filename contains today's date
        today = datetime.now().strftime('%Y-%m-%d')
        self.assertIn(today, os.path.basename(file_path))
        
    def test_fetch_seqwater_data(self):
        """Test fetching SEQ Water data."""
        dam_id = "wivenhoe"
        data_type = "level"
        start_date = "2023-01-01"
        end_date = "2023-01-31"
        
        file_path = self.fetcher.fetch_seqwater_data(dam_id, data_type, start_date, end_date)
        
        # Check that the file was created
        self.assertTrue(os.path.exists(file_path))
        
        # Check that the filename is correct
        expected_filename = f"seqwater_{dam_id}_{data_type}_{start_date}_to_{end_date}.csv"
        self.assertEqual(os.path.basename(file_path), expected_filename)
        
    def test_fetch_dem_data(self):
        """Test fetching DEM data."""
        region = "Brisbane CBD"
        resolution = "10m"
        
        file_path = self.fetcher.fetch_dem_data(region, resolution)
        
        # Check that the file was created
        self.assertTrue(os.path.exists(file_path))
        
        # Check that the filename is correct
        expected_filename = f"dem_brisbane_cbd_{resolution}.tif"
        self.assertEqual(os.path.basename(file_path), expected_filename)


if __name__ == "__main__":
    unittest.main()
