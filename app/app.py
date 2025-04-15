from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import os
import json
import uuid
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import sys
import glob
import shutil
import time
import gc
import subprocess

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the DEM fetcher
from src.pipeline.dem_fetcher import DEMFetcher, fetch_dem

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    return send_from_directory(DEM_DIR, filename)

@app.route('/api/fetch-dem', methods=['POST'])
def fetch_dem_api():
    """Fetch a DEM based on the specified parameters."""
    try:
        # Get parameters from the request
        data = request.json
        dem_type = data.get('dem_type', 'lidar_5m')
        dem_name = data.get('dem_name', '')  # Get the DEM name from the request
        
        # Log the request
        logger.info(f"DEM fetch request: type={dem_type}, name={dem_name}, data={data}")
        
        # Get DEM type configuration
        dem_config = DEM_TYPES.get(dem_type)
        if not dem_config:
            logger.error(f"Unknown DEM type requested: {dem_type}")
            return jsonify({'success': False, 'message': f'Unknown DEM type: {dem_type}'})
        
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
        
        # Generate a unique filename based on the DEM type and bounding box
        bbox_str = '_'.join([str(coord).replace('.', 'p') for coord in bbox])
        base_output_file = f"{dem_type}_{bbox_str}.tif"
        
        # Check if the file already exists and generate a unique name if needed
        output_file = base_output_file
        output_path = os.path.join(DEM_DIR, output_file)
        
        # If the file already exists, append a number to make it unique
        if os.path.exists(output_path):
            # Instead of returning the existing file, create a new one with a number appended
            counter = 1
            while True:
                output_file = f"{dem_type}_{bbox_str}_{counter}.tif"
                output_path = os.path.join(DEM_DIR, output_file)
                if not os.path.exists(output_path):
                    break
                counter += 1
            
            logger.info(f"Generated unique filename for new DEM: {output_file}")
        
        # Create a status file to track progress
        status_file = os.path.join(DEM_DIR, f"{os.path.splitext(output_file)[0]}_status.json")
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        
        # Initialize status file with explicit permissions
        try:
            # Format initial display name to include DEM type if user provided a name
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
                    'display_name': display_name  # Store the formatted display name in the status file
                }, f)
            
            # Verify the status file was created
            if not os.path.exists(status_file):
                logger.error(f"Failed to create status file: {status_file}")
                return jsonify({'success': False, 'message': 'Failed to create status file', 'status': 'error'})
            
            logger.info(f"Created status file: {status_file}")
        except Exception as e:
            logger.exception(f"Error creating status file: {e}")
            return jsonify({'success': False, 'message': f'Error creating status file: {str(e)}', 'status': 'error'})
        
        logger.info(f"Starting DEM fetch: type={dem_type}, name={dem_name}, bbox={bbox}, output={output_file}")
        
        # Fetch the DEM in a separate thread to avoid blocking
        import threading
        
        def fetch_dem_thread():
            try:
                # Update status to downloading
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                # Preserve the display_name from the original status file
                display_name = status_data.get('display_name', '')
                
                with open(status_file, 'w') as f:
                    json.dump({
                        'status': 'downloading',
                        'progress': 5,
                        'message': 'Starting DEM download...',
                        'timestamp': time.time(),
                        'display_name': display_name  # Preserve the display name
                    }, f)
                
                logger.info(f"Updated status file to downloading: {status_file}")
                
                success = fetch_dem(
                    bbox=bbox,
                    target_res_meters=dem_config['resolution'],
                    output_dir=DEM_DIR,
                    output_file=output_path,
                    rest_url=dem_config['url'],
                    status_file=status_file
                )
                
                if success:
                    # Create metadata with the DEM name if provided
                    if dem_name:
                        # Create metadata directory if it doesn't exist
                        metadata_dir = os.path.join(DEM_DIR, 'metadata')
                        os.makedirs(metadata_dir, exist_ok=True)
                        
                        # Create metadata file
                        metadata_file = os.path.join(metadata_dir, f"{output_file}.json")
                        
                        # Format initial display name to include DEM type if user provided a name
                        display_name = dem_name
                        if dem_name:
                            display_name = f"{dem_name} ({dem_config['name']})"
                        else:
                            display_name = dem_config['name']
                        
                        with open(metadata_file, 'w') as f:
                            json.dump({
                                'display_name': display_name,
                                'created_at': time.time(),
                                'dem_type': dem_type,
                                'bbox': bbox,
                                'resolution': dem_config['resolution']
                            }, f)
                        
                        logger.info(f"Created metadata for DEM: {output_file} with name: {display_name}")
                else:
                    # Update status file with failure if fetch_dem returns False
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'failed',
                            'progress': 0,
                            'message': 'Failed to fetch DEM. Check logs for details.',
                            'timestamp': time.time()
                        }, f)
                    logger.error(f"DEM fetch failed for {output_file}")
            except Exception as e:
                # Handle any exceptions in the thread
                logger.exception(f"Exception in DEM fetch thread: {e}")
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'failed',
                            'progress': 0,
                            'message': f'Error fetching DEM: {str(e)}',
                            'timestamp': time.time()
                        }, f)
                except Exception as write_error:
                    logger.error(f"Failed to write error to status file: {write_error}")
        
        # Start the fetch in a background thread
        thread = threading.Thread(target=fetch_dem_thread)
        thread.daemon = True
        thread.start()
        
        # Return immediately with the status file info
        return jsonify({
            'success': True,
            'message': 'DEM fetch started',
            'file': output_file,
            'resolution': dem_config['resolution'],
            'coverage': f"{bbox[0]},{bbox[1]} to {bbox[2]},{bbox[3]}",
            'status': 'starting',
            'display_name': dem_name
        })
            
    except Exception as e:
        logger.exception(f"Error in fetch_dem_api: {e}")
        return jsonify({'success': False, 'message': str(e), 'status': 'error'})

