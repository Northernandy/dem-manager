import requests
from PIL import Image
from io import BytesIO
import os
import numpy as np
import tifffile
import json
import re
import argparse
import math
import sys
import threading
import time

# Directory constants - use absolute paths for reliability
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DATA_DIR = os.path.join(BASE_DIR, "data", "geo")
TILES_DIR = os.path.join(BASE_DATA_DIR, "tiles")

# Ensure necessary directories exist
os.makedirs(BASE_DATA_DIR, exist_ok=True)
os.makedirs(TILES_DIR, exist_ok=True)

def setup_config(dataset_choice=None):
    """Configure the WMS endpoints and parameters
    
    Args:
        dataset_choice: Optional string to choose which dataset to use
                        Can be 'lidar', 'srtm', or 'both' (default)
    """
    # Define both endpoints
    wms_endpoints = {
        'srtm': {
            "name": "DEM_SRTM_1Second_Hydro_Enforced_2024",
            "url": "https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_Hydro_Enforced_2024/MapServer/WMSServer",
            "description": "SRTM 1 Second Hydro Enforced DEM"
        },
        'lidar': {
            "name": "DEM_LiDAR_5m_2025",
            "url": "https://services.ga.gov.au/gis/services/DEM_LiDAR_5m_2025/MapServer/WMSServer",
            "description": "LiDAR 5m DEM"
        }
    }
    
    # Default to both if not specified
    if dataset_choice is None:
        dataset_choice = 'both'
    
    # Validate dataset choice
    valid_choices = ['lidar', 'srtm', 'both']
    if dataset_choice not in valid_choices:
        print(f"Invalid dataset choice: {dataset_choice}")
        print(f"Valid choices are: {', '.join(valid_choices)}")
        print("Defaulting to 'both'")
        dataset_choice = 'both'
    
    # Create a list of active endpoints
    active_endpoints = []
    if dataset_choice == 'both':
        active_endpoints = [wms_endpoints['srtm'], wms_endpoints['lidar']]
    elif dataset_choice == 'srtm':
        active_endpoints = [wms_endpoints['srtm']]
    elif dataset_choice == 'lidar':
        active_endpoints = [wms_endpoints['lidar']]
    
    # Bounding box for Brisbane River basin
    # Includes Somerset Dam (north), Brisbane River mouth (east),
    # area west of Gatton, and Jimboomba (south)
    brisbane_basin_bbox = {
        "min_lat": -27.9344,
        "min_lon": 152.1765,
        "max_lat": -27.0164,
        "max_lon": 153.2674
    }
    
    print("Brisbane River Basin Bounding Box:")
    print(f"  North: {brisbane_basin_bbox['max_lat']} (near Somerset Dam)")
    print(f"  South: {brisbane_basin_bbox['min_lat']} (near Jimboomba)")
    print(f"  East: {brisbane_basin_bbox['max_lon']} (Brisbane River mouth)")
    print(f"  West: {brisbane_basin_bbox['min_lon']} (west of Gatton)")
    
    # Calculate dimensions
    lat_range = brisbane_basin_bbox["max_lat"] - brisbane_basin_bbox["min_lat"]
    lon_range = brisbane_basin_bbox["max_lon"] - brisbane_basin_bbox["min_lon"]
    print(f"  Latitude range: {lat_range:.4f}° (about {lat_range * 111:.0f}km)")
    print(f"  Longitude range: {lon_range:.4f}° (about {lon_range * 111 * math.cos(math.radians(brisbane_basin_bbox['min_lat'])):.0f}km)")
    
    # Common configuration parameters
    common_config = {
        "bbox": brisbane_basin_bbox,
        "max_tile_size": 4096,  # Maximum allowed by the server
        "image_format": "image/png"  # Always use PNG for RGB visualization
    }
    
    # Create a configuration for each active endpoint
    configs = []
    for endpoint in active_endpoints:
        config = common_config.copy()
        config["wms_url"] = endpoint["url"]
        config["wms_name"] = endpoint["name"]
        config["wms_description"] = endpoint["description"]
        configs.append(config)
    
    return configs

def extract_dataset_name(wms_url):
    match = re.search(r'/services/(.+?)/MapServer', wms_url)
    return match.group(1) if match else None

