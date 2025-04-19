"""
DEM Metadata Module

This module contains functions for retrieving metadata about Digital Elevation Models (DEMs),
including listing available DEMs and getting their bounds.
"""

import os
import json
import time
import logging
import rasterio
from PIL import Image
from flask import jsonify

# Disable PIL's size limit to avoid decompression bomb warnings
Image.MAX_IMAGE_PIXELS = None

# Initialize the logger
logger = logging.getLogger(__name__)

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEM_DIR = os.path.join(BASE_DIR, 'data', 'geo')

# Define DEM types and their corresponding REST URLs
DEM_TYPES = {
    'lidar_5m': {
        'name': '5m LiDAR DEM',
        'url': 'https://services.ga.gov.au/gis/rest/services/DEM_LiDAR_5m_2025/MapServer',
        'resolution': 5,
        'description': 'High-resolution 5m LiDAR-derived Digital Elevation Model covering Brisbane and surrounds.'
    },
    'national_1s': {
        'name': '1 Second National DEM',
        'url': 'https://services.ga.gov.au/gis/rest/services/DEM_SRTM_1Second_2024/MapServer',
        'resolution': 30,
        'description': 'National 1 Second (~30m) Digital Elevation Model derived from SRTM with hydrological enforcement.'
    }
}


def get_available_dems():
    """Get a list of available DEMs."""
    dems = []
    
    try:
        # Get all files in the DEM directory
        files = os.listdir(DEM_DIR)
        
        # Filter for TIF and PNG files
        dem_files = [f for f in files if f.lower().endswith(('.tif', '.png')) and not f.endswith(('.pgw', '.aux.xml'))]
        
        # Sort files by modification time (newest first)
        dem_files.sort(key=lambda f: os.path.getmtime(os.path.join(DEM_DIR, f)), reverse=True)
        
        for i, filename in enumerate(dem_files):
            try:
                file_path = os.path.join(DEM_DIR, filename)
                
                # Skip if not a file
                if not os.path.isfile(file_path):
                    continue
                
                # Get file stats
                file_stats = os.stat(file_path)
                file_size_bytes = file_stats.st_size
                file_size_mb = file_size_bytes / (1024 * 1024)
                
                # Get file extension and determine data type
                file_ext = os.path.splitext(filename)[1].lower()
                data_type = "Elevation Data" if file_ext == '.tif' else "Visualization Image"
                
                # Try to extract DEM type from filename
                dem_type = None
                for dt in DEM_TYPES:
                    if filename.startswith(dt):
                        dem_type = dt
                        break
                
                if not dem_type:
                    # Default to lidar_5m if can't determine
                    dem_type = "lidar_5m"
                
                # Get DEM resolution from config
                resolution = DEM_TYPES.get(dem_type, {}).get('resolution', 30)
                
                # Try to extract bounding box from filename
                bbox = None
                parts = filename.split('_')
                if len(parts) >= 5:
                    try:
                        # Format: dem_type_minx_miny_maxx_maxy.ext
                        # or: dem_type_minx_miny_maxx_maxy_counter.ext
                        minx = float(parts[1].replace('p', '.'))
                        miny = float(parts[2].replace('p', '.'))
                        
                        # Check if the fourth part has an extension (in case of no counter)
                        maxx_part = parts[3]
                        if '.' in maxx_part:
                            maxx_part = maxx_part.split('.')[0]
                        maxx = float(maxx_part.replace('p', '.'))
                        
                        # Check if the fifth part has an extension
                        maxy_part = parts[4]
                        if '.' in maxy_part:
                            maxy_part = maxy_part.split('.')[0]
                        maxy = float(maxy_part.replace('p', '.'))
                        
                        bbox = [minx, miny, maxx, maxy]
                    except (ValueError, IndexError):
                        bbox = None
                
                # If couldn't extract bbox from filename, try to get from metadata
                if not bbox:
                    if file_ext == '.tif':
                        try:
                            # Try to get bounds from the GeoTIFF
                            with rasterio.open(file_path) as src:
                                bounds = src.bounds
                                bbox = [bounds.left, bounds.bottom, bounds.right, bounds.top]
                        except Exception as e:
                            logger.warning(f"Could not extract bounds from GeoTIFF: {e}")
                            bbox = [152.0, -28.0, 153.5, -27.0]  # Default to Brisbane area
                    else:
                        # For PNG files, check if there's a world file (.pgw)
                        world_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}.pgw")
                        if os.path.exists(world_file):
                            try:
                                with open(world_file, 'r') as f:
                                    lines = f.readlines()
                                    if len(lines) >= 6:
                                        pixel_width = float(lines[0])
                                        pixel_height = float(lines[3])
                                        top_left_x = float(lines[4])
                                        top_left_y = float(lines[5])
                                        
                                        # Get image dimensions
                                        img = Image.open(file_path)
                                        width, height = img.size
                                        
                                        # Calculate bounds
                                        minx = top_left_x
                                        maxx = top_left_x + (width * pixel_width)
                                        miny = top_left_y + (height * pixel_height)
                                        maxy = top_left_y
                                        
                                        bbox = [minx, miny, maxx, maxy]
                            except Exception as e:
                                logger.warning(f"Could not extract bounds from world file: {e}")
                                bbox = [152.0, -28.0, 153.5, -27.0]  # Default to Brisbane area
                        else:
                            bbox = [152.0, -28.0, 153.5, -27.0]  # Default to Brisbane area
                
                # Format the bounding box for display
                coverage = f"{bbox[0]:.4f}, {bbox[1]:.4f} to {bbox[2]:.4f}, {bbox[3]:.4f}"
                
                # Default display name from DEM type
                display_name = DEM_TYPES.get(dem_type, {}).get('name', 'Unknown DEM')
                
                # First check metadata directory for display name (used by rename function)
                metadata_dir = os.path.join(DEM_DIR, 'metadata')
                metadata_file = os.path.join(metadata_dir, f"{filename}.json")
                
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            if 'display_name' in metadata:
                                display_name = metadata['display_name']
                    except Exception as e:
                        logger.warning(f"Could not read metadata file for {filename}: {e}")
                
                # If no display name found in metadata, check the status file (legacy method)
                if display_name == DEM_TYPES.get(dem_type, {}).get('name', 'Unknown DEM'):
                    status_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json")
                    if os.path.exists(status_file):
                        try:
                            with open(status_file, 'r') as f:
                                status_data = json.load(f)
                                if 'display_name' in status_data:
                                    display_name = status_data['display_name']
                        except Exception as e:
                            logger.warning(f"Could not read status file for {filename}: {e}")
                
                # Create DEM object
                dem = {
                    'id': str(i + 1),
                    'name': filename,
                    'display_name': display_name,
                    'type': dem_type,
                    'resolution': resolution,
                    'coverage': coverage,
                    'bbox': bbox,
                    'data_type': data_type,
                    'size': f"{file_size_mb:.2f} MB",
                    'date': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stats.st_mtime))
                }
                
                dems.append(dem)
            except Exception as e:
                logger.exception(f"Error processing DEM file {filename}: {e}")
    except Exception as e:
        logger.exception(f"Error listing DEMs: {e}")
    
    return dems


