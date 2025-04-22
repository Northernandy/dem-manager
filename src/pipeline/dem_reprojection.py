"""
DEM Reprojection Module

This module handles the reprojection of GeoTIFF files from one coordinate reference system
to another using rasterio. Specifically designed to convert Australia-specific projections
(EPSG:4283/GDA94) to the more widely supported EPSG:4326 (WGS84) for frontend compatibility.
"""

import os
import logging
import tempfile
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reproject_geotiff(input_path, output_path=None, target_crs='EPSG:4326', in_place=False):
    """
    Reproject a GeoTIFF file from its source CRS to a target CRS.
    
    Args:
        input_path (str): Path to the input GeoTIFF file
        output_path (str, optional): Path to save the reprojected GeoTIFF file.
            If None, a path will be generated based on the input path.
        target_crs (str, optional): Target coordinate reference system.
            Defaults to 'EPSG:4326' (WGS84).
        in_place (bool, optional): If True, replace the input file with the
            reprojected version. Defaults to False.
    
    Returns:
        dict: Result of the operation with success status and file path
    """
    try:
        # If in_place is True, we'll eventually overwrite the input file
        if in_place:
            final_output_path = input_path
        # If no output path is provided, create one based on the input path
        elif output_path is None:
            input_file = Path(input_path)
            output_dir = input_file.parent
            output_filename = f"{input_file.stem}_reprojected{input_file.suffix}"
            final_output_path = os.path.join(output_dir, output_filename)
        else:
            final_output_path = output_path
        
        # Always use a temporary file for the reprojection process
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as temp_file:
            temp_path = temp_file.name
        
        logger.info(f"Reprojecting GeoTIFF from {input_path} to {target_crs}")
        
        with rasterio.open(input_path) as src:
            # Log source information
            logger.info(f"Source CRS: {src.crs}")
            logger.info(f"Source bounds: {src.bounds}")
            logger.info(f"Source shape: {src.width}x{src.height}")
            
            # Check if reprojection is needed
            if src.crs.to_string() == target_crs:
                logger.info(f"Source already in target CRS ({target_crs}), no reprojection needed")
                
                if in_place:
                    # No action needed if already in target CRS
                    return {
                        'success': True,
                        'file_path': input_path,
                        'message': 'File already in target CRS, no reprojection needed'
                    }
                elif output_path:
                    # Copy to the requested output path
                    with open(input_path, 'rb') as src_file:
                        with open(final_output_path, 'wb') as dst_file:
                            dst_file.write(src_file.read())
                    return {
                        'success': True,
                        'file_path': final_output_path,
                        'message': 'File already in target CRS, copied without reprojection'
                    }
                else:
                    # Return the original path
                    return {
                        'success': True,
                        'file_path': input_path,
                        'message': 'File already in target CRS, no reprojection needed'
                    }
            
            # Calculate the optimal transform and dimensions
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds)
            
            # Prepare the keyword arguments for the output
            kwargs = src.meta.copy()
            kwargs.update({
                'crs': target_crs,
                'transform': transform,
                'width': width,
                'height': height
            })
            
            # Perform the reprojection to the temporary file
            with rasterio.open(temp_path, 'w', **kwargs) as dst:
                # Reproject each band
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=target_crs,
                        resampling=Resampling.nearest
                    )
        
        # Move the temporary file to the final destination
        if os.path.exists(final_output_path):
            os.remove(final_output_path)
        os.rename(temp_path, final_output_path)
        
        # Validate the reprojected file
        with rasterio.open(final_output_path) as dst:
            logger.info(f"Reprojected CRS: {dst.crs}")
            logger.info(f"Reprojected bounds: {dst.bounds}")
            logger.info(f"Reprojected shape: {dst.width}x{dst.height}")
        
        return {
            'success': True,
            'file_path': final_output_path,
            'message': f'Successfully reprojected from {src.crs} to {target_crs}'
        }
    
    except Exception as e:
        logger.error(f"Error reprojecting GeoTIFF: {str(e)}")
        # Clean up any temporary files
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        
        return {
            'success': False,
            'message': f'Error reprojecting GeoTIFF: {str(e)}'
        }

def reproject_lidar_5m(input_path, output_path=None, in_place=False):
    """
    Specialized function to reproject 5m LiDAR GeoTIFF files from EPSG:4283 (GDA94)
    to EPSG:4326 (WGS84) for frontend compatibility.
    
    Args:
        input_path (str): Path to the input 5m LiDAR GeoTIFF file
        output_path (str, optional): Path to save the reprojected GeoTIFF file.
            If None, a path will be generated based on the input path.
        in_place (bool, optional): If True, replace the input file with the
            reprojected version. Defaults to False.
    
    Returns:
        dict: Result of the operation with success status and file path
    """
    # Validate that the input file exists
    if not os.path.exists(input_path):
        return {
            'success': False,
            'message': f'Input file does not exist: {input_path}'
        }
    
    try:
        # Check if the input file is actually a 5m LiDAR GeoTIFF in EPSG:4283
        with rasterio.open(input_path) as src:
            source_crs = src.crs.to_string()
            if 'EPSG:4283' not in source_crs and 'EPSG:4283' not in source_crs.upper():
                logger.warning(f"Input file is not in EPSG:4283 (found {source_crs}), but proceeding with reprojection anyway")
        
        # If no output path is provided and not in_place, create one based on the input path
        if output_path is None and not in_place:
            input_file = Path(input_path)
            output_dir = input_file.parent
            output_filename = f"{input_file.stem}_wgs84{input_file.suffix}"
            output_path = os.path.join(output_dir, output_filename)
        
        # Call the general reprojection function with WGS84 as the target CRS
        result = reproject_geotiff(input_path, output_path, 'EPSG:4326', in_place)
        
        if result['success']:
            logger.info(f"Successfully reprojected 5m LiDAR GeoTIFF to WGS84: {result['file_path']}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error in reproject_lidar_5m: {str(e)}")
        return {
            'success': False,
            'message': f'Error reprojecting 5m LiDAR GeoTIFF: {str(e)}'
        }

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        if os.path.exists(input_file):
            # Default to in-place reprojection when run as a script
            result = reproject_lidar_5m(input_file, in_place=True)
            print(f"Reprojection result: {result}")
        else:
            print(f"Input file does not exist: {input_file}")
    else:
        print("Usage: python dem_reprojection.py <path_to_geotiff>")
