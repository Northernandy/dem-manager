"""
DEM Operations Module

This module contains functions for Digital Elevation Model (DEM) operations,
including fetching, deleting, and checking status.
"""

import os
import json
import time
import uuid
import logging
import threading
import filelock
from io import StringIO
import sys
from werkzeug.utils import secure_filename
import gc
import subprocess

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

# Import the DEM handlers
try:
    from src.pipeline.wcs_geotiff_handler import fetch_geotiff_dem
    from src.pipeline.wms_rgb_handler import fetch_rgb_dem
    logger.info("Successfully imported DEM handlers in dem_operations.py")
except ImportError as e:
    logger.warning(f"Could not import DEM handlers in dem_operations.py: {e}")

def fetch_dem(bbox, dem_type, data_type, resolution=None, output_file=None):
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
    
    # Add data_type prefix to output_file if provided
    if output_file:
        base, ext = os.path.splitext(output_file)
        if not base.startswith(f"{data_type}_"):
            output_file = f"{data_type}_{base}{ext}"
    
    # Redirect stdout to capture print statements from handlers
    original_stdout = sys.stdout
    captured_output = StringIO()
    sys.stdout = captured_output
    
    try:
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
        
        # Restore stdout
        sys.stdout = original_stdout
        
        # Get the captured output
        output_text = captured_output.getvalue()
        
        # Log the captured output
        for line in output_text.splitlines():
            if line.strip():
                logger.info(f"DEM Handler: {line.strip()}")
        
        return result
    except Exception as e:
        # Make sure to restore stdout even if an exception occurs
        sys.stdout = original_stdout
        logger.error(f"Error in fetch_dem: {str(e)}")
        return {
            'success': False,
            'message': f"Error fetching DEM: {str(e)}"
        }

def delete_dem(filename):
    """
    Delete a DEM file and its associated auxiliary files.
    
    Args:
        filename (str): Name of the DEM file to delete
        
    Returns:
        dict: Result of the operation
    """
    try:
        filename = secure_filename(filename)
        file_path = os.path.join(DEM_DIR, filename)
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except PermissionError as e:
                logger.info(f"File {filename} is in use, attempting to force close...")
                
                gc.collect()
                
                time.sleep(0.5)
                
                try:
                    os.remove(file_path)
                except Exception as inner_e:
                    if os.name == 'nt':  
                        try:
                            subprocess.run(['cmd', '/c', f'del /F "{file_path}"'], 
                                          shell=True, check=True, 
                                          stderr=subprocess.PIPE, 
                                          stdout=subprocess.PIPE)
                        except subprocess.CalledProcessError as cmd_e:
                            return {
                                'success': False, 
                                'message': f'File is in use by another process. Please close any applications using this DEM and try again. Error: {str(e)}'
                            }
                    else:
                        return {
                            'success': False, 
                            'message': f'File is in use by another process. Please close any applications using this DEM and try again. Error: {str(e)}'
                        }
            
            # Delete associated auxiliary files (like .aux.xml)
            aux_file = os.path.join(DEM_DIR, f"{filename}.aux.xml")
            if os.path.exists(aux_file):
                try:
                    os.remove(aux_file)
                    logger.info(f"Deleted associated auxiliary file: {aux_file}")
                except Exception as aux_e:
                    logger.warning(f"Could not delete auxiliary file: {aux_file}, error: {str(aux_e)}")
            
            # Delete associated info.json file
            info_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_info.json")
            if os.path.exists(info_file):
                try:
                    os.remove(info_file)
                    logger.info(f"Deleted associated info file: {info_file}")
                except Exception as info_e:
                    logger.warning(f"Could not delete info file: {info_file}, error: {str(info_e)}")
            
            # Delete associated status.json.log file
            status_log_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json.log")
            if os.path.exists(status_log_file):
                try:
                    os.remove(status_log_file)
                    logger.info(f"Deleted associated status log file: {status_log_file}")
                except Exception as log_e:
                    logger.warning(f"Could not delete status log file: {status_log_file}, error: {str(log_e)}")
            
            status_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json")
            if os.path.exists(status_file):
                try:
                    os.remove(status_file)
                except Exception:
                    logger.warning(f"Could not delete status file: {status_file}")
            
            # Delete associated PGW file if it exists
            pgw_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}.pgw")
            if os.path.exists(pgw_file):
                try:
                    os.remove(pgw_file)
                    logger.info(f"Deleted associated PGW file: {pgw_file}")
                except Exception as pgw_e:
                    logger.warning(f"Could not delete PGW file: {pgw_file}, error: {str(pgw_e)}")
            
            metadata_dir = os.path.join(DEM_DIR, 'metadata')
            metadata_file = os.path.join(metadata_dir, f"{filename}.json")
            if os.path.exists(metadata_file):
                try:
                    os.remove(metadata_file)
                except Exception:
                    logger.warning(f"Could not delete metadata file: {metadata_file}")
            
            return {'success': True, 'message': f'DEM {filename} deleted successfully'}
        else:
            return {'success': False, 'message': f'DEM {filename} not found'}
    except Exception as e:
        logger.exception("Error deleting DEM")
        return {'success': False, 'message': str(e)}

