"""
Test script for fetching DEM data from Geoscience Australia's updated REST service.
This script tests the new URL without modifying the existing codebase.
"""

import os
import sys
import logging
import requests
import time
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project root to the Python path to import the DEMFetcher
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.pipeline.dem_fetcher import DEMFetcher, fetch_dem

def test_rest_service_connection(url):
    """
    Test if the REST service is accessible and returns a valid response.
    
    Args:
        url (str): The REST service URL to test
        
    Returns:
        bool: True if the service is accessible, False otherwise
    """
    try:
        logger.info(f"Testing connection to REST service: {url}")
        response = requests.get(f"{url}?f=json", timeout=30)
        
        if response.status_code == 200:
            logger.info("Connection successful!")
            logger.info(f"Service response: {response.text[:500]}...")
            return True
        else:
            logger.error(f"Connection failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return False
    except Exception as e:
        logger.error(f"Error connecting to REST service: {str(e)}")
        return False

def test_fetch_dem_with_new_url():
    """
    Test fetching DEM data using the updated REST service URL.
    """
    # Define the updated URL for the 1 Second National DEM
    new_url = "https://services.ga.gov.au/gis/rest/services/DEM_SRTM_1Second_2024/MapServer"
    
    # Test if the service is accessible
    if not test_rest_service_connection(new_url):
        logger.error("Cannot proceed with DEM fetch test as the service is not accessible.")
        return False
    
    # Define a smaller test area (around Brisbane CBD) to speed up testing
    test_bbox = (152.95, -27.5, 153.05, -27.4)  # Small area around Brisbane CBD
    
    # Create output directory for test data
    test_output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                  'data', 'test_geo')
    os.makedirs(test_output_dir, exist_ok=True)
    
    # Define output file
    test_output_file = os.path.join(test_output_dir, "test_1sec_dem.tif")
    
    logger.info(f"Testing DEM fetch with new URL: {new_url}")
    logger.info(f"Test area: {test_bbox}")
    logger.info(f"Output file: {test_output_file}")
    
    # Try to fetch the DEM
    try:
        success = fetch_dem(
            bbox=test_bbox,
            target_res_meters=30,  # 1 Second DEM is approximately 30m resolution
            output_dir=test_output_dir,
            output_file=test_output_file,
            rest_url=new_url
        )
        
        if success:
            logger.info("DEM fetch test successful!")
            logger.info(f"DEM saved to: {test_output_file}")
            return True
        else:
            logger.error("DEM fetch test failed.")
            return False
    except Exception as e:
        logger.error(f"Error during DEM fetch test: {str(e)}")
        return False

def test_export_params():
    """
    Test different export parameters to see which ones work with the new service.
    """
    # Define the updated URL for the 1 Second National DEM
    new_url = "https://services.ga.gov.au/gis/rest/services/DEM_SRTM_1Second_2024/MapServer"
    export_url = f"{new_url}/export"
    
    # Test area (small area around Brisbane CBD)
    test_bbox = (152.95, -27.5, 153.05, -27.4)
    
    # Basic export parameters
    params = {
        'bbox': ','.join(map(str, test_bbox)),
        'bboxSR': 4326,  # WGS84
        'imageSR': 4326,
        'size': '500,500',
        'format': 'tiff',
        'pixelType': 'F32',
        'noDataInterpretation': 'esriNoDataMatchAny',
        'interpolation': 'RSP_BilinearInterpolation',
        'f': 'image'
    }
    
    logger.info(f"Testing export parameters with URL: {export_url}")
    logger.info(f"Parameters: {params}")
    
    try:
        response = requests.get(export_url, params=params, timeout=60)
        
        if response.status_code == 200:
            # Save the response to a file
            test_output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                          'data', 'test_geo')
            os.makedirs(test_output_dir, exist_ok=True)
            output_file = os.path.join(test_output_dir, "test_export_params.tif")
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Export test successful! Saved to: {output_file}")
            return True
        else:
            logger.error(f"Export test failed with status code: {response.status_code}")
            if response.text:
                logger.error(f"Response: {response.text[:500]}")
            return False
    except Exception as e:
        logger.error(f"Error during export test: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting DEM fetch test script")
    
    # Test the REST service connection
    new_url = "https://services.ga.gov.au/gis/rest/services/DEM_SRTM_1Second_2024/MapServer"
    if test_rest_service_connection(new_url):
        # Test export parameters
        if test_export_params():
            # Test full DEM fetch
            test_fetch_dem_with_new_url()
        else:
            logger.error("Export parameters test failed. Skipping full DEM fetch test.")
    else:
        logger.error("REST service connection test failed. Cannot proceed with further tests.")
    
    logger.info("DEM fetch test script completed")
