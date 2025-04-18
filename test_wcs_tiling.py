"""
Test script to fetch a high-resolution DEM by breaking the request into smaller tiles
and stitching them together. This is a standalone script for testing purposes.
"""

import os
import requests
import rasterio
from rasterio.merge import merge
import math
import time
import sys
from datetime import datetime

# Create output directories
os.makedirs("test_output", exist_ok=True)
os.makedirs("test_output/tiles", exist_ok=True)

# DEM configurations
DEM_CONFIGS = {
    'national_1s': {
        'url': 'https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_Hydro_Enforced_2024/MapServer/WCSServer',
        'crs': 'EPSG:4326',
        'resolution': 30  # 30 meters per pixel (native SRTM resolution)
    },
    'lidar_5m': {
        'url': 'https://services.ga.gov.au/gis/services/DEM_LiDAR_5m_2025/MapServer/WCSServer',
        'crs': 'EPSG:4283',
        'resolution': 5  # 5 meters per pixel (native LiDAR resolution)
    }
}

def fetch_tile(bbox, output_file, dem_type='national_1s', width=2048, height=2048):
    """
    Fetch a single DEM tile using WCS GetCoverage request.
    
    Args:
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy)
        output_file (str): Path to save the tile
        dem_type (str): Type of DEM to fetch ('national_1s' or 'lidar_5m')
        width (int): Width of the tile in pixels
        height (int): Height of the tile in pixels
        
    Returns:
        bool: True if successful, False otherwise
    """
    if dem_type not in DEM_CONFIGS:
        print(f"Unknown DEM type: {dem_type}")
        return False
    
    config = DEM_CONFIGS[dem_type]
    wcs_url = config['url']
    crs = config['crs']
    
    # For national_1s, use coverage ID 1
    # For lidar_5m, use coverage ID 1 (assuming it's the first layer)
    coverage_id = '1'
    
    minx, miny, maxx, maxy = bbox
    bbox_str = f"{minx},{miny},{maxx},{maxy}"
    
    print(f"Connecting to WCS service for tile {minx},{miny} to {maxx},{maxy}")
    
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
        'FORMAT': 'GeoTIFF'
    }
    
    print("Sending WCS GetCoverage request for tile...")
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
            return False
    
    except Exception as e:
        print(f"Error fetching tile: {e}")
        return False

def fetch_dem_with_tiling(bbox, dem_type='national_1s', max_tile_size=2048, target_resolution=None):
    """
    Fetch a DEM for the specified bounding box using a tiling strategy.
    
    Args:
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy)
        dem_type (str): Type of DEM to fetch ('national_1s' or 'lidar_5m')
        max_tile_size (int): Maximum tile size in pixels
        target_resolution (int, optional): Target resolution in meters. If None, uses the native resolution.
        
    Returns:
        str: Path to the merged DEM file, or None if failed
    """
    print(f"\n--- Fetching DEM with tiling strategy ---")
    print(f"Bounding box: {bbox}")
    print(f"DEM type: {dem_type}")
    print(f"Max tile size: {max_tile_size} pixels")
    
    if dem_type not in DEM_CONFIGS:
        print(f"Unknown DEM type: {dem_type}")
        return None
    
    config = DEM_CONFIGS[dem_type]
    
    # Use provided target resolution or default to the DEM's native resolution
    if target_resolution is None:
        target_resolution = config['resolution']
    
    print(f"Target resolution: {target_resolution}m per pixel")
    
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
    
    # Calculate required pixels for native resolution
    required_width_px = int(bbox_width_km * 1000 / target_resolution)
    required_height_px = int(bbox_height_km * 1000 / target_resolution)
    
    print(f"Required pixels for native resolution: {required_width_px} × {required_height_px}")
    
    # Calculate number of tiles needed
    num_tiles_x = math.ceil(required_width_px / max_tile_size)
    num_tiles_y = math.ceil(required_height_px / max_tile_size)
    
    print(f"Number of tiles needed: {num_tiles_x} × {num_tiles_y} = {num_tiles_x * num_tiles_y} tiles")
    
    # Calculate tile size in degrees
    tile_size_lon = lon_range / num_tiles_x
    tile_size_lat = lat_range / num_tiles_y
    
    # Fetch each tile
    tile_files = []
    
    for y in range(num_tiles_y):
        for x in range(num_tiles_x):
            print(f"\nFetching tile {x+1},{y+1} of {num_tiles_x},{num_tiles_y}")
            
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
            tile_file = f"test_output/tiles/tile_{tile_minx:.6f}_{tile_miny:.6f}_{tile_maxx:.6f}_{tile_maxy:.6f}.tif"
            
            # Fetch the tile
            success = fetch_tile(tile_bbox, tile_file, dem_type, max_tile_size, max_tile_size)
            
            if success:
                tile_files.append(tile_file)
            else:
                print(f"Warning: Failed to fetch tile {x+1},{y+1}")
    
    if not tile_files:
        print("Error: No tiles were successfully fetched.")
        return None
    
    # Merge the tiles
    print("\nMerging tiles...")
    
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
        return None
    
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
    
    # Generate output file path for the merged DEM
    bbox_str = '_'.join([str(coord) for coord in bbox])
    merged_file = f"test_output/merged_dem_{dem_type}_{bbox_str}.tif"
    
    # Write the merged DEM
    with rasterio.open(merged_file, "w", **out_meta) as dest:
        dest.write(mosaic)
    
    # Close all the tile files
    for src in src_files_to_mosaic:
        src.close()
    
    print(f"Successfully merged {len(tile_files)} tiles into {merged_file}")
    
    return merged_file

if __name__ == "__main__":
    # Define a bounding box around Brisbane
    bbox = (152.0, -28.0, 153.5, -27.0)
    
    # Fetch DEM with tiling strategy for national_1s (30m resolution)
    print("\n=== Testing national_1s DEM (30m resolution) ===")
    merged_dem_national = fetch_dem_with_tiling(
        bbox, 
        dem_type='national_1s',
        max_tile_size=2048, 
        target_resolution=30
    )
    
    if merged_dem_national:
        print(f"\nSuccessfully created high-resolution national DEM: {merged_dem_national}")
    else:
        print("\nFailed to create high-resolution national DEM")
    
    # Fetch DEM with tiling strategy for lidar_5m (5m resolution)
    print("\n=== Testing lidar_5m DEM (5m resolution) ===")
    merged_dem_lidar = fetch_dem_with_tiling(
        bbox, 
        dem_type='lidar_5m',
        max_tile_size=2048, 
        target_resolution=5
    )
    
    if merged_dem_lidar:
        print(f"\nSuccessfully created high-resolution LiDAR DEM: {merged_dem_lidar}")
    else:
        print("\nFailed to create high-resolution LiDAR DEM")