def calculate_tiles(config):
    """Calculate the number and size of tiles needed to match native dataset resolution"""
    bbox = config["bbox"]
    
    # Calculate the total range
    lat_range = bbox["max_lat"] - bbox["min_lat"]
    lon_range = bbox["max_lon"] - bbox["min_lon"]
    
    # Set target resolution based on the dataset
    # LiDAR is 5m native resolution, SRTM is ~30m native resolution
    if "LiDAR" in config.get("wms_name", ""):
        target_resolution = 5  # 5 meters per pixel (native LiDAR resolution)
        native_res = "5m"
    else:
        target_resolution = 30  # 30 meters per pixel (native SRTM resolution)
        native_res = "30m"
    
    print(f"Dataset: {config.get('wms_name', 'Unknown')}")
    print(f"Using native resolution: {native_res}")
    
    # Calculate rough dimensions in meters (approximate at these latitudes)
    meters_per_degree_lon = 111320 * math.cos(bbox["min_lat"] * (math.pi/180))
    meters_per_degree_lat = 111320
    
    bbox_width_m = lon_range * meters_per_degree_lon
    bbox_height_m = lat_range * meters_per_degree_lat
    
    print(f"Area dimensions: ~{bbox_width_m/1000:.1f}km x {bbox_height_m/1000:.1f}km")
    
    # Calculate required pixels
    required_width_px = int(bbox_width_m / target_resolution)
    required_height_px = int(bbox_height_m / target_resolution)
    
    print(f"Required pixels for {native_res} resolution: {required_width_px} x {required_height_px}")
    
    # Calculate required number of tiles
    lon_tiles = math.ceil(required_width_px / config["max_tile_size"])
    lat_tiles = math.ceil(required_height_px / config["max_tile_size"])
    
    # Ensure at least 2x2 tiles but limit maximum tiles
    lon_tiles = max(2, min(lon_tiles, 6))
    lat_tiles = max(2, min(lat_tiles, 6))
    
    # Calculate the size of each tile in degrees
    tile_lat_size = lat_range / lat_tiles
    tile_lon_size = lon_range / lon_tiles
    
    # Calculate actual resolution
    pixels_per_tile = config["max_tile_size"]
    total_width_px = lon_tiles * pixels_per_tile
    total_height_px = lat_tiles * pixels_per_tile
    
    lon_res_m = bbox_width_m / total_width_px
    lat_res_m = bbox_height_m / total_height_px
    
    print(f"Using {lat_tiles}x{lon_tiles} grid of tiles ({lat_tiles * lon_tiles} total)")
    print(f"Total output dimensions: {total_width_px}x{total_height_px} pixels")
    print(f"Actual resolution: {lon_res_m:.2f}m/pixel (lon), {lat_res_m:.2f}m/pixel (lat)")
    
    if lon_res_m < target_resolution * 0.9 or lat_res_m < target_resolution * 0.9:
        print(f"Warning: Final resolution is higher than needed for {native_res} data")
    
    return lat_tiles, lon_tiles, tile_lat_size, tile_lon_size

