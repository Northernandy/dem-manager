# DEM Fetching System Documentation

## Overview

The Brisbane Flood Visualization project includes a robust Digital Elevation Model (DEM) fetching system that retrieves elevation data from Geoscience Australia services. The system supports two primary data types:

1. **Raw Elevation Data (GeoTIFF)**: Fetched using Web Coverage Service (WCS)
2. **Visualization Images (RGB)**: Fetched using Web Map Service (WMS)

This document describes the complete flow from user request to file creation, including progress reporting and statistics.

## System Architecture

The DEM fetching system uses a modular architecture with separate handlers for different data types:

```
Frontend (UI) → Flask API → DEM Handlers → File System
```

### Key Components

- **Frontend**: HTML forms and JavaScript for user interaction
- **Flask API**: Routes for handling DEM requests and responses
- **DEM Handlers**: Specialized modules for different data types
  - `wcs_geotiff_handler.py`: Handles raw elevation data (GeoTIFF)
  - `wms_rgb_handler.py`: Handles visualization images (RGB)
- **File System**: Organized storage for DEM files
  - `data/geo/`: Main directory for all DEM files
  - `data/geo/tiles/`: Subdirectory for intermediate tile files

## User Flow: Requesting a DEM

### 1. User Navigates to Settings Page
- User opens the Brisbane Flood Visualization application
- User navigates to the Settings tab
- User sees the DEM Download section

### 2. User Configures DEM Request
- User selects DEM type (lidar_5m or national_1s)
- User enters bounding box coordinates (min/max longitude/latitude)
- User selects data type (Elevation Data .tif or Visualization Image .png)
- User clicks "Download DEM" button

### 3. User Waits for Processing
- User sees a loading indicator
- User sees progress statistics:
  - **For GeoTIFF (raw) data:**
    - Request initiated timestamp
    - Download progress percentage
    - File size being downloaded
    - Estimated time remaining
  
  - **For RGB visualization:**
    - Request initiated timestamp
    - Number of tiles to download (e.g., "Downloading tile 2/9")
    - Current tile coordinates being processed
    - Overall progress percentage
    - Stitching progress status
    - File size of final image

### 4. User Receives Confirmation
- User sees a success message when the DEM is ready
- User sees final statistics:
  - Total processing time
  - Final file size
  - Resolution of the DEM (pixels and geographic units)
  - Bounding box of the downloaded area
- The new DEM appears in the available DEMs list
- User can select and visualize the new DEM

## Backend Implementation Flow

### 1. Frontend Form Submission
- Form data is collected from input fields
- JavaScript creates a request object with:
  - `dem_type`: Selected DEM type (lidar_5m or national_1s)
  - `bbox`: Array of coordinates [min_lon, min_lat, max_lon, max_lat]
  - `data_type`: Selected data type (raw or rgb)
- AJAX POST request is sent to the backend endpoint

### 2. Backend API Endpoint Processing
- Flask route `/fetch_dem` receives the request
- Request parameters are validated
- Based on `data_type`, the appropriate handler is selected:
  - `raw` → `wcs_geotiff_handler.fetch_geotiff_dem()`
  - `rgb` → `wms_rgb_handler.fetch_rgb_dem()`

### 3. Handler Execution
- **For GeoTIFF (raw) data:**
  - `fetch_geotiff_dem()` constructs a WCS request
  - Request is sent to Geoscience Australia WCS service
  - Progress statistics are collected:
    - Start time
    - Download size and progress
    - Response status
  - GeoTIFF file is saved to `data/geo/` directory
  - File is named with pattern: `{dem_type}_{bbox_string}.tif`
  - Final statistics are calculated:
    - Processing time
    - File size
    - DEM resolution and dimensions
    - Elevation range (min/max values)

- **For RGB visualization:**
  - `fetch_rgb_dem()` determines tile configuration
  - Progress statistics are initialized:
    - Start time
    - Total number of tiles
    - Tile grid dimensions
  - Multiple WMS requests are sent for each tile
  - For each tile, progress is updated:
    - Current tile number and coordinates
    - Percentage complete
    - Download size
  - Tiles are saved to `data/geo/tiles/` directory
  - Stitching progress is reported:
    - Stitching start time
    - Image dimensions
    - Memory usage
  - Tiles are stitched into a single PNG image
  - Final image is saved to `data/geo/` directory
  - World file (.pgw) and metadata (.json) are created
  - Files are named with pattern: `{dem_type}_{bbox_string}.png`
  - Final statistics are calculated:
    - Total processing time
    - Number of tiles processed
    - Final image dimensions and resolution
    - File size

### 4. Response Handling
- Handler returns a result object with statistics:
  ```json
  {
    "success": true/false,
    "message": "Success/error message",
    "file_path": "Path to the created file",
    "statistics": {
      "processing_time_seconds": 10.5,
      "file_size_bytes": 1048576,
      "dimensions": {
        "width": 1000,
        "height": 1000
      },
      "resolution": {
        "x_meters_per_pixel": 5.0,
        "y_meters_per_pixel": 5.0
      },
      "bbox": [152.9, -27.5, 153.0, -27.4],
      "elevation_range": {
        "min": 0.0,
        "max": 500.0
      }
    }
  }
  ```
- Flask endpoint returns this result as JSON
- Frontend processes the response:
  - Shows success/error message
  - Displays final statistics
  - Updates the available DEMs list
  - Enables visualization of the new DEM

## File Naming and Storage

