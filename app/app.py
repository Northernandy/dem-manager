from flask import Flask, render_template, jsonify, request
import os
import json
from datetime import datetime, timedelta
import random
import sys

# Add the project root to the Python path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the DEM fetcher
from src.pipeline.dem_fetcher import fetch_dem

app = Flask(__name__)

@app.route('/')
def index():
    """Render the main visualization page."""
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    """API endpoint to retrieve flood data."""
    # This will be expanded to load actual data from the processed directory
    sample_data = {
        'message': 'Brisbane Flood Visualization API',
        'status': 'operational'
    }
    return jsonify(sample_data)

@app.route('/api/flood-data')
def get_flood_data():
    """API endpoint to retrieve flood data for a specific date and layer type."""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    layer_type = request.args.get('layer', 'flood-extent')
    
    # In production, this would query actual data from Parquet files or a database
    # For now, return sample data
    return jsonify({
        'date': date,
        'layer_type': layer_type,
        'data_source': 'Sample Data',
        'data_available': True,
        'message': f'Retrieved {layer_type} data for {date}'
    })

@app.route('/api/fetch-dem')
def fetch_dem_data():
    """API endpoint to fetch DEM data from Geoscience Australia."""
    try:
        # Get parameters from the request
        bbox = request.args.get('bbox')
        if bbox:
            # Parse bbox from string to tuple
            bbox = tuple(map(float, bbox.split(',')))
        
        resolution = request.args.get('resolution')
        if resolution:
            resolution = float(resolution)
        else:
            resolution = 5  # Default 5m resolution
        
        # Define output paths
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'geo')
        output_file = os.path.join(output_dir, "brisbane_dem.tif")
        
        # Check if the file already exists
        if os.path.exists(output_file):
            return jsonify({
                'success': True,
                'message': 'DEM data already exists',
                'file': output_file,
                'resolution': f"{resolution}",
                'coverage': 'Brisbane Area',
                'url': f'/static/dem/brisbane_dem.tif'
            })
        
        # Create data/geo directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # For wider Brisbane area including Ipswich and Wivenhoe Dam
        if bbox is None:
            bbox = (152.0, -28.0, 153.5, -27.0)  # Much wider Brisbane catchment area
            
        # Run the DEM fetcher
        try:
            success = fetch_dem(bbox, resolution, output_dir, output_file)
            
            if success:
                # Copy the DEM file to a location accessible by the web server
                static_dem_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'dem')
                if not os.path.exists(static_dem_dir):
                    os.makedirs(static_dem_dir)
                    
                import shutil
                static_dem_file = os.path.join(static_dem_dir, "brisbane_dem.tif")
                shutil.copy2(output_file, static_dem_file)
                
                return jsonify({
                    'success': True,
                    'message': 'Successfully fetched DEM data',
                    'file': output_file,
                    'resolution': f"{resolution}",
                    'coverage': 'Brisbane Area',
                    'url': f'/static/dem/brisbane_dem.tif'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to fetch DEM data'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error fetching DEM data: {str(e)}'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@app.route('/api/locations')
def search_locations():
    """API endpoint to search for locations (proxy for Nominatim to avoid CORS issues)."""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    # In production, this would proxy to Nominatim or use a local geocoding service
    # For now, return a sample response
    return jsonify([{
        'place_id': 12345,
        'lat': '-27.470125',
        'lon': '153.021072',
        'display_name': f'Sample result for: {query}, Brisbane, Queensland, Australia'
    }])

@app.route('/api/timeseries')
def get_timeseries():
    """API endpoint to retrieve time series data for a specific location."""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        return jsonify({'error': 'Latitude and longitude are required'}), 400
    
    # Generate sample time series data (7 days)
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    
    # Sample data for water levels
    water_levels = [round(random.uniform(0.5, 3.5), 2) for _ in range(7)]
    
    return jsonify({
        'location': {'lat': lat, 'lon': lon},
        'dates': dates,
        'water_levels': water_levels,
        'unit': 'meters'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
