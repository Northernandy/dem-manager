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
const demLayer = L.layerGroup();

// Track if DEM is currently loading to prevent duplicate loads
let isLoadingDEM = false;
let lastLoadedDemId = null;

// Add Wivenhoe Dam marker
const wivenhoeDam = L.marker([-27.3919, 152.6085])
    .bindPopup("<b>Wivenhoe Dam</b><br>Major water supply and flood mitigation dam.")
    .addTo(map);

// Create an overlay layers object
const overlayMaps = {
    "Wivenhoe Dam": wivenhoeDam
};

// Add layer control to the map
L.control.layers(baseMaps, overlayMaps).addTo(map);

// Layer toggle controls
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
    
    // Update slider background gradient to reflect current value
    const percentage = e.target.value;
    e.target.style.background = `linear-gradient(to right, #3498db 0%, #3498db ${percentage}%, #e0e0e0 ${percentage}%, #e0e0e0 100%)`;
    
    // Update opacity for DEM layer
    demLayer.eachLayer(function(layer) {
        if (layer.setOpacity) {
            layer.setOpacity(opacityValue);
        } else if (layer.setStyle) {
            layer.setStyle({ fillOpacity: opacityValue });
        }
    });
});

// Initialize slider background on page load
document.addEventListener('DOMContentLoaded', function() {
    const opacitySlider = document.getElementById('opacity-slider');
    if (opacitySlider) {
        const percentage = opacitySlider.value;
        opacitySlider.style.background = `linear-gradient(to right, #3498db 0%, #3498db ${percentage}%, #e0e0e0 ${percentage}%, #e0e0e0 100%)`;
    }
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

// Function to load a DEM layer from a GeoTIFF URL
function loadDEMLayer(url) {
    // Prevent multiple simultaneous loads
    if (isLoadingDEM) {
        console.log('DEM already loading, ignoring duplicate request');
        return;
    }
    
    isLoadingDEM = true;
    
    // Clear existing DEM layer
    demLayer.clearLayers();
    
    // Show loading message
    document.getElementById('info-content').innerHTML = '<p>Loading DEM data...</p>';
    
    // Check if this is a PNG (RGB visualization) or TIF (raw elevation data)
    const isPNG = url.toLowerCase().endsWith('.png');
    
    if (isPNG) {
        // For PNG files, use a simple ImageOverlay
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.blob();
            })
            .then(blob => {
                const imageUrl = URL.createObjectURL(blob);
                
                // We need to get the bounds for this PNG
                // Extract from the URL or filename
                const urlParts = url.split('/');
                const filename = urlParts[urlParts.length - 1];
                const filenameWithoutExt = filename.replace('.png', '');
                
                // Try to get the bounds from the server
                fetch(`/api/get-dem-bounds/${filenameWithoutExt}`)
                    .then(response => response.json())
                    .then(data => {
                        let bounds;
                        if (data.success && data.bounds) {
                            bounds = [
                                [data.bounds.min_lat, data.bounds.min_lon],
                                [data.bounds.max_lat, data.bounds.max_lon]
                            ];
                        } else {
                            // Fallback to Brisbane area if bounds not available
                            bounds = [[-27.7, 152.5], [-27.2, 153.2]];
                        }
                        
                        // Create an image overlay with the PNG
                        const imageOverlay = L.imageOverlay(imageUrl, bounds, {
                            opacity: 0.7
                        });
                        
                        // Add the layer to the DEM layer group
                        imageOverlay.addTo(demLayer);
                        
                        // Add the DEM layer to the map if not already visible
                        if (!map.hasLayer(demLayer)) {
                            map.addLayer(demLayer);
                            document.getElementById('toggle-dem').checked = true;
                        }
                        
                        // Update the opacity slider to control this layer
                        const currentOpacity = document.getElementById('opacity-slider').value / 100;
                        imageOverlay.setOpacity(currentOpacity);
                        
                        // Update info panel
                        document.getElementById('info-content').innerHTML = `
                            <p><strong>RGB Visualization Loaded</strong></p>
                            <p>Type: Visualization Image (PNG)</p>
                            <p>Use the opacity slider to adjust visibility</p>
                        `;
                        
                        // Fit map to the bounds
                        map.fitBounds(bounds);
                        
                        // Reset loading flag
                        isLoadingDEM = false;
                    })
                    .catch(error => {
                        console.error('Error getting bounds:', error);
                        // Fallback to Brisbane area
                        const bounds = [[-27.7, 152.5], [-27.2, 153.2]];
                        
                        // Create an image overlay with the PNG
                        const imageOverlay = L.imageOverlay(imageUrl, bounds, {
                            opacity: 0.7
                        });
                        
                        // Add the layer to the DEM layer group
                        imageOverlay.addTo(demLayer);
                        
                        // Add the DEM layer to the map if not already visible
                        if (!map.hasLayer(demLayer)) {
                            map.addLayer(demLayer);
                            document.getElementById('toggle-dem').checked = true;
                        }
                        
                        // Update the opacity slider to control this layer
                        const currentOpacity = document.getElementById('opacity-slider').value / 100;
                        imageOverlay.setOpacity(currentOpacity);
                        
                        // Update info panel
                        document.getElementById('info-content').innerHTML = `
                            <p><strong>RGB Visualization Loaded</strong></p>
                            <p>Type: Visualization Image (PNG)</p>
                            <p>Use the opacity slider to adjust visibility</p>
                        `;
                        
                        // Fit map to the bounds
                        map.fitBounds(bounds);
                        
                        // Reset loading flag
                        isLoadingDEM = false;
                    });
            })
            .catch(error => {
                console.error('Error loading RGB visualization:', error);
                document.getElementById('info-content').innerHTML = `
                    <p><strong>Error:</strong> Failed to load RGB visualization</p>
                    <p>${error.message}</p>
                `;
                
                // Reset loading flag
                isLoadingDEM = false;
            });
    } else {
        // For GeoTIFF files, use georaster-layer-for-leaflet as before
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.arrayBuffer();
            })
            .then(arrayBuffer => {
                parseGeoraster(arrayBuffer).then(georaster => {
                    // Log the georaster object to see all available metadata
                    console.log('GeoRaster metadata:', georaster);
                    
                    // Create a Leaflet layer with the georaster
                    const demRasterLayer = new GeoRasterLayer({
                        georaster: georaster,
                        opacity: 0.7,
                        resolution: 256,
                        pixelValuesToColorFn: values => {
                            const value = values[0]; // Get the first band value
                            if (value === -9999 || value === null || value === undefined) {
                                return null; // No color for nodata values
                            }
                            
                            // QGIS-like color ramp for elevation
                            // Get min and max values from the georaster if available
                            const min = georaster.mins ? georaster.mins[0] : 0;
                            const max = georaster.maxs ? georaster.maxs[0] : 1000;
                            const range = max - min;
                            
                            // Normalize the value to 0-1 range
                            const normalized = Math.max(0, Math.min(1, (value - min) / range));
                            
                            // Apply a color ramp similar to QGIS elevation visualization
                            // Blue (low) -> Green -> Yellow -> Red -> White (high)
                            if (normalized < 0.2) {
                                // Blue to Cyan (0-20%)
                                const t = normalized / 0.2;
                                return [0, Math.floor(255 * t), 255, 255];
                            } else if (normalized < 0.4) {
                                // Cyan to Green (20-40%)
                                const t = (normalized - 0.2) / 0.2;
                                return [0, 255, Math.floor(255 * (1 - t)), 255];
                            } else if (normalized < 0.6) {
                                // Green to Yellow (40-60%)
                                const t = (normalized - 0.4) / 0.2;
                                return [Math.floor(255 * t), 255, 0, 255];
                            } else if (normalized < 0.8) {
                                // Yellow to Red (60-80%)
                                const t = (normalized - 0.6) / 0.2;
                                return [255, Math.floor(255 * (1 - t)), 0, 255];
                            } else {
                                // Red to White (80-100%)
                                const t = (normalized - 0.8) / 0.2;
                                return [255, Math.floor(255 * t), Math.floor(255 * t), 255];
                            }
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
                        <p><strong>Elevation Data Loaded</strong></p>
                        <p>Type: Raw Elevation Data (GeoTIFF)</p>
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
                    
                    // Reset loading flag
                    isLoadingDEM = false;
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
                
                // Reset loading flag
                isLoadingDEM = false;
            });
    }
}

// Function to handle DEM selection and loading
function handleDEMSelection(demId) {
    if (!demId) {
        document.getElementById('info-content').innerHTML = '<p>Please select a DEM layer first.</p>';
        return;
    }
    
    // Skip if this is the same DEM that was just loaded
    if (demId === lastLoadedDemId && map.hasLayer(demLayer) && demLayer.getLayers().length > 0) {
        console.log('DEM already loaded, skipping duplicate request');
        return;
    }
    
    // Fetch DEM information
    fetch(`/api/get-dem/${demId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.dem) {
                loadDEMLayer(data.dem.url);
                lastLoadedDemId = demId;
            } else {
                document.getElementById('info-content').innerHTML = `
                    <p><strong>Error:</strong> ${data.message || 'Failed to get DEM information'}</p>
                `;
            }
        })
        .catch(error => {
            console.error('Error fetching DEM information:', error);
            document.getElementById('info-content').innerHTML = '<p>Error fetching DEM information. Please try again.</p>';
        });
}

// Event listener for DEM selector
document.getElementById('dem-selector')?.addEventListener('change', function() {
    const demId = this.value;
    if (!demId) return;
    handleDEMSelection(demId);
});

// Event listener for the update button
document.getElementById('update-map').addEventListener('click', function() {
    const selectedDem = document.getElementById('dem-selector').value;
    handleDEMSelection(selectedDem);
});

// Handle map clicks to show information
map.on('click', function(e) {
    const latlng = e.latlng;
    
    // This would be replaced with an actual query to get data at the clicked location
    document.getElementById('info-content').innerHTML = `
        <p><strong>Clicked Location:</strong></p>
        <p>Latitude: ${latlng.lat.toFixed(6)}</p>
        <p>Longitude: ${latlng.lng.toFixed(6)}</p>
        <p>Click on DEM areas for more details.</p>
    `;
});
