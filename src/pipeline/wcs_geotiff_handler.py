import random
import os
import requests
from owslib.wcs import WebCoverageService
import rasterio
from rasterio.merge import merge
import sys
import math
import time
from .dem_reprojection import reproject_lidar_5m

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

def fetch_geotiff_dem(bbox, dem_type, resolution=None, output_file=None, use_tiling=True, max_tile_size=2048):
    """
    Fetch a GeoTIFF DEM for the specified bounding box and DEM type.
    
    Args:
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy)
        dem_type (str): Type of DEM to fetch (e.g., 'national_1s', 'lidar_5m')
        resolution (int, optional): Resolution in meters
        output_file (str, optional): Output file name
        use_tiling (bool, optional): Whether to use tiling strategy for high-resolution requests
        max_tile_size (int, optional): Maximum tile size in pixels when using tiling
        
    Returns:
        dict: Result of the operation with success status and file path
    """
    # Map dem_type to the appropriate WCS URL and CRS
    dem_configs = {
        'national_1s': {
            'url': 'https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_Hydro_Enforced_2024/MapServer/WCSServer',
            'crs': 'EPSG:4326',
            'resolution': 30  # 30 meters per pixel (native SRTM resolution)
        },
        'lidar_5m': {
            'url': 'https://services.ga.gov.au/gis/services/DEM_LiDAR_5m_2025/MapServer/WCSServer',
            #'crs': 'EPSG:4326',  # This projection is unfortunately not working which means a headache on the UI side. 
            'crs': 'EPSG:4283',  # Only this projection is working for fetching data 
            'resolution': 5  # 5 meters per pixel (native LiDAR resolution)
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
        # Calculate geographic information
        minx, miny, maxx, maxy = bbox
        lon_range = maxx - minx
        lat_range = maxy - miny
        
        # Calculate approximate dimensions in kilometers
        meters_per_degree_lon = 111320 * math.cos(miny * (math.pi/180))
        meters_per_degree_lat = 111320
        bbox_width_km = (lon_range * meters_per_degree_lon) / 1000
        bbox_height_km = (lat_range * meters_per_degree_lat) / 1000
        
        print(f"Area dimensions: ~{bbox_width_km:.1f}km × {bbox_height_km:.1f}km")
        
        # Set target resolution based on the dataset
        if resolution:
            target_resolution_m = resolution
        elif dem_type == 'lidar_5m':
            target_resolution_m = dem_config['resolution']  # 5 meters per pixel (native LiDAR resolution)
        else:
            target_resolution_m = dem_config['resolution']  # 30 meters per pixel (native SRTM resolution)
        
        print(f"Target resolution: {target_resolution_m}m per pixel")
        
        # Calculate required pixels for target resolution
        required_width_px = int(bbox_width_km * 1000 / target_resolution_m)
        required_height_px = int(bbox_height_km * 1000 / target_resolution_m)
        
        print(f"Required pixels for native resolution: {required_width_px} × {required_height_px}")
        
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
        
        # Check if we need to use tiling strategy
        # Use tiling if:
        # 1. use_tiling is True, AND
        # 2. Either width or height exceeds max_tile_size
        if use_tiling and (required_width_px > max_tile_size or required_height_px > max_tile_size):
            print(f"Using tiling strategy (max tile size: {max_tile_size}×{max_tile_size} pixels)")
            return fetch_geotiff_dem_tiled(
                bbox, 
                dem_type, 
                target_resolution_m, 
                file_path, 
                max_tile_size,
                wcs_url,
                crs
            )
        
        # If not using tiling, proceed with single request
        print("Using single request strategy")
        
        # Connect to the WCS
        wcs = WebCoverageService(wcs_url, version='1.0.0')
        
        # Get the first coverage ID
        coverage_keys = list(wcs.contents.keys())
        coverage_id = coverage_keys[0]
        
        # Calculate width and height for the request
        # Limit to max_tile_size if needed
        width = min(required_width_px, max_tile_size)
        height = min(required_height_px, max_tile_size)
        
        print(f"Requesting image with dimensions: {width}×{height} pixels")
        
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
        
        # Make the request
        print(f"Sending WCS GetCoverage request...")
        start_time = time.time()
        response = requests.get(wcs_url, params=params)
        
        # Check if the request was successful
        if response.status_code != 200:
            print(f"Request failed with status code: {response.status_code}")
            print(f"Response: {response.text[:500]}...")
            return {
                'success': False,
                'message': f"WCS request failed with status code: {response.status_code}"
            }
        
        # Save the response content to a file
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        elapsed_time = time.time() - start_time
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        print(f"Successfully fetched DEM in {elapsed_time:.2f}s ({file_size_mb:.2f}MB)")
        print(f"Saved to: {file_path}")
        
        # Reproject 5m LiDAR data from EPSG:4283 to EPSG:4326 for frontend compatibility
        if dem_type == 'lidar_5m':
            print(f"Reprojecting 5m LiDAR data from EPSG:4283 to EPSG:4326 for frontend compatibility...")
            reprojection_result = reproject_lidar_5m(file_path, in_place=True)
            
            if reprojection_result['success']:
                print(f"Successfully reprojected 5m LiDAR data: {reprojection_result['message']}")
                # file_path remains the same since we're doing in-place reprojection
            else:
                print(f"Warning: Reprojection failed: {reprojection_result['message']}")
                # Continue with the original file if reprojection fails
        
        # Validate the file
        validate_geotiff(file_path)
        
        return {
            'success': True,
            'file_path': file_path,
            'width_px': width,
            'height_px': height,
            'resolution_m': target_resolution_m
        }
    
    except Exception as e:
        print(f"Error fetching DEM: {str(e)}")
        return {
            'success': False,
            'message': f"Error fetching DEM: {str(e)}"
        }

def fetch_geotiff_dem_tiled(bbox, dem_type, target_resolution_m, output_file, max_tile_size, wcs_url, crs):
    """
    Fetch a GeoTIFF DEM using a tiling strategy for high-resolution requests.
    
    Args:
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy)
        dem_type (str): Type of DEM to fetch
        target_resolution_m (float): Target resolution in meters per pixel
        output_file (str): Output file path
        max_tile_size (int): Maximum tile size in pixels
        wcs_url (str): WCS service URL
        crs (str): Coordinate reference system
        
    Returns:
        dict: Result of the operation with success status and file path
    """
    try:
        start_time = time.time()
        
        # Calculate geographic information
        minx, miny, maxx, maxy = bbox
        lon_range = maxx - minx
        lat_range = maxy - miny
        
        # Calculate approximate dimensions in kilometers
        meters_per_degree_lon = 111320 * math.cos(miny * (math.pi/180))
        meters_per_degree_lat = 111320
        bbox_width_km = (lon_range * meters_per_degree_lon) / 1000
        bbox_height_km = (lat_range * meters_per_degree_lat) / 1000
        
        # Calculate required pixels for target resolution
        required_width_px = int(bbox_width_km * 1000 / target_resolution_m)
        required_height_px = int(bbox_height_km * 1000 / target_resolution_m)
        
        # Calculate number of tiles needed
        num_tiles_x = math.ceil(required_width_px / max_tile_size)
        num_tiles_y = math.ceil(required_height_px / max_tile_size)
        total_tiles = num_tiles_x * num_tiles_y
        
        print(f"Number of tiles needed: {num_tiles_x} × {num_tiles_y} = {total_tiles} tiles")
        
        # Calculate tile size in degrees
        tile_size_lon = lon_range / num_tiles_x
        tile_size_lat = lat_range / num_tiles_y
        
        # Create a directory for tiles
        tiles_dir = os.path.join(os.path.dirname(output_file), "tiles")
        os.makedirs(tiles_dir, exist_ok=True)
        
        # Fetch each tile
        tile_files = []
        tile_count = 0
        
        for y in range(num_tiles_y):
            for x in range(num_tiles_x):
                tile_count += 1
                print(f"\nFetching tile {tile_count}/{total_tiles} ({x+1},{y+1} of {num_tiles_x},{num_tiles_y})")
                
                # Calculate tile bbox
                tile_minx = minx + (x * tile_size_lon)
                tile_miny = miny + (y * tile_size_lat)
                tile_maxx = minx + ((x + 1) * tile_size_lon)
                tile_maxy = miny + ((y + 1) * tile_size_lat)
                
                # Ensure we don't exceed the original bbox
                tile_maxx = min(tile_maxx, maxx)
                tile_maxy = min(tile_maxy, maxy)
                
                tile_bbox = (tile_minx, tile_miny, tile_maxx, tile_maxy)
                
                # Generate output file path for the tile
                tile_file = os.path.join(tiles_dir, f"tile_{tile_minx:.6f}_{tile_miny:.6f}_{tile_maxx:.6f}_{tile_maxy:.6f}.tif")
                
                # Fetch the tile
                success = fetch_tile(tile_bbox, tile_file, wcs_url, crs, max_tile_size, max_tile_size)
                
                if success:
                    tile_files.append(tile_file)
                else:
                    print(f"Warning: Failed to fetch tile {tile_count}/{total_tiles}")
        
        if not tile_files:
            print("Error: No tiles were successfully fetched.")
            return {
                'success': False,
                'message': "No tiles were successfully fetched."
            }
        
        # Merge the tiles
        print("\n=== STARTING TILE MERGING PROCESS ===")
        print(f"Merging {len(tile_files)} tiles into a single high-resolution DEM...")
        
        # Open all the tile files
        src_files_to_mosaic = []
        for tile_file in tile_files:
            try:
                src = rasterio.open(tile_file)
                src_files_to_mosaic.append(src)
            except Exception as e:
                print(f"Warning: Could not open tile {tile_file}: {e}")
        
        if not src_files_to_mosaic:
            print("Error: No valid tile files to merge.")
            return {
                'success': False,
                'message': "No valid tile files to merge."
            }
        
        # Merge the tiles
        mosaic, out_trans = merge(src_files_to_mosaic)
        
        # Copy the metadata from the first tile
        out_meta = src_files_to_mosaic[0].meta.copy()
        
        # Update the metadata
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans
        })
        
        # Write the merged DEM
        with rasterio.open(output_file, "w", **out_meta) as dest:
            dest.write(mosaic)
        
        # Close all the tile files
        for src in src_files_to_mosaic:
            src.close()
        
        elapsed_time = time.time() - start_time
        file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
        
        print("\n=== MERGE COMPLETED SUCCESSFULLY ===")
        print(f"Successfully merged {len(tile_files)}/{total_tiles} tiles into a single DEM")
        print(f"Output file: {output_file}")
        print(f"Output dimensions: {out_meta['width']}×{out_meta['height']} pixels")
        print(f"Output file size: {file_size_mb:.2f}MB")
        print(f"Total processing time: {elapsed_time:.2f}s")
        print("=======================================")
        
        # Reproject 5m LiDAR data from EPSG:4283 to EPSG:4326 for frontend compatibility
        if dem_type == 'lidar_5m':
            print(f"Reprojecting 5m LiDAR data from EPSG:4283 to EPSG:4326 for frontend compatibility...")
            reprojection_result = reproject_lidar_5m(output_file, in_place=True)
            
            if reprojection_result['success']:
                print(f"Successfully reprojected 5m LiDAR data: {reprojection_result['message']}")
                # output_file remains the same since we're doing in-place reprojection
            else:
                print(f"Warning: Reprojection failed: {reprojection_result['message']}")
                # Continue with the original file if reprojection fails
        
        # Validate the merged file
        validate_geotiff(output_file)
        
        return {
            'success': True,
            'file_path': output_file,
            'width_px': out_meta['width'],
            'height_px': out_meta['height'],
            'resolution_m': target_resolution_m,
            'tiles_fetched': len(tile_files),
            'tiles_total': total_tiles
        }
    
    except Exception as e:
        print(f"Error in tiled DEM fetching: {str(e)}")
        return {
            'success': False,
            'message': f"Error in tiled DEM fetching: {str(e)}"
        }

