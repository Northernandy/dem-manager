"""
DEM Fetcher Module

This module coordinates DEM fetching operations between the WMS RGB handler and WCS GeoTIFF handler.
It provides a unified interface for fetching digital elevation models in different formats.
"""

import os
import logging
import sys
import inspect

# Add the project root to the Python path to ensure imports work correctly
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import handlers
from src.pipeline.wms_rgb_handler import fetch_rgb_dem
from src.pipeline.wcs_geotiff_handler import fetch_geotiff_dem

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for file formats
RAW_FORMAT = 'tif'  # Raw elevation data is always stored as TIF
RGB_FORMAT = 'png'  # RGB visualization is always stored as PNG

class DEMFetcher:
    """
    Coordinates DEM fetching operations between different handlers.
    """
    
    def __init__(self, base_dir='data/geo'):
        """
        Initialize the DEM fetcher.
        
        Args:
            base_dir (str): Base directory for storing DEM files
        """
        self.base_dir = base_dir
        self.raw_dir = os.path.join(base_dir, 'raw')
        self.rgb_dir = os.path.join(base_dir, 'rgb')
        self.rgb_tiles_dir = os.path.join(base_dir, 'rgb', 'tiles')
        
        # Create directories if they don't exist
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.rgb_dir, exist_ok=True)
        os.makedirs(self.rgb_tiles_dir, exist_ok=True)
        
        logger.info(f"DEM Fetcher initialized with base directory: {base_dir}")
    
    def fetch_dem(self, bbox, dem_type, data_type, resolution=None, output_file=None):
        """
        Fetch a DEM based on the specified parameters.
        
        Args:
            bbox (tuple): Bounding box (minx, miny, maxx, maxy)
            dem_type (str): Type of DEM to fetch (e.g., 'national_1s', 'lidar_5m')
            data_type (str): Type of data to fetch ('raw' or 'rgb')
            resolution (int, optional): Resolution in meters
            output_file (str, optional): Output file name
            
        Returns:
            dict: Result of the operation
        """
        logger.info(f"Fetching DEM: {dem_type}, {data_type}, bbox={bbox}")
        
        # Generate a default output file name if not provided
        if not output_file:
            bbox_str = '_'.join([str(coord).replace('.', 'p') for coord in bbox])
            file_ext = f".{RAW_FORMAT}" if data_type == 'raw' else f".{RGB_FORMAT}"
            output_file = f"{dem_type}_{bbox_str}{file_ext}"
        
        # Ensure the file extension matches the data type
        base, ext = os.path.splitext(output_file)
        if data_type == 'raw' and ext.lower() != f".{RAW_FORMAT}":
            output_file = f"{base}.{RAW_FORMAT}"
        elif data_type == 'rgb' and ext.lower() != f".{RGB_FORMAT}":
            output_file = f"{base}.{RGB_FORMAT}"
        
        # Determine which handler to use based on data type
        if data_type == 'raw':
            result = fetch_geotiff_dem(bbox, dem_type, resolution, output_file)
        elif data_type == 'rgb':
            result = fetch_rgb_dem(bbox, dem_type, resolution, output_file)
        else:
            logger.error(f"Invalid data type: {data_type}")
            return {
                'success': False,
                'message': f"Invalid data type: {data_type}. Must be 'raw' or 'rgb'."
            }
        
        return result


def fetch_dem(bbox, dem_type, data_type, resolution=None, output_file=None):
    """
    Convenience function to fetch a DEM without creating a DEMFetcher instance.
    
    Args:
        bbox (tuple): Bounding box (minx, miny, maxx, maxy)
        dem_type (str): Type of DEM to fetch (e.g., 'national_1s', 'lidar_5m')
        data_type (str): Type of data to fetch ('raw' or 'rgb')
        resolution (int, optional): Resolution in meters
        output_file (str, optional): Output file name
        
    Returns:
        dict: Result of the operation
    """
    fetcher = DEMFetcher()
    return fetcher.fetch_dem(bbox, dem_type, data_type, resolution, output_file)