"""
Test script for the modified DEM fetcher that retrieves raw elevation data
"""

import os
import sys
import logging

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the modified DEM fetcher
from src.pipeline.dem_fetcher_raw import fetch_dem

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Test with a small area around Brisbane CBD to minimize download time
    test_bbox = (152.95, -27.5, 153.05, -27.45)  # Very small area for quick testing
    
    # Set output file in the data/geo directory
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'geo')
    output_file = os.path.join(output_dir, "test_raw_dem.tif")
    
    logger.info(f"Testing raw DEM fetcher with bbox: {test_bbox}")
    logger.info(f"Output file will be: {output_file}")
    
    # Run the fetcher
    success = fetch_dem(
        bbox=test_bbox,
        target_res_meters=5,  # 5m resolution
        output_dir=output_dir,
        output_file=output_file
    )
    
    if success:
        logger.info(f"Test successful! Raw DEM saved to: {output_file}")
        
        # Get file size
        file_size_bytes = os.path.getsize(output_file)
        file_size_mb = file_size_bytes / (1024 * 1024)
        logger.info(f"File size: {file_size_mb:.2f} MB ({file_size_bytes} bytes)")
        
        return 0
    else:
        logger.error("Test failed! Could not fetch raw DEM data.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
