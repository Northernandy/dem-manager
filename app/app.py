from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_from_directory, send_file
import os
import json
import logging
import sys
import shutil
import time

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
# Set up file logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Initialize the logger
logger = logging.getLogger(__name__)

# Set up basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'app.log')),
        logging.StreamHandler()
    ]
)

# Import the DEM handlers
try:
    from src.pipeline.wcs_geotiff_handler import fetch_geotiff_dem
    from src.pipeline.wms_rgb_handler import fetch_rgb_dem
    
    # Import DEM metadata functions
    try:
        from app.dem_metadata import get_available_dems, get_dem_bounds
        logger.info("Successfully imported DEM metadata functions")
    except ImportError as e:
        logger.warning(f"Could not import DEM metadata functions: {e}")
    
    # Import DEM operations functions
    try:
        from app.dem_operations import fetch_dem, fetch_dem_api, delete_dem, check_dem_status, rename_dem
        logger.info("Successfully imported DEM operations functions")
    except ImportError as e:
        logger.warning(f"Could not import DEM operations functions: {e}")
except ImportError as e:
    logger.warning(f"Could not import DEM handlers: {e}")

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
def fetch_dem_api_route():
    """Fetch a DEM based on the specified parameters."""
    try:
        # Get parameters from the request
        data = request.json
        return jsonify(fetch_dem_api(data))
    except Exception as e:
        logger.exception("Error in fetch_dem_api_route")
        return jsonify({'success': False, 'message': f'An unexpected error occurred: {str(e)}', 'status': 'error'})

@app.route('/api/delete-dem/<filename>', methods=['POST'])
def delete_dem_route(filename):
    """Delete a DEM file."""
    result = delete_dem(filename)
    return jsonify(result)

@app.route('/api/check-dem-status/<filename>')
def check_dem_status_route(filename):
    """Check the status of a DEM download."""
    result = check_dem_status(filename)
    return jsonify(result)

@app.route('/api/rename-dem', methods=['POST'])
def rename_dem_route():
    """Rename a DEM (update display name)."""
    try:
        data = request.json
        filename = data.get('filename')
        new_display_name = data.get('display_name')
        
        result = rename_dem(filename, new_display_name)
        return jsonify(result)
    except Exception as e:
        logger.exception("Error in rename_dem_route")
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

@app.route('/api/logs/app')
def get_app_logs():
    """Get application logs."""
    try:
        log_file = os.path.join(log_dir, 'app.log')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = f.readlines()
            
            # Return all logs without filtering - let frontend handle filtering
            # Return only the last 1000 entries to avoid excessive payload size
            logs = logs[-1000:]
            return jsonify({'success': True, 'logs': logs})
        else:
            return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        logger.exception(f"Error retrieving app logs")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Clear application logs."""
    try:
        log_file = os.path.join(log_dir, 'app.log')
        if os.path.exists(log_file):
            # Open the file in write mode to clear its contents
            with open(log_file, 'w') as f:
                f.write('')
            logger.info("Log file cleared")
            return jsonify({'success': True, 'message': 'Logs cleared successfully'})
        else:
            return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        logger.exception(f"Error clearing logs")
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

@app.route('/api/logs/filter/status', methods=['GET'])
def get_log_filtering_status():
    """Get the current status of log filtering."""
    return jsonify({
        'success': True,
        'filter_status': False
    })

@app.route('/logs')
def view_logs():
    """Render the logs viewer page."""
    return render_template('logs.html')

@app.route('/api/get-dem-bounds/<dem_id>', methods=['GET'])
def get_dem_bounds_route(dem_id):
    """Get the bounds for a specific DEM file."""
    return get_dem_bounds(dem_id)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