def fetch_tile(bbox, output_file, wcs_url, crs, width, height):
    """
    Fetch a single DEM tile using WCS GetCoverage request.
    
    Args:
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy)
        output_file (str): Path to save the tile
        wcs_url (str): WCS service URL
        crs (str): Coordinate reference system
        width (int): Width of the tile in pixels
        height (int): Height of the tile in pixels
        
    Returns:
        bool: True if successful, False otherwise
    """
    minx, miny, maxx, maxy = bbox
    bbox_str = f"{minx},{miny},{maxx},{maxy}"
    
    print(f"Connecting to WCS service for tile {minx:.6f},{miny:.6f} to {maxx:.6f},{maxy:.6f}")
    
    # For both national_1s and lidar_5m, use coverage ID 1 (assuming it's the first layer)
    coverage_id = '1'
    
    # Construct WCS GetCoverage request
    params = {
        'service': 'WCS',
        'request': 'GetCoverage',
        'version': '1.0.0',
        'coverage': coverage_id,
        'CRS': crs,
        'BBOX': bbox_str,
        'WIDTH': width,
        'HEIGHT': height,
        'FORMAT': 'GeoTIFF',
    }
    
    # Hardcoded retry parameters
    max_retries = 3
    retry_delay = 2
    
    # Try up to max_retries + 1 times (initial attempt + retries)
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"Retry attempt {attempt}/{max_retries} for tile...")
            time.sleep(retry_delay)
            
        print(f"Sending WCS GetCoverage request for tile (attempt {attempt + 1}/{max_retries + 1})...")
        start_time = time.time()
        
        try:
            response = requests.get(wcs_url, params=params, stream=True)
            
            if response.status_code == 200:
                # Save the response content to a file
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                elapsed_time = time.time() - start_time
                file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
                
                print(f"Successfully fetched tile in {elapsed_time:.2f}s ({file_size_mb:.2f}MB)")
                return True
            else:
                print(f"Failed to fetch tile. Status code: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                
                # If not the last attempt, continue to next retry
                if attempt < max_retries:
                    continue
                return False
        
        except Exception as e:
            print(f"Error fetching tile: {e}")
            
            # If not the last attempt, continue to next retry
            if attempt < max_retries:
                continue
            return False
    
    # If we get here, all retries have failed
    return False

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
