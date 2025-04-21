from PIL import Image
import os
import json
import sys

Image.MAX_IMAGE_PIXELS = None

def read_pgw(pgw_name):
    print(f"Reading PGW file: {pgw_name}")
    try:
        with open(pgw_name, "r") as f:
            lines = [float(line.strip()) for line in f.readlines()]
            return {
                "pixel_size_x": lines[0],
                "rotation_x": lines[1],
                "rotation_y": lines[2],
                "pixel_size_y": lines[3],
                "upper_left_x": lines[4],
                "upper_left_y": lines[5],
            }
    except FileNotFoundError:
        print(f"Error: PGW file not found at {pgw_name}")
        return None
    except Exception as e:
        print(f"Error reading PGW file: {e}")
        return None

def tile_png_to_webp(image_name, quality, lossless):
    print(f"Processing image: {image_name} with quality: {quality}, lossless: {lossless}")
    # Hard-coded tile size
    tile_size = 2048
    
    # Create base paths and folders
    geo_folder = "data/geo"
    print(f"Ensuring geo folder exists: {geo_folder}")
    try:
        os.makedirs(geo_folder, exist_ok=True)
    except Exception as e:
        print(f"Error creating geo folder: {e}")
        return
    
    # Extract base name without extension for folder creation
    base_name = os.path.splitext(os.path.basename(image_name))[0]
    
    # Create quality suffix for folder and file naming
    quality_suffix = "lossless" if lossless else f"q{quality}"
    
    # Print debug information
    print(f"Creating WebP tiles with suffix: {quality_suffix}")
    
    # Create JSON path in the root geo directory
    json_filename = f"{base_name}_tiles_{quality_suffix}.json"
    json_path = os.path.join(geo_folder, json_filename)
    print(f"JSON metadata will be saved to: {json_path}")
    
    # Create output folder with the same name as the JSON file (without .json extension)
    output_folder_name = json_filename.replace(".json", "")
    output_folder = os.path.join(geo_folder, output_folder_name)
    print(f"Creating output folder: {output_folder}")
    try:
        os.makedirs(output_folder, exist_ok=True)
    except Exception as e:
        print(f"Error creating output folder: {e}")
        return
    
    # Load image and geo data - look for files in data/geo directory
    input_image_path = os.path.join(geo_folder, image_name)
    pgw_name = input_image_path.replace(".png", ".pgw")
    
    print(f"Looking for image at: {input_image_path}")
    print(f"Looking for PGW file at: {pgw_name}")
    
    geo = read_pgw(pgw_name)
    if geo is None:
        print("Error: unable to read PGW file")
        return
    
    print("Successfully read PGW file")
    print("Loading image...")
    
    try:
        img = Image.open(input_image_path).convert("RGBA")
    except FileNotFoundError:
        print(f"Error: Image file not found at {input_image_path}")
        return
    except Exception as e:
        print(f"Error loading image: {e}")
        return
    
    print(f"Image loaded, dimensions: {img.size}")
    
    width, height = img.size

    cols = (width + tile_size - 1) // tile_size
    rows = (height + tile_size - 1) // tile_size
    print(f"Image will be split into {rows}x{cols} tiles of size {tile_size}px")

    tiles = []
    total_tiles = rows * cols
    current_tile = 0

    for row in range(rows):
        for col in range(cols):
            current_tile += 1
            sys.stdout.write(f"\rProcessing tile {current_tile}/{total_tiles} ({(current_tile/total_tiles)*100:.1f}%)")
            sys.stdout.flush()
            
            left = col * tile_size
            upper = row * tile_size
            right = min(left + tile_size, width)
            lower = min(upper + tile_size, height)

            tile = img.crop((left, upper, right, lower))
            filename = f"tile_{col}_{row}.webp"
            tile_path = os.path.join(output_folder, filename)

            try:
                tile.save(tile_path, format="WEBP", quality=quality, lossless=lossless, method=6)
            except Exception as e:
                print(f"\nError saving tile: {e}")
                continue

            px, py = geo["pixel_size_x"], geo["pixel_size_y"]
            ox, oy = geo["upper_left_x"], geo["upper_left_y"]

            west = ox + (left * px)
            north = oy + (upper * py)
            east = ox + (right * px)
            south = oy + (lower * py)

            tiles.append({
                "tile": f"{filename}",
                "bounds": [[south, west], [north, east]]
            })
    
    print("\nAll tiles processed")
    print(f"Writing metadata to JSON: {json_path}")
    try:
        with open(json_path, "w") as f:
            json.dump(tiles, f, indent=2)
    except Exception as e:
        print(f"Error writing metadata to JSON: {e}")
        return

    print(f"Saved {len(tiles)} tiles to: {output_folder}")
    print(f"Metadata saved to: {json_path}")
    print("Tile processing complete!")

def main():

#This was only used for testing purposes. The functions are called directly from wms_rgb_handler.py

    image_name = "rgb_lidar_5m_152p0_-28p0_153p5_-27p0.png"

# Commented out lossless processing to simplify initial testing
    """
    print(f"Starting WebP tile generation for: {image_name}")
    # Process with quality=75, non-lossless
    tile_png_to_webp(
        image_name=image_name,
        quality=75,
        lossless=False,
    )
    """

    # Commented out lossless processing to simplify initial testing
    """
    # Process with lossless compression
    tile_png_to_webp(
        image_name=image_name,
        quality=100,
        lossless=True,
    )
    """

if __name__ == "__main__":
    main()