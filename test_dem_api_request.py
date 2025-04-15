"""
Simple test script to directly test the Geoscience Australia REST API
"""

import os
import sys
import requests
import logging
import rasterio

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_api_request():
    """Test a direct request to the Geoscience Australia REST API /export endpoint"""
    
    # --- Configuration ---
    # REST service URL
    rest_url = 'https://services.ga.gov.au/gis/rest/services/DEM_LiDAR_5m_2025/MapServer'
    endpoint = '/export'
    export_url = f"{rest_url}{endpoint}"

    # Test with a small area around Brisbane CBD
    BBOX = (153.0100, -27.4750, 153.0200, -27.4650)
    
    # Define the desired output resolution (pixels)
    WIDTH = 512
    HEIGHT = 512

    # Output file path
    output_tif = "test_raw_elevation.tif"
    # --- End Configuration ---

    # --- Request Parameters (ArcGIS REST API /export) ---
    params = {
        'bbox': ','.join(map(str, BBOX)),
        'bboxSR': 4326,  # WGS84
        'imageSR': 4326, # WGS84
        'size': f"{WIDTH},{HEIGHT}",
        'f': 'image',
        'format': 'tiff',
        'transparent': 'true', # Match setting from original script
        'pixelType': 'F32',  # Request raw floating-point elevation data
        'noDataInterpretation': 'esriNoDataMatchAny' # Match setting from original script
    }
    # --- End Request Parameters ---
    
    logger.info(f"\n\n===== Testing REST API /export endpoint =====")
    
    logger.info(f"Requesting DEM data from REST endpoint: {export_url}")
    logger.info(f"Parameters: {params}")

    try:
        response = requests.get(export_url, params=params, timeout=300, stream=True)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        logger.info(f"Response Status Code: {response.status_code}")
        logger.info(f"Response Headers: {dict(response.headers)}")

        content_type = response.headers.get('Content-Type', '').lower()
        content_disp = response.headers.get('Content-Disposition', '')

        # Check content type - REST API should ideally return 'image/tiff' or similar
        if 'tiff' in content_type or 'geotiff' in content_type:
            logger.info(f"Received expected Content-Type: {content_type}")
        elif content_disp and '.tif' in content_disp.lower():
            logger.info(f"Content-Type missing/unexpected ({content_type}), but Content-Disposition suggests TIFF ({content_disp}). Proceeding.")
        else:
            logger.warning(f"Unexpected Content-Type: {content_type}. Will attempt to save anyway.")
            # Log first part of content if type is unexpected
            try:
                preview = next(response.iter_content(chunk_size=500))
                logger.warning(f"Response content preview: {preview!r}...")
            except StopIteration:
                logger.warning("Response content is empty.")
            # We need to re-request if we consumed the preview
            logger.info("Re-requesting data after preview...")
            response = requests.get(export_url, params=params, timeout=300, stream=True)
            response.raise_for_status()

        # Save the response content to a file
        with open(output_tif, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Saved response content to {output_tif}")

        # Check file size and content
        if os.path.exists(output_tif) and os.path.getsize(output_tif) > 0:
            logger.info(f"File size: {os.path.getsize(output_tif)} bytes")
            logger.info(f"File exists and is not empty. Proceeding with validation.")
        else:
            logger.error(f"Output file {output_tif} was not created or is empty.")
            return

        # --- Validate the Output (using Rasterio) ---
        try:
            with rasterio.open(output_tif) as dataset:
                logger.info("Successfully opened the raster file.")
                logger.info(f"CRS: {dataset.crs}")
                logger.info(f"Bounds: {dataset.bounds}")
                logger.info(f"Width: {dataset.width}, Height: {dataset.height}")
                logger.info(f"Number of bands: {dataset.count}")
                if dataset.count > 0:
                    # Check the data type of the first band
                    dtype = dataset.dtypes[0]
                    logger.info(f"Band 1 Data Type (dtype): {dtype}")
                    if dtype == 'float32':
                        logger.info("SUCCESS: Raster data type is Float32 as desired.")
                    else:
                        logger.warning(f"WARNING: Raster data type is {dtype}, not Float32.")
                logger.info("Rasterio validation successful.")
        except rasterio.RasterioIOError as e:
            logger.error(f"RasterioIOError: Failed to open or read {output_tif}. It might not be a valid GeoTIFF.")
            logger.error(e)
            # Log first few bytes if validation fails
            try:
                with open(output_tif, 'rb') as f:
                    preview = f.read(500)
                logger.error(f"File content preview (first 500 bytes): {preview!r}")
            except Exception as fe:
                logger.error(f"Could not read file preview: {fe}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        if e.response is not None:
            logger.error(f"Response Status Code: {e.response.status_code}")
            logger.error(f"Response Text: {e.response.text[:500]}...") # Log first 500 chars
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_api_request()
