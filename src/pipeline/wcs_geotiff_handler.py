import random
import os
import requests
from owslib.wcs import WebCoverageService
import rasterio
import sys

# Directory constants - use absolute paths for reliability
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DATA_DIR = os.path.join(BASE_DIR, "data", "geo")

# Ensure base data directory exists
os.makedirs(BASE_DATA_DIR, exist_ok=True)

def validate_geotiff(file_path):
    """Reads a GeoTIFF file using rasterio and prints its metadata."""
    print(f"--- Validating GeoTIFF: {file_path} ---")
    try:
        with rasterio.open(file_path) as dataset:
            print(f"Successfully opened file.")
            print(f"  CRS: {dataset.crs}")
            print(f"  Bounds: {dataset.bounds}")
            print(f"  Width: {dataset.width}")
            print(f"  Height: {dataset.height}")
            print(f"  Number of bands: {dataset.count}")
            print(f"  Data types: {dataset.dtypes}")
            print(f"  NoData value: {dataset.nodata}")
            print(f"  Driver: {dataset.driver}")
            try:
                data_block = dataset.read(1, window=((0, 10), (0, 10)))
                print(f"  Successfully read a 10x10 data block from band 1.")
                print(f"  Sample data: {data_block}")
            except Exception as read_err:
                print(f"  Warning: Could not read data block: {read_err}")
        print("--- Validation Complete ---\n")
    except rasterio.RasterioIOError as e:
        print(f"ERROR: Could not open file. It might not be a valid GeoTIFF or path is incorrect.")
        print(f"  Details: {e}")
    except FileNotFoundError:
        print(f"ERROR: File not found at path: {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def request_and_validate_tile(wcs_url, bbox_extent, crs, filename_prefix):
    print(f"\n--- Connecting to WCS: {wcs_url} ---")
    wcs = WebCoverageService(wcs_url, version='1.0.0')
    coverage_keys = list(wcs.contents.keys())
    print(f"Coverage Keys: {coverage_keys}")
    coverage_id = coverage_keys[0]

    minx, maxx, miny, maxy = bbox_extent
    tile_width = (maxx - minx) * 0.1  # 10% of the full extent
    tile_height = (maxy - miny) * 0.1
    lon = round(random.uniform(minx, maxx - tile_width), 6)
    lat = round(random.uniform(miny, maxy - tile_height), 6)
    bbox = (lon, lat, lon + tile_width, lat + tile_height)

    print(f"Requesting coverage '{coverage_id}' for BBOX: {bbox}")

    params = {
        'service': 'WCS',
        'request': 'GetCoverage',
        'version': '1.0.0',
        'coverage': coverage_id,
        'CRS': crs,
        'BBOX': ','.join(map(str, bbox)),
        'WIDTH': 500,
        'HEIGHT': 500,
        'FORMAT': 'GeoTIFF'
    }

    response = requests.get(wcs_url, params=params)
    
    # Ensure the base data directory exists
    os.makedirs(BASE_DATA_DIR, exist_ok=True)
    
    # Save file directly in the data/geo directory
    filename = os.path.join(BASE_DATA_DIR, f"{filename_prefix}_tile.tif")
    
    with open(filename, 'wb') as f:
        f.write(response.content)

    print(f"Saved GeoTIFF to: {filename}")
    validate_geotiff(filename)

def fetch_geotiff_dem(bbox, dem_type, resolution=None, output_file=None):
    """
    Fetch a GeoTIFF DEM for the specified bounding box and DEM type.
    
    Args:
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy)
        dem_type (str): Type of DEM to fetch (e.g., 'national_1s', 'lidar_5m')
        resolution (int, optional): Resolution in meters
        output_file (str, optional): Output file name
        
    Returns:
        dict: Result of the operation with success status and file path
    """
    # Map dem_type to the appropriate WCS URL and CRS
    dem_configs = {
        'national_1s': {
            'url': 'https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_Hydro_Enforced_2024/MapServer/WCSServer',
            'crs': 'EPSG:4326'
        },
        'lidar_5m': {
            'url': 'https://services.ga.gov.au/gis/services/DEM_LiDAR_5m_2025/MapServer/WCSServer',
            'crs': 'EPSG:4283'
        }
    }
    
    if dem_type not in dem_configs:
        return {
            'success': False,
            'message': f"Unknown DEM type: {dem_type}"
        }
    
    dem_config = dem_configs[dem_type]
    wcs_url = dem_config['url']
    crs = dem_config['crs']
    
    try:
        # Determine output file path
        if output_file:
            file_name = output_file
        else:
            # Generate a file name based on the DEM type and bounding box
            bbox_str = '_'.join([str(coord).replace('.', 'p') for coord in bbox])
            file_name = f"{dem_type}_{bbox_str}.tif"
        
        # Save directly to the main data/geo directory instead of a subdirectory
        output_dir = os.path.join(BASE_DATA_DIR)
        os.makedirs(output_dir, exist_ok=True)
        
        file_path = os.path.join(output_dir, file_name)
        
        # Connect to the WCS
        wcs = WebCoverageService(wcs_url, version='1.0.0')
        coverage_keys = list(wcs.contents.keys())
        coverage_id = coverage_keys[0]
        
        # Prepare the parameters for the WCS GetCoverage request
        params = {
            'service': 'WCS',
            'request': 'GetCoverage',
            'version': '1.0.0',
            'coverage': coverage_id,
            'CRS': crs,
            'BBOX': ','.join(map(str, bbox)),
            'WIDTH': 500 if not resolution else int(resolution),
            'HEIGHT': 500 if not resolution else int(resolution),
            'FORMAT': 'GeoTIFF'
        }
        
        # Make the request
        response = requests.get(wcs_url, params=params)
        
        # Check if the request was successful
        if response.status_code != 200:
            return {
                'success': False,
                'message': f"Failed to fetch GeoTIFF. Status code: {response.status_code}"
            }
        
        # Save the file
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        # Validate the GeoTIFF
        try:
            with rasterio.open(file_path) as dataset:
                # Basic validation passed if we can open the file
                pass
        except Exception as e:
            return {
                'success': False,
                'message': f"Failed to validate GeoTIFF: {str(e)}"
            }
        
        return {
            'success': True,
            'message': f"Successfully fetched GeoTIFF DEM",
            'file_path': file_path
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f"Error fetching GeoTIFF DEM: {str(e)}"
        }

if __name__ == "__main__":
    # Test the fetch_geotiff_dem function directly
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Testing fetch_geotiff_dem function with small bounding box...")
        
        # Define a small bounding box around Brisbane
        bbox = (152.9, -27.5, 153.0, -27.4)
        
        # Test fetching raw elevation data
        result = fetch_geotiff_dem(
            bbox=bbox,
            dem_type='national_1s',
            resolution=500,
            output_file="test_geotiff.tif"
        )
        
        print(f"Test result: {result}")
        
        if result.get('success', False):
            print(f"Successfully saved file to: {result.get('file_path')}")
            validate_geotiff(result.get('file_path'))
        else:
            print(f"Failed to fetch GeoTIFF: {result.get('message')}")
    else:
        print("Testing fetch_geotiff_dem function with default parameters...")
        
        # Test with SRTM 1 Second DEM (national_1s)
        srtm_result = fetch_geotiff_dem(
            bbox=(152.5, -28.4, 153.2, -27.0),
            dem_type='national_1s',
            resolution=500,
            output_file="national_1s_full.tif"
        )
        
        print(f"SRTM result: {srtm_result}")
        
        if srtm_result.get('success', False):
            print(f"Successfully saved SRTM file to: {srtm_result.get('file_path')}")
            validate_geotiff(srtm_result.get('file_path'))
        
        # Test with LiDAR 5m DEM (lidar_5m)
        lidar_result = fetch_geotiff_dem(
            bbox=(139.6726, -36.9499, 139.6851, -36.9412),
            dem_type='lidar_5m',
            resolution=500,
            output_file="lidar_5m_full.tif"
        )
        
        print(f"LiDAR result: {lidar_result}")
        
        if lidar_result.get('success', False):
            print(f"Successfully saved LiDAR file to: {lidar_result.get('file_path')}")
            validate_geotiff(lidar_result.get('file_path'))