def check_dem_status(filename):
    """
    Check the status of a DEM download.
    
    Args:
        filename (str): Name of the DEM file to check
        
    Returns:
        dict: Status information
    """
    try:
        filename = secure_filename(filename)
        status_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json")
        log_file = status_file + ".log"
        
        logger.info(f"Checking DEM status for: {filename}")
        
        # Initialize status data with default values
        status_data = {
            'status': 'unknown',
            'message': 'No status information available',
            'logs': []
        }
        
        # First, check if the status file exists
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                # Only show percentage in logs for completed status
                if status_data.get('status') == 'completed' or status_data.get('status') == 'complete':
                    logger.info(f"DEM status check for {filename}: completed - {status_data.get('message', 'No message')}")
                else:
                    logger.info(f"DEM status check for {filename}: {status_data.get('status', 'unknown')} - {status_data.get('message', 'No message')}")
                
                # Check if the DEM file exists
                dem_file_path = os.path.join(DEM_DIR, filename)
                if os.path.exists(dem_file_path):
                    file_size_bytes = os.path.getsize(dem_file_path)
                    file_size_mb = file_size_bytes / (1024 * 1024)
                    
                    status_data['file_size'] = {
                        'bytes': file_size_bytes,
                        'mb': round(file_size_mb, 2),
                        'formatted': f"{file_size_mb:.2f} MB"
                    }
                    
                    # If the file exists but status is not 'completed', update it
                    if status_data.get('status') != 'completed' and status_data.get('status') != 'complete':
                        status_data['status'] = 'completed'
                        status_data['message'] = 'DEM download completed successfully'
                        
                        with open(status_file, 'w') as f:
                            json.dump(status_data, f)
            except Exception as e:
                logger.exception(f"Error reading status file for {filename}")
                return {
                    'success': False,
                    'message': f"Error reading status file: {str(e)}"
                }
        else:
            # If no status file exists, check if the DEM file exists
            dem_file_path = os.path.join(DEM_DIR, filename)
            if os.path.exists(dem_file_path):
                # File exists but no status file, create a completed status
                file_size_bytes = os.path.getsize(dem_file_path)
                file_size_mb = file_size_bytes / (1024 * 1024)
                
                status_data = {
                    'status': 'completed',
                    'message': 'DEM file exists',
                    'timestamp': time.time(),
                    'file_path': dem_file_path,
                    'file_size': {
                        'bytes': file_size_bytes,
                        'mb': round(file_size_mb, 2),
                        'formatted': f"{file_size_mb:.2f} MB"
                    },
                    'logs': []
                }
            else:
                logger.warning(f"No status file or DEM file found for {filename}")
                return {
                    'success': False,
                    'message': f"No status information available for {filename}"
                }
        
        # Now, check if the log file exists and read its contents
        log_contents = []
        if os.path.exists(log_file):
            try:
                # Try different encodings to handle potential encoding issues
                encodings = ['utf-8', 'latin-1', 'cp1252']
                for encoding in encodings:
                    try:
                        with open(log_file, 'r', encoding=encoding) as f:
                            log_contents = [line.strip() for line in f.readlines()]
                        break  # If successful, break out of the loop
                    except UnicodeDecodeError:
                        continue  # Try the next encoding
                
                # If we couldn't read with any encoding, log an error
                if not log_contents and len(encodings) > 0:
                    logger.warning(f"Could not read log file with any of the attempted encodings: {log_file}")
            except Exception as e:
                logger.warning(f"Error reading log file for {filename}: {str(e)}")
        
        # Add log contents to status data
        status_data['logs'] = log_contents
        
        # Map status values to what the frontend expects
        status_mapping = {
            'starting': 'starting',
            'downloading': 'downloading',
            'completed': 'complete',
            'complete': 'complete',
            'error': 'failed'
        }
        
        # Create a response that matches what the frontend expects
        response = {
            'success': True,
            'status': {
                'status': status_mapping.get(status_data.get('status', 'unknown'), 'unknown'),
                'message': status_data.get('message', 'No status message available')
            },
            'status_data': status_data
        }
        
        return response
    except Exception as e:
        logger.exception(f"Error checking DEM status for {filename}")
        return {
            'success': False,
            'message': f"Error checking DEM status: {str(e)}"
        }

