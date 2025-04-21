"""
BOILERPLATE FILE - NOT IN USE

This file is a boilerplate implementation and is not currently used in the application.
The active WebP tile generation functionality is implemented in dem_generate_webp_tiles.py.
This file has been moved to old_files_not_in_use for reference purposes.

WebP Tiler Module for Brisbane Flood Visualization

This module provides functionality to split large PNG images into WebP tiles,
preserving geographic metadata and supporting both lossy and lossless formats.
"""

from PIL import Image
import os
import json
import asyncio
import concurrent.futures
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Default tile size (2048x2048 pixels)
DEFAULT_TILE_SIZE = 2048

def read_pgw(pgw_path):
    """
    Read a PGW (PNG World) file to extract georeferencing parameters.
    
    Args:
        pgw_path (str): Path to the PGW file
        
    Returns:
        dict: Dictionary containing georeferencing parameters
    """
    try:
        with open(pgw_path, "r") as f:
            lines = [float(line.strip()) for line in f.readlines()]
            return {
                "pixel_size_x": lines[0],
                "rotation_x": lines[1],
                "rotation_y": lines[2],
                "pixel_size_y": lines[3],
                "upper_left_x": lines[4],
                "upper_left_y": lines[5],
            }
    except Exception as e:
        logger.error(f"Error reading PGW file {pgw_path}: {str(e)}")
        raise ValueError(f"Failed to read PGW file: {str(e)}")

def tile_png_to_webp(img, geo, quality, lossless, output_folder, json_path, tile_size=DEFAULT_TILE_SIZE):
    """
    Split a large PNG image into WebP tiles and save metadata.
    
    Args:
        img (PIL.Image): The input image to tile
        geo (dict): Georeferencing parameters from PGW file
        quality (int): WebP quality (0-100)
        lossless (bool): Whether to use lossless WebP encoding
        output_folder (str): Folder to save WebP tiles
        json_path (str): Path to save tile metadata JSON
        tile_size (int, optional): Size of tiles in pixels. Defaults to 2048.
        
    Returns:
        list: List of tile metadata objects
    """
    os.makedirs(output_folder, exist_ok=True)
    width, height = img.size

    cols = (width + tile_size - 1) // tile_size
    rows = (height + tile_size - 1) // tile_size

    tiles = []

    for row in range(rows):
        for col in range(cols):
            left = col * tile_size
            upper = row * tile_size
            right = min(left + tile_size, width)
            lower = min(upper + tile_size, height)

            tile = img.crop((left, upper, right, lower))
            filename = f"tile_{col}_{row}.webp"
            tile_path = os.path.join(output_folder, filename)

            # Save tile with WebP format
            tile.save(tile_path, format="WEBP", quality=quality, lossless=lossless, method=6)

            # Calculate geographic bounds for this tile
            px, py = geo["pixel_size_x"], geo["pixel_size_y"]
            ox, oy = geo["upper_left_x"], geo["upper_left_y"]

            west = ox + (left * px)
            north = oy + (upper * py)
            east = ox + (right * px)
            south = oy + (lower * py)

            # Add tile metadata
            tiles.append({
                "tile": f"{os.path.basename(output_folder)}/{filename}",
                "bounds": [[south, west], [north, east]]
            })

    # Save metadata to JSON file
    with open(json_path, "w") as f:
        json.dump(tiles, f, indent=2)

    logger.info(f"✅ Saved {len(tiles)} tiles to: {output_folder}")
    logger.info(f"🗺️ Metadata saved to: {json_path}")
    
    return tiles

async def process_tile_async(row, col, img, geo, quality, lossless, output_folder, tile_size):
    """
    Process a single tile asynchronously.
    
    Args:
        row (int): Tile row index
        col (int): Tile column index
        img (PIL.Image): Source image
        geo (dict): Georeferencing parameters
        quality (int): WebP quality (0-100)
        lossless (bool): Whether to use lossless WebP encoding
        output_folder (str): Folder to save WebP tiles
        tile_size (int): Size of tiles in pixels
        
    Returns:
        dict: Tile metadata
    """
    left = col * tile_size
    upper = row * tile_size
    right = min(left + tile_size, img.width)
    lower = min(upper + tile_size, img.height)

    # Crop the tile
    tile = img.crop((left, upper, right, lower))
    filename = f"tile_{col}_{row}.webp"
    tile_path = os.path.join(output_folder, filename)

    # Use a thread pool executor for the actual image processing
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(
            pool, 
            lambda: tile.save(tile_path, format="WEBP", quality=quality, lossless=lossless, method=6)
        )

    # Calculate geographic bounds for this tile
    px, py = geo["pixel_size_x"], geo["pixel_size_y"]
    ox, oy = geo["upper_left_x"], geo["upper_left_y"]

    west = ox + (left * px)
    north = oy + (upper * py)
    east = ox + (right * px)
    south = oy + (lower * py)

    return {
        "tile": f"{os.path.basename(output_folder)}/{filename}",
        "bounds": [[south, west], [north, east]]
    }

