# Testing Framework for Brisbane Flood Visualization

This directory contains the testing framework for the Brisbane Flood Visualization project.

## Directory Structure

```
tests/
├── app/                 # Flask application tests
├── pipeline/            # Data pipeline tests
├── integration/         # Integration tests
├── raster/              # Raster processing tests
├── modeling/            # Machine learning model tests
├── utils/               # Test utility functions
├── fixtures/            # Test data and mock objects
│   ├── data/            # Sample data for tests
│   └── mocks/           # Mock objects
└── conftest.py          # Shared pytest configurations
```

## Running Tests

To run all tests:
```
python -m pytest
```

To run a specific test file:
```
python -m pytest tests/pipeline/test_dem_fetcher.py
```

To run a specific test case:
```
python -m pytest tests/pipeline/test_dem_fetcher.py::TestDEMFetcher::test_fetch_1second_dem
```

## Current Test Coverage

- DEM fetcher tests (downloading, renaming, deleting)
- Data fetcher tests (BOM, SEQ Water)

## Adding New Tests

As new functionality is developed, add corresponding tests in the appropriate directory.
