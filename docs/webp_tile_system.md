# WebP Tile System Documentation

## Overview

The Brisbane Flood Visualization application includes a WebP tile system that converts PNG visualization images into smaller, more efficient WebP format tiles. These tiles are used for faster loading and better performance when viewing DEM visualizations in the map interface.

## How It Works

### 1. WebP Tile Generation Process

When a new RGB visualization image (PNG) is downloaded, the system can automatically generate WebP tiles from this image. The process works as follows:

1. A PNG visualization image is downloaded via the `fetch_rgb_dem` function in `src/pipeline/wms_rgb_handler.py`
2. If WebP tile generation is enabled, the system starts a background thread that calls `generate_webp_tiles_background`
3. This function imports and calls `tile_png_to_webp` from `src/pipeline/dem_generate_webp_tiles.py`
4. The `tile_png_to_webp` function:
   - Divides the PNG image into tiles of 2048x2048 pixels
   - Converts each tile to WebP format
   - Saves the tiles in a folder named after the original PNG file with a quality suffix
   - Creates a JSON metadata file with tile information and geographic bounds

### 2. WebP Tile Quality Options

The system supports two quality options for WebP tiles:

1. **Low Resolution (Quality 75)**
   - Faster to generate and smaller file size
   - Uses lossy compression with quality=75
   - Files are stored in a folder with suffix `_tiles_q75`
   - JSON metadata file has suffix `_tiles_q75.json`

2. **High Resolution (Lossless)**
   - Higher quality but larger file size
   - Uses lossless compression
   - Files are stored in a folder with suffix `_tiles_lossless`
   - JSON metadata file has suffix `_tiles_lossless.json`

### 3. Folder Structure

For a PNG file named `rgb_lidar_5m_152p0_-28p0_153p5_-27p0.png`, the WebP tiles are organized as follows:

```
data/geo/
├── rgb_lidar_5m_152p0_-28p0_153p5_-27p0.png         # Original PNG file
├── rgb_lidar_5m_152p0_-28p0_153p5_-27p0.pgw         # World file with geo-coordinates
├── rgb_lidar_5m_152p0_-28p0_153p5_-27p0_tiles_q75/  # Folder for low-resolution WebP tiles
│   ├── tile_0_0.webp
│   ├── tile_0_1.webp
│   ├── ...
├── rgb_lidar_5m_152p0_-28p0_153p5_-27p0_tiles_q75.json  # Metadata for low-resolution tiles
├── rgb_lidar_5m_152p0_-28p0_153p5_-27p0_tiles_lossless/ # Folder for high-resolution WebP tiles (if generated)
│   ├── tile_0_0.webp
│   ├── tile_0_1.webp
│   ├── ...
└── rgb_lidar_5m_152p0_-28p0_153p5_-27p0_tiles_lossless.json  # Metadata for high-resolution tiles (if generated)
```

> **Note:** As of version 1.0.11, the folder structure has been simplified. Tiles are now stored directly in a folder with the same name as the JSON file (without the .json extension), rather than in a nested folder structure.

## Configuration

### Current Configuration

Currently, WebP tile generation is configured in the following locations:

1. **Main Configuration (WebP Generation Toggle)**
   - File: `src/pipeline/wms_rgb_handler.py`
   - Function: `generate_webp_tiles_background`
   - This function is called after a PNG file is downloaded
   - Currently, it only generates low-resolution (quality=75) tiles

2. **WebP Tile Generation Parameters**
   - File: `src/pipeline/dem_generate_webp_tiles.py`
   - Function: `tile_png_to_webp`
   - Parameters:
     - `image_name`: Name of the PNG file
     - `quality`: Quality setting for lossy compression (default: 75)
     - `lossless`: Boolean flag for lossless compression (default: False)

3. **Manual Testing**
   - File: `src/pipeline/dem_generate_webp_tiles.py`
   - Function: `main`
   - This function can be used to manually test WebP tile generation
   - Contains commented-out code for both low and high resolution options

### Changing the Configuration

To modify the WebP tile generation configuration:

#### 1. Enable/Disable WebP Tile Generation

To enable or disable WebP tile generation entirely:

```python
# In src/pipeline/wms_rgb_handler.py
def fetch_rgb_dem(...):
    # ...
    
    # Comment out or remove these lines to disable WebP tile generation
    threading.Thread(
        target=generate_webp_tiles_background,
        args=(file_path,),
        daemon=True
    ).start()
    
    # ...
```

#### 2. Change Quality Settings

To modify the quality settings for WebP tiles:

```python
# In src/pipeline/wms_rgb_handler.py
def generate_webp_tiles_background(png_file):
    # ...
    
    # Change quality value (1-100) or lossless flag (True/False)
    tile_png_to_webp(
        image_name=image_name,
        quality=75,  # Change this value
        lossless=False  # Change this flag
    )
    
    # ...
```

#### 3. Generate Both Low and High Resolution Tiles

To generate both low and high resolution tiles:

```python
# In src/pipeline/wms_rgb_handler.py
def generate_webp_tiles_background(png_file):
    # ...
    
    # Generate low-resolution tiles
    tile_png_to_webp(
        image_name=image_name,
        quality=75,
        lossless=False
    )
    
    # Generate high-resolution tiles
    tile_png_to_webp(
        image_name=image_name,
        quality=100,
        lossless=True
    )
    
    # ...
```

## UI Integration

The WebP tile availability is displayed in the UI on the Settings page:

1. Each PNG visualization image has a "WebP Formats" section
2. This section shows badges for available WebP formats:
   - "High Resolution" (purple badge): Lossless WebP tiles are available
   - "Low Resolution" (blue badge): Quality 75 WebP tiles are available
   - "None" (gray badge): No WebP tiles are available

3. An information icon (ⓘ) next to "WebP Formats" provides a tooltip with configuration details:
   - Shows the quality settings for each format
   - Explains the difference between lossless and lossy compression
   - Helps users understand the WebP tile generation options

## Future Enhancements

Potential future enhancements to the WebP tile system include:

1. **UI Configuration**
   - Add UI controls to configure WebP tile generation options
   - Allow users to select quality settings from the interface

2. **On-Demand Generation**
   - Add a button to generate WebP tiles for existing PNG files
   - Allow regeneration of tiles with different quality settings

3. **Progress Tracking**
   - Add progress tracking for WebP tile generation
   - Display generation status in the UI

4. **Tile Viewer**
   - Add a dedicated tile viewer interface
   - Allow inspection of individual tiles and their properties

## Troubleshooting

Common issues with WebP tile generation:

1. **Missing WebP Tiles**
   - Check if the PNG file exists in the `data/geo` directory
   - Verify that the WebP tile generation thread completed successfully
   - Look for error messages in the application logs

2. **Slow Tile Generation**
   - WebP tile generation can be resource-intensive, especially for large PNG files
   - Consider using only low-resolution tiles for faster generation
   - Generation happens in a background thread to avoid blocking the UI

3. **File Permission Issues**
   - Ensure the application has write permissions to the `data/geo` directory
   - Check for locked files that might prevent tile generation