def get_dem_bounds(dem_id):
    """
    Get the bounds for a specific DEM file.
    
    Args:
        dem_id (str): The ID of the DEM file
        
    Returns:
        dict: JSON response with bounds information
    """
    logger.info(f"Getting bounds for DEM: {dem_id}")
    
    # Check if the DEM ID contains a file extension
    if '.' in dem_id:
        dem_id = os.path.splitext(dem_id)[0]
    
    # Try to find the DEM file with either .tif or .png extension
    tif_file = os.path.join(DEM_DIR, f"{dem_id}.tif")
    png_file = os.path.join(DEM_DIR, f"{dem_id}.png")
    
    dem_file = None
    if os.path.exists(tif_file):
        dem_file = tif_file
    elif os.path.exists(png_file):
        dem_file = png_file
    
    if not dem_file:
        logger.error(f"DEM file not found for ID: {dem_id}")
        return jsonify({'success': False, 'message': 'DEM file not found'})
    
    # Check for metadata file
    metadata_dir = os.path.join(DEM_DIR, 'metadata')
    metadata_file = os.path.join(metadata_dir, f"{dem_id}.json")
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                
            if 'bbox' in metadata:
                bbox = metadata['bbox']
                bounds = {
                    'min_lat': bbox[1],
                    'min_lon': bbox[0],
                    'max_lat': bbox[3],
                    'max_lon': bbox[2]
                }
                return jsonify({'success': True, 'bounds': bounds})
        except Exception as e:
            logger.error(f"Error reading metadata file: {e}")
    
    # If we have a TIF file, try to get bounds from it
    if dem_file.lower().endswith('.tif'):
        try:
            # Try to get bounds from the GeoTIFF
            with rasterio.open(dem_file) as src:
                bounds = src.bounds
                return jsonify({
                    'success': True,
                    'bounds': {
                        'min_lat': bounds.bottom,
                        'min_lon': bounds.left,
                        'max_lat': bounds.top,
                        'max_lon': bounds.right
                    }
                })
        except Exception as e:
            logger.error(f"Error reading GeoTIFF bounds: {e}")
    
    # If we have a PNG file, try to get bounds from the associated PGW file
    if dem_file.lower().endswith('.png'):
        try:
            # Check for a world file (.pgw)
            world_file = os.path.join(DEM_DIR, f"{dem_id}.pgw")
            if os.path.exists(world_file):
                with open(world_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) >= 6:
                        pixel_width = float(lines[0])
                        pixel_height = float(lines[3])
                        top_left_x = float(lines[4])
                        top_left_y = float(lines[5])
                        
                        # Get image dimensions
                        img = Image.open(dem_file)
                        width, height = img.size
                        
                        # Calculate bounds
                        minx = top_left_x
                        maxx = top_left_x + (width * pixel_width)
                        miny = top_left_y + (height * pixel_height)
                        maxy = top_left_y
                        
                        return jsonify({
                            'success': True,
                            'bounds': {
                                'min_lat': miny,
                                'min_lon': minx,
                                'max_lat': maxy,
                                'max_lon': maxx
                            }
                        })
        except Exception as e:
            logger.error(f"Error reading PNG world file bounds: {e}")
    
    # Fallback to Brisbane area if all else fails
    return jsonify({
        'success': True,
        'bounds': {
            'min_lat': -27.7,
            'min_lon': 152.5,
            'max_lat': -27.2,
            'max_lon': 153.2
        }
    })