@app.route('/api/delete-dem/<filename>', methods=['POST'])
def delete_dem(filename):
    """Delete a DEM file."""
    try:
        # Secure the filename to prevent directory traversal
        filename = secure_filename(filename)
        file_path = os.path.join(DEM_DIR, filename)
        
        # Check if the file exists
        if os.path.exists(file_path):
            try:
                # Try to delete the file
                os.remove(file_path)
            except PermissionError as e:
                # If file is in use, try to force close it (Windows-specific)
                logger.info(f"File {filename} is in use, attempting to force close...")
                
                # Force garbage collection to release file handles
                gc.collect()
                
                # Try again after a short delay
                time.sleep(0.5)
                
                try:
                    os.remove(file_path)
                except Exception as inner_e:
                    # If still can't delete, try using Windows-specific solution
                    if os.name == 'nt':  # Windows
                        try:
                            import subprocess
                            # Use del command with force option
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
            
            # Also delete status file if it exists
            status_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json")
            if os.path.exists(status_file):
                try:
                    os.remove(status_file)
                except Exception:
                    logger.warning(f"Could not delete status file: {status_file}")
            
            # Also delete metadata file if it exists
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
        # Secure the filename to prevent directory traversal
        filename = secure_filename(filename)
        status_file = os.path.join(DEM_DIR, f"{os.path.splitext(filename)[0]}_status.json")
        
        logger.info(f"Checking DEM status for: {filename}")
        
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                # Log the status check
                logger.info(f"DEM status check for {filename}: {status_data['status']} - {status_data['progress']}% - {status_data['message']}")
                
                # Add additional information if available
                if os.path.exists(os.path.join(DEM_DIR, filename)):
                    dem_file_path = os.path.join(DEM_DIR, filename)
                    file_size_bytes = os.path.getsize(dem_file_path)
                    file_size_mb = file_size_bytes / (1024 * 1024)
                    
                    # Add file size information to the status
                    status_data['file_size'] = {
                        'bytes': file_size_bytes,
                        'mb': round(file_size_mb, 2),
                        'formatted': f"{file_size_mb:.2f} MB"
                    }
                    
                    # If the file exists but status is still in progress, it might be the final processing
                    if status_data['status'] not in ['complete', 'failed']:
                        status_data['message'] += f" (Current file size: {file_size_mb:.2f} MB)"
                
                return jsonify({'success': True, 'status': status_data})
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing status file for {filename}: {e}")
                return jsonify({'success': False, 'message': f'Error reading status file: {e}', 'status': 'error'})
        else:
            # Check if the actual DEM file exists
            dem_file = os.path.join(DEM_DIR, filename)
            if os.path.exists(dem_file):
                # Get file size information
                file_size_bytes = os.path.getsize(dem_file)
                file_size_mb = file_size_bytes / (1024 * 1024)
                
                status_data = {
                    'status': 'complete', 
                    'progress': 100, 
                    'message': f'DEM download complete: {file_size_mb:.2f} MB file created',
                    'file_size': {
                        'bytes': file_size_bytes,
                        'mb': round(file_size_mb, 2),
                        'formatted': f"{file_size_mb:.2f} MB"
                    }
                }
                
                logger.info(f"DEM status check for {filename}: complete - file exists ({file_size_mb:.2f} MB)")
                return jsonify({'success': True, 'status': status_data})
            else:
                logger.warning(f"DEM status check for {filename}: status file not found and DEM file does not exist")
                return jsonify({
                    'success': False, 
                    'message': 'Status file not found and DEM file does not exist',
                    'status': 'failed'
                })
    except Exception as e:
        logger.exception(f"Error checking DEM status for {filename}")
        return jsonify({'success': False, 'message': str(e), 'status': 'error'})

