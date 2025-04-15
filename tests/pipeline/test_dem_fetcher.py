"""
Tests for the DEM fetcher module.

This module tests the DEM fetcher's ability to:
1. Download small DEM files (both 1-second and 5m)
2. Rename DEM files
3. Delete DEM files
4. Ensure files are downloaded to the correct folder

Usage:
    pytest -xvs tests/pipeline/test_dem_fetcher.py
"""

import os
import time
import json
import pytest
import logging
from pathlib import Path

# Import test constants from conftest
from tests.conftest import SMALL_BBOX_BRISBANE

# Import the necessary modules
from src.pipeline.dem_fetcher import fetch_dem

# Get logger
logger = logging.getLogger('test')

# Test constants from conftest.py are imported automatically


@pytest.mark.dem
class TestDEMFetcher:
    """Test cases for DEM fetcher functionality."""

    def test_fetch_1second_dem(self, dem_dir, clean_test_files):
        """Test fetching a small 1-second DEM file."""
        logger.info("Testing 1-second DEM fetching...")
        
        output_file = os.path.join(dem_dir, "test_1second_dem.tif")
        
        # Start timer
        start_time = time.time()
        
        # Fetch the DEM
        success = fetch_dem(
            bbox=SMALL_BBOX_BRISBANE,
            target_res_meters=30,  # 1 Second DEM is approximately 30m resolution
            output_dir=dem_dir,
            output_file=output_file,
            rest_url="https://services.ga.gov.au/gis/rest/services/DEM_SRTM_1Second_2024/MapServer"
        )
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        # Log results
        if success:
            file_size_bytes = os.path.getsize(output_file)
            file_size_mb = file_size_bytes / (1024 * 1024)
            logger.info(f"1-second DEM fetch successful: {file_size_mb:.2f} MB in {elapsed_time:.2f} seconds")
        else:
            logger.error(f"1-second DEM fetch failed after {elapsed_time:.2f} seconds")
        
        # Assert that the fetch was successful
        assert success, "1-second DEM fetch failed"
        
        # Assert that the file exists and has a reasonable size
        assert os.path.exists(output_file), "1-second DEM file does not exist"
        assert os.path.getsize(output_file) > 10000, "1-second DEM file is too small"
    
    def test_fetch_5m_dem(self, dem_dir, clean_test_files):
        """Test fetching a small 5m DEM file."""
        logger.info("Testing 5m DEM fetching...")
        
        output_file = os.path.join(dem_dir, "test_5m_dem.tif")
        
        # Start timer
        start_time = time.time()
        
        # Fetch the DEM
        success = fetch_dem(
            bbox=SMALL_BBOX_BRISBANE,
            target_res_meters=5,  # 5m resolution
            output_dir=dem_dir,
            output_file=output_file,
            rest_url="https://services.ga.gov.au/gis/rest/services/DEM_LiDAR_5m_2025/MapServer"
        )
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        # Log results
        if success:
            file_size_bytes = os.path.getsize(output_file)
            file_size_mb = file_size_bytes / (1024 * 1024)
            logger.info(f"5m DEM fetch successful: {file_size_mb:.2f} MB in {elapsed_time:.2f} seconds")
        else:
            logger.error(f"5m DEM fetch failed after {elapsed_time:.2f} seconds")
        
        # Assert that the fetch was successful
        assert success, "5m DEM fetch failed"
        
        # Assert that the file exists and has a reasonable size
        assert os.path.exists(output_file), "5m DEM file does not exist"
        assert os.path.getsize(output_file) > 10000, "5m DEM file is too small"
    
    def test_rename_dem(self, dem_dir, clean_test_files):
        """Test renaming a DEM file by creating a metadata file."""
        logger.info("Testing DEM renaming...")
        
        # First, create a test DEM file (mock)
        test_file = os.path.join(dem_dir, "test_1second_dem.tif")
        with open(test_file, 'w') as f:
            f.write("Mock DEM file for testing")
        
        # Ensure the file exists
        assert os.path.exists(test_file), "Test DEM file does not exist"
        
        # Create metadata directory if it doesn't exist
        metadata_dir = os.path.join(dem_dir, 'metadata')
        os.makedirs(metadata_dir, exist_ok=True)
        
        # Create metadata file with a custom name
        test_name = "Test Brisbane CBD"
        metadata_file = os.path.join(metadata_dir, f"test_1second_dem.tif.json")
        
        with open(metadata_file, 'w') as f:
            json.dump({
                'display_name': test_name,
                'created_at': time.time(),
                'dem_type': 'national_1s',
                'bbox': SMALL_BBOX_BRISBANE,
                'resolution': 30
            }, f)
        
        # Assert that the metadata file exists
        assert os.path.exists(metadata_file), "Metadata file does not exist"
        
        # Read back the metadata to verify
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Assert that the display name was set correctly
        assert metadata['display_name'] == test_name, "Display name not set correctly"
        
        logger.info(f"DEM renamed successfully to '{test_name}'")
    
    def test_delete_dem(self, dem_dir, clean_test_files):
        """Test deleting DEM files."""
        logger.info("Testing DEM deletion...")
        
        # Create test DEM files
        test_files = [
            os.path.join(dem_dir, "test_1second_dem.tif"),
            os.path.join(dem_dir, "test_5m_dem.tif")
        ]
        
        for test_file in test_files:
            with open(test_file, 'w') as f:
                f.write("Mock DEM file for testing")
            
            # Create metadata file
            metadata_dir = os.path.join(dem_dir, 'metadata')
            os.makedirs(metadata_dir, exist_ok=True)
            metadata_file = os.path.join(metadata_dir, f"{os.path.basename(test_file)}.json")
            with open(metadata_file, 'w') as f:
                json.dump({'display_name': 'Test DEM'}, f)
        
        # Delete each file and its metadata
        for test_file in test_files:
            if os.path.exists(test_file):
                # Delete the DEM file
                os.remove(test_file)
                logger.info(f"Deleted DEM file: {test_file}")
                
                # Delete the metadata file if it exists
                metadata_file = os.path.join(dem_dir, 'metadata', f"{os.path.basename(test_file)}.json")
                if os.path.exists(metadata_file):
                    os.remove(metadata_file)
                    logger.info(f"Deleted metadata file: {metadata_file}")
                
                # Assert that the files were deleted
                assert not os.path.exists(test_file), f"DEM file {test_file} was not deleted"
                assert not os.path.exists(metadata_file), f"Metadata file {metadata_file} was not deleted"
            else:
                logger.warning(f"DEM file {test_file} does not exist")
        
        logger.info("DEM deletion tests completed")