def download_tiles(config, lat_tiles, lon_tiles, tile_lat_size, tile_lon_size):
    """Download all tiles for the area"""
    # Create the tiles directory
    os.makedirs(TILES_DIR, exist_ok=True)
    tile_info = []
    
    # Always use PNG for RGB files
    file_ext = ".png"  # RGB files should always be PNG
    
    # Get a short name for the dataset to use in filenames
    short_name = config['wms_name'].replace("DEM_", "").replace("_2024", "").replace("_2025", "")
    
    # Calculate total number of tiles for progress tracking
    total_tiles = lat_tiles * lon_tiles
    tile_count = 0
    
    for lat_idx in range(lat_tiles):
        for lon_idx in range(lon_tiles):
            # Update tile count and display progress
            tile_count += 1
            print(f"Downloading tile {tile_count}/{total_tiles} ({tile_count/total_tiles*100:.1f}%)...")
            
            # Calculate this tile's bounds
            min_lat = config["bbox"]["min_lat"] + lat_idx * tile_lat_size
            max_lat = min_lat + tile_lat_size
            min_lon = config["bbox"]["min_lon"] + lon_idx * tile_lon_size
            max_lon = min_lon + tile_lon_size
            
            # WMS 1.3.0 with EPSG:4326 uses lat,lon order (y,x)
            bbox_str = f"{min_lat:.6f},{min_lon:.6f},{max_lat:.6f},{max_lon:.6f}"
            
            filename = os.path.join(TILES_DIR, f"tile_{short_name}_{lat_idx}_{lon_idx}{file_ext}")
            
            # Prepare WMS request parameters
            params = {
                "service": "WMS",
                "version": "1.3.0",
                "request": "GetMap",
                "layers": "0",
                "styles": "",
                "crs": "EPSG:4326",  # Using geographic coordinates for correct bbox ordering
                "bbox": bbox_str,
                "width": str(config["max_tile_size"]),
                "height": str(config["max_tile_size"]),
                "format": config["image_format"],
                "transparent": "true"
            }
            
            try:
                print(f"  Tile {lat_idx},{lon_idx} with bbox {bbox_str}")
                
                # Hardcoded retry parameters
                max_retries = 3
                retry_delay = 2
                
                # Try up to max_retries + 1 times (initial attempt + retries)
                for attempt in range(max_retries + 1):
                    if attempt > 0:
                        print(f"  Retry attempt {attempt}/{max_retries} for tile {lat_idx},{lon_idx}...")
                        time.sleep(retry_delay)
                    
                    print(f"  Sending WMS GetMap request for tile (attempt {attempt + 1}/{max_retries + 1})...")
                    
                    try:
                        response = requests.get(config["wms_url"], params=params)
                        response.raise_for_status()
                        
                        # Check for XML error response
                        if 'xml' in response.headers.get('Content-Type', '').lower() or response.content[:5] == b'<?xml':
                            print(f"  Server returned an XML error response for tile {lat_idx},{lon_idx}:")
                            print(response.text)
                            if attempt < max_retries:
                                continue
                            break
                        
                        # Validate image content
                        if "image" not in response.headers.get('Content-Type', '').lower():
                            print(f"  Unexpected content type: {response.headers.get('Content-Type', '')}")
                            if attempt < max_retries:
                                continue
                            break
                        
                        # Save the tile
                        with open(filename, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"  Saved {filename}")
                        tile_info.append({
                            "filename": filename,
                            "lat_idx": lat_idx,
                            "lon_idx": lon_idx,
                            "bbox": {
                                "min_lat": min_lat,
                                "min_lon": min_lon,
                                "max_lat": max_lat,
                                "max_lon": max_lon
                            }
                        })
                        
                        # Successfully saved the tile, break out of retry loop
                        break
                        
                    except Exception as e:
                        print(f"  Failed to download tile {lat_idx},{lon_idx} (attempt {attempt + 1}/{max_retries + 1}): {e}")
                        if attempt < max_retries:
                            continue
                        raise  # Re-raise the exception on the last attempt
                
            except Exception as e:
                print(f"  Failed to download tile {lat_idx},{lon_idx} after all retry attempts: {e}")
    
    print(f"Downloaded {len(tile_info)} valid tiles.")
    return tile_info