### Directory Structure
```
data/
└── geo/
    ├── tiles/                  # Intermediate tile files for RGB visualization
    │   └── tile_SRTM_*_*.png   # Individual tiles
    ├── national_1s_*.tif       # Raw elevation data (GeoTIFF)
    ├── national_1s_*.png       # RGB visualization
    ├── national_1s_*.pgw       # World file for georeferencing
    ├── national_1s_*.json      # Metadata file
    ├── lidar_5m_*.tif          # Raw elevation data (GeoTIFF)
    ├── lidar_5m_*.png          # RGB visualization
    ├── lidar_5m_*.pgw          # World file for georeferencing
    └── lidar_5m_*.json         # Metadata file
```

### File Naming Convention
- **Raw Elevation Data**: `{dem_type}_{bbox_string}.tif`
  - Example: `national_1s_152p9_-27p5_153p0_-27p4.tif`
- **RGB Visualization**: `{dem_type}_{bbox_string}.png`
  - Example: `lidar_5m_152p9_-27p5_153p0_-27p4.png`
- **World File**: `{dem_type}_{bbox_string}.pgw`
- **Metadata**: `{dem_type}_{bbox_string}_info.json`

## API Reference

### Endpoint: `/fetch_dem`

**Method**: POST

**Parameters**:
- `dem_type` (string): Type of DEM to fetch
  - Valid values: `lidar_5m`, `national_1s`
- `bbox` (array): Bounding box coordinates [min_lon, min_lat, max_lon, max_lat]
- `data_type` (string): Type of data to fetch
  - Valid values: `raw`, `rgb`
- `resolution` (integer, optional): Resolution in pixels (default varies by dem_type)

**Response**:
```json
{
  "success": true,
  "message": "Successfully fetched DEM",
  "file_path": "data/geo/national_1s_152p9_-27p5_153p0_-27p4.tif",
  "statistics": {
    "processing_time_seconds": 5.2,
    "file_size_bytes": 1048576,
    "dimensions": {
      "width": 1000,
      "height": 1000
    },
    "resolution": {
      "x_meters_per_pixel": 30.0,
      "y_meters_per_pixel": 30.0
    },
    "bbox": [152.9, -27.5, 153.0, -27.4],
    "elevation_range": {
      "min": 0.0,
      "max": 500.0
    }
  }
}
```

### Endpoint: `/get_available_dems`

**Method**: GET

**Response**:
```json
{
  "dems": [
    {
      "id": 1,
      "name": "national_1s_152p9_-27p5_153p0_-27p4",
      "type": "national_1s",
      "data_type": "Elevation Data",
      "file_path": "data/geo/national_1s_152p9_-27p5_153p0_-27p4.tif",
      "bbox": [152.9, -27.5, 153.0, -27.4],
      "date_created": "2025-04-17T20:47:00",
      "file_size": "1.0 MB",
      "dimensions": "1000x1000"
    },
    {
      "id": 2,
      "name": "lidar_5m_152p9_-27p5_153p0_-27p4",
      "type": "lidar_5m",
      "data_type": "Visualization Image",
      "file_path": "data/geo/lidar_5m_152p9_-27p5_153p0_-27p4.png",
      "bbox": [152.9, -27.5, 153.0, -27.4],
      "date_created": "2025-04-17T20:49:00",
      "file_size": "289.4 KB",
      "dimensions": "1000x1000"
    }
  ]
}
```

## Error Handling

The DEM fetching system includes comprehensive error handling for various scenarios:

1. **Invalid Parameters**:
   - Invalid DEM type
   - Invalid bounding box coordinates
   - Invalid data type

2. **Service Errors**:
   - WCS/WMS service unavailable
   - Authentication failure
   - Rate limiting

3. **Processing Errors**:
   - Tile download failures
   - Stitching errors
   - File system errors

Each error is logged with appropriate context and returned to the frontend with a descriptive message.

## Implementation Notes

### WCS GeoTIFF Handler

The `wcs_geotiff_handler.py` module handles fetching raw elevation data using the Web Coverage Service (WCS) protocol. It:

1. Constructs a WCS GetCoverage request with appropriate parameters
2. Sends the request to the Geoscience Australia WCS service
3. Processes the response and saves the GeoTIFF file
4. Validates the downloaded file to ensure it contains valid elevation data

### WMS RGB Handler

The `wms_rgb_handler.py` module handles fetching visualization images using the Web Map Service (WMS) protocol. It:

1. Determines the appropriate tile configuration based on the bounding box and resolution
2. Downloads individual tiles for the specified area
3. Stitches the tiles together into a single image
4. Creates a world file (.pgw) for georeferencing
5. Generates metadata for the visualization

## Testing

To test the DEM fetching system:

1. **Direct Handler Testing**:
   ```bash
   python src/pipeline/wcs_geotiff_handler.py
   python src/pipeline/wms_rgb_handler.py
   ```

2. **API Endpoint Testing**:
   ```bash
   curl -X POST http://localhost:5000/fetch_dem \
     -H "Content-Type: application/json" \
     -d '{"dem_type":"national_1s","bbox":[152.9,-27.5,153.0,-27.4],"data_type":"raw"}'
   ```

3. **Frontend Testing**:
   - Navigate to the Settings page
   - Fill in the DEM Download form
   - Click "Download DEM" button

## Future Improvements

1. **Progress Streaming**:
   - Implement WebSocket or Server-Sent Events for real-time progress updates

2. **Caching System**:
   - Implement caching for frequently requested DEMs
   - Add partial download resumption

3. **Advanced Visualization**:
   - Add hillshade and contour generation
   - Support for custom color ramps

4. **Batch Processing**:
   - Allow queuing multiple DEM requests
   - Implement background processing with job status tracking

## Conclusion

The DEM fetching system provides a robust and flexible solution for retrieving elevation data from Geoscience Australia services. Its modular architecture allows for easy extension and maintenance, while the comprehensive progress reporting ensures a good user experience during potentially long-running operations.
