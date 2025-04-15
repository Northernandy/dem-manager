"""
Brisbane DEM Data Fetcher - Raw Elevation Data Version

This module handles downloading high-resolution Digital Elevation Model (DEM) data
from Geoscience Australia's REST service as raw elevation values. It can split large areas 
into manageable chunks and merge them back together.
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
import json

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DEMFetcher:
    """Class to fetch and process Digital Elevation Model (DEM) data as raw elevation values"""
    
    def __init__(self, 
                 bbox=(152.0, -28.0, 153.5, -27.0),  # Wider Brisbane catchment area
                 target_res_meters=5,
                 output_dir=None,
                 output_file=None,
                 rest_url=None,
                 status_file=None):
        """
        Initialize the DEM fetcher with configuration parameters.
        
        Args:
            bbox (tuple): Bounding box (minx, miny, maxx, maxy) in WGS84
            target_res_meters (float): Target resolution in meters
            output_dir (str): Directory to save output files
            output_file (str): Name of the output GeoTIFF file
            rest_url (str): URL of the REST service to use (overrides default)
            status_file (str): Path to a file to write status updates
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
        
        # Status file for progress updates
        self.status_file = status_file
        
        # Geoscience Australia REST service URL
        if rest_url:
            self.rest_url = rest_url
        else:
            # Default to 5m LiDAR DEM
            self.rest_url = 'https://services.ga.gov.au/gis/rest/services/DEM_LiDAR_5m_2025/MapServer'
        
        # Set export parameters - MODIFIED FOR RAW ELEVATION DATA
        self.export_params = {
            'f': 'image',  # Request image format
            'format': 'tiff',  # Specify TIFF format
            'transparent': 'false',
            'interpolation': 'RSP_BilinearInterpolation',
            'noDataInterpretation': 'esriNoDataMatchAny',
            'time': '',
            'layerDefs': '',
            'layers': '',
            'layerOption': 'visible'
            # Removed renderingRule to get raw data without rendering
        }
        
        # Maximum number of retries for failed requests
        self.max_retries = 3
        
        # Create temp directory if it doesn't exist
        self.create_temp_dir()
    
    def create_temp_dir(self):
        """Create temporary directory for DEM chunks"""
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
            logger.info(f"Created temporary directory: {self.temp_dir}")
        else:
            logger.info(f"Using existing temporary directory: {self.temp_dir}")
    
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
        minx, miny, maxx, maxy = self.bbox
        
        # Calculate chunk width and height in degrees
        chunk_width_deg = self.width_deg / cols
        chunk_height_deg = self.height_deg / rows
        
        # Calculate chunk bbox
        chunk_minx = minx + col * chunk_width_deg
        chunk_miny = miny + row * chunk_height_deg
        chunk_maxx = chunk_minx + chunk_width_deg
        chunk_maxy = chunk_miny + chunk_height_deg
        
        return (chunk_minx, chunk_miny, chunk_maxx, chunk_maxy)
    
    def export_image_chunk(self, url, bbox, width, height, chunk_id):
        """
        Export an image chunk from the REST service as raw elevation data.
        
        Args:
            url (str): REST service URL
            bbox (tuple): Bounding box (minx, miny, maxx, maxy)
            width (int): Width in pixels
            height (int): Height in pixels
            chunk_id (str): Identifier for this chunk
            
        Returns:
            str: Path to the saved chunk file, or None if failed
        """
        # MODIFIED: Use exportImage endpoint instead of export
        export_url = f"{url}/exportImage"
        
        params = {
            'bbox': ','.join(map(str, bbox)),
            'bboxSR': 4326,  # WGS84
            'imageSR': 4326,
            'size': f"{width},{height}",
            **self.export_params
        }
        
        logger.info(f"Exporting raw elevation chunk {chunk_id} with bbox {bbox}")
        logger.info(f"Request size: {width}x{height} pixels")
        logger.info(f"Request URL: {export_url}")
        logger.info(f"Request params: {params}")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempt {attempt+1}/{self.max_retries} to export chunk {chunk_id}")
                response = requests.get(export_url, params=params, timeout=300, stream=True)
                
                # Log response status and headers for debugging
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    # Check content type to ensure we got a TIFF
                    content_type = response.headers.get('Content-Type', '')
                    if 'tiff' not in content_type.lower() and 'image' not in content_type.lower():
                        logger.warning(f"Unexpected content type: {content_type}")
                        
                        # Log a small sample of the response content for debugging
                        content_sample = response.content[:1000]
                        logger.warning(f"Response content sample: {content_sample}")
                        
                        # If it looks like HTML or JSON, it's probably an error message
                        if b'<html' in content_sample or b'{' in content_sample:
                            logger.error(f"Response appears to be HTML or JSON, not a TIFF: {content_sample}")
                            if attempt < self.max_retries - 1:
                                logger.info(f"Retrying in {2 ** attempt} seconds...")
                                time.sleep(2 ** attempt)
                                continue
                            return None
                    
                    output_file = os.path.join(self.temp_dir, f"chunk_{chunk_id}.tif")
                    
                    # Save the response to a file
                    with open(output_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Check if the file is valid
                    file_size = os.path.getsize(output_file)
                    if file_size < 1000:  # If file is too small, it's probably an error
                        logger.warning(f"Chunk file is suspiciously small: {file_size} bytes")
                        with open(output_file, 'rb') as f:
                            content = f.read(1000)
                        logger.warning(f"File content preview: {content[:100]}")
                        
                        # If it's clearly an error message, not a TIFF
                        if b'error' in content.lower() or b'exception' in content.lower():
                            logger.error(f"Response contains error message: {content}")
                            if attempt < self.max_retries - 1:
                                logger.info(f"Retrying in {2 ** attempt} seconds...")
                                time.sleep(2 ** attempt)
                                continue
                            return None
                    
                    logger.info(f"Saved chunk {chunk_id} to {output_file} ({file_size} bytes)")
                    return output_file
                else:
                    logger.warning(f"Attempt {attempt+1}/{self.max_retries} failed: {response.status_code}")
                    if response.text:
                        logger.warning(f"Response: {response.text[:500]}")
                    
                    # Wait before retrying
                    if attempt < self.max_retries - 1:
                        retry_delay = 2 ** attempt
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)  # Exponential backoff
            except Exception as e:
                logger.error(f"Attempt {attempt+1}/{self.max_retries} error: {str(e)}")
                
                # Wait before retrying
                if attempt < self.max_retries - 1:
                    retry_delay = 2 ** attempt
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)  # Exponential backoff
        
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
                
                # Get the nodata value from the source if available
                nodata_value = src.nodata
                if nodata_value is None:
                    # If no nodata value is specified, use a common value for DEMs
                    nodata_value = -9999
                
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
                    nodata=nodata_value
                ) as dst:
                    dst.write(data)
                
                logger.info(f"Added georeference to {file_path} with nodata value: {nodata_value}")
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
            # Open all the chunks
            src_files_to_mosaic = []
            for file in chunk_files:
                try:
                    src = rasterio.open(file)
                    src_files_to_mosaic.append(src)
                except Exception as e:
                    logger.error(f"Error opening chunk file {file}: {str(e)}")
                    # Continue with other files
            
            if not src_files_to_mosaic:
                logger.error("No valid chunk files to merge")
                return False
            
            # Merge the chunks
            mosaic, out_trans = merge(src_files_to_mosaic)
            
            # Get metadata from the first file
            out_meta = src_files_to_mosaic[0].meta.copy()
            
            # Update metadata for the merged file
            out_meta.update({
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": out_trans,
                "crs": src_files_to_mosaic[0].crs
            })
            
            # Write the merged file
            with rasterio.open(output_file, "w", **out_meta) as dest:
                dest.write(mosaic)
            
            # Close all source files
            for src in src_files_to_mosaic:
                src.close()
            
            logger.info(f"Successfully merged {len(chunk_files)} chunks to {output_file}")
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
                # Check if we can read the data
                data = src.read(1, window=((0, min(10, src.height)), (0, min(10, src.width))))
                
                # Check if the data is valid
                if data is None or data.size == 0:
                    logger.error(f"Invalid data in GeoTIFF file: {file_path}")
                    return False
                
                # Log some information about the file
                logger.info(f"GeoTIFF verification successful: {file_path}")
                logger.info(f"  Size: {src.width}x{src.height} pixels")
                logger.info(f"  CRS: {src.crs}")
                logger.info(f"  Bounds: {src.bounds}")
                logger.info(f"  NoData value: {src.nodata}")
                
                # Check for all NaN or NoData values
                if np.all(data == src.nodata) or (np.isnan(data).all() if src.nodata is None else False):
                    logger.warning(f"GeoTIFF contains all NoData values in sample: {file_path}")
                
                return True
        except Exception as e:
            logger.error(f"Error verifying GeoTIFF file {file_path}: {str(e)}")
            return False
    
    def update_status(self, status, progress, message):
        """
        Update the status file with current progress.
        
        Args:
            status (str): Current status (starting, downloading, processing, complete, failed)
            progress (float): Progress percentage (0-100)
            message (str): Status message
        """
        if not self.status_file:
            return
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
            
            # Write status to file
            with open(self.status_file, 'w') as f:
                json.dump({
                    'status': status,
                    'progress': progress,
                    'message': message,
                    'timestamp': time.time()
                }, f)
            
            logger.debug(f"Updated status: {status}, {progress}%, {message}")
        except Exception as e:
            logger.error(f"Error updating status file: {str(e)}")
    
    def download_high_res_dem(self):
        """
        Download high-resolution DEM by splitting into chunks if necessary.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if output file already exists
        if os.path.exists(self.output_file):
            logger.info(f"Output file already exists: {self.output_file}")
            return True
        
        # Calculate number of chunks
        if self.split_requests > 1:
            rows = cols = self.split_requests
        else:
            rows = cols = 1
        
        total_chunks = rows * cols
        logger.info(f"Splitting area into {rows}x{cols} = {total_chunks} chunks")
        
        # Update status
        self.update_status('downloading', 0, f'Starting download of {total_chunks} chunks...')
        
        # Download each chunk
        chunk_files = []
        georef_chunk_files = []
        current_chunk = 0
        total_downloaded_bytes = 0
        
        for row in range(rows):
            for col in range(cols):
                current_chunk += 1
                chunk_id = f"{row}_{col}"
                
                # Calculate bbox for this chunk
                chunk_bbox = self.get_chunk_bbox(row, col, rows, cols)
                
                # Update status
                progress = (current_chunk - 1) / total_chunks * 50  # First 50% is downloading
                self.update_status('downloading', progress, f'Downloading chunk {current_chunk}/{total_chunks}...')
                
                # Export image chunk
                chunk_file = self.export_image_chunk(
                    self.rest_url, 
                    chunk_bbox, 
                    self.chunk_width, 
                    self.chunk_height, 
                    chunk_id
                )
                
                if chunk_file:
                    # Track downloaded data
                    chunk_size_bytes = os.path.getsize(chunk_file)
                    total_downloaded_bytes += chunk_size_bytes
                    chunk_size_mb = chunk_size_bytes / (1024 * 1024)
                    logger.info(f'Chunk {current_chunk}/{total_chunks} downloaded: {chunk_size_mb:.2f} MB')
                    
                    chunk_files.append(chunk_file)
                    
                    # Add georeference information
                    progress = 50 + (current_chunk - 1) / total_chunks * 25  # Next 25% is georeferencing
                    self.update_status('processing', progress, f'Georeferencing chunk {current_chunk}/{total_chunks}...')
                    
                    georef_file = self.add_georeference_to_chunk(chunk_file, chunk_bbox)
                    
                    if georef_file:
                        # Log georeferenced chunk size
                        georef_size_bytes = os.path.getsize(georef_file)
                        georef_size_mb = georef_size_bytes / (1024 * 1024)
                        logger.info(f'Chunk {current_chunk}/{total_chunks} georeferenced: {georef_size_mb:.2f} MB')
                        
                        georef_chunk_files.append(georef_file)
        
            # Log total downloaded data
            total_downloaded_mb = total_downloaded_bytes / (1024 * 1024)
            logger.info(f"Total downloaded data: {total_downloaded_mb:.2f} MB ({total_downloaded_bytes} bytes) across {len(chunk_files)} chunks")
            
            # Merge all georeferenced chunks
            if len(georef_chunk_files) > 0:
                merge_msg = f'Merging {len(georef_chunk_files)} chunks (total {total_downloaded_mb:.2f} MB)...'
                logger.info(merge_msg)
                self.update_status('processing', 75, merge_msg)
                
                if self.merge_geotiff_chunks(georef_chunk_files, self.output_file):
                    # Get final file size
                    final_size_bytes = os.path.getsize(self.output_file)
                    final_size_mb = final_size_bytes / (1024 * 1024)
                    logger.info(f"Merged file size: {final_size_mb:.2f} MB ({final_size_bytes} bytes)")
                    
                    # Verify the result
                    verify_msg = f'Verifying merged DEM file ({final_size_mb:.2f} MB)...'
                    logger.info(verify_msg)
                    self.update_status('processing', 90, verify_msg)
                    
                    if self.verify_geotiff(self.output_file):
                        success_msg = f'DEM download complete: {final_size_mb:.2f} MB file created from {len(georef_chunk_files)} chunks'
                        logger.info(success_msg)
                        self.update_status('complete', 100, success_msg)
                        return True
    
        logger.error("Failed to download high-resolution DEM")
        self.update_status('failed', 0, 'Failed to download high-resolution DEM')
        return False

def fetch_dem(bbox=None, target_res_meters=5, output_dir=None, output_file=None, rest_url=None, status_file=None):
    """
    Convenience function to fetch raw elevation DEM data.
    
    Args:
        bbox (tuple): Bounding box (minx, miny, maxx, maxy) in WGS84
        target_res_meters (float): Target resolution in meters
        output_dir (str): Directory to save output files
        output_file (str): Name of the output GeoTIFF file
        rest_url (str): URL of the REST service to use (overrides default)
        status_file (str): Path to a file to write status updates
        
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
        output_file=output_file,
        rest_url=rest_url,
        status_file=status_file
    )
    
    # Log parameters
    logger.info(f"Starting high-resolution raw DEM download (target resolution: {target_res_meters}m)")
    logger.info(f"Calculated required dimensions: {fetcher.required_width}x{fetcher.required_height} pixels")
    
    # Update initial status
    if status_file:
        fetcher.update_status('starting', 0, 'Initializing raw DEM download...')
    
    # Download DEM
    success = fetcher.download_high_res_dem()
    
    if success:
        logger.info("High-resolution raw DEM download completed successfully")
    else:
        logger.error("High-resolution raw DEM download failed")
    
    return success

if __name__ == "__main__":
    # If run as a script, fetch DEM with default parameters
    success = fetch_dem()
    
    if not success:
        sys.exit(1)