def stitch_tiles_with_metadata(tile_info, lat_tiles, lon_tiles, max_tile_size, config, output_path=None):
    """Stitch all downloaded tiles into a single image with embedded metadata"""
    if not tile_info:
        print("No valid tiles to stitch.")
        return False

    print("Stitching tiles with embedded metadata...")

    # Create an empty array to hold all the tile data
    stitched_width = max_tile_size * lon_tiles
    stitched_height = max_tile_size * lat_tiles
    
    # Need to determine number of channels based on first image
    first_image = Image.open(tile_info[0]["filename"])
    if first_image.mode == "RGBA":
        channels = 4
    else:
        channels = 3
    
    stitched_array = np.zeros((stitched_height, stitched_width, channels), dtype=np.uint8)

    # For each tile, place it in the correct position in the stitched image
    for tile in tile_info:
        try:
            img = Image.open(tile["filename"])
            if channels == 4 and img.mode != "RGBA":
                img = img.convert("RGBA")
            elif channels == 3 and img.mode != "RGB":
                img = img.convert("RGB")
                
            tile_array = np.array(img)

            y_offset = (lat_tiles - 1 - tile["lat_idx"]) * max_tile_size
            x_offset = tile["lon_idx"] * max_tile_size

            tile_height, tile_width = tile_array.shape[:2]
            stitched_array[y_offset:y_offset + tile_height,
                           x_offset:x_offset + tile_width, :] = tile_array

        except Exception as e:
            print(f"Error processing tile {tile['filename']}: {e}")

    # Extract dataset name from URL
    dataset_name = config['wms_name']

    # Get bounding box
    bbox = config["bbox"]

    # Generate metadata
    metadata = {
        "AREA_OR_POINT": "Area",
        "TIFFTAG_DOCUMENTNAME": dataset_name,
        "TIFFTAG_SOFTWARE": "Python WMS Client",
        "EPSG": "4326",
        "BBOX_MinLat": str(bbox["min_lat"]),
        "BBOX_MinLon": str(bbox["min_lon"]),
        "BBOX_MaxLat": str(bbox["max_lat"]),
        "BBOX_MaxLon": str(bbox["max_lon"]),
        "BBOX_JSON": json.dumps(bbox)
    }

    lon_range = bbox["max_lon"] - bbox["min_lon"]
    lat_range = bbox["max_lat"] - bbox["min_lat"]
    x_scale = lon_range / stitched_width
    y_scale = lat_range / stitched_height

    metadata["PIXEL_SCALE_X"] = str(x_scale)
    metadata["PIXEL_SCALE_Y"] = str(y_scale)
    metadata["ORIGIN_X"] = str(bbox["min_lon"])
    metadata["ORIGIN_Y"] = str(bbox["max_lat"])

    # Use a simplified name for the output file - only save as PNG
    # Remove DEM prefix and year suffixes for cleaner names
    short_name = dataset_name.replace("DEM_", "").replace("_2024", "").replace("_2025", "")
    
    # Handle the problematic SRTM filename specifically
    if short_name == "SRTM_1Second_Hydro_Enforced":
        short_name = "SRTM_Hydro"
    
    if output_path:
        # Use the provided output path
        png_file = output_path
        # Ensure the directory for the output path exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    else:
        # Ensure the RGB directory exists only if we're using it
        png_file = os.path.join(BASE_DATA_DIR, f"{short_name}.png")
    
    # Save as PNG for web-friendly format with transparency
    pil_img = Image.fromarray(stitched_array)
    pil_img.save(png_file)
    print(f"Web-friendly PNG saved as {png_file}")

    # Write world file for PNG
    if not output_path:
        png_world_file = os.path.join(BASE_DATA_DIR, f"{short_name}.pgw")
    else:
        png_world_file = output_path.replace('.png', '.pgw')
    
    try:
        os.makedirs(os.path.dirname(png_world_file) if os.path.dirname(png_world_file) else '.', exist_ok=True)
        
        with open(png_world_file, "w") as wf:
            wf.write(f"{x_scale}\n")      # pixel size in x
            wf.write("0.0\n")             # rotation
            wf.write("0.0\n")             # rotation
            wf.write(f"{-y_scale}\n")     # pixel size in -y
            wf.write(f"{bbox['min_lon']}\n")  # x upper left
            wf.write(f"{bbox['max_lat']}\n")  # y upper left
        print(f"World file (PGW) saved as {png_world_file}")
    except Exception as e:
        print(f"Error creating PGW file: {str(e)}")

    # Create a small info file
    if not output_path:
        info_file = os.path.join(BASE_DATA_DIR, f"{short_name}_info.json")
    else:
        info_file = output_path.replace('.png', '_info.json')
    
    info = {
        "dataset": dataset_name,
        "description": config.get("wms_description", ""),
        "bbox": bbox,
        "files": {
            "png": png_file
        },
        "resolution": {
            "width": stitched_width,
            "height": stitched_height
        },
        "scale": {
            "x": x_scale,
            "y": y_scale
        }
    }
    
    with open(info_file, "w") as f:
        json.dump(info, f, indent=2)
    
    print(f"Info file saved as {info_file}")

    # Check if the PNG file exceeds 10MB
    if os.path.exists(png_file):
        file_size_mb = os.path.getsize(png_file) / (1024 * 1024)  # Convert to MB
        if file_size_mb > 10:  # 10MB threshold
            print(f"PNG file size is {file_size_mb:.2f}MB, exceeds 10MB threshold")
            print(f"Generating WebP tiles in background...")
            
            # Start a background thread to generate WebP tiles
            webp_thread = threading.Thread(
                target=generate_webp_tiles_background,
                args=(png_file,),
                daemon=True  # Make it a daemon thread so it doesn't block program exit
            )
            webp_thread.start()
            print(f"WebP tile generation started in background for {png_file}")
        else:
            print(f"PNG file size is {file_size_mb:.2f}MB, does not exceed 10MB threshold")
            print(f"WebP tiles will not be generated")

    return True

