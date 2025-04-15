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
import json

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
                 output_file=None,
                 rest_url=None,
                 status_file=None,
                 data_type='rgb'):
        """
        Initialize the DEM fetcher with configuration parameters.
        
        Args:
            bbox (tuple): Bounding box (minx, miny, maxx, maxy) in WGS84
            target_res_meters (float): Target resolution in meters
            output_dir (str): Directory to save output files
            output_file (str): Name of the output GeoTIFF file
            rest_url (str): URL of the REST service to use (overrides default)
            status_file (str): Path to a file to write status updates
            data_type (str): Type of data to fetch ('rgb' or 'raw'). Default is 'rgb'.
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
            self.rest_url = "https://services.ga.gov.au/gis/rest/services/DEM_LiDAR_5m_2025/MapServer"
        
        # Maximum retries
        self.max_retries = 3
        
        # Export parameters
        self.export_params = {
            'transparent': 'true',
            'f': 'image',
            'noDataInterpretation': 'esriNoDataMatchAny'
        }
        
        # Data type
        self.data_type = data_type

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
        
        # Determine format, pixelType, and file extension based on data_type
        if self.data_type == 'raw':
            export_format = 'tiff'
            export_pixel_type = 'F32'
            output_extension = '.tif'
            expected_content_type = 'tiff'
        elif self.data_type == 'rgb':
            export_format = 'png8' # Use 8-bit PNG for RGB
            export_pixel_type = 'U8'
            output_extension = '.png'
            expected_content_type = 'png'
        else:
            # Default or error case - fall back to raw for now, but log error
            logger.error(f"Unsupported data_type '{self.data_type}' in export_image_chunk. Defaulting to raw.")
            export_format = 'tiff'
            export_pixel_type = 'F32'
            output_extension = '.tif'
            expected_content_type = 'tiff'
            
        params = {
            'bbox': ','.join(map(str, bbox)),
            'bboxSR': 4326,  # WGS84
            'imageSR': 4326,
            'size': f"{width},{height}",
            # Add dynamic format and pixelType
            'format': export_format, 
            'pixelType': export_pixel_type, 
            **self.export_params # Keep other default export params like noDataInterpretation
        }
        
        logger.info(f"Exporting chunk {chunk_id} ({self.data_type}) with bbox {bbox}") 
        logger.info(f"Request size: {width}x{height} pixels")
        logger.info(f"Request URL: {export_url}")
        logger.info(f"Request params: {params}")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempt {attempt+1}/{self.max_retries} to export chunk {chunk_id} ({self.data_type})") 
                response = requests.get(export_url, params=params, timeout=300, stream=True)
                
                if response.status_code == 200:
                    # Check content type based on expected format
                    content_type = response.headers.get('Content-Type', '').lower()
                    if expected_content_type not in content_type and 'image' not in content_type:
                        # Log warning but continue, sometimes content-type is generic 'image/...' or incorrect
                        logger.warning(f"Unexpected content type for {self.data_type} request: {content_type} (expected similar to '{expected_content_type}')")
                        logger.warning(f"Response headers: {dict(response.headers)}")
                    
                    # Use dynamic file extension
                    output_file = os.path.join(self.temp_dir, f"chunk_{chunk_id}{output_extension}") 
                    
                    # Save the response to a file
                    with open(output_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Check if the file is valid
                    file_size = os.path.getsize(output_file)
                    # Adjust minimum size check slightly for potentially smaller PNGs
                    min_expected_size = 500 if self.data_type == 'rgb' else 1000 
                    if file_size < min_expected_size:  
                        logger.warning(f"Chunk file {output_file} is suspiciously small: {file_size} bytes (expected > {min_expected_size})")
                        try: # Try reading as text first for error messages
                            with open(output_file, 'r', errors='ignore') as f:
                                content_preview = f.read(500)
                            logger.warning(f"File text content preview: {content_preview}")
                            if 'error' in content_preview.lower() or 'exception' in content_preview.lower() or 'failed' in content_preview.lower():
                               logger.error(f"Response appears to contain an error message.")
                               # If error found, trigger retry/failure logic
                               if attempt < self.max_retries - 1:
                                   logger.info(f"Retrying due to error content in {attempt+1}/{self.max_retries}...")
                                   time.sleep(2 ** attempt)
                                   continue # Go to next attempt
                               else:
                                   logger.error(f"Failed after {self.max_retries} attempts due to error content in response.")
                                   return None # Failed all retries
                        except Exception: 
                             # If reading as text fails, it might be binary - log binary preview
                             with open(output_file, 'rb') as f:
                                 content_preview = f.read(100)
                             logger.warning(f"File binary content preview: {content_preview}")
                             # Cannot reliably detect errors in binary preview, proceed with caution
                             # Maybe add check here to retry if file size is extremely small (e.g. <100 bytes)?
    
                        # If it passed the error content check but is still small, maybe log and continue?
                        logger.warning(f"File {output_file} is small but does not appear to be a text error. Proceeding cautiously.")
    
                    logger.info(f"Saved chunk {chunk_id} ({self.data_type}) to {output_file} ({file_size} bytes)") 
                    return output_file # Success for this attempt
                else:
                    logger.warning(f"Attempt {attempt+1}/{self.max_retries} failed: {response.status_code}")
                    if response.text:
                        logger.warning(f"Response: {response.text[:500]}")
                    
                    # Wait before retrying
                    if attempt < self.max_retries - 1:
                        retry_delay = 2 ** attempt
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)  # Exponential backoff
            except requests.exceptions.Timeout:
                 logger.error(f"Attempt {attempt+1}/{self.max_retries} timed out for chunk {chunk_id} ({self.data_type})")
                 if attempt < self.max_retries - 1:
                     time.sleep(2 ** (attempt + 1)) # Longer backoff after timeout
                     continue
                 else:
                     logger.error(f"Failed chunk {chunk_id} due to timeout after {self.max_retries} attempts.")
                     return None
            except Exception as e:
                logger.exception(f"Attempt {attempt+1}/{self.max_retries} error exporting chunk {chunk_id} ({self.data_type}): {e}") # Log data type and exception
                
                # Wait before retrying
                if attempt < self.max_retries - 1:
                    retry_delay = 2 ** attempt
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)  # Exponential backoff
        
        logger.error(f"Failed to export chunk {chunk_id} ({self.data_type}) after {self.max_retries} attempts") 
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

    def update_status(self, status, progress, message):
        """
        Update the status file with current progress.
        
        Args:
            status (str): Current status (starting, downloading, processing, complete, failed)
            progress (float): Progress percentage (0-100)
            message (str): Status message
        """
        if self.status_file:
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
                
                # Write status to file
                with open(self.status_file, 'w') as f:
                    json.dump({
                        'status': status,
                        'progress': progress,
                        'message': message,
                        'timestamp': time.time()
                    }, f)
                
                # Log status update
                logger.info(f"Status update: {status} - {progress}% - {message}")
            except Exception as e:
                logger.error(f"Error updating status file: {e}")

    def download_high_res_dem(self):
        """
        Download high-resolution DEM by splitting into chunks if necessary.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.create_temp_dir()
        
        # Log the start of the DEM download with detailed parameters
        logger.info(f"Starting DEM download with the following parameters:")
        logger.info(f"  - Bounding box: {self.bbox}")
        logger.info(f"  - Target resolution: {self.target_res_meters}m")
        logger.info(f"  - Output file: {self.output_file}")
        logger.info(f"  - REST URL: {self.rest_url}")
        logger.info(f"  - Data type: {self.data_type}")
        
        # Check if the service is available
        try:
            check_url = f"{self.rest_url}/info?f=json"
            logger.info(f"Checking service availability: {check_url}")
            response = requests.get(check_url, timeout=30)
            
            if response.status_code != 200:
                error_msg = f"Service not available: {response.status_code}"
                logger.error(error_msg)
                self.update_status('failed', 0, error_msg)
                return False
            
            logger.info("Service is available and responding")
            service_info = response.json()
            logger.info(f"Service info: {service_info.get('serviceDescription', 'No description available')}")
        except Exception as e:
            error_msg = f"Error checking service: {str(e)}"
            logger.error(error_msg)
            self.update_status('failed', 0, error_msg)
            return False
        
        # If the request is small enough, just do one request
        if self.split_requests == 1:
            logger.info("Single request mode - exporting full area as one chunk")
            self.update_status('downloading', 10, f'Downloading {self.data_type.upper()} data as a single chunk...')
            
            chunk_file = self.export_image_chunk(self.rest_url, self.bbox, self.chunk_width, self.chunk_height, "full")
            
            if chunk_file:
                # Log file size
                file_size_bytes = os.path.getsize(chunk_file)
                file_size_mb = file_size_bytes / (1024 * 1024)
                logger.info(f"Downloaded chunk file size: {file_size_mb:.2f} MB ({file_size_bytes} bytes)")
                
                # <<< MODIFIED: Handle RGB vs RAW >>>
                if self.data_type == 'rgb':
                    # For RGB, just copy the downloaded PNG chunk directly to the output
                    logger.info(f"RGB mode: Copying downloaded chunk {chunk_file} directly to {self.output_file}")
                    self.update_status('processing', 80, f'Saving RGB image ({file_size_mb:.2f} MB)...')
                    try:
                        import shutil
                        shutil.copy2(chunk_file, self.output_file)
                        final_size_bytes = os.path.getsize(self.output_file)
                        final_size_mb = final_size_bytes / (1024 * 1024)
                        success_msg = f'RGB image download complete: {final_size_mb:.2f} MB file created'
                        logger.info(success_msg)
                        self.update_status('complete', 100, success_msg)
                        return True
                    except Exception as e:
                        error_msg = f"Error copying RGB chunk to output: {e}"
                        logger.exception(error_msg)
                        self.update_status('failed', 90, error_msg)
                        return False
            
                elif self.data_type == 'raw':
                    # For RAW, proceed with georeferencing and verification
                    logger.info("RAW mode: Proceeding with georeferencing...")
                    self.update_status('processing', 50, f'Adding georeference information to {file_size_mb:.2f} MB chunk...')
                    georef_file = self.add_georeference_to_chunk(chunk_file, self.bbox)
                    
                    if georef_file:
                        # Log georeferenced file size
                        georef_size_bytes = os.path.getsize(georef_file)
                        georef_size_mb = georef_size_bytes / (1024 * 1024)
                        logger.info(f"Georeferenced file size: {georef_size_mb:.2f} MB ({georef_size_bytes} bytes)")
                        
                        # Copy to output file
                        self.update_status('processing', 80, f'Finalizing {self.data_type.upper()} DEM file ({georef_size_mb:.2f} MB)...')
                        if os.path.exists(georef_file):
                            import shutil
                            shutil.copy2(georef_file, self.output_file)
                            logger.info(f"Copied georeferenced file to {self.output_file}")
                            
                            # Verify the result
                            self.update_status('processing', 90, 'Verifying DEM file...')
                            if self.verify_geotiff(self.output_file):
                                final_size_bytes = os.path.getsize(self.output_file)
                                final_size_mb = final_size_bytes / (1024 * 1024)
                                success_msg = f'{self.data_type.upper()} DEM download complete: {final_size_mb:.2f} MB file created'
                                logger.info(success_msg)
                                self.update_status('complete', 100, success_msg)
                                return True
                            else:
                                error_msg = "Verification of final GeoTIFF failed."
                                logger.error(error_msg)
                                self.update_status('failed', 95, error_msg)
                                return False
                        else:
                            error_msg = f"Georeferenced file {georef_file} not found after creation."
                            logger.error(error_msg)
                            self.update_status('failed', 85, error_msg)
                            return False
                    else:
                        error_msg = "Failed to add georeference to the downloaded chunk."
                        logger.error(error_msg)
                        self.update_status('failed', 60, error_msg)
                        return False
                else:
                     logger.error(f"Unsupported data_type '{self.data_type}' during single chunk processing.")
                     self.update_status('failed', 50, f"Internal error: Unsupported data type {self.data_type}")
                     return False
            else: 
                # Chunk download failed
                error_msg = f"Failed to download the single chunk for {self.data_type.upper()} data."
                logger.error(error_msg)
                self.update_status('failed', 20, error_msg)
                return False
        else:
            # Split into chunks
            logger.info(f"Splitting request into {self.split_requests}x{self.split_requests} chunks")
            self.update_status('downloading', 5, f'Splitting area into {self.split_requests}x{self.split_requests} chunks...')
            
            chunk_files = []
            georef_chunk_files = []
            
            total_chunks = self.split_requests * self.split_requests
            current_chunk = 0
            total_downloaded_bytes = 0
            failed_chunks = 0
            
            for row in range(self.split_requests):
                for col in range(self.split_requests):
                    current_chunk += 1
                    chunk_id = f"{row}_{col}"
                    chunk_bbox = self.get_chunk_bbox(row, col, self.split_requests, self.split_requests)
                    
                    # Update status with detailed chunk information
                    chunk_info = f'Downloading chunk {current_chunk}/{total_chunks} ({self.data_type.upper()})'
                    logger.info(chunk_info + f" (bbox: {chunk_bbox})")
                    progress = 5 + (current_chunk / total_chunks) * 45  # 5-50% progress during download
                    self.update_status('downloading', progress, chunk_info)
                    
                    chunk_file = self.export_image_chunk(self.rest_url, chunk_bbox, self.chunk_width, self.chunk_height, chunk_id)
                    
                    if chunk_file:
                        chunk_files.append(chunk_file)
                        # Log size of downloaded chunk
                        chunk_size = os.path.getsize(chunk_file)
                        total_downloaded_bytes += chunk_size
                        logger.info(f"Chunk {current_chunk}/{total_chunks} downloaded: {chunk_file} ({chunk_size} bytes)")
                    else:
                        failed_chunks += 1
                        logger.error(f"Failed to download chunk {current_chunk}/{total_chunks} (ID: {chunk_id})")
                        # Decide whether to continue or fail fast (e.g., if too many chunks fail)
                        if failed_chunks > total_chunks * 0.2: # Allow up to 20% failures
                           error_msg = f"Too many chunk downloads failed ({failed_chunks}/{total_chunks}). Aborting."
                           logger.error(error_msg)
                           self.update_status('failed', progress, error_msg)
                           return False
                           
            # Check if any chunks were successfully downloaded
            if not chunk_files:
                error_msg = "No chunks were successfully downloaded."
                logger.error(error_msg)
                self.update_status('failed', 50, error_msg)
                return False
                
            total_downloaded_mb = total_downloaded_bytes / (1024*1024)
            logger.info(f"Total downloaded data across {len(chunk_files)} chunks: {total_downloaded_mb:.2f} MB")
            if failed_chunks > 0:
                logger.warning(f"{failed_chunks} chunks failed to download.")

            # <<< MODIFIED: Handle RGB vs RAW for multiple chunks >>>
            if self.data_type == 'rgb':
                # For RGB, use the first successfully downloaded chunk as the output
                first_chunk_file = chunk_files[0]
                logger.info(f"RGB mode (multi-chunk): Using first downloaded chunk {first_chunk_file} as output {self.output_file}")
                self.update_status('processing', 80, f'Saving first RGB image chunk...')
                try:
                    import shutil
                    shutil.copy2(first_chunk_file, self.output_file)
                    final_size_bytes = os.path.getsize(self.output_file)
                    final_size_mb = final_size_bytes / (1024 * 1024)
                    success_msg = f'RGB image download complete (using first chunk): {final_size_mb:.2f} MB file created'
                    logger.info(success_msg)
                    self.update_status('complete', 100, success_msg)
                    return True
                except Exception as e:
                    error_msg = f"Error copying first RGB chunk to output: {e}"
                    logger.exception(error_msg)
                    self.update_status('failed', 90, error_msg)
                    return False

            elif self.data_type == 'raw':
                # For RAW, proceed with georeferencing and merging
                logger.info("RAW mode (multi-chunk): Proceeding with georeferencing chunks...")
                self.update_status('processing', 50, f'Georeferencing {len(chunk_files)} downloaded chunks...')
                
                for i, chunk_file in enumerate(chunk_files):
                    chunk_bbox = self.get_chunk_bbox(i // self.split_requests, i % self.split_requests, self.split_requests, self.split_requests)
                    progress = 50 + ((i + 1) / len(chunk_files)) * 30 # 50-80% progress during georef
                    self.update_status('processing', progress, f'Georeferencing chunk {i+1}/{len(chunk_files)}...')
                    georef_file = self.add_georeference_to_chunk(chunk_file, chunk_bbox)
                    if georef_file:
                        georef_chunk_files.append(georef_file)
                    else:
                        logger.warning(f"Failed to georeference chunk: {chunk_file}")
                        # Potentially handle failure here, e.g., skip this chunk in merge
            
                if not georef_chunk_files:
                    error_msg = "Failed to georeference any downloaded chunks."
                    logger.error(error_msg)
                    self.update_status('failed', 80, error_msg)
                    return False
                
                # Merge georeferenced chunks
                logger.info(f"Merging {len(georef_chunk_files)} georeferenced chunks...")
                merge_msg = f'Merging {len(georef_chunk_files)} georeferenced chunks...' 
                if len(chunk_files) != len(georef_chunk_files):
                     merge_msg += f' ({len(chunk_files) - len(georef_chunk_files)} failed georef)'
                self.update_status('processing', 80, merge_msg)
                
                # Merge using rasterio
                try:
                    self.merge_chunks(georef_chunk_files, self.output_file)
                except Exception as e:
                    error_msg = f"Error merging chunks: {e}"
                    logger.exception(error_msg)
                    self.update_status('failed', 85, error_msg)
                    return False
                
                if os.path.exists(self.output_file):
                    # Log final size
                    final_size_bytes = os.path.getsize(self.output_file)
                    final_size_mb = final_size_bytes / (1024 * 1024)
                    logger.info(f"Merged file size: {final_size_mb:.2f} MB ({final_size_bytes} bytes)")
                    
                    # Verify the result
                    verify_msg = f'Verifying merged {self.data_type.upper()} DEM file ({final_size_mb:.2f} MB)...'
                    logger.info(verify_msg)
                    self.update_status('processing', 90, verify_msg)
                    
                    if self.verify_geotiff(self.output_file):
                        success_msg = f'{self.data_type.upper()} DEM download complete: {final_size_mb:.2f} MB file created from {len(georef_chunk_files)} chunks'
                        logger.info(success_msg)
                        self.update_status('complete', 100, success_msg)
                        return True
                    else:
                        error_msg = f"Verification of merged GeoTIFF ({self.output_file}) failed."
                        logger.error(error_msg)
                        self.update_status('failed', 95, error_msg)
                        return False
                else:
                    error_msg = f"Merged output file {self.output_file} not found after merge operation."
                    logger.error(error_msg)
                    self.update_status('failed', 88, error_msg)
                    return False
            else:
                logger.error(f"Unsupported data_type '{self.data_type}' during multi-chunk processing.")
                self.update_status('failed', 50, f"Internal error: Unsupported data type {self.data_type}")
                return False
                
        # Fallback if something went wrong before returning True
        logger.error(f"Failed to download high-resolution {self.data_type.upper()} DEM")
        self.update_status('failed', 0, f'Failed to download high-resolution {self.data_type.upper()} DEM')
        return False

def fetch_dem(bbox=None, target_res_meters=5, output_dir=None, output_file=None, rest_url=None, status_file=None, data_type='rgb'):
    """
    Convenience function to fetch DEM data.
    
    Args:
        bbox (tuple): Bounding box (minx, miny, maxx, maxy) in WGS84
        target_res_meters (float): Target resolution in meters
        output_dir (str): Directory to save output files
        output_file (str): Name of the output GeoTIFF file
        rest_url (str): URL of the REST service to use (overrides default)
        status_file (str): Path to a file to write status updates
        data_type (str): Type of data to fetch ('rgb' or 'raw'). Default is 'rgb'.
        
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
        status_file=status_file,
        data_type=data_type
    )
    
    # Log parameters
    logger.info(f"Starting high-resolution DEM download (type: {data_type}, target resolution: {target_res_meters}m)")
    logger.info(f"Calculated required dimensions: {fetcher.required_width}x{fetcher.required_height} pixels")
    
    # Update initial status
    if status_file:
        message = f"Initializing {data_type.upper()} DEM download..."
        fetcher.update_status('starting', 0, message)
    
    # Download DEM
    success = fetcher.download_high_res_dem() 
    
    if success:
        logger.info(f"High-resolution {data_type.upper()} DEM download completed successfully")
    else:
        logger.error(f"High-resolution {data_type.upper()} DEM download failed")
    
    return success

if __name__ == "__main__":
    # If run as a script, fetch DEM with default parameters
    success = fetch_dem()
    
    if not success:
        sys.exit(1)
