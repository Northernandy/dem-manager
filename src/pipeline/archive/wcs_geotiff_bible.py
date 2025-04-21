import random
import os
import requests
from owslib.wcs import WebCoverageService
import rasterio

def validate_geotiff(file_path):
    """Reads a GeoTIFF file using rasterio and prints its metadata."""
    print(f"--- Validating GeoTIFF: {file_path} ---")
    try:
        with rasterio.open(file_path) as dataset:
            print(f"Successfully opened file.")
            print(f"  CRS: {dataset.crs}")
            print(f"  Bounds: {dataset.bounds}")
            print(f"  Width: {dataset.width}")
            print(f"  Height: {dataset.height}")
            print(f"  Number of bands: {dataset.count}")
            print(f"  Data types: {dataset.dtypes}")
            print(f"  NoData value: {dataset.nodata}")
            print(f"  Driver: {dataset.driver}")
            try:
                data_block = dataset.read(1, window=((0, 10), (0, 10)))
                print(f"  Successfully read a 10x10 data block from band 1.")
                print(f"  Sample data: {data_block}")
            except Exception as read_err:
                print(f"  Warning: Could not read data block: {read_err}")
        print("--- Validation Complete ---\n")
    except rasterio.RasterioIOError as e:
        print(f"ERROR: Could not open file. It might not be a valid GeoTIFF or path is incorrect.")
        print(f"  Details: {e}")
    except FileNotFoundError:
        print(f"ERROR: File not found at path: {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def request_and_validate_tile(wcs_url, bbox_extent, crs, filename_prefix):
    print(f"\n--- Connecting to WCS: {wcs_url} ---")
    wcs = WebCoverageService(wcs_url, version='1.0.0')
    coverage_keys = list(wcs.contents.keys())
    print(f"Coverage Keys: {coverage_keys}")
    coverage_id = coverage_keys[0]

    minx, maxx, miny, maxy = bbox_extent
    tile_width = (maxx - minx) * 0.1  # 10% of the full extent
    tile_height = (maxy - miny) * 0.1
    lon = round(random.uniform(minx, maxx - tile_width), 6)
    lat = round(random.uniform(miny, maxy - tile_height), 6)
    bbox = (lon, lat, lon + tile_width, lat + tile_height)

    print(f"Requesting coverage '{coverage_id}' for BBOX: {bbox}")

    params = {
        'service': 'WCS',
        'request': 'GetCoverage',
        'version': '1.0.0',
        'coverage': coverage_id,
        'CRS': crs,
        'BBOX': ','.join(map(str, bbox)),
        'WIDTH': 500,
        'HEIGHT': 500,
        'FORMAT': 'GeoTIFF'
    }

    response = requests.get(wcs_url, params=params)
    
    # Save file in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, f"{filename_prefix}_tile.tif")
    
    with open(filename, 'wb') as f:
        f.write(response.content)

    print(f"Saved GeoTIFF to: {filename}")
    validate_geotiff(filename)

if __name__ == "__main__":
    datasets = [
        {
            "url": "https://services.ga.gov.au/gis/services/DEM_SRTM_1Second_Hydro_Enforced_2024/MapServer/WCSServer",
            "bbox": (152.5, 153.2, -28.4, -27.0),
            "crs": "EPSG:4326",
            "prefix": "1s"
        },
        {
            "url": "https://services.ga.gov.au/gis/services/DEM_LiDAR_5m_2025/MapServer/WCSServer",
            "bbox": (139.6726, 139.6851, -36.9499, -36.9412),
            "crs": "EPSG:4283",
            "prefix": "5m"
        }
    ]

    for ds in datasets:
        request_and_validate_tile(ds["url"], ds["bbox"], ds["crs"], ds["prefix"])
