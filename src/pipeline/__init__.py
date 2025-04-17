"""
Brisbane Flood Visualization - Pipeline Package
"""

# Import key functions for easier access
try:
    from .wcs_geotiff_handler import fetch_geotiff_dem
    from .wms_rgb_handler import fetch_rgb_dem
    # dem_fetcher module is no longer used in the main application
except ImportError as e:
    import logging
    logging.warning(f"Error importing pipeline modules: {e}")
