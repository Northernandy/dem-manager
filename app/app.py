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

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the DEM fetcher
from src.pipeline.dem_fetcher import DEMFetcher, fetch_dem

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        'name': '5m LiDAR DEM (Brisbane Area)',
        'url': 'https://services.ga.gov.au/gis/rest/services/DEM_LiDAR_5m_2025/MapServer',
        'resolution': 5,
        'description': 'High-resolution 5m LiDAR-derived Digital Elevation Model covering Brisbane and surrounds.'
    },
    'national_1s': {
        'name': '1 Second National DEM',
        'url': 'https://services.ga.gov.au/gis/rest/services/DEM_SRTM_1Second_2024/MapServer',
        'resolution': 30,
        'description': 'National 1 Second (~30m) Digital Elevation Model derived from SRTM with hydrological enforcement.'
    },
    'national_3s': {
        'name': '3 Second National DEM',
        'url': 'https://services.ga.gov.au/gis/rest/services/DEM_SRTM_3second/MapServer',
        'resolution': 90,
        'description': 'National 3 Second (~90m) Digital Elevation Model derived from SRTM.'
    }
}

# Routes
@app.route('/')
def index():
    """Render the main application page."""
    dems = get_available_dems()
    return render_template('index.html', dems=dems)

@app.route('/settings')
def settings():
    """Render the settings page."""
    dems = get_available_dems()
    dem_types = DEM_TYPES
    return render_template('settings.html', dems=dems, dem_types=dem_types)

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
        
        # Get DEM type configuration
        dem_config = DEM_TYPES.get(dem_type)
        if not dem_config:
            return jsonify({'success': False, 'message': f'Unknown DEM type: {dem_type}'})
        
        # Get bounding box (default to Brisbane area if not specified)
        bbox = data.get('bbox', (152.0, -28.0, 153.5, -27.0))
        
        # Generate a unique filename based on the DEM type and bounding box
        bbox_str = '_'.join([str(coord).replace('.', 'p') for coord in bbox])
        output_file = f"{dem_type}_{bbox_str}.tif"
        output_path = os.path.join(DEM_DIR, output_file)
        
        # Check if the file already exists
        if os.path.exists(output_path):
            return jsonify({
                'success': True, 
                'message': 'DEM already exists',
                'file': output_file,
                'resolution': dem_config['resolution'],
                'coverage': f"{bbox[0]},{bbox[1]} to {bbox[2]},{bbox[3]}"
            })
        
        # Fetch the DEM
        success = fetch_dem(
            bbox=bbox,
            target_res_meters=dem_config['resolution'],
            output_dir=DEM_DIR,
            output_file=output_path,
            rest_url=dem_config['url']
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'DEM fetched successfully',
                'file': output_file,
                'resolution': dem_config['resolution'],
                'coverage': f"{bbox[0]},{bbox[1]} to {bbox[2]},{bbox[3]}"
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to fetch DEM'})
            
    except Exception as e:
        logger.exception("Error fetching DEM")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete-dem/<filename>', methods=['POST'])
def delete_dem(filename):
    """Delete a DEM file."""
    try:
        # Secure the filename to prevent directory traversal
        filename = secure_filename(filename)
        file_path = os.path.join(DEM_DIR, filename)
        
        # Check if the file exists
        if os.path.exists(file_path):
            # Delete the file
            os.remove(file_path)
            return jsonify({'success': True, 'message': f'DEM {filename} deleted successfully'})
        else:
            return jsonify({'success': False, 'message': f'DEM {filename} not found'})
    except Exception as e:
        logger.exception("Error deleting DEM")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/list-dems')
def list_dems():
    """List all available DEMs."""
    dems = get_available_dems()
    return jsonify({'success': True, 'dems': dems})

def get_available_dems():
    """Get a list of available DEM files with metadata."""
    dems = []
    
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
                name = DEM_TYPES[dem_type]['name']
            else:
                # Try to extract resolution from filename
                if '5m' in filename or 'lidar' in filename.lower():
                    resolution = 5
                    name = '5m LiDAR DEM'
                elif '1s' in filename or '1sec' in filename:
                    resolution = 30
                    name = '1 Second National DEM'
                elif '3s' in filename or '3sec' in filename:
                    resolution = 90
                    name = '3 Second National DEM'
                else:
                    resolution = 'Unknown'
                    name = 'Custom DEM'
                
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
            
            dems.append({
                'id': str(i),
                'name': filename,
                'display_name': name,
                'resolution': resolution,
                'coverage': coverage,
                'size': f"{size_mb:.1f} MB",
                'description': description
            })
        except Exception as e:
            logger.exception(f"Error processing DEM file {tif_file}")
    
    return dems

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