def rename_dem(filename, new_display_name):
    """
    Rename a DEM (update display name).
    
    Args:
        filename (str): Name of the DEM file to rename
        new_display_name (str): New display name for the DEM
        
    Returns:
        dict: Result of the operation
    """
    try:
        if not filename or not new_display_name:
            return {'success': False, 'message': 'Missing filename or display name'}
        
        metadata_dir = os.path.join(DEM_DIR, 'metadata')
        os.makedirs(metadata_dir, exist_ok=True)
        
        metadata_file = os.path.join(metadata_dir, f"{filename}.json")
        
        metadata = {}
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        metadata['display_name'] = new_display_name
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f)
        
        return {'success': True, 'message': 'DEM renamed successfully'}
    except Exception as e:
        logger.exception("Error renaming DEM")
        return {'success': False, 'message': str(e)}

def fetch_dem_api(data):
    """
    Fetch a DEM based on the specified parameters.
    
    Args:
        data (dict): Request data containing DEM parameters
        
    Returns:
        dict: Result of the operation
    """
    try:
        # Get parameters from the request
        dem_type = data.get('dem_type', 'lidar_5m')
        dem_name = data.get('dem_name', '')  # Get the DEM name from the request
        data_type = data.get('dataType', 'rgb').lower() 

        if data_type not in ['rgb', 'raw']:
             logger.error(f"Invalid dataType requested: {data_type}. Must be 'rgb' or 'raw'.")
             return {'success': False, 'message': "Invalid dataType requested. Must be 'rgb' or 'raw'."}

        logger.info(f"DEM fetch request: type={dem_type}, name={dem_name}, dataType={data_type}, data={data}")
        
        # Get DEM type configuration
        dem_config = DEM_TYPES.get(dem_type)
        if not dem_config:
            logger.error(f"Unknown DEM type requested: {dem_type}")
            return {'success': False, 'message': f'Unknown DEM type: {dem_type}'}
        
        # Get resolution from DEM type configuration
        target_res_meters = dem_config.get('resolution', 5)  # Default to 5m if not specified
        
        # Get bounding box (default to Brisbane area if not specified)
        bbox = data.get('bbox', (152.0, -28.0, 153.5, -27.0))
        
        # Validate bbox
        if len(bbox) != 4:
            logger.error(f"Invalid bounding box: {bbox}")
            return {'success': False, 'message': 'Invalid bounding box format. Must be [minX, minY, maxX, maxY]'}
        
        try:
            bbox = tuple(float(coord) for coord in bbox)
        except (ValueError, TypeError):
            logger.error(f"Invalid bounding box coordinates: {bbox}")
            return {'success': False, 'message': 'Invalid bounding box coordinates. Must be numeric values.'}
        
        # Use appropriate extension based on data type
        file_extension = '.tif' if data_type == 'raw' else '.png'
        
        bbox_str = '_'.join([str(coord).replace('.', 'p') for coord in bbox])
        base_output_file = f"{data_type}_{dem_type}_{bbox_str}{file_extension}" 
        
        output_file = base_output_file
        output_path = os.path.join(DEM_DIR, output_file)
        
        if os.path.exists(output_path):
            counter = 1
            while True:
                output_file = f"{data_type}_{dem_type}_{bbox_str}_{counter}{file_extension}" 
                output_path = os.path.join(DEM_DIR, output_file)
                if not os.path.exists(output_path):
                    break
                counter += 1
            
            logger.info(f"Generated unique filename for new DEM: {output_file}")
        
        status_file = os.path.join(DEM_DIR, f"{os.path.splitext(output_file)[0]}_status.json")
        
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        
        try:
            display_name = dem_name
            if dem_name:
                display_name = f"{dem_name} ({dem_config['name']})"
            else:
                display_name = dem_config['name']
            
            with open(status_file, 'w') as f:
                json.dump({
                    'status': 'starting',
                    'message': 'Initializing DEM download...',
                    'timestamp': time.time(),
                    'display_name': display_name,
                    'dataType': data_type  
                }, f)
            
            if not os.path.exists(status_file):
                logger.error(f"Failed to create status file: {status_file}")
                return {'success': False, 'message': 'Failed to create status file', 'status': 'error'}
            
            logger.info(f"Created status file: {status_file}")
        except Exception as e:
            logger.exception(f"Error creating status file: {e}")
            return {'success': False, 'message': f'Error creating status file: {str(e)}', 'status': 'error'}
        
        logger.info(f"Starting DEM fetch: type={dem_type}, name={dem_name}, dataType={data_type}, bbox={bbox}, output={output_file}")
        
        thread = threading.Thread(target=fetch_dem_thread, args=(
            dem_type, dem_name, data_type, bbox, output_file, status_file, target_res_meters, dem_config
        ))
        thread.start()
        
        logger.info(f"Started background thread for {output_file}")
        
        return {'success': True, 'filename': output_file, 'status': 'starting'}

    except Exception as e:
        logger.exception("Error in fetch_dem_api")
        return {'success': False, 'message': f'An unexpected error occurred: {str(e)}', 'status': 'error'}

def fetch_dem_thread(dem_type, dem_name, data_type, bbox, output_file, status_file, target_res_meters, dem_config):
    """
    Background thread function for fetching DEMs.
    
    Args:
        dem_type (str): Type of DEM to fetch
        dem_name (str): Display name for the DEM
        data_type (str): Type of data to fetch ('raw' or 'rgb')
        bbox (tuple): Bounding box (minx, miny, maxx, maxy)
        output_file (str): Output file name
        status_file (str): Path to the status file
        target_res_meters (int): Resolution in meters
        dem_config (dict): DEM type configuration
    """
    try:
        # Use file locking to prevent race conditions
        lock_file = f"{status_file}.lock"
        lock = filelock.FileLock(lock_file, timeout=10)
        
        try:
            with lock:
                try:
                    with open(status_file, 'r') as f:
                        status_data = json.load(f)
                    
                    display_name = status_data.get('display_name', '')
                    thread_data_type = status_data.get('dataType', data_type) 
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error reading status file: {e}")
                    # Create a fresh status data if the file is corrupted
                    status_data = {
                        'status': 'starting',
                        'message': 'Initializing...',
                        'timestamp': time.time(),
                        'display_name': dem_name or dem_type,
                        'dataType': data_type
                    }
                    display_name = dem_name or dem_type
                    thread_data_type = data_type
                except Exception as e:
                    logger.error(f"Error reading status file: {e}")
                    # Create a fresh status data if the file can't be read
                    status_data = {
                        'status': 'starting',
                        'message': 'Initializing...',
                        'timestamp': time.time(),
                        'display_name': dem_name or dem_type,
                        'dataType': data_type
                    }
                    display_name = dem_name or dem_type
                    thread_data_type = data_type
        
            # Record start time for execution timing
            start_time = time.time()
        
            with lock:
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'downloading',
                            'message': 'Starting DEM download...',
                            'timestamp': time.time(),
                            'display_name': display_name,
                            'dataType': thread_data_type 
                        }, f)
                except Exception as e:
                    logger.error(f"Error writing to status file: {e}")
        except filelock.Timeout:
            logger.error(f"Could not acquire lock for status file: {status_file}")
            
        # Set up temporary log handler for this thread
        status_handler = logging.FileHandler(status_file + ".log")
        thread_logger = logging.getLogger('dem_fetch')
        thread_logger.setLevel(logging.INFO)
        thread_logger.addHandler(status_handler)
        
        try:
            # Log initial message
            thread_logger.info(f"Starting DEM download for {dem_type}, data type: {thread_data_type}")
            thread_logger.info(f"Bounding box: {bbox}")
            
            # Create a subclass of the handler that logs to our status system
            class LoggingDEMHandler:
                def __init__(self, original_handler, logger):
                    self.original_handler = original_handler
                    self.logger = logger
                    
                def __call__(self, *args, **kwargs):
                    # Create a wrapper for print that logs to our status system
                    import builtins
                    original_print = builtins.print
                    
                    def logging_print(*args, **kwargs):
                        # Call the original print
                        original_print(*args, **kwargs)
                        
                        # Log to our status system without timestamp
                        message = ' '.join(str(arg) for arg in args)
                        # Use a custom log record to bypass the formatter
                        record = logging.LogRecord(
                            name=self.logger.name,
                            level=logging.INFO,
                            pathname='',
                            lineno=0,
                            msg=message,
                            args=(),
                            exc_info=None
                        )
                        self.logger.handle(record)
                    
                    # Replace the built-in print with our logging print
                    builtins.print = logging_print
                    
                    try:
                        # Call the original handler
                        result = self.original_handler(*args, **kwargs)
                        return result
                    finally:
                        # Restore the original print
                        builtins.print = original_print
            
            # Wrap the handlers with our logging handler
            logging_geotiff_handler = LoggingDEMHandler(fetch_geotiff_dem, thread_logger)
            logging_rgb_handler = LoggingDEMHandler(fetch_rgb_dem, thread_logger)
            
            # Update progress
            try:
                with lock:
                    try:
                        with open(status_file, 'r') as f:
                            status_data = json.load(f)
                        
                        with open(status_file, 'w') as f:
                            json.dump({
                                'status': 'downloading',
                                'message': 'Fetching DEM data...',
                                'timestamp': time.time(),
                                'display_name': display_name,
                                'dataType': thread_data_type,
                                'logs': status_data.get('logs', [])
                            }, f)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error updating progress: {e}")
                        # Create a fresh status update if the file is corrupted
                        with open(status_file, 'w') as f:
                            json.dump({
                                'status': 'downloading',
                                'message': 'Fetching DEM data...',
                                'timestamp': time.time(),
                                'display_name': display_name,
                                'dataType': thread_data_type,
                                'logs': []
                            }, f)
                    except Exception as e:
                        logger.error(f"Error updating progress: {e}")
            except filelock.Timeout:
                logger.error(f"Could not acquire lock for status file: {status_file}")
            
            # Fetch the DEM using the appropriate handler
            if thread_data_type == 'raw':
                result = logging_geotiff_handler(bbox, dem_type, target_res_meters, output_file)
            else:  # rgb
                result = logging_rgb_handler(bbox, dem_type, target_res_meters, output_file)
            
            # Log the result
            print(f"DEBUG: dem_operations.py received result with success={result.get('success', False)}, message={result.get('message', '')}, file_path={result.get('file_path', '')}")
            
            if result.get('success', False):
                # Calculate total execution time
                execution_time = time.time() - start_time
                # Add a more prominent completion message for RGB DEMs
                if thread_data_type == 'rgb':
                    # Format the final completion message for the logger
                    completion_message = (
                        f"[COMPLETED] RGB DEM visualization successfully created.\n"
                        f"  Message: {result.get('message', '')}\n"
                        f"  File: {result.get('file_path', '')}\n"
                        f"  Time: {execution_time:.2f} seconds"
                    )
                    thread_logger.info(completion_message)
                
                # Final update with success
                try:
                    with lock:
                        try:
                            with open(status_file, 'r') as f:
                                status_data = json.load(f)
                            
                            status_data.update({
                                'status': 'complete',
                                'message': 'DEM download complete',
                                'timestamp': time.time()
                            })
                            
                            with open(status_file, 'w') as f:
                                json.dump(status_data, f)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error updating final status: {e}")
                            # Create a fresh status update if the file is corrupted
                            with open(status_file, 'w') as f:
                                json.dump({
                                    'status': 'complete',
                                    'message': 'DEM download complete',
                                    'timestamp': time.time(),
                                    'display_name': display_name,
                                    'dataType': thread_data_type,
                                    'logs': []
                                }, f)
                        except Exception as e:
                            logger.error(f"Error updating final status: {e}")
                except filelock.Timeout:
                    logger.error(f"Could not acquire lock for status file: {status_file}")
            else:
                # Calculate total execution time even for failures
                execution_time = time.time() - start_time
                thread_logger.error(f"DEM download failed: {result.get('message', '')}")
                thread_logger.error(f"Total execution time: {execution_time:.2f} seconds")
                
                # Update with error
                try:
                    with lock:
                        try:
                            with open(status_file, 'r') as f:
                                status_data = json.load(f)
                            
                            status_data.update({
                                'status': 'error', 
                                'message': f"Error: {result.get('message', '')}",
                                'timestamp': time.time(),
                                'display_name': display_name,
                                'dataType': thread_data_type,
                                'logs': status_data.get('logs', [])
                            })
                            
                            with open(status_file, 'w') as f:
                                json.dump(status_data, f)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error updating error status: {e}")
                            # Create a fresh status update if the file is corrupted
                            with open(status_file, 'w') as f:
                                json.dump({
                                    'status': 'error', 
                                    'message': f"Error: {result.get('message', '')}",
                                    'timestamp': time.time(),
                                    'display_name': display_name,
                                    'dataType': thread_data_type,
                                    'logs': []
                                }, f)
                        except Exception as e:
                            logger.error(f"Error updating error status: {e}")
                except filelock.Timeout:
                    logger.error(f"Could not acquire lock for status file: {status_file}")
        except Exception as inner_e:
            # Log the exception
            thread_logger.error(f"Inner exception during DEM download: {str(inner_e)}")
            
            # Re-raise to be caught by outer exception handler
            raise inner_e
        finally:
            # Always remove the handler
            thread_logger.removeHandler(status_handler)
    except Exception as e:
        logger.exception(f"Error in fetch_dem_thread: {e}")
        # Try to update the status file with the error
        try:
            with lock:
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'error',
                            'message': f"Error: {str(e)}",
                            'timestamp': time.time(),
                            'display_name': dem_name or dem_type,
                            'dataType': data_type,
                            'logs': []
                        }, f)
                except Exception as se:
                    logger.error(f"Failed to update status file after thread error: {se}")
        except Exception as le:
            logger.error(f"Failed to acquire lock after thread error: {le}")
