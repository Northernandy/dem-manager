"""
Test script to determine the maximum size the WCS server can handle.
This is a standalone script that doesn't affect the main application.
"""

import os
import requests
from owslib.wcs import WebCoverageService
import rasterio
import time

def test_wcs_size(width, height, bbox=(152.0, -28.0, 153.5, -27.0)):
    """
    Test fetching a DEM with specific dimensions.
    
    Args:
        width (int): Width in pixels
        height (int): Height in pixels
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy)
    """
    start_time = time.time()
    
    print(f"\n--- Testing WCS request with dimensions: {width}×{height} ---")
    
    # WCS service URL and CRS
    wcs_url = 'https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_Hydro_Enforced_2024/MapServer/WCSServer'
    crs = 'EPSG:4326'
    
    # Create output directory
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output filename
    file_name = f"test_dem_{width}x{height}.tif"
    file_path = os.path.join(output_dir, file_name)
    
    try:
        # Connect to the WCS
        print(f"Connecting to WCS service: {wcs_url}")
        wcs = WebCoverageService(wcs_url, version='1.0.0')
        coverage_keys = list(wcs.contents.keys())
        coverage_id = coverage_keys[0]
        print(f"Available coverage keys: {coverage_keys}")
        print(f"Using coverage ID: {coverage_id}")
        
        # Prepare the parameters for the WCS GetCoverage request
        params = {
            'service': 'WCS',
            'request': 'GetCoverage',
            'version': '1.0.0',
            'coverage': coverage_id,
            'CRS': crs,
            'BBOX': ','.join(map(str, bbox)),
            'WIDTH': width,
            'HEIGHT': height,
            'FORMAT': 'GeoTIFF'
        }
        
        print(f"Request parameters: {params}")
        
        # Make the request
        print(f"Sending WCS GetCoverage request...")
        response = requests.get(wcs_url, params=params)
        
        # Check if the request was successful
        if response.status_code != 200:
            print(f"Request failed with status code: {response.status_code}")
            print(f"Response content: {response.text}")
            return False
        
        print(f"Received response: {len(response.content)} bytes")
        
        # Save the file
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Saved GeoTIFF to: {file_path}")
        
        # Validate the GeoTIFF
        with rasterio.open(file_path) as dataset:
            # Basic validation passed if we can open the file
            print(f"GeoTIFF validation successful:")
            print(f"  CRS: {dataset.crs}")
            print(f"  Bounds: {dataset.bounds}")
            print(f"  Width: {dataset.width} pixels")
            print(f"  Height: {dataset.height} pixels")
            print(f"  Number of bands: {dataset.count}")
            print(f"  Data types: {dataset.dtypes}")
        
        print(f"Test successful for dimensions: {width}×{height}")
        return True
        
    except Exception as e:
        print(f"Error in test: {str(e)}")
        return False
    finally:
        end_time = time.time()
        print(f"Total execution time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    # Test with 2000×2000 pixels
    print("\n=== TESTING 2000×2000 PIXELS ===")
    test_wcs_size(2000, 2000)
    
    # Uncomment to test other sizes
    # test_wcs_size(500, 500)
    # test_wcs_size(1000, 1000)
    # test_wcs_size(3000, 3000)
    # test_wcs_size(3100, 3100)
    # test_wcs_size(3500, 3500)
    # test_wcs_size(4000, 4000)
    # test_wcs_size(4914, 3710)  # Full native resolution