async def tile_png_to_webp_async(img, geo, quality, lossless, output_folder, json_path, tile_size=DEFAULT_TILE_SIZE):
    """
    Split a large PNG image into WebP tiles asynchronously and save metadata.
    
    Args:
        img (PIL.Image): The input image to tile
        geo (dict): Georeferencing parameters from PGW file
        quality (int): WebP quality (0-100)
        lossless (bool): Whether to use lossless WebP encoding
        output_folder (str): Folder to save WebP tiles
        json_path (str): Path to save tile metadata JSON
        tile_size (int, optional): Size of tiles in pixels. Defaults to 2048.
        
    Returns:
        list: List of tile metadata objects
    """
    os.makedirs(output_folder, exist_ok=True)
    width, height = img.size

    cols = (width + tile_size - 1) // tile_size
    rows = (height + tile_size - 1) // tile_size

    # Create tasks for all tiles
    tasks = []
    for row in range(rows):
        for col in range(cols):
            tasks.append(process_tile_async(row, col, img, geo, quality, lossless, output_folder, tile_size))

    # Process all tiles concurrently
    tiles = await asyncio.gather(*tasks)

    # Save metadata to JSON file
    with open(json_path, "w") as f:
        json.dump(tiles, f, indent=2)

    logger.info(f"✅ Saved {len(tiles)} tiles to: {output_folder}")
    logger.info(f"🗺️ Metadata saved to: {json_path}")
    
    return tiles

