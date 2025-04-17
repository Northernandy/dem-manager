from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import os
import json
import uuid
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
import sys
import glob
import shutil
import time
import gc
import subprocess
import rasterio

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the DEM fetcher
try:
    from src.pipeline.wcs_geotiff_handler import fetch_geotiff_dem
    from src.pipeline.wms_rgb_handler import fetch_rgb_dem
    
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
    
    logger.info("Successfully imported DEM handlers")
except ImportError as e:
    logger.warning(f"Could not import DEM handlers: {e}")
    # Define placeholder function if import fails
    def fetch_dem(bbox, dem_type, data_type, resolution=None, output_file=None):
        return {'success': False, 'message': 'DEM Fetcher not fully implemented yet.'}

# Set up file logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
file_handler = logging.FileHandler(os.path.join(log_dir, 'app.log'))
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Configure root logger to use the same handlers
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if not root_logger.handlers:
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(console_handler)
    # Add file handler
    root_logger.addHandler(file_handler)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'brisbane_flood_viz_secret_key'  # For session management

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEM_DIR = os.path.join(BASE_DIR, 'data', 'geo')
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

# Create directories if they don't exist
os.makedirs(DEM_DIR, exist_ok=True)

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

# Routes
@app.route('/')
def index():
    """Render the main application page."""
    dems = get_available_dems()
    return render_template('index.html', dems=dems, now=int(time.time()))

@app.route('/settings')
def settings():
    """Render the settings page."""
    dems = get_available_dems()
    dem_types = DEM_TYPES
    return render_template('settings.html', dems=dems, dem_types=dem_types, now=int(time.time()))

@app.route('/api/get-dem/<dem_id>')
def get_dem(dem_id):
    """Get information about a specific DEM."""
    dems = get_available_dems()
    
    # Find the DEM with the specified ID
    dem = next((d for d in dems if d['id'] == dem_id), None)
    
    if dem:
        # Add URL to the DEM file for the frontend to access
        dem_filename = dem['name']
        dem['url'] = f'/dem/{dem_filename}'
        return jsonify({'success': True, 'dem': dem})
    else:
        return jsonify({'success': False, 'message': 'DEM not found'})