@app.route('/api/rename-dem', methods=['POST'])
def rename_dem():
    """Rename a DEM (update display name)."""
    try:
        data = request.json
        filename = data.get('filename')
        new_display_name = data.get('display_name')
        
        if not filename or not new_display_name:
            return jsonify({'success': False, 'message': 'Missing filename or display name'})
        
        # Create metadata directory if it doesn't exist
        metadata_dir = os.path.join(DEM_DIR, 'metadata')
        os.makedirs(metadata_dir, exist_ok=True)
        
        # Create or update metadata file
        metadata_file = os.path.join(metadata_dir, f"{filename}.json")
        
        metadata = {}
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        
        # Simply update the display name without appending any additional information
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
        
        # Validate log data
        if not log_data or not isinstance(log_data, dict):
            return jsonify({'success': False, 'message': 'Invalid log data'})
        
        # Extract log information
        level = log_data.get('level', 'info').upper()
        message = log_data.get('message', 'No message provided')
        data = log_data.get('data')
        
        # Format the log message
        log_message = f"CLIENT LOG: {message}"
        if data:
            # Convert data to string if it's not already
            if isinstance(data, dict) or isinstance(data, list):
                data_str = json.dumps(data)
            else:
                data_str = str(data)
            log_message += f" | Data: {data_str}"
        
        # Log with appropriate level
        if level == 'ERROR':
            logger.error(log_message)
        elif level == 'WARNING':
            logger.warning(log_message)
        elif level == 'DEBUG':
            logger.debug(log_message)
        else:  # Default to INFO
            logger.info(log_message)
        
        # Also save to client logs file
        client_log_file = os.path.join(log_dir, 'client_logs.json')
        
        # Load existing logs or create new log array
        client_logs = []
        if os.path.exists(client_log_file):
            try:
                with open(client_log_file, 'r') as f:
                    client_logs = json.load(f)
            except json.JSONDecodeError:
                # File exists but is not valid JSON, start fresh
                client_logs = []
        
        # Add new log entry with server timestamp
        log_data['server_timestamp'] = time.time()
        client_logs.append(log_data)
        
        # Keep only the last 1000 logs
        if len(client_logs) > 1000:
            client_logs = client_logs[-1000:]
        
        # Write back to file
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
        # Check if user is authorized (you might want to add proper authentication)
        client_log_file = os.path.join(log_dir, 'client_logs.json')
        
        if not os.path.exists(client_log_file):
            return jsonify({'success': True, 'logs': []})
        
        with open(client_log_file, 'r') as f:
            logs = json.load(f)
        
        # Return the most recent logs first
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
        
        # Get basic system info
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
        
        # Get open files in the DEM directory
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
        # Secure the filename to prevent directory traversal
        filename = secure_filename(filename)
        file_path = os.path.join(DEM_DIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': f'File {filename} not found'})
        
        # Get information about processes that might be locking the file
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
        
        # Try to find processes that have this file open
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline', 'open_files']):
            try:
                proc_info = proc.info
                open_files = proc_info.get('open_files', [])
                
                # Check if any of the open files match our target
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
        
        # If on Windows, try using handle.exe if available (Sysinternals)
        if platform.system() == 'Windows':
            try:
                import subprocess
                handle_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools', 'handle.exe')
                
                if os.path.exists(handle_path):
                    # Run handle.exe to find processes with handles to this file
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
        
        # Try to open the file to see if it's actually locked
        try:
            with open(file_path, 'rb') as f:
                # Read a small part of the file
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
            # Return the most recent logs first (up to 1000 lines)
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
            
            # Filter for DEM-related logs
            dem_logs = [log for log in all_logs if any(term in log.lower() for term in 
                       ['dem', 'fetch', 'download', 'chunk', 'geotiff', 'export', 'service'])]
            
            # Return the most recent logs first (up to 1000 lines)
            dem_logs = dem_logs[-1000:]
            return jsonify({'success': True, 'logs': dem_logs})
        else:
            return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        logger.exception(f"Error retrieving DEM logs")
        return jsonify({'success': False, 'message': str(e)})

def get_available_dems():
    """Get a list of available DEM files with metadata."""
    dems = []
    
    # Create metadata directory if it doesn't exist
    metadata_dir = os.path.join(DEM_DIR, 'metadata')
    os.makedirs(metadata_dir, exist_ok=True)
    
    # Find all GeoTIFF files in the DEM directory
    for i, tif_file in enumerate(glob.glob(os.path.join(DEM_DIR, '*.tif'))):
        try:
            # Extract filename
            filename = os.path.basename(tif_file)
            
            # Calculate file size in MB
            size_bytes = os.path.getsize(tif_file)
            size_mb = size_bytes / (1024 * 1024)
            
            # Try to determine the DEM type from the filename
            dem_type = None
            for key, config in DEM_TYPES.items():
                if key in filename:
                    dem_type = key
                    break
            
            # If we couldn't determine the type, use a generic description
            if dem_type:
                resolution = DEM_TYPES[dem_type]['resolution']
                description = DEM_TYPES[dem_type]['description']
                type_name = DEM_TYPES[dem_type]['name']
            else:
                # Try to extract resolution from filename
                if '5m' in filename or 'lidar' in filename.lower():
                    resolution = 5
                    type_name = '5m LiDAR DEM'
                elif '1s' in filename or '1sec' in filename:
                    resolution = 30
                    type_name = '1 Second National DEM'
                elif '3s' in filename or '3sec' in filename:
                    resolution = 90
                    type_name = '3 Second National DEM'
                else:
                    resolution = 'Unknown'
                    type_name = 'Custom DEM'
                
                description = 'Custom Digital Elevation Model'
            
            # Try to extract coverage from filename
            coverage = 'Brisbane Area'
            if '_' in filename:
                parts = filename.split('_')
                if len(parts) >= 5:  # Assuming format like dem_type_minx_miny_maxx_maxy.tif
                    try:
                        # Convert from filename format (p instead of .)
                        minx = float(parts[-4].replace('p', '.'))
                        miny = float(parts[-3].replace('p', '.'))
                        maxx = float(parts[-2].replace('p', '.'))
                        maxy = float(parts[-1].split('.')[0].replace('p', '.'))
                        coverage = f"{minx:.2f},{miny:.2f} to {maxx:.2f},{maxy:.2f}"
                    except (ValueError, IndexError):
                        pass
            
            # Load display name from metadata if available
            metadata_file = os.path.join(metadata_dir, f"{filename}.json")
            user_name = ""
            if os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    user_name = metadata.get('display_name', "")
                except Exception as e:
                    logger.error(f"Error reading metadata for {filename}: {e}")
            
            # Use the user-provided display name exactly as stored, or fall back to type_name if none exists
            display_name = user_name if user_name else type_name
            
            dems.append({
                'id': str(i),
                'name': filename,
                'display_name': display_name,
                'user_name': user_name,
                'type_name': type_name,
                'resolution': resolution,
                'coverage': coverage,
                'size': f"{size_mb:.1f} MB",
                'size_bytes': size_bytes,
                'description': description
            })
        except Exception as e:
            logger.exception(f"Error processing DEM file {tif_file}")
    
    # Sort DEMs by size (largest first)
    dems.sort(key=lambda x: x.get('size_bytes', 0), reverse=True)
    
    return dems

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
