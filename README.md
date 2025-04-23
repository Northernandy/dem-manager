# Brisbane Flood Visualization Project

A web-based visualization tool for Brisbane flood data, enabling analysis, forecasting, and risk assessment.

## Project Overview

This project aims to provide an interactive visualization of flood data for Brisbane, Australia. It combines historical data from the Bureau of Meteorology (BOM) and SEQ Water with digital elevation models (DEMs) to create accurate flood visualizations.

### Current Achievements (as of v1.3.5)

- Implemented a robust DEM fetching system with support for both GeoTIFF and RGB visualization formats
- Created a tile-based WebP generation system for optimized map rendering
- Developed a user-friendly interface for DEM management and visualization
- Implemented proper file organization with clear separation between raw data and visualizations
- Fixed critical rendering issues for both raw DEM data and WebP tiles
- Added support for different quality levels of WebP tiles (lossless and lossy compression)
- Successfully integrated the DEM visualization with different base map layers

## Features

- Interactive map-based visualization with multiple base layers (Street and Topographic)
- Digital Elevation Model (DEM) visualization with adjustable opacity
- Support for multiple DEM types and resolutions:
  - 5m LiDAR DEM
  - 1 Second National DEM (~30m resolution)
- Custom naming for DEM files with automatic numbering to prevent conflicts
- Enhanced slider UI for map settings and opacity controls
- Address search functionality using Nominatim API
- DEM management interface for fetching, viewing, and deleting elevation data
- REST API endpoints for DEM operations
- WebP tile generation for optimized map rendering
- Comprehensive logging and error handling

## Project Structure

```
brisbane-flood-viz/
├── app/                     # Flask backend
│   ├── static/              # Static web assets
│   │   ├── css/             # Stylesheet files
│   │   │   ├── admin.css    # Admin interface styles
│   │   │   └── style.css    # Main application styles
│   │   ├── js/              # JavaScript files
│   │   │   ├── main.js      # Main application logic
│   │   │   └── settings.js  # Settings page functionality
│   │   └── dem/             # Sample DEM files
│   ├── templates/           # HTML templates
│   │   ├── admin_base.html  # Admin layout template
│   │   ├── index.html       # Main map page
│   │   ├── logs.html        # Log viewer
│   │   └── settings.html    # DEM management page
│   ├── app.py               # Flask application entry point
│   ├── dem_metadata.py      # DEM metadata handling
│   └── dem_operations.py    # DEM file operations
├── data/                    # Data storage
│   ├── geo/                 # DEM files and visualizations
│   │   ├── metadata/        # DEM metadata
│   │   ├── tiles/           # Tile storage
│   │   └── *_tiles_*/       # WebP tile directories
│   ├── raw/                 # Raw data storage
│   ├── processed/           # Processed data
│   └── test/                # Test data
├── docs/                    # Documentation
│   └── dem_fetching_system.md  # DEM fetching system documentation
├── logs/                    # Application logs
├── notebooks/               # Jupyter notebooks
├── src/                     # Core application logic
│   ├── pipeline/            # Data processing pipeline
│   │   ├── dem_fetcher.py   # DEM fetching coordination
│   │   ├── wcs_geotiff_handler.py  # GeoTIFF data handler
│   │   ├── wms_rgb_handler.py      # RGB visualization handler
│   │   └── dem_generate_webp_tiles.py  # WebP tile generation
│   ├── modeling/            # Data modeling components
│   └── raster/              # Raster data processing
├── archive/                 # Archived files and backups
├── requirements.txt         # Python dependencies
└── version.txt              # Current version number
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/Northernandy/dem-manager.git
   cd dem-manager
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   # On Windows
   .venv\Scripts\activate
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create necessary directories (if they don't exist):
   ```
   # On Windows
   mkdir -p data\geo data\raw data\processed logs
   # On macOS/Linux
   mkdir -p data/geo data/raw data/processed logs
   ```

## Usage

### Running the Flask Application

```
# Navigate to the project directory
cd brisbane-flood-viz

# Activate the virtual environment (if not already activated)
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Run the Flask application
python app/app.py
```

The application will be available at `http://localhost:5000`.

### Logging

The application maintains logs in the `logs/app.log` file. These logs include:
- DEM fetching operations and status
- API requests and responses
- Error messages and exceptions
- Application startup and shutdown events

### DEM Management

1. **Fetching DEMs**: Select a DEM type, specify a bounding box, and click "Fetch DEM Data"
2. **Viewing DEMs**: Available DEMs are displayed as cards with metadata
3. **Using DEMs**: Select a DEM from the dropdown on the main map page
4. **Deleting DEMs**: Remove unwanted DEMs using the delete button
5. **WebP Tiles**: The system automatically generates WebP tiles for optimized rendering

### Map Controls

- **DEM Layer Selection**: Choose from available DEMs in the dropdown
- **Layer Toggle**: Enable/disable the DEM layer
- **Opacity Control**: Adjust the transparency of the DEM layer
- **Address Search**: Find locations within Brisbane and surrounding areas
- **Base Layer Selection**: Switch between Street and Topographic views

## Data Sources

- [Geoscience Australia](https://www.ga.gov.au/) - DEM data via REST services
  - [Geoscience Australia Services Portal](https://services.ga.gov.au/) - REST API services for geospatial data
  - [ELVIS - Elevation Information System](https://elevation.fsdf.org.au/) - National elevation data portal
- [Bureau of Meteorology (BOM)](http://www.bom.gov.au/) - Weather and flood data
- [SEQ Water](https://www.seqwater.com.au/) - Dam levels and releases
- [Queensland Spatial Catalogue](https://qldspatial.information.qld.gov.au/) - Additional spatial data

## Development Approach

This project follows an incremental, careful development approach where stability and reliability are prioritized. Changes are made in small, tested increments to ensure functionality is preserved while new features are added.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

[MIT License](LICENSE)

## Contact

For questions or support, please open an issue in the GitHub repository.