def generate_webp_tiles(input_path, geo_folder="geo", tile_size=DEFAULT_TILE_SIZE, async_processing=False, quality=75, lossless=False):
    """
    Generate WebP tiles from a PNG image with PGW file.
    
    Args:
        input_path (str): Path to the input PNG image
        geo_folder (str): Base folder for geographic data
        tile_size (int, optional): Size of tiles in pixels. Defaults to 2048.
        async_processing (bool, optional): Whether to use async processing. Defaults to False.
        quality (int, optional): WebP quality (0-100). Defaults to 75.
        lossless (bool, optional): Whether to use lossless WebP encoding. Defaults to False.
        
    Returns:
        dict: Dictionary with paths to metadata files
    """
    try:
        # Ensure the geo folder exists
        os.makedirs(geo_folder, exist_ok=True)
        
        # Get the PGW file path
        pgw_path = input_path.replace(".png", ".pgw")
        if not os.path.exists(pgw_path):
            raise ValueError(f"PGW file not found: {pgw_path}")
        
        # Read georeferencing information
        geo = read_pgw(pgw_path)
        
        # Open the image
        img = Image.open(input_path).convert("RGBA")
        
        # Create output folders based on format
        if lossless:
            output_folder = os.path.join(geo_folder, "tiles_webp_lossless")
            json_path = os.path.join(geo_folder, "tiles_webp_lossless.json")
            format_name = "lossless"
        else:
            output_folder = os.path.join(geo_folder, f"tiles_webp_q{quality}")
            json_path = os.path.join(geo_folder, f"tiles_webp_q{quality}.json")
            format_name = f"lossy (q{quality})"
        
        # Generate tiles
        if async_processing:
            # Run the async version
            loop = asyncio.get_event_loop()
            tiles = loop.run_until_complete(
                tile_png_to_webp_async(
                    img=img,
                    geo=geo,
                    quality=quality,
                    lossless=lossless,
                    output_folder=output_folder,
                    json_path=json_path,
                    tile_size=tile_size
                )
            )
        else:
            # Run the synchronous version
            tiles = tile_png_to_webp(
                img=img,
                geo=geo,
                quality=quality,
                lossless=lossless,
                output_folder=output_folder,
                json_path=json_path,
                tile_size=tile_size
            )
        
        # Return success with metadata
        result = {
            "success": True,
            "format": format_name,
            "tile_size": tile_size,
            "tiles_count": len(tiles)
        }
        
        # Add format-specific keys for backward compatibility
        if lossless:
            result["lossless_json"] = json_path
            result["lossless_tiles_count"] = len(tiles)
        else:
            result["lossy_json"] = json_path
            result["lossy_tiles_count"] = len(tiles)
        
        return result
    
    except Exception as e:
        logger.error(f"Error generating WebP tiles: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def check_webp_status(input_path, geo_folder="geo"):
    """
    Check if WebP tiles exist for a given PNG image.
    
    Args:
        input_path (str): Path to the input PNG image
        geo_folder (str): Base folder for geographic data
        
    Returns:
        dict: Status information about WebP tiles
    """
    try:
        # Get base name without extension
        base_name = os.path.basename(input_path)
        base_name = os.path.splitext(base_name)[0]
        
        # Define paths
        lossy_folder = os.path.join(geo_folder, "tiles_webp_q75")
        lossless_folder = os.path.join(geo_folder, "tiles_webp_lossless")
        lossy_json = os.path.join(geo_folder, "tiles_webp_q75.json")
        lossless_json = os.path.join(geo_folder, "tiles_webp_lossless.json")
        
        # Check if folders and JSON files exist
        lossy_exists = os.path.exists(lossy_folder) and os.path.exists(lossy_json)
        lossless_exists = os.path.exists(lossless_folder) and os.path.exists(lossless_json)
        
        # Count tiles if they exist
        lossy_count = 0
        lossless_count = 0
        
        if lossy_exists:
            try:
                with open(lossy_json, 'r') as f:
                    lossy_data = json.load(f)
                    lossy_count = len(lossy_data)
            except Exception as e:
                logger.warning(f"Error reading lossy WebP metadata: {str(e)}")
        
        if lossless_exists:
            try:
                with open(lossless_json, 'r') as f:
                    lossless_data = json.load(f)
                    lossless_count = len(lossless_data)
            except Exception as e:
                logger.warning(f"Error reading lossless WebP metadata: {str(e)}")
        
        return {
            "dem_id": base_name,
            "lossy_webp_available": lossy_exists,
            "lossless_webp_available": lossless_exists,
            "lossy_tiles_count": lossy_count,
            "lossless_tiles_count": lossless_count,
            "lossy_json": lossy_json if lossy_exists else None,
            "lossless_json": lossless_json if lossless_exists else None
        }
    except Exception as e:
        logger.error(f"Error checking WebP status: {str(e)}")
        return {
            "dem_id": os.path.basename(input_path),
            "lossy_webp_available": False,
            "lossless_webp_available": False,
            "lossy_tiles_count": 0,
            "lossless_tiles_count": 0,
            "lossy_json": None,
            "lossless_json": None,
            "error": str(e)
        }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate WebP tiles from a PNG image with PGW file")
    parser.add_argument("input_path", help="Path to the input PNG image")
    parser.add_argument("--geo-folder", default="geo", help="Base folder for geographic data")
    parser.add_argument("--tile-size", type=int, default=DEFAULT_TILE_SIZE, help="Size of tiles in pixels")
    parser.add_argument("--async", dest="async_processing", action="store_true", help="Use async processing")
    parser.add_argument("--quality", type=int, default=75, help="WebP quality (0-100)")
    parser.add_argument("--lossless", dest="lossless", action="store_true", help="Use lossless WebP encoding")
    
    args = parser.parse_args()
    
    result = generate_webp_tiles(
        input_path=args.input_path,
        geo_folder=args.geo_folder,
        tile_size=args.tile_size,
        async_processing=args.async_processing,
        quality=args.quality,
        lossless=args.lossless
    )
    
    if result["success"]:
        print(f"Successfully generated WebP tiles:")
        print(f"  Format: {result['format']}")
        print(f"  Tile size: {result['tile_size']}")
        print(f"  Tiles count: {result['tiles_count']}")
        if "lossy_json" in result:
            print(f"  Lossy WebP metadata saved to: {result['lossy_json']}")
        if "lossless_json" in result:
            print(f"  Lossless WebP metadata saved to: {result['lossless_json']}")
    else:
        print(f"Error generating WebP tiles: {result['error']}")
