# Brisbane Flood Visualization Project

A web-based visualization tool for Brisbane flood data, enabling analysis, forecasting, and risk assessment.

## Project Overview

This project aims to provide an interactive visualization of flood data for Brisbane, Australia. It combines historical data from the Bureau of Meteorology (BOM) and SEQ Water with digital elevation models (DEMs) to create accurate flood visualizations and potentially predictive models.

## Features

- Interactive map-based visualization of flood extents
- Historical flood data analysis
- Water depth and flow velocity visualization
- Integration with elevation data for accurate flood modeling
- Data pipeline for automated updates from official sources

## Project Structure

```
brisbane-flood-viz/
├── app/                     # Flask backend
│   ├── static/              # JS, CSS, Leaflet plugins
│   ├── templates/           # HTML (Jinja2)
│   └── app.py               # Flask entrypoint
├── data/                    # All data files
│   ├── raw/                 # Original CSVs, raster downloads
│   ├── processed/           # Cleaned data, Parquet files
│   └── geo/                 # DEMs, shapefiles, overlays
├── notebooks/               # Data exploration and modeling (Jupyter)
├── src/                     # Reusable logic modules
│   ├── pipeline/            # ETL scripts for BOM, SEQ Water
│   ├── modeling/            # ML or rule-based forecasting
│   └── raster/              # DEM processing and flood simulation
├── tests/                   # Unit tests
├── requirements.txt         # Python dependencies
└── README.md
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/brisbane-flood-viz.git
   cd brisbane-flood-viz
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Running the Flask Application

```
cd app
python app.py
```

The application will be available at `http://localhost:5000`.

### Data Processing

Data processing scripts are located in the `src/pipeline` directory. These scripts can be used to fetch and process data from official sources.

### Notebooks

Jupyter notebooks for data exploration and analysis are located in the `notebooks` directory.

## Data Sources

- [Bureau of Meteorology (BOM)](http://www.bom.gov.au/)
- [SEQ Water](https://www.seqwater.com.au/)
- [Queensland Spatial Catalogue](https://qldspatial.information.qld.gov.au/)

## Deployment

This application can be deployed to Railway or Render for production use.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

[MIT License](LICENSE)

## Contact

For questions or support, please open an issue in the GitHub repository.
