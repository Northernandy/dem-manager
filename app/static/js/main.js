// Brisbane Flood Visualization - Main JavaScript

// Initialize the map centered on Brisbane with a wider view that includes Ipswich and Wivenhoe Dam
const map = L.map('map').setView([-27.5, 152.8], 10);

// Base map layers
const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
});

// Topographic layer from OpenTopoMap
const topoLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
    maxZoom: 17
});

// Add the default OSM layer to the map
osmLayer.addTo(map);

// Create a layer control for base maps
const baseMaps = {
    "Street Map": osmLayer,
    "Topographic Map": topoLayer
};

// Add a scale control
L.control.scale().addTo(map);

// Layer groups for organization
const floodLayers = L.layerGroup().addTo(map);
const demLayer = L.layerGroup();

// Sample GeoJSON layer (placeholder for actual flood data)
const sampleGeoJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "name": "Sample Flood Area",
                "depth": "2.5m",
                "date": "2022-02-28"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [153.0, -27.45],
                        [153.05, -27.45],
                        [153.05, -27.5],
                        [153.0, -27.5],
                        [153.0, -27.45]
                    ]
                ]
            }
        }
    ]
};

// Add Wivenhoe Dam marker
const wivenhoeDam = L.marker([-27.3919, 152.6085])
    .bindPopup("<b>Wivenhoe Dam</b><br>Major water supply and flood mitigation dam.")
    .addTo(map);

// Style function for the flood layer
function getFloodStyle(feature) {
    return {
        fillColor: '#3498db',
        weight: 2,
        opacity: 1,
        color: '#2980b9',
        fillOpacity: 0.7
    };
}

// Create a popup for each feature
function onEachFeature(feature, layer) {
    if (feature.properties) {
        let popupContent = `
            <h3>${feature.properties.name}</h3>
            <p>Water Depth: ${feature.properties.depth}</p>
            <p>Date: ${feature.properties.date}</p>
        `;
        layer.bindPopup(popupContent);
    }
}

// Add the sample GeoJSON layer to the map
const floodLayer = L.geoJSON(sampleGeoJSON, {
    style: getFloodStyle,
    onEachFeature: onEachFeature
}).addTo(floodLayers);

// Function to load a DEM layer from a GeoTIFF URL
function loadDEMLayer(url) {
    // Clear existing DEM layer
    demLayer.clearLayers();
    
    // Show loading message
    document.getElementById('info-content').innerHTML = '<p>Loading DEM data...</p>';
    
    // Use georaster-layer-for-leaflet to display the GeoTIFF
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.arrayBuffer();
        })
        .then(arrayBuffer => {
            parseGeoraster(arrayBuffer).then(georaster => {
                // Create a Leaflet layer with the georaster
                const demRasterLayer = new GeoRasterLayer({
                    georaster: georaster,
                    opacity: 0.7,
                    resolution: 256,
                    pixelValuesToColorFn: values => {
                        const value = values[0]; // Get the first band value
                        if (value === -9999 || value === 0 || value === null || value === undefined) {
                            return null; // No color for nodata values
                        }
                        
                        // Color ramp for elevation
                        // Lower elevations (blue) to higher elevations (brown)
                        if (value < 0) return [0, 0, 255, 255]; // Deep water
                        if (value < 5) return [0, 100, 255, 255]; // Shallow water
                        if (value < 20) return [0, 255, 0, 255]; // Low elevation (green)
                        if (value < 50) return [255, 255, 0, 255]; // Medium elevation (yellow)
                        if (value < 100) return [255, 150, 0, 255]; // Higher elevation (orange)
                        return [150, 75, 0, 255]; // Highest elevation (brown)
                    }
                });
                
                // Add the layer to the DEM layer group
                demRasterLayer.addTo(demLayer);
                
                // Add the DEM layer to the map if not already visible
                if (!map.hasLayer(demLayer)) {
                    map.addLayer(demLayer);
                    document.getElementById('toggle-dem').checked = true;
                }
                
                // Update the opacity slider to control this layer
                const currentOpacity = document.getElementById('opacity-slider').value / 100;
                demRasterLayer.setOpacity(currentOpacity);
                
                // Update info panel
                document.getElementById('info-content').innerHTML = `
                    <p><strong>DEM Data Loaded</strong></p>
                    <p>Resolution: ${georaster.pixelWidth.toFixed(6)} x ${georaster.pixelHeight.toFixed(6)} degrees</p>
                    <p>Size: ${georaster.width} x ${georaster.height} pixels</p>
                    <p>Use the opacity slider to adjust visibility</p>
                `;
                
                // Fit map to the bounds of the DEM
                const bounds = [
                    [georaster.ymin, georaster.xmin],
                    [georaster.ymax, georaster.xmax]
                ];
                map.fitBounds(bounds);
            });
        })
        .catch(error => {
            console.error('Error loading DEM data:', error);
            document.getElementById('info-content').innerHTML = `
                <p><strong>Error:</strong> Failed to load DEM data</p>
                <p>${error.message}</p>
            `;
            
            // Add a placeholder rectangle as fallback
            const demPlaceholder = L.rectangle(
                [[-27.7, 152.5], [-27.2, 153.2]], // Wider Brisbane area
                { 
                    color: "#ff7800", 
                    weight: 1,
                    fillOpacity: 0.5
                }
            ).bindPopup("DEM Layer (Placeholder - Failed to load actual data)");
            
            demLayer.addLayer(demPlaceholder);
            
            // If not already visible, add the DEM layer to the map
            if (!map.hasLayer(demLayer)) {
                map.addLayer(demLayer);
                document.getElementById('toggle-dem').checked = true;
            }
        });
}