def download_and_stitch_tiles(config, output_path=None):
    """
    Download and stitch tiles for a DEM visualization.
    
    Args:
        config (dict): Configuration for the WMS request
        output_path (str, optional): Full path to save the output file
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Set default values if not provided
        if 'max_tile_size' not in config:
            config['max_tile_size'] = 4096  # Maximum allowed by the server
        
        if 'image_format' not in config:
            config['image_format'] = 'image/png'  # Always use PNG for RGB visualization
        
        # Calculate how to divide the area into tiles
        lat_tiles, lon_tiles, tile_lat_size, tile_lon_size = calculate_tiles(config)
        
        # Download all tiles
        tile_info = download_tiles(config, lat_tiles, lon_tiles, tile_lat_size, tile_lon_size)
        
        # Stitch them together with metadata
        success = stitch_tiles_with_metadata(
            tile_info, 
            lat_tiles, 
            lon_tiles, 
            config["max_tile_size"], 
            config,
            output_path=output_path
        )
        
        return success, "Tiles stitched successfully" if success else "Failed to stitch tiles"
    except Exception as e:
        return False, f"Error in download_and_stitch_tiles: {str(e)}"

def process_dataset(config):
    """Process a single dataset from start to finish"""
    print(f"\n{'='*80}")
    print(f"Processing dataset: {config['wms_name']}")
    print(f"Description: {config.get('wms_description', 'No description')}")
    print(f"URL: {config['wms_url']}")
    print(f"{'='*80}\n")
    
    # Calculate how to divide the area into tiles
    lat_tiles, lon_tiles, tile_lat_size, tile_lon_size = calculate_tiles(config)
    
    # Download all tiles
    tile_info = download_tiles(config, lat_tiles, lon_tiles, tile_lat_size, tile_lon_size)
    
    # Stitch them together with metadata
    success = stitch_tiles_with_metadata(tile_info, lat_tiles, lon_tiles, config["max_tile_size"], config)
    
    if success:
        print(f"Successfully processed {config['wms_name']}!")
        return True
    else:
        print(f"Failed to process {config['wms_name']}.")
        return False

def fetch_rgb_dem(bbox, dem_type, resolution=None, output_file=None):
    """
    Fetch an RGB visualization DEM for the specified bounding box and DEM type.
    
    Args:
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy)
        dem_type (str): Type of DEM to fetch (e.g., 'national_1s', 'lidar_5m')
        resolution (int, optional): Resolution in pixels
        output_file (str, optional): Output file name
        
    Returns:
        dict: Result of the operation with success status and file path
    """
    try:
        # Map dem_type to the appropriate WMS URL and configuration
        dem_configs = {
            'national_1s': {
                'url': 'https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_Hydro_Enforced_2024/MapServer/WMSServer',
                'name': 'DEM_SRTM_1Second_Hydro_Enforced_2024',
                'description': 'SRTM 1 Second Hydro Enforced DEM'
            },
            'lidar_5m': {
                'url': 'https://services.ga.gov.au/gis/services/DEM_LiDAR_5m_2025/MapServer/WMSServer',
                'name': 'DEM_LiDAR_5m_2025',
                'description': 'LiDAR 5m DEM'
            }
        }
        
        if dem_type not in dem_configs:
            return {
                'success': False,
                'message': f"Unknown DEM type: {dem_type}",
                'file_path': None
            }
        
        dem_config = dem_configs[dem_type]
        wms_url = dem_config['url']
        dataset_name = dem_config['name']
        
        # Determine output file path
        if output_file:
            file_name = output_file
        else:
            # Generate a file name based on the DEM type and bounding box
            bbox_str = '_'.join([str(coord).replace('.', 'p') for coord in bbox])
            file_name = f"{dem_type}_{bbox_str}.png"
        
        # Save directly to the main data/geo directory instead of a subdirectory
        output_dir = os.path.join(BASE_DATA_DIR)
        os.makedirs(output_dir, exist_ok=True)
        
        file_path = os.path.join(output_dir, file_name)
        
        # Convert bbox from (minx, miny, maxx, maxy) to the format expected by the WMS
        min_lon, min_lat, max_lon, max_lat = bbox
        
        # Configure the WMS request
        request_config = {
            'wms_url': wms_url,
            'wms_name': dataset_name,
            'wms_description': dem_config['description'],
            'bbox': {
                'min_lat': min_lat,
                'min_lon': min_lon,
                'max_lat': max_lat,
                'max_lon': max_lon
            }
        }
        
        # Add resolution if provided
        if resolution:
            request_config['resolution'] = resolution
        
        # Fetch and stitch tiles
        success, message = download_and_stitch_tiles(
            request_config,
            output_path=file_path  # Pass the full output path to the function
        )
        
        if not success:
            return {
                'success': False,
                'message': f"Failed to stitch tiles for {dataset_name}: {message}",
                'file_path': None
            }
        
        return {
            'success': True,
            'message': f"Successfully fetched RGB DEM: {message}",
            'file_path': file_path
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f"Error fetching RGB DEM visualization: {str(e)}",
            'file_path': None
        }

def generate_webp_tiles_background(png_file):
    """Generate WebP tiles for a PNG file in a background thread"""
    try:
        from src.pipeline.dem_generate_webp_tiles import tile_png_to_webp
        
        # Extract the image name from the full path
        image_name = os.path.basename(png_file)
        
        print(f"Starting WebP tile generation for {image_name}...")

        # Generate tiles with quality=100, lossless
        print(f"Job 1: Generating WebP tiles with quality=100, lossless...")
        tile_png_to_webp(
            image_name=image_name,
            quality=100,
            lossless=True
        )
        
        # Generate tiles with quality=75, non-lossless
        print(f"Job 2: Generating WebP tiles with quality=75, non-lossless...")
        tile_png_to_webp(
            image_name=image_name,
            quality=75,
            lossless=False
        )
        
        print(f"WebP tile generation completed for {image_name}")
    except Exception as e:
        print(f"Error generating WebP tiles: {str(e)}")

def main():
    """Main function to run the script with command line arguments"""
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Download and stitch WMS tiles.')
    parser.add_argument('--dataset', choices=['lidar', 'srtm', 'both'], default='both',
                        help='Which dataset to process (default: both)')
    
    args = parser.parse_args()
    
    print("Starting WMS tile download and stitching...")
    configs = setup_config(args.dataset)
    
    results = []
    for config in configs:
        result = process_dataset(config)
        results.append((config['wms_name'], result))
    
    # Print a summary
    print("\n\n" + "="*40)
    print("PROCESSING SUMMARY")
    print("="*40)
    for name, success in results:
        status = "SUCCESS" if success else "FAILED"
        print(f"{name}: {status}")
    print("="*40)

if __name__ == "__main__":
    # Test the fetch_rgb_dem function directly
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Testing fetch_rgb_dem function with small bounding box...")
        
        # Define a small bounding box around Brisbane
        bbox = (152.9, -27.5, 153.0, -27.4)
        
        # Test fetching RGB visualization
        result = fetch_rgb_dem(
            bbox=bbox,
            dem_type='national_1s',
            resolution=500,
            output_file="test_rgb.png"
        )
        
        print(f"Test result: {result}")
        
        if result.get('success', False):
            print(f"Successfully saved file to: {result.get('file_path')}")
        else:
            print(f"Failed to fetch RGB visualization: {result.get('message')}")
    else:
        print("Testing fetch_rgb_dem function with default parameters...")
        
        # Test with SRTM 1 Second DEM (national_1s)
        srtm_result = fetch_rgb_dem(
            bbox=(152.5, -28.4, 153.2, -27.0),
            dem_type='national_1s',
            resolution=1000,
            output_file="national_1s_full.png"
        )
        
        print(f"SRTM result: {srtm_result}")
        
        if srtm_result.get('success', False):
            print(f"Successfully saved SRTM file to: {srtm_result.get('file_path')}")
        
        # Test with LiDAR 5m DEM (lidar_5m)
        lidar_result = fetch_rgb_dem(
            bbox=(139.6726, -36.9499, 139.6851, -36.9412),
            dem_type='lidar_5m',
            resolution=1000,
            output_file="lidar_5m_full.png"
        )
        
        print(f"LiDAR result: {lidar_result}")
        
        if lidar_result.get('success', False):
            print(f"Successfully saved LiDAR file to: {lidar_result.get('file_path')}")