@app.route('/dem/<filename>')
def serve_dem(filename):
    """Serve a DEM file."""
    file_path = os.path.join(DEM_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Determine content type based on file extension
    content_type = 'image/tiff'
    if filename.lower().endswith('.png'):
        content_type = 'image/png'
    
    return send_file(file_path, mimetype=content_type)

@app.route('/api/fetch-dem', methods=['POST'])
def fetch_dem_api():
    """Fetch a DEM based on the specified parameters."""
    try:
        # Get parameters from the request
        data = request.json
        dem_type = data.get('dem_type', 'lidar_5m')
        dem_name = data.get('dem_name', '')  # Get the DEM name from the request
        data_type = data.get('dataType', 'rgb').lower() 

        if data_type not in ['rgb', 'raw']:
             logger.error(f"Invalid dataType requested: {data_type}. Must be 'rgb' or 'raw'.")
             return jsonify({'success': False, 'message': "Invalid dataType requested. Must be 'rgb' or 'raw'."})

        logger.info(f"DEM fetch request: type={dem_type}, name={dem_name}, dataType={data_type}, data={data}")
        
        # Get DEM type configuration
        dem_config = DEM_TYPES.get(dem_type)
        if not dem_config:
            logger.error(f"Unknown DEM type requested: {dem_type}")
            return jsonify({'success': False, 'message': f'Unknown DEM type: {dem_type}'})
        
        # Get resolution from DEM type configuration
        target_res_meters = dem_config.get('resolution', 5)  # Default to 5m if not specified
        
        # Get bounding box (default to Brisbane area if not specified)
        bbox = data.get('bbox', (152.0, -28.0, 153.5, -27.0))
        
        # Validate bbox
        if len(bbox) != 4:
            logger.error(f"Invalid bounding box: {bbox}")
            return jsonify({'success': False, 'message': 'Invalid bounding box format. Must be [minX, minY, maxX, maxY]'})
        
        try:
            bbox = tuple(float(coord) for coord in bbox)
        except (ValueError, TypeError):
            logger.error(f"Invalid bounding box coordinates: {bbox}")
            return jsonify({'success': False, 'message': 'Invalid bounding box coordinates. Must be numeric values.'})
        
        # Use appropriate extension based on data type
        file_extension = '.tif' if data_type == 'raw' else '.png'
        
        bbox_str = '_'.join([str(coord).replace('.', 'p') for coord in bbox])
        base_output_file = f"{dem_type}_{bbox_str}{file_extension}" 
        
        output_file = base_output_file
        output_path = os.path.join(DEM_DIR, output_file)
        
        if os.path.exists(output_path):
            counter = 1
            while True:
                output_file = f"{dem_type}_{bbox_str}_{counter}{file_extension}" 
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
                    'progress': 0,
                    'message': 'Initializing DEM download...',
                    'timestamp': time.time(),
                    'display_name': display_name,
                    'dataType': data_type  
                }, f)
            
            if not os.path.exists(status_file):
                logger.error(f"Failed to create status file: {status_file}")
                return jsonify({'success': False, 'message': 'Failed to create status file', 'status': 'error'})
            
            logger.info(f"Created status file: {status_file}")
        except Exception as e:
            logger.exception(f"Error creating status file: {e}")
            return jsonify({'success': False, 'message': f'Error creating status file: {str(e)}', 'status': 'error'})
        
        logger.info(f"Starting DEM fetch: type={dem_type}, name={dem_name}, dataType={data_type}, bbox={bbox}, output={output_file}")
        
        import threading
        
        def fetch_dem_thread():
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                display_name = status_data.get('display_name', '')
                thread_data_type = status_data.get('dataType', data_type) 

                with open(status_file, 'w') as f:
                    json.dump({
                        'status': 'downloading',
                        'progress': 5,
                        'message': 'Starting DEM download...',
                        'timestamp': time.time(),
                        'display_name': display_name,
                        'dataType': thread_data_type 
                    }, f)
                
                logger.info(f"Thread starting fetch for {output_file} with dataType={thread_data_type}")
                
                # Use our updated fetch_dem function with the correct parameters
                result = fetch_dem(
                    bbox=bbox,
                    dem_type=dem_type,
                    data_type=thread_data_type,
                    resolution=target_res_meters,
                    output_file=output_file
                )
                
                logger.info(f"fetch_dem completed for {output_file} with result: {result}")
                
                # Update status based on the result
                if result.get('success', False):
                    # If successful, update the status file
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'completed',
                            'progress': 100,
                            'message': 'DEM download completed successfully',
                            'timestamp': time.time(),
                            'display_name': display_name,
                            'dataType': thread_data_type,
                            'file_path': result.get('file_path', '')
                        }, f)
                else:
                    # If failed, update the status file with the error message
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'error',
                            'progress': 100,
                            'message': f"Error fetching DEM: {result.get('message', 'Unknown error')}",
                            'timestamp': time.time(),
                            'display_name': display_name,
                            'dataType': thread_data_type
                        }, f)
                
            except Exception as e:
                logger.exception(f"Error in fetch_dem_thread for {output_file}: {e}")
                try:
                    with open(status_file, 'r') as f:
                         status_data = json.load(f)
                    display_name = status_data.get('display_name', '')
                    thread_data_type = status_data.get('dataType', data_type)

                    with open(status_file, 'w') as f:
                         json.dump({
                             'status': 'error', 
                             'progress': 100, 
                             'message': f'Error fetching DEM: {str(e)}',
                             'timestamp': time.time(),
                             'display_name': display_name,
                             'dataType': thread_data_type
                         }, f)
                except Exception as se:
                    logger.error(f"Failed to update status file after thread error for {output_file}: {se}")
        
        thread = threading.Thread(target=fetch_dem_thread)
        thread.start()
        
        logger.info(f"Started background thread for {output_file}")
        
        return jsonify({'success': True, 'filename': output_file, 'status': 'starting'})

    except Exception as e:
        logger.exception("Error in fetch_dem_api")
        return jsonify({'success': False, 'message': f'An unexpected error occurred: {str(e)}', 'status': 'error'})

@app.route('/api/delete-dem/<filename>', methods=['POST'])
def delete_dem(filename):
    """Delete a DEM file."""
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
                            import subprocess
                            subprocess.run(['cmd', '/c', f'del /F "{file_path}"'], 
                                          shell=True, check=True, 
                                          stderr=subprocess.PIPE, 
                                          stdout=subprocess.PIPE)
                        except subprocess.CalledProcessError as cmd_e:
                            return jsonify({
                                'success': False, 
                                'message': f'File is in use by another process. Please close any applications using this DEM and try again. Error: {str(e)}'
                            })
                    else:
                        return jsonify({
                            'success': False, 
                                'message': f'File is in use by another process. Please close any applications using this DEM and try again. Error: {str(e)}'
                            })
            
            status_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json")
            if os.path.exists(status_file):
                try:
                    os.remove(status_file)
                except Exception:
                    logger.warning(f"Could not delete status file: {status_file}")
            
            metadata_dir = os.path.join(DEM_DIR, 'metadata')
            metadata_file = os.path.join(metadata_dir, f"{filename}.json")
            if os.path.exists(metadata_file):
                try:
                    os.remove(metadata_file)
                except Exception:
                    logger.warning(f"Could not delete metadata file: {metadata_file}")
                
            return jsonify({'success': True, 'message': f'DEM {filename} deleted successfully'})
        else:
            return jsonify({'success': False, 'message': f'DEM {filename} not found'})
    except Exception as e:
        logger.exception("Error deleting DEM")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/check-dem-status/<filename>')
