"""
Test data fixtures for Brisbane Flood Visualization tests.

This module provides sample data for tests to avoid hitting external APIs.
"""

# Sample DEM metadata
SAMPLE_DEM_METADATA = {
    'display_name': 'Test Brisbane CBD',
    'dem_type': 'lidar_5m',
    'bbox': [152.95, -27.5, 153.05, -27.4],
    'resolution': 5,
    'created_at': 1681545600.0  # 2023-04-15 timestamp
}

# Sample BOM data (first few lines of a CSV)
SAMPLE_BOM_DATA = """Station,Date,Rainfall (mm)
040913,2023-01-01,0.0
040913,2023-01-02,1.2
040913,2023-01-03,5.4
040913,2023-01-04,0.0
040913,2023-01-05,0.0
"""

# Sample SEQ Water data (first few lines of a CSV)
SAMPLE_SEQWATER_DATA = """Date,Level (m),Volume (ML),Percentage (%)
2023-01-01,67.2,1025000,83.2
2023-01-02,67.1,1020000,82.8
2023-01-03,67.0,1015000,82.4
2023-01-04,66.9,1010000,82.0
2023-01-05,66.8,1005000,81.6
"""

# Sample bounding boxes for different areas
BOUNDING_BOXES = {
    'brisbane_cbd': (152.95, -27.5, 153.05, -27.4),
    'brisbane_metro': (152.8, -27.6, 153.2, -27.3),
    'southeast_qld': (152.0, -28.0, 153.5, -27.0),
    'small_test_area': (153.0, -27.48, 153.05, -27.45)
}

# Sample DEM file paths
DEM_FILE_PATHS = {
    'lidar_5m': 'lidar_5m_152p95_-27p5_153p05_-27p4.tif',
    'national_1s': 'national_1s_152p95_-27p5_153p05_-27p4.tif'
}

# Sample API responses
API_RESPONSES = {
    'list_dems': {
        'success': True,
        'dems': [
            {
                'id': '0',
                'name': 'lidar_5m_152p95_-27p5_153p05_-27p4.tif',
                'display_name': 'Brisbane CBD (5m LiDAR DEM)',
                'user_name': 'Brisbane CBD',
                'type_name': '5m LiDAR DEM',
                'resolution': 5,
                'coverage': '152.95,-27.50 to 153.05,-27.40',
                'size': '45.2 MB',
                'size_bytes': 47382528,
                'description': 'High-resolution 5m LiDAR-derived Digital Elevation Model covering Brisbane and surrounds.'
            },
            {
                'id': '1',
                'name': 'national_1s_152p0_-28p0_153p5_-27p0.tif',
                'display_name': 'Southeast QLD (1 Second National DEM)',
                'user_name': 'Southeast QLD',
                'type_name': '1 Second National DEM',
                'resolution': 30,
                'coverage': '152.00,-28.00 to 153.50,-27.00',
                'size': '120.5 MB',
                'size_bytes': 126345216,
                'description': 'National 1 Second (~30m) Digital Elevation Model derived from SRTM with hydrological enforcement.'
            }
        ]
    }
}
