# Brisbane Flood Visualization Project

A web-based visualization tool for Brisbane flood data, enabling analysis, forecasting, and risk assessment.

## Project Overview

This project aims to provide an interactive visualization of flood data for Brisbane, Australia. It combines historical data from the Bureau of Meteorology (BOM) and SEQ Water with digital elevation models (DEMs) to create accurate flood visualizations and potentially predictive models.

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
- Historical flood data analysis
- Water depth and flow velocity visualization
- Integration with elevation data for accurate flood modeling
- Data pipeline for automated updates from official sources
- Comprehensive logging and error handling

## Project Structure

```
brisbane-flood-viz/
├── app/                     # Flask backend
│   ├── static/              # JS, CSS, Leaflet plugins
│   ├── templates/           # HTML (Jinja2)
│   └── app.py               # Flask entrypoint
├── data/                    # All data files
│   ├── raw/                 # Original CSVs, raster downloads
│   ├── processed/           # Cleaned data, Parquet files
│   └── geo/                 # DEMs, shapefiles, overlays
│       └── metadata/        # Metadata for DEM files
├── logs/                    # Application logs
│   └── app.log              # Main log file
├── notebooks/               # Data exploration and modeling (Jupyter)
├── src/                     # Reusable logic modules
│   ├── pipeline/            # ETL scripts for BOM, SEQ Water, DEM fetching
│   │   └── dem_fetcher.py   # DEM download and processing from Geoscience Australia
│   ├── modeling/            # ML or rule-based forecasting
│   ├── raster/              # DEM processing and flood simulation
│   └── tests/               # Automated tests
│       └── test_dem_fetcher.py  # Tests for DEM fetching functionality
├── tests/                   # Unit tests
├── requirements.txt         # Python dependencies
└── README.md
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/brisbane-flood-viz.git
   cd brisbane-flood-viz
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Running the Flask Application

```
python app/app.py
```

The application will be available at `http://localhost:5000`.

### Logging

The application maintains comprehensive logs in the `logs/app.log` file. These logs include:
- DEM fetching operations and status
- API requests and responses
- Error messages and exceptions
- Application startup and shutdown events

You can view the logs directly or through the application's log viewer interface.

### Running Tests

The project includes a comprehensive test suite built with pytest. To run the tests:

```bash
# Install pytest if you don't have it
pip install pytest

# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test categories
pytest -m dem  # DEM-related tests
pytest -m app  # Flask app tests
pytest -m data  # Data fetching tests

# Run tests in a specific file
pytest tests/pipeline/test_dem_fetcher.py

# Run tests with coverage report
pytest --cov=app --cov=src
```

The test suite includes:
- Unit tests for the DEM fetcher
- API endpoint tests for the Flask application
- Data fetching tests

#### Test Structure
```
tests/
├── conftest.py          # Shared test fixtures and configuration
├── app/                 # Tests for Flask application
│   └── test_routes.py   # Tests for API endpoints
├── pipeline/            # Tests for data pipeline modules
│   ├── test_dem_fetcher.py  # Tests for DEM fetching
│   └── test_data_fetcher.py  # Tests for other data sources
└── fixtures/            # Test data fixtures
```

### DEM Management

1. **Fetching DEMs**: Select a DEM type, specify a bounding box, and click "Fetch DEM Data"
2. **Viewing DEMs**: Available DEMs are displayed as cards with metadata
3. **Using DEMs**: Select a DEM from the dropdown on the main map page
4. **Deleting DEMs**: Remove unwanted DEMs using the delete button

### Map Controls

- **DEM Layer Selection**: Choose from available DEMs in the dropdown
- **Layer Toggle**: Enable/disable the DEM layer
- **Opacity Control**: Adjust the transparency of the DEM layer
- **Address Search**: Find locations within Brisbane and surrounding areas

## Data Sources

- [Geoscience Australia](https://www.ga.gov.au/) - DEM data via REST services
  - [Geoscience Australia Services Portal](https://services.ga.gov.au/) - REST API services for geospatial data
  - [ELVIS - Elevation Information System](https://elevation.fsdf.org.au/) - National elevation data portal
- [Bureau of Meteorology (BOM)](http://www.bom.gov.au/) - Weather and flood data
- [SEQ Water](https://www.seqwater.com.au/) - Dam levels and releases
- [Queensland Spatial Catalogue](https://qldspatial.information.qld.gov.au/) - Additional spatial data

## Deployment

This application can be deployed to Railway or Render for production use.

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
