# WebP Tiling from Georeferenced PNG using Python

## Goal
Convert a large georeferenced PNG image (with an associated `.pgw` world file) into two sets of WebP tiles:
1. A lossy version at 75% quality.
2. A lossless version.

Each tile includes geographic bounds based on the original image's georeferencing, and outputs are suitable for use with Leaflet.js.

## Tools and Libraries
- Python 3
- Pillow (Python Imaging Library)

No external binaries or system dependencies are required. The WebP encoding is done entirely through Pillow.

## Input
- A high-resolution PNG file (e.g., `image.png`)
- A matching PGW world file (e.g., `image.pgw`)

## Output
- Folder structure:
  - `geo/tiles_webp_q75/` — lossy WebP tiles
  - `geo/tiles_webp_lossless/` — lossless WebP tiles
- Metadata files:
  - `geo/tiles_webp_q75.json`
  - `geo/tiles_webp_lossless.json`

Each `.json` file contains an array of objects with:
- `tile`: Relative path to the WebP tile
- `bounds`: Geographic bounds of the tile in Leaflet format `[[south, west], [north, east]]`

## Process Summary
1. Read image and world file.
2. Split image into tiles (default: 2048x2048 pixels).
3. Calculate geographic bounds for each tile using PGW data.
4. Save each tile:
   - Lossy WebP with `quality=75`, `lossless=False`
   - Lossless WebP with `quality=100`, `lossless=True`
5. Save tile metadata in JSON format.

## Leaflet Integration
Load the tiles with JavaScript using:

```js
fetch("geo/tiles_webp_q75.json")
  .then(res => res.json())
  .then(tiles => {
    tiles.forEach(t => {
      L.imageOverlay("geo/" + t.tile, t.bounds).addTo(map);
    });
  });
```

Switch to the lossless version by using `tiles_webp_lossless.json` instead.

## Result
- Efficient, browser-friendly WebP tiles
- Full georeferencing preserved
- 100% Python-native workflow

<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

Sample script that does this


from PIL import Image
import os
import json

Image.MAX_IMAGE_PIXELS = None

def read_pgw(pgw_path):
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

def tile_png_to_webp(img, geo, quality, lossless, output_folder, json_path, tile_size=2048):
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

            tile.save(tile_path, format="WEBP", quality=quality, lossless=lossless, method=6)

            px, py = geo["pixel_size_x"], geo["pixel_size_y"]
            ox, oy = geo["upper_left_x"], geo["upper_left_y"]

            west = ox + (left * px)
            north = oy + (upper * py)
            east = ox + (right * px)
            south = oy + (lower * py)

            tiles.append({
                "tile": f"{os.path.basename(output_folder)}/{filename}",
                "bounds": [[south, west], [north, east]]
            })

    with open(json_path, "w") as f:
        json.dump(tiles, f, indent=2)

    print(f"Saved {len(tiles)} tiles to: {output_folder}")
    print(f"Metadata saved to: {json_path}")

def main(
    input_path="rgb_lidar_5m_152p0_-28p0_153p5_-27p0_1.png",
    geo_folder="geo",
    tile_size=2048
):
    os.makedirs(geo_folder, exist_ok=True)
    pgw_path = input_path.replace(".png", ".pgw")
    geo = read_pgw(pgw_path)
    img = Image.open(input_path).convert("RGBA")

    tile_png_to_webp(
        img=img,
        geo=geo,
        quality=75,
        lossless=False,
        output_folder=os.path.join(geo_folder, "tiles_webp_q75"),
        json_path=os.path.join(geo_folder, "tiles_webp_q75.json"),
        tile_size=tile_size
    )

    tile_png_to_webp(
        img=img,
        geo=geo,
        quality=100,
        lossless=True,
        output_folder=os.path.join(geo_folder, "tiles_webp_lossless"),
        json_path=os.path.join(geo_folder, "tiles_webp_lossless.json"),
        tile_size=tile_size
    )

if __name__ == "__main__":
    main()