def check_dem_status(filename):
    """Check the status of a DEM download."""
    try:
        filename = secure_filename(filename)
        status_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json")
        
        logger.info(f"Checking DEM status for: {filename}")
        
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                logger.info(f"DEM status check for {filename}: {status_data.get('status', 'unknown')} - {status_data.get('progress', 0)}% - {status_data.get('message', 'No message')}")
                
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
                    if status_data.get('status') != 'completed':
                        status_data['status'] = 'completed'
                        status_data['progress'] = 100
                        status_data['message'] = 'DEM download completed successfully'
                        
                        with open(status_file, 'w') as f:
                            json.dump(status_data, f)
                
                # Map status values to what the frontend expects
                status_mapping = {
                    'starting': 'starting',
                    'downloading': 'downloading',
                    'completed': 'complete',
                    'error': 'failed'
                }
                
                # Create a response that matches what the frontend expects
                response = {
                    'success': True,
                    'status': {
                        'status': status_mapping.get(status_data.get('status', 'unknown'), 'unknown'),
                        'progress': status_data.get('progress', 0),
                        'message': status_data.get('message', 'No status message available')
                    },
                    'status_data': status_data
                }
                
                return jsonify(response)
            except Exception as e:
                logger.exception(f"Error reading status file for {filename}")
                return jsonify({
                    'success': False,
                    'message': f"Error reading status file: {str(e)}"
                })
        else:
            # If no status file exists, check if the DEM file exists
            dem_file_path = os.path.join(DEM_DIR, filename)
            if os.path.exists(dem_file_path):
                # File exists but no status file, create a completed status
                file_size_bytes = os.path.getsize(dem_file_path)
                file_size_mb = file_size_bytes / (1024 * 1024)
                
                status_data = {
                    'status': 'completed',
                    'progress': 100,
                    'message': 'DEM file exists',
                    'timestamp': time.time(),
                    'file_path': dem_file_path,
                    'file_size': {
                        'bytes': file_size_bytes,
                        'mb': round(file_size_mb, 2),
                        'formatted': f"{file_size_mb:.2f} MB"
                    }
                }
                
                # Create a response that matches what the frontend expects
                response = {
                    'success': True,
                    'status': {
                        'status': 'complete',
                        'progress': 100,
                        'message': 'DEM file exists'
                    },
                    'status_data': status_data
                }
                
                return jsonify(response)
            else:
                logger.warning(f"No status file or DEM file found for {filename}")
                return jsonify({
                    'success': False,
                    'message': f"No status information available for {filename}"
                })
    except Exception as e:
        logger.exception(f"Error checking DEM status for {filename}")
        return jsonify({
            'success': False,
            'message': f"Error checking DEM status: {str(e)}"
        })

@app.route('/api/rename-dem', methods=['POST'])
def rename_dem():
    """Rename a DEM (update display name)."""
    try:
        data = request.json
        filename = data.get('filename')
        new_display_name = data.get('display_name')
        
        if not filename or not new_display_name:
            return jsonify({'success': False, 'message': 'Missing filename or display name'})
        
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
        
        return jsonify({'success': True, 'message': 'DEM renamed successfully'})
    except Exception as e:
        logger.exception("Error renaming DEM")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/list-dems')
def list_dems():
    """List all available DEMs."""
    dems = get_available_dems()
    return jsonify({'success': True, 'dems': dems})

@app.route('/api/log', methods=['POST'])
def log_client_message():
    """Log a message from the client."""
    try:
        log_data = request.json
        
        if not log_data or not isinstance(log_data, dict):
            return jsonify({'success': False, 'message': 'Invalid log data'})
        
        level = log_data.get('level', 'info').upper()
        message = log_data.get('message', 'No message provided')
        data = log_data.get('data')
        
        log_message = f"CLIENT LOG: {message}"
        if data:
            if isinstance(data, dict) or isinstance(data, list):
                data_str = json.dumps(data)
            else:
                data_str = str(data)
            log_message += f" | Data: {data_str}"
        
        if level == 'ERROR':
            logger.error(log_message)
        elif level == 'WARNING':
            logger.warning(log_message)
        elif level == 'DEBUG':
            logger.debug(log_message)
        else:  
            logger.info(log_message)
        
        client_log_file = os.path.join(log_dir, 'client_logs.json')
        
        client_logs = []
        if os.path.exists(client_log_file):
            try:
                with open(client_log_file, 'r') as f:
                    client_logs = json.load(f)
            except json.JSONDecodeError:
                client_logs = []
        
        log_data['server_timestamp'] = time.time()
        client_logs.append(log_data)
        
        if len(client_logs) > 1000:
            client_logs = client_logs[-1000:]
        
        with open(client_log_file, 'w') as f:
            json.dump(client_logs, f)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error logging client message")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logs')
