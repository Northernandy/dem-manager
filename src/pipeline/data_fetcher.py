"""
Data fetching module for Brisbane flood visualization project.
Handles downloading data from BOM and SEQ Water sources.
"""

import os
import requests
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataFetcher:
    """Class to fetch data from various sources for flood visualization."""
    
    def __init__(self, data_dir=None):
        """
        Initialize the DataFetcher with a data directory.
        
        Args:
            data_dir (str, optional): Path to the data directory. 
                Defaults to project's data/raw directory.
        """
        if data_dir is None:
            # Get the project root directory
            project_root = Path(__file__).parent.parent.parent
            self.data_dir = project_root / 'data' / 'raw'
        else:
            self.data_dir = Path(data_dir)
            
        # Create directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
    def fetch_bom_data(self, station_id, start_date=None, end_date=None):
        """
        Fetch rainfall and water level data from BOM.
        
        Args:
            station_id (str): BOM station identifier
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            
        Returns:
            str: Path to the downloaded data file
        """
        logger.info(f"Fetching BOM data for station {station_id}")
        
        # Set default dates if not provided
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            # Default to 30 days before end date
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            start_date = (end_dt.replace(day=1) if end_dt.day > 1 else 
                         (end_dt.replace(month=end_dt.month-1 if end_dt.month > 1 else 12, 
                                        year=end_dt.year if end_dt.month > 1 else end_dt.year-1, 
                                        day=1)))
            start_date = start_date.strftime('%Y-%m-%d')
        
        # Construct filename
        filename = f"bom_{station_id}_{start_date}_to_{end_date}.csv"
        file_path = self.data_dir / filename
        
        # TODO: Implement actual BOM API request
        # This is a placeholder for the actual implementation
        logger.info(f"Would download data to {file_path}")
        
        # For demonstration, create an empty file
        with open(file_path, 'w') as f:
            f.write(f"# BOM data for station {station_id} from {start_date} to {end_date}\n")
            f.write("date,rainfall_mm,water_level_m\n")
        
        return str(file_path)
    
    def fetch_seqwater_data(self, dam_id, data_type='release', start_date=None, end_date=None):
        """
        Fetch data from SEQ Water for dam levels and releases.
        
        Args:
            dam_id (str): SEQ Water dam identifier
            data_type (str): Type of data ('level', 'release', 'inflow')
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            
        Returns:
            str: Path to the downloaded data file
        """
        logger.info(f"Fetching SEQ Water {data_type} data for dam {dam_id}")
        
        # Set default dates if not provided
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            # Default to 30 days before end date
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            start_date = (end_dt.replace(day=1) if end_dt.day > 1 else 
                         (end_dt.replace(month=end_dt.month-1 if end_dt.month > 1 else 12, 
                                        year=end_dt.year if end_dt.month > 1 else end_dt.year-1, 
                                        day=1)))
            start_date = start_date.strftime('%Y-%m-%d')
        
        # Construct filename
        filename = f"seqwater_{dam_id}_{data_type}_{start_date}_to_{end_date}.csv"
        file_path = self.data_dir / filename
        
        # TODO: Implement actual SEQ Water API request
        # This is a placeholder for the actual implementation
        logger.info(f"Would download data to {file_path}")
        
        # For demonstration, create an empty file
        with open(file_path, 'w') as f:
            f.write(f"# SEQ Water {data_type} data for dam {dam_id} from {start_date} to {end_date}\n")
            f.write("date,time,value\n")
        
        return str(file_path)
    
    def fetch_dem_data(self, region, resolution='30m'):
        """
        Fetch Digital Elevation Model (DEM) data for a specific region.
        
        Args:
            region (str): Name or bounding box of the region
            resolution (str, optional): Resolution of the DEM. Defaults to '30m'.
            
        Returns:
            str: Path to the downloaded DEM file
        """
        logger.info(f"Fetching DEM data for region {region} at {resolution} resolution")
        
        # Construct filename
        filename = f"dem_{region.replace(' ', '_').lower()}_{resolution}.tif"
        file_path = self.data_dir / filename
        
        # TODO: Implement actual DEM data download
        # This is a placeholder for the actual implementation
        logger.info(f"Would download DEM to {file_path}")
        
        # For demonstration, create an empty file
        with open(file_path, 'w') as f:
            f.write(f"# DEM data for {region} at {resolution} resolution\n")
        
        return str(file_path)


if __name__ == "__main__":
    # Example usage
    fetcher = DataFetcher()
    
    # Fetch BOM data
    bom_file = fetcher.fetch_bom_data('040913', '2023-01-01', '2023-01-31')
    print(f"BOM data saved to: {bom_file}")
    
    # Fetch SEQ Water data
    seqwater_file = fetcher.fetch_seqwater_data('wivenhoe', 'level', '2023-01-01', '2023-01-31')
    print(f"SEQ Water data saved to: {seqwater_file}")
    
    # Fetch DEM data
    dem_file = fetcher.fetch_dem_data('Brisbane CBD', '10m')
    print(f"DEM data saved to: {dem_file}")
