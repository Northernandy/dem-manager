"""
Brisbane DEM Data Fetcher

This module handles downloading high-resolution Digital Elevation Model (DEM) data
from Geoscience Australia's REST service. It can split large areas into manageable chunks
and merge them back together.
"""

import os
import sys
import logging
import requests
from requests.exceptions import RequestException
import time
import numpy as np
import rasterio
from rasterio.transform import from_origin
from affine import Affine
from rasterio.crs import CRS
from rasterio.merge import merge

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DEMFetcher:
    """Class to fetch and process Digital Elevation Model (DEM) data"""
    
    def __init__(self, 
                 bbox=(152.0, -28.0, 153.5, -27.0),  # Wider Brisbane catchment area
                 target_res_meters=5,
                 output_dir=None,
                 output_file=None):
        """
        Initialize the DEM fetcher with configuration parameters.
        
        Args:
            bbox (tuple): Bounding box (minx, miny, maxx, maxy) in WGS84
            target_res_meters (float): Target resolution in meters
            output_dir (str): Directory to save output files
            output_file (str): Name of the output GeoTIFF file
        """
        # Bounding box
        self.bbox = bbox
        
        # Calculate dimensions in degrees
        self.width_deg = bbox[2] - bbox[0]
        self.height_deg = bbox[3] - bbox[1]
        
        # Target resolution
        self.target_res_meters = target_res_meters
        
        # Convert to approximate degrees at this latitude
        # At Brisbane's latitude, 1 degree is roughly 111km, so 5m is about 0.000045 degrees
        self.approx_res_deg = target_res_meters / 111000
        
        # Calculate required dimensions to achieve target resolution
        self.required_width = int(self.width_deg / self.approx_res_deg)
        self.required_height = int(self.height_deg / self.approx_res_deg)
        
        # Maximum dimensions to request at once
        self.max_request_size = 4000
        
        # Determine if we need to split the request
        self.split_requests = max(1, max(self.required_width, self.required_height) // self.max_request_size + 1)
        
        # Set chunk dimensions
        if self.split_requests > 1:
            logger.info(f"Area requires splitting into {self.split_requests}x{self.split_requests} requests for full resolution")
            # Adjust to more reasonable chunk size
            self.chunk_width = min(self.max_request_size, self.required_width // self.split_requests + 1)
            self.chunk_height = min(self.max_request_size, self.required_height // self.split_requests + 1)
            logger.info(f"Using chunk size of {self.chunk_width}x{self.chunk_height} pixels")
        else:
            # Request at maximum feasible resolution
            self.chunk_width = min(self.required_width, self.max_request_size)
            self.chunk_height = min(self.required_height, self.max_request_size)
            logger.info(f"Requesting at {self.chunk_width}x{self.chunk_height} pixels")
        
        # Set output paths
        self.output_dir = output_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'geo')
        self.temp_dir = os.path.join(self.output_dir, "temp_dem_chunks")
        self.output_file = output_file or os.path.join(self.output_dir, "brisbane_dem_highres.tif")
        
        # Geoscience Australia REST service URL
        self.rest_url = "https://services.ga.gov.au/gis/rest/services/DEM_LiDAR_5m_2025/MapServer"
        
        # Maximum retries
        self.max_retries = 3
        
        # Export parameters
        self.export_params = {
            'transparent': 'true',
            'format': 'tiff',
            'f': 'image'
        }

    def create_temp_dir(self):
        """Create temporary directory for DEM chunks"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.info(f"Created output directory: {self.output_dir}")
            
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
            logger.info(f"Created temporary directory: {self.temp_dir}")

    def get_chunk_bbox(self, row, col, rows, cols):
        """
        Calculate the bbox for a specific chunk.
        
        Args:
            row (int): Row index
            col (int): Column index
            rows (int): Total rows
            cols (int): Total columns
            
        Returns:
            tuple: Bounding box (minx, miny, maxx, maxy)
        """
        # Calculate the width and height of each chunk in degrees
        chunk_width_deg = self.width_deg / cols
        chunk_height_deg = self.height_deg / rows
        
        # Calculate the bbox for this chunk
        minx = self.bbox[0] + col * chunk_width_deg
        miny = self.bbox[1] + row * chunk_height_deg
        maxx = self.bbox[0] + (col + 1) * chunk_width_deg
        maxy = self.bbox[1] + (row + 1) * chunk_height_deg
        
        return (minx, miny, maxx, maxy)

    def export_image_chunk(self, url, bbox, width, height, chunk_id):
        """
        Export an image chunk from the REST service.
        
        Args:
            url (str): REST service URL
            bbox (tuple): Bounding box (minx, miny, maxx, maxy)
            width (int): Width in pixels
            height (int): Height in pixels
            chunk_id (str): Identifier for this chunk
            
        Returns:
            str: Path to the saved chunk file, or None if failed
        """
        export_url = f"{url}/export"
        
        params = {
            'bbox': ','.join(map(str, bbox)),
            'bboxSR': 4326,  # WGS84
            'imageSR': 4326,
            'size': f"{width},{height}",
            **self.export_params
        }
        
        logger.info(f"Exporting chunk {chunk_id} with bbox {bbox}")
        logger.info(f"Request size: {width}x{height} pixels")
        
        for attempt in range(self.max_retries):
            try:
                response = requests.get(export_url, params=params, timeout=300, stream=True)
                
                if response.status_code == 200:
                    output_file = os.path.join(self.temp_dir, f"chunk_{chunk_id}.tif")
                    
                    # Save the response to a file
                    with open(output_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    logger.info(f"Saved chunk {chunk_id} to {output_file}")
                    return output_file
                else:
                    logger.warning(f"Attempt {attempt+1}/{self.max_retries} failed: {response.status_code}")
                    if response.text:
                        logger.warning(f"Response: {response.text[:500]}")
                    
                    # Wait before retrying
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                logger.error(f"Attempt {attempt+1}/{self.max_retries} error: {str(e)}")
                
                # Wait before retrying
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"Failed to export chunk {chunk_id} after {self.max_retries} attempts")
        return None

    def add_georeference_to_chunk(self, file_path, bbox):
        """
        Add georeference information to a TIFF file.
        
        Args:
            file_path (str): Path to the TIFF file
            bbox (tuple): Bounding box (minx, miny, maxx, maxy)
            
        Returns:
            str: Path to the georeferenced file, or None if failed
        """
        try:
            # Open the file
            with rasterio.open(file_path) as src:
                data = src.read()
                
                # Create a new GeoTIFF with the correct transform
                minx, miny, maxx, maxy = bbox
                width = src.width
                height = src.height
                
                # Calculate the resolution
                res_x = (maxx - minx) / width
                res_y = (maxy - miny) / height
                
                # Create transform (top-left corner and pixel sizes)
                transform = from_origin(minx, maxy, res_x, res_y)
                
                # Create output file with georeference
                georef_file = file_path.replace('.tif', '_georef.tif')
                
                with rasterio.open(
                    georef_file,
                    'w',
                    driver='GTiff',
                    height=height,
                    width=width,
                    count=src.count,
                    dtype=src.dtypes[0],
                    crs='EPSG:4326',
                    transform=transform,
                    nodata=src.nodata
                ) as dst:
                    dst.write(data)
                
                logger.info(f"Added georeference to {file_path}")
                return georef_file
        except Exception as e:
            logger.error(f"Error adding georeference: {str(e)}")
            return None

    def merge_geotiff_chunks(self, chunk_files, output_file):
        """
        Merge multiple GeoTIFF chunks into a single file.
        
        Args:
            chunk_files (list): List of file paths to merge
            output_file (str): Output file path
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Merging {len(chunk_files)} chunks into {output_file}")
            
            # Open all chunk files
            src_files = [rasterio.open(f) for f in chunk_files]
            
            # Merge them
            mosaic, out_trans = merge(src_files)
            
            # Get metadata from the first file
            src = src_files[0]
            
            # Create output file
            with rasterio.open(
                output_file,
                'w',
                driver='GTiff',
                height=mosaic.shape[1],
                width=mosaic.shape[2],
                count=src.count,
                dtype=src.dtypes[0],
                crs=src.crs,
                transform=out_trans,
                nodata=src.nodata
            ) as dst:
                dst.write(mosaic)
            
            # Close input files
            for src in src_files:
                src.close()
            
            logger.info(f"Successfully merged chunks into {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error merging GeoTIFF chunks: {str(e)}")
            return False

    def verify_geotiff(self, file_path):
        """
        Verify a GeoTIFF file.
        
        Args:
            file_path (str): Path to the GeoTIFF file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with rasterio.open(file_path) as src:
                logger.info(f"Verified GeoTIFF: {file_path}")
                logger.info(f" - CRS: {src.crs}")
                logger.info(f" - Resolution: {src.res} degrees")
                
                # Convert resolution to approximate meters
                res_meters_x = src.res[0] * 111000  # Roughly 111km per degree at the equator
                res_meters_y = src.res[1] * 111000
                logger.info(f" - Approximate resolution: {res_meters_x:.2f}m x {res_meters_y:.2f}m")
                
                logger.info(f" - Bounds: {src.bounds}")
                logger.info(f" - Size: {src.width} x {src.height} pixels")
                return True
        except Exception as e:
            logger.error(f"Error verifying GeoTIFF: {str(e)}")
            return False

    def download_high_res_dem(self):
        """
        Download high-resolution DEM by splitting into chunks if necessary.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.create_temp_dir()
        
        # Check if the service is available
        try:
            check_url = f"{self.rest_url}/info?f=json"
            response = requests.get(check_url, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Service not available: {response.status_code}")
                return False
            
            logger.info("Service is available")
        except Exception as e:
            logger.error(f"Error checking service: {str(e)}")
            return False
        
        # If the request is small enough, just do one request
        if self.split_requests == 1:
            logger.info("Single request mode - exporting full area")
            chunk_file = self.export_image_chunk(self.rest_url, self.bbox, self.chunk_width, self.chunk_height, "full")
            
            if chunk_file:
                # Add georeference
                georef_file = self.add_georeference_to_chunk(chunk_file, self.bbox)
                
                if georef_file:
                    # Copy to output file
                    if os.path.exists(georef_file):
                        import shutil
                        shutil.copy2(georef_file, self.output_file)
                        logger.info(f"Copied georeferenced file to {self.output_file}")
                        
                        # Verify the result
                        if self.verify_geotiff(self.output_file):
                            return True
        else:
            # Split into chunks
            logger.info(f"Splitting request into {self.split_requests}x{self.split_requests} chunks")
            
            chunk_files = []
            georef_chunk_files = []
            
            for row in range(self.split_requests):
                for col in range(self.split_requests):
                    chunk_id = f"{row}_{col}"
                    chunk_bbox = self.get_chunk_bbox(row, col, self.split_requests, self.split_requests)
                    
                    # Export this chunk
                    chunk_file = self.export_image_chunk(self.rest_url, chunk_bbox, self.chunk_width, self.chunk_height, chunk_id)
                    
                    if chunk_file:
                        chunk_files.append(chunk_file)
                        
                        # Add georeference
                        georef_file = self.add_georeference_to_chunk(chunk_file, chunk_bbox)
                        
                        if georef_file:
                            georef_chunk_files.append(georef_file)
            
            # Merge all georeferenced chunks
            if len(georef_chunk_files) > 0:
                if self.merge_geotiff_chunks(georef_chunk_files, self.output_file):
                    # Verify the result
                    if self.verify_geotiff(self.output_file):
                        return True
        
        logger.error("Failed to download high-resolution DEM")
        return False

def fetch_dem(bbox=None, target_res_meters=5, output_dir=None, output_file=None):
    """
    Convenience function to fetch DEM data.
    
    Args:
        bbox (tuple): Bounding box (minx, miny, maxx, maxy) in WGS84
        target_res_meters (float): Target resolution in meters
        output_dir (str): Directory to save output files
        output_file (str): Name of the output GeoTIFF file
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Use default bbox if not provided
    if bbox is None:
        bbox = (152.0, -28.0, 153.5, -27.0)  # Wider Brisbane catchment area
    
    # Create fetcher
    fetcher = DEMFetcher(
        bbox=bbox,
        target_res_meters=target_res_meters,
        output_dir=output_dir,
        output_file=output_file
    )
    
    # Log parameters
    logger.info(f"Starting high-resolution DEM download (target resolution: {target_res_meters}m)")
    logger.info(f"Calculated required dimensions: {fetcher.required_width}x{fetcher.required_height} pixels")
    
    # Download DEM
    success = fetcher.download_high_res_dem()
    
    if success:
        logger.info("High-resolution DEM download completed successfully")
    else:
        logger.error("High-resolution DEM download failed")
    
    return success

if __name__ == "__main__":
    # If run as a script, fetch DEM with default parameters
    success = fetch_dem()
    
    if not success:
        sys.exit(1)