def get_logs():
    """Get client logs."""
    try:
        client_log_file = os.path.join(log_dir, 'client_logs.json')
        
        if not os.path.exists(client_log_file):
            return jsonify({'success': True, 'logs': []})
        
        with open(client_log_file, 'r') as f:
            logs = json.load(f)
        
        logs.reverse()
        
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        logger.exception("Error retrieving logs")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/system-info')
def get_system_info():
    """Get system information to help with debugging."""
    try:
        import platform
        import psutil
        
        system_info = {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'processor': platform.processor(),
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent
            },
            'disk': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free,
                'percent': psutil.disk_usage('/').percent
            }
        }
        
        open_files = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'open_files']):
                for file in proc.info.get('open_files') or []:
                    if DEM_DIR in file.path:
                        open_files.append({
                            'path': file.path,
                            'process_name': proc.info['name'],
                            'pid': proc.info['pid']
                        })
        except Exception as e:
            open_files = [f"Error getting open files: {str(e)}"]
        
        system_info['open_dem_files'] = open_files
        
        return jsonify({'success': True, 'system_info': system_info})
    except Exception as e:
        logger.exception("Error getting system info")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/file-locks/<filename>')
def check_file_locks(filename):
    """Check what processes are locking a specific file."""
    try:
        filename = secure_filename(filename)
        file_path = os.path.join(DEM_DIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': f'File {filename} not found'})
        
        import psutil
        import platform
        
        locks_info = {
            'filename': filename,
            'path': file_path,
            'size': os.path.getsize(file_path),
            'last_modified': time.ctime(os.path.getmtime(file_path)),
            'processes': [],
            'system': platform.system()
        }
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline', 'open_files']):
            try:
                proc_info = proc.info
                open_files = proc_info.get('open_files', [])
                
                if open_files:
                    for open_file in open_files:
                        if open_file and hasattr(open_file, 'path') and file_path.lower() in open_file.path.lower():
                            locks_info['processes'].append({
                                'pid': proc_info['pid'],
                                'name': proc_info['name'],
                                'username': proc_info.get('username', 'unknown'),
                                'cmdline': ' '.join(proc_info.get('cmdline', [])),
                                'file_mode': getattr(open_file, 'mode', 'unknown')
                            })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if platform.system() == 'Windows':
            try:
                import subprocess
                handle_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools', 'handle.exe')
                
                if os.path.exists(handle_path):
                    cmd = [handle_path, file_path, '/accepteula']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        locks_info['handle_output'] = result.stdout
                    else:
                        locks_info['handle_error'] = result.stderr
                else:
                    locks_info['handle_status'] = 'handle.exe not found'
            except Exception as e:
                locks_info['handle_error'] = str(e)
        
        try:
            with open(file_path, 'rb') as f:
                f.read(1)
            locks_info['can_open'] = True
        except Exception as e:
            locks_info['can_open'] = False
            locks_info['open_error'] = str(e)
        
        return jsonify({'success': True, 'locks_info': locks_info})
    except Exception as e:
        logger.exception(f"Error checking file locks for {filename}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/logs')
def view_logs():
    """Render the logs viewer page."""
    return render_template('logs.html')

@app.route('/api/logs/app')
def get_app_logs():
    """Get application logs."""
    try:
        log_file = os.path.join(log_dir, 'app.log')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = f.readlines()
            logs = logs[-1000:]
            return jsonify({'success': True, 'logs': logs})
        else:
            return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        logger.exception(f"Error retrieving app logs")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logs/dem')
def get_dem_logs():
    """Get DEM-specific logs."""
    try:
        log_file = os.path.join(log_dir, 'app.log')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                all_logs = f.readlines()
            
            dem_logs = [log for log in all_logs if any(term in log.lower() for term in 
                       ['dem', 'fetch', 'download', 'chunk', 'geotiff', 'export', 'service'])]
            
            dem_logs = dem_logs[-1000:]
            return jsonify({'success': True, 'logs': dem_logs})
        else:
            return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        logger.exception(f"Error retrieving DEM logs")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get-dem-bounds/<dem_id>', methods=['GET'])
def get_dem_bounds(dem_id):
    """Get the bounds for a specific DEM file."""
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
                                        from PIL import Image
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
                
                # Check for a status file to get the display name
                status_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json")
                display_name = DEM_TYPES.get(dem_type, {}).get('name', 'Unknown DEM')
                
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