// Function to fetch DEM data from the backend
function fetchDEMData() {
    document.getElementById('info-content').innerHTML = '<p>Requesting DEM data...</p>';
    
    fetch('/api/fetch-dem')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                document.getElementById('info-content').innerHTML = `
                    <p><strong>DEM Data:</strong> Successfully fetched</p>
                    <p>Resolution: ${data.resolution}m</p>
                    <p>Coverage: ${data.coverage}</p>
                    <p>File: ${data.file}</p>
                `;
                
                // If the DEM data includes a URL to the GeoTIFF, we could load it here
                if (data.url) {
                    loadDEMLayer(data.url);
                }
            } else {
                document.getElementById('info-content').innerHTML = `
                    <p><strong>Error:</strong> ${data.message}</p>
                `;
            }
        })
        .catch(error => {
            console.error('Error fetching DEM data:', error);
            document.getElementById('info-content').innerHTML = '<p>Error fetching DEM data. Please try again.</p>';
        });
}

// Create an overlay layers object
const overlayMaps = {
    "Flood Extent": floodLayers,
    "Elevation Model": demLayer
};

// Add layer control to the map
L.control.layers(baseMaps, overlayMaps).addTo(map);

// Layer toggle controls
document.getElementById('toggle-flood').addEventListener('change', function(e) {
    if (e.target.checked) {
        map.addLayer(floodLayers);
    } else {
        map.removeLayer(floodLayers);
    }
});

document.getElementById('toggle-dem').addEventListener('change', function(e) {
    if (e.target.checked) {
        map.addLayer(demLayer);
    } else {
        map.removeLayer(demLayer);
    }
});

// Opacity slider control
document.getElementById('opacity-slider').addEventListener('input', function(e) {
    const opacityValue = e.target.value / 100;
    document.getElementById('opacity-value').textContent = `${e.target.value}%`;
    
    // Update opacity for flood layers
    floodLayers.eachLayer(function(layer) {
        if (layer.setStyle) {
            layer.setStyle({ fillOpacity: opacityValue });
        }
    });
    
    // Update opacity for DEM layer
    demLayer.eachLayer(function(layer) {
        if (layer.setStyle) {
            layer.setStyle({ fillOpacity: opacityValue });
        }
    });
});

// Nominatim address search functionality
document.getElementById('search-btn').addEventListener('click', function() {
    searchAddress();
});

document.getElementById('address-search').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        searchAddress();
    }
});

function searchAddress() {
    const address = document.getElementById('address-search').value;
    if (!address) return;
    
    // Show loading indicator
    document.getElementById('info-content').innerHTML = '<p>Searching for address...</p>';
    
    // Use Nominatim API to search for the address
    fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1&countrycodes=au`)
        .then(response => response.json())
        .then(data => {
            if (data && data.length > 0) {
                const result = data[0];
                const lat = parseFloat(result.lat);
                const lon = parseFloat(result.lon);
                
                // Create a marker at the found location
                const marker = L.marker([lat, lon]).addTo(map);
                marker.bindPopup(`<b>${result.display_name}</b>`).openPopup();
                
                // Center map on the found location
                map.setView([lat, lon], 15);
                
                // Update info panel
                document.getElementById('info-content').innerHTML = `
                    <p><strong>Found Location:</strong> ${result.display_name}</p>
                    <p>Latitude: ${lat.toFixed(6)}</p>
                    <p>Longitude: ${lon.toFixed(6)}</p>
                `;
            } else {
                document.getElementById('info-content').innerHTML = '<p>No results found for that address.</p>';
            }
        })
        .catch(error => {
            console.error('Error searching for address:', error);
            document.getElementById('info-content').innerHTML = '<p>Error searching for address. Please try again.</p>';
        });
}

// Event listener for the update button
document.getElementById('update-map').addEventListener('click', function() {
    const selectedDate = document.getElementById('date-selector').value;
    const selectedLayer = document.getElementById('data-layer').value;
    
    // This would be replaced with an actual API call to fetch data
    console.log(`Updating map with: Date=${selectedDate}, Layer=${selectedLayer}`);
    
    // If DEM layer is selected, fetch DEM data
    if (selectedLayer === 'dem') {
        fetchDEMData();
        return;
    }
    
    // Simulate API call and update
    document.getElementById('info-content').innerHTML = '<p>Loading data...</p>';
    
    // Simulate network delay
    setTimeout(() => {
        // Update the info panel
        document.getElementById('info-content').innerHTML = `
            <p><strong>Selected Date:</strong> ${selectedDate || 'None'}</p>
            <p><strong>Selected Layer:</strong> ${selectedLayer}</p>
            <p>Data updated successfully.</p>
            <hr>
            <p><small>This is a placeholder. In production, this would display actual data from the backend API.</small></p>
        `;
    }, 500);
});

// Handle map clicks to show information
map.on('click', function(e) {
    const latlng = e.latlng;
    
    // This would be replaced with an actual query to get data at the clicked location
    document.getElementById('info-content').innerHTML = `
        <p><strong>Clicked Location:</strong></p>
        <p>Latitude: ${latlng.lat.toFixed(6)}</p>
        <p>Longitude: ${latlng.lng.toFixed(6)}</p>
        <p>Click on flood areas for more details.</p>
    `;
});
