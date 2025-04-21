import os
import json
import time
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

class DEMStatusHandler:
    """
    Handles status reporting for DEM file operations.
    Provides common functionality for both GeoTIFF and RGB status reporting.
    """
    
    def __init__(self, output_dir, dem_type, filename_prefix=None):
        """
        Initialize the status handler.
        
        Args:
            output_dir (str): Directory where DEM files and status files will be stored
            dem_type (str): Type of DEM ('geotiff' or 'rgb')
            filename_prefix (str, optional): Prefix for the output filename
        """
        self.output_dir = output_dir
        self.dem_type = dem_type
        self.filename_prefix = filename_prefix or f"dem_{int(time.time())}"
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize status data
        self.status_data = {
            'dem_type': dem_type,
            'start_time': datetime.now().isoformat(),
            'status': 'initializing',
            'progress': 0,
            'message': 'Initializing DEM fetching process',
            'errors': [],
            'warnings': [],
            'dataType': 'raw' if dem_type == 'geotiff' else 'rgb',
            'display_name': self.filename_prefix
        }
        
        # Create status file
        self.status_file = os.path.join(output_dir, f"{self.filename_prefix}_status.json")
        self._write_status()
        
        logger.info(f"Initialized {dem_type} status handler with prefix '{self.filename_prefix}'")
    
    def _write_status(self):
        """Write current status to the status file."""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(self.status_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write status file: {e}")
    
    def update_status(self, status, progress=None, message=None):
        """
        Update the status with new information.
        
        Args:
            status (str): Current status (e.g., 'downloading', 'processing', 'complete', 'failed')
            progress (int, optional): Progress percentage (0-100)
            message (str, optional): Status message
        """
        self.status_data['status'] = status
        
        if progress is not None:
            self.status_data['progress'] = progress
        
        if message:
            self.status_data['message'] = message
            logger.info(f"DEM {self.dem_type} status: {message}")
        
        self.status_data['last_update'] = datetime.now().isoformat()
        self._write_status()
    
    def add_error(self, error_message):
        """
        Add an error message to the status.
        
        Args:
            error_message (str): Error message to add
        """
        error_entry = {
            'time': datetime.now().isoformat(),
            'message': error_message
        }
        self.status_data['errors'].append(error_entry)
        logger.error(f"DEM {self.dem_type} error: {error_message}")
        self._write_status()
    
    def add_warning(self, warning_message):
        """
        Add a warning message to the status.
        
        Args:
            warning_message (str): Warning message to add
        """
        warning_entry = {
            'time': datetime.now().isoformat(),
            'message': warning_message
        }
        self.status_data['warnings'].append(warning_entry)
        logger.warning(f"DEM {self.dem_type} warning: {warning_message}")
        self._write_status()
    
    def set_complete(self, output_file=None, metadata=None):
        """
        Mark the process as complete.
        
        Args:
            output_file (str, optional): Path to the output file
            metadata (dict, optional): Additional metadata to include in the status
        """
        self.status_data['status'] = 'complete'
        self.status_data['progress'] = 100
        self.status_data['end_time'] = datetime.now().isoformat()
        self.status_data['message'] = 'DEM fetching process completed successfully'
        
        if output_file:
            self.status_data['output_file'] = output_file
        
        if metadata:
            self.status_data['metadata'] = metadata
        
        self._write_status()
        logger.info(f"DEM {self.dem_type} process completed successfully")
    
    def set_failed(self, error_message):
        """
        Mark the process as failed.
        
        Args:
            error_message (str): Error message explaining the failure
        """
        self.status_data['status'] = 'failed'
        self.status_data['end_time'] = datetime.now().isoformat()
        self.status_data['message'] = f'DEM fetching process failed: {error_message}'
        self.add_error(error_message)
        logger.error(f"DEM {self.dem_type} process failed: {error_message}")
    
    def update_display_name(self, display_name):
        """
        Update the display name for the DEM.
        
        Args:
            display_name (str): New display name
        """
        self.status_data['display_name'] = display_name
        logger.info(f"Updated display name to '{display_name}'")
        self._write_status()
    
    # RGB-specific status methods
    def update_tile_progress(self, current_tile, total_tiles, tile_info=None):
        """
        Update status for RGB tile downloading progress.
        Only relevant for RGB DEM processing.
        
        Args:
            current_tile (int): Current tile number
            total_tiles (int): Total number of tiles
            tile_info (dict, optional): Information about the current tile
        """
        if self.dem_type != 'rgb':
            logger.warning("Called RGB-specific method on non-RGB status handler")
            return
        
        progress = int((current_tile / total_tiles) * 80)  # Tiles are ~80% of the process
        message = f"Downloading tile {current_tile}/{total_tiles} ({progress}%)"
        
        self.status_data['tile_progress'] = {
            'current': current_tile,
            'total': total_tiles,
            'percentage': progress
        }
        
        if tile_info:
            self.status_data['current_tile_info'] = tile_info
        
        self.update_status('downloading_tiles', progress, message)
    
    def update_stitching_status(self, stage, progress_within_stage=0):
        """
        Update status for RGB tile stitching process.
        Only relevant for RGB DEM processing.
        
        Args:
            stage (str): Current stitching stage (e.g., 'preparing', 'stitching', 'saving')
            progress_within_stage (int): Progress percentage within the current stage (0-100)
        """
        if self.dem_type != 'rgb':
            logger.warning("Called RGB-specific method on non-RGB status handler")
            return
        
        # Stitching is the last 20% of the process
        base_progress = 80
        stage_progress = int((progress_within_stage / 100) * 20)
        total_progress = base_progress + stage_progress
        
        message = f"Stitching tiles: {stage} ({progress_within_stage}%)"
        
        self.status_data['stitching_status'] = {
            'stage': stage,
            'progress_within_stage': progress_within_stage
        }
        
        self.update_status('stitching', total_progress, message)
    
    # GeoTIFF-specific status methods
    def update_download_progress(self, bytes_downloaded, total_bytes=None):
        """
        Update status for GeoTIFF download progress.
        Only relevant for GeoTIFF DEM processing.
        
        Args:
            bytes_downloaded (int): Number of bytes downloaded
            total_bytes (int, optional): Total number of bytes to download
        """
        if self.dem_type != 'geotiff':
            logger.warning("Called GeoTIFF-specific method on non-GeoTIFF status handler")
            return
        
        if total_bytes:
            progress = int((bytes_downloaded / total_bytes) * 100)
            message = f"Downloading: {bytes_downloaded / 1024 / 1024:.1f} MB of {total_bytes / 1024 / 1024:.1f} MB ({progress}%)"
        else:
            progress = 50  # Assume 50% if we don't know the total
            message = f"Downloading: {bytes_downloaded / 1024 / 1024:.1f} MB"
        
        self.status_data['download_progress'] = {
            'bytes_downloaded': bytes_downloaded,
            'total_bytes': total_bytes,
            'percentage': progress
        }
        
        self.update_status('downloading', progress, message)
    
    def update_processing_status(self, stage, progress_within_stage=0):
        """
        Update status for GeoTIFF processing.
        Only relevant for GeoTIFF DEM processing.
        
        Args:
            stage (str): Current processing stage (e.g., 'validating', 'reprojecting')
            progress_within_stage (int): Progress percentage within the current stage (0-100)
        """
        if self.dem_type != 'geotiff':
            logger.warning("Called GeoTIFF-specific method on non-GeoTIFF status handler")
            return
        
        # Assume download is 80% of the process, processing is 20%
        base_progress = 80
        stage_progress = int((progress_within_stage / 100) * 20)
        total_progress = base_progress + stage_progress
        
        message = f"Processing: {stage} ({progress_within_stage}%)"
        
        self.status_data['processing_status'] = {
            'stage': stage,
            'progress_within_stage': progress_within_stage
        }
        
        self.update_status('processing', total_progress, message)
