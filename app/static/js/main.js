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
let lastLoadedDemData = null;

// Store a reference to the current georaster for elevation queries
let currentGeoRaster = null;

// Track WebP availability for the current DEM
let currentWebPAvailability = {
    has_high_res_webp: false,
    has_low_res_webp: false
};

// Get user preference for WebP resolution (default to high)
let preferHighResWebP = localStorage.getItem('preferHighResWebP') !== 'false';

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
    
    // Helper function to recursively apply opacity to layers and layer groups
    function applyOpacityRecursively(layer, opacity) {
        // If it's a layer group, apply to each child layer
        if (layer instanceof L.LayerGroup) {
            layer.eachLayer(function(childLayer) {
                applyOpacityRecursively(childLayer, opacity);
            });
        } 
        // If layer has setOpacity method, use it
        else if (layer.setOpacity) {
            layer.setOpacity(opacity);
        } 
        // For vector layers that use setStyle
        else if (layer.setStyle) {
            layer.setStyle({ fillOpacity: opacity });
        }
    }
    
    // Update opacity for DEM layer
    demLayer.eachLayer(function(layer) {
        applyOpacityRecursively(layer, opacityValue);
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
    if (isLoadingDEM) {
        console.log('Already loading a DEM, please wait');
        return;
    }
    
    isLoadingDEM = true;
    
    // Clear existing DEM layer
    demLayer.clearLayers();
    
    // Show loading message
    document.getElementById('info-content').innerHTML = '<p>Loading DEM data...</p>';
    
    // Check if this is a PNG (RGB visualization) or TIF (raw elevation data)
    const isPNG = url.toLowerCase().endsWith('.png');
    
    // Hide WebP toggle for non-RGB DEMs
    const toggleContainer = document.getElementById('webp-resolution-toggle-container');
    if (!isPNG) {
        console.log('Non-RGB DEM selected, hiding WebP toggle');
        toggleContainer.style.display = 'none';
    }
    
    if (isPNG) {
        // Extract filename information for WebP checks
        const urlParts = url.split('/');
        const filename = urlParts[urlParts.length - 1];
        const filenameWithoutExt = filename.replace('.png', '');
        
        // First, try to get the bounds from the server
        fetch(`/api/get-dem-bounds/${filenameWithoutExt}`)
            .then(response => response.json())
            .then(data => {
                let bounds;
                if (data.success && data.bounds) {
                    bounds = [
                        [data.bounds.min_lat, data.bounds.min_lon],
                        [data.bounds.max_lat, data.bounds.max_lon]
                    ];
                    console.log(`Got bounds from server: ${JSON.stringify(bounds)}`);
                } else {
                    // Fallback to Brisbane area if bounds not available
                    bounds = [[-27.7, 152.5], [-27.2, 153.2]];
                    console.log(`Using fallback bounds: ${JSON.stringify(bounds)}`);
                }
                
                // Get DEM information to check for WebP availability
                return fetch(`/api/get-dem/${lastLoadedDemId}`)
                    .then(response => response.json())
                    .then(demData => {
                        if (!demData.success || !demData.dem) {
                            throw new Error('Failed to get DEM information');
                        }
                        
                        // Store WebP availability information
                        currentWebPAvailability = {
                            has_high_res_webp: demData.dem.has_high_res_webp || false,
                            has_low_res_webp: demData.dem.has_low_res_webp || false
                        };
                        
                        // Show/hide WebP resolution toggle based on availability and DEM type
                        const toggleContainer = document.getElementById('webp-resolution-toggle-container');
                        
                        // Check if this is an RGB visualization (PNG) or raw elevation data (TIF)
                        const isRGB = demData.dem.url.toLowerCase().endsWith('.png');
                        console.log(`DEM type check: URL=${demData.dem.url}, isRGB=${isRGB}`);
                        
                        // Only show toggle for RGB visualizations with both WebP resolutions available
                        if (isRGB && currentWebPAvailability.has_high_res_webp && currentWebPAvailability.has_low_res_webp) {
                            console.log(`Showing WebP toggle: isRGB=${isRGB}, high_res=${currentWebPAvailability.has_high_res_webp}, low_res=${currentWebPAvailability.has_low_res_webp}`);
                            toggleContainer.style.display = 'block';
                            
                            // Set toggle state based on user preference
                            const toggle = document.getElementById('toggle-webp-resolution');
                            toggle.checked = preferHighResWebP;
                            toggle.nextElementSibling.textContent = preferHighResWebP ? 'High Resolution' : 'Low Resolution';
                        } else {
                            console.log(`Hiding WebP toggle: isRGB=${isRGB}, high_res=${currentWebPAvailability.has_high_res_webp}, low_res=${currentWebPAvailability.has_low_res_webp}`);
                            toggleContainer.style.display = 'none';
                        }
                        
                        // Try to load WebP tiles with the user's preference
                        console.log(`Attempting to load WebP tiles (prefer high res: ${preferHighResWebP})`);
                        
                        // Store the bounds for use in later promise chains
                        demData.dem.bounds = bounds;
                        
                        // Only attempt to load WebP if the DEM has WebP tiles available
                        if (currentWebPAvailability.has_high_res_webp || currentWebPAvailability.has_low_res_webp) {
                            return window.WebPHandler.tryLoadWebPWithFallback(lastLoadedDemId, demData.dem, bounds, preferHighResWebP)
                                .then(result => {
                                    if (result) {
                                        console.log(`Successfully loaded ${result.quality}-resolution WebP tiles`);
                                        
                                        // Add the WebP layer to the DEM layer group
                                        demLayer.addLayer(result.layer);
                                        
                                        // Add the DEM layer to the map if not already visible
                                        if (!map.hasLayer(demLayer)) {
                                            map.addLayer(demLayer);
                                            document.getElementById('toggle-dem').checked = true;
                                        }
                                        
                                        // Update the opacity for all layers in the group
                                        const currentOpacity = document.getElementById('opacity-slider').value / 100;
                                        demLayer.eachLayer(function(layer) {
                                            if (layer.setOpacity) {
                                                layer.setOpacity(currentOpacity);
                                            }
                                        });
                                        
                                        // Update info panel
                                        document.getElementById('info-content').innerHTML = `
                                            <p><strong>WebP Tiles Loaded</strong></p>
                                            <p>Type: ${result.quality === 'high' ? 'High Resolution (Lossless)' : 'Low Resolution (Quality 75)'} WebP Tiles</p>
                                            <p>Use the opacity slider to adjust visibility</p>
                                        `;
                                        
                                        // Fit map to the bounds
                                        map.fitBounds(bounds);
                                        
                                        // Reset loading flag
                                        isLoadingDEM = false;
                                        
                                        // Return true to indicate we've handled the layer
                                        return true;
                                    }
                                    
                                    // If WebP loading failed, return false to continue with PNG loading
                                    console.log('No WebP tiles available or loading failed, falling back to PNG');
                                    return false;
                                });
                        } else {
                            // No WebP tiles available, skip WebP loading and return false to continue with PNG loading
                            console.log('No WebP tiles available for this DEM, skipping WebP loading');
                            return Promise.resolve(false);
                        }
                    });
            })
            .then(webpLoaded => {
                console.log(`WebP loading result: ${webpLoaded}, type: ${typeof webpLoaded}`);
                // If WebP was loaded successfully, we're done
                if (webpLoaded === true) {
                    console.log('WebP loading was successful, skipping PNG fallback');
                    return Promise.resolve(); // Return a resolved promise to end the chain
                }
                
                // Otherwise, fall back to the original PNG loading logic
                console.log('Falling back to original PNG loading');
                
                // Extract filename from URL for bounds lookup
                const urlParts = url.split('/');
                const filename = urlParts[urlParts.length - 1];
                const filenameWithoutExt = filename.replace('.png', '');
                
                // Fetch bounds from the server using the PGW file
                console.log(`Fetching bounds for PNG from server: ${filenameWithoutExt}`);
                
                return fetch(`/api/get-dem-bounds/${filenameWithoutExt}`)
                    .then(response => response.json())
                    .then(boundsData => {
                        let bounds;
                        if (boundsData.success && boundsData.bounds) {
                            bounds = [
                                [boundsData.bounds.min_lat, boundsData.bounds.min_lon],
                                [boundsData.bounds.max_lat, boundsData.bounds.max_lon]
                            ];
                            console.log(`Got bounds from server for PNG: ${JSON.stringify(bounds)}`);
                        } else {
                            // Fallback to Brisbane area if bounds not available
                            bounds = [[-27.7, 152.5], [-27.2, 153.2]];
                            console.log(`Using fallback bounds for PNG: ${JSON.stringify(bounds)}`);
                        }
                        
                        // For PNG files, use a simple ImageOverlay
                        console.log(`Attempting to fetch PNG from URL: ${url}`);
                        return fetch(url, { cache: 'no-store' }) // Force a fresh fetch, don't use cache
                            .then(response => {
                                console.log(`PNG fetch response status: ${response.status}`);
                                if (!response.ok) {
                                    throw new Error(`HTTP error! Status: ${response.status}`);
                                }
                                return response.blob();
                            })
                            .then(blob => {
                                console.log(`Successfully got PNG blob, size: ${blob.size} bytes`);
                                const imageUrl = URL.createObjectURL(blob);
                                console.log(`Created object URL for PNG: ${imageUrl}`);
                                
                                // Create an image overlay with the PNG
                                console.log(`Creating image overlay with bounds: ${JSON.stringify(bounds)}`);
                                const imageOverlay = L.imageOverlay(imageUrl, bounds, {
                                    opacity: 0.7
                                });
                                
                                console.log(`Adding image overlay to DEM layer group`);
                                imageOverlay.addTo(demLayer);
                                
                                console.log(`Checking if DEM layer is already on map: ${map.hasLayer(demLayer)}`);
                                if (!map.hasLayer(demLayer)) {
                                    console.log(`Adding DEM layer to map`);
                                    map.addLayer(demLayer);
                                    document.getElementById('toggle-dem').checked = true;
                                } else {
                                    console.log(`DEM layer already on map, not adding again`);
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
                                console.log(`Fitting map to bounds: ${JSON.stringify(bounds)}`);
                                map.fitBounds(bounds);
                                
                                // Reset loading flag
                                isLoadingDEM = false;
                                
                                // Return true to indicate success
                                return true;
                            })
                            .catch(error => {
                                // Handle errors in PNG loading
                                console.error(`Error loading PNG: ${error.message}`);
                                document.getElementById('info-content').innerHTML = `
                                    <p><strong>Error Loading Visualization</strong></p>
                                    <p>${error.message}</p>
                                `;
                                
                                // Reset loading flag
                                isLoadingDEM = false;
                                
                                // Return false to indicate failure
                                return false;
                            });
                    });
            })
            .catch(error => {
                console.error('Error loading DEM data:', error);
                document.getElementById('info-content').innerHTML = `
                    <p><strong>Error:</strong> Failed to load DEM data</p>
                    <p>${error.message}</p>
                `;
                
                // Reset loading flag
                isLoadingDEM = false;
            });
    } else {
        // For GeoTIFF files, use georaster-layer-for-leaflet as before
        console.log('Loading GeoTIFF file:', url);
        fetch(url)
            .then(response => {
                console.log('GeoTIFF fetch response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.arrayBuffer();
            })
            .then(arrayBuffer => {
                console.log('GeoTIFF arrayBuffer received, size:', arrayBuffer.byteLength);
                console.log('Parsing GeoTIFF with parseGeoraster...');
                
                parseGeoraster(arrayBuffer).then(georaster => {
                    console.log('GeoTIFF successfully parsed!');
                    // Store the georaster reference for elevation queries
                    currentGeoRaster = georaster;
                    
                    // Create a Leaflet layer with the georaster - using minimal configuration
                    const demRasterLayer = new GeoRasterLayer({
                        georaster: georaster,
                        opacity: 0.7,
                        pane: 'overlayPane',
                        zIndex: 650
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
                    console.log('Fitting map to GeoTIFF bounds:', bounds);
                    map.fitBounds(bounds);
                    
                    // Reset loading flag
                    isLoadingDEM = false;
                    
                    console.log('GeoTIFF loading complete, currentGeoRaster:', 
                        currentGeoRaster ? 'available' : 'null');
                }).catch(error => {
                    console.error('Error parsing GeoTIFF:', error);
                    currentGeoRaster = null;
                    document.getElementById('info-content').innerHTML = `
                        <p><strong>Error:</strong> Failed to parse GeoTIFF</p>
                        <p>${error.message}</p>
                    `;
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
                lastLoadedDemData = data;
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

// Event listener for WebP resolution toggle
document.getElementById('toggle-webp-resolution').addEventListener('change', function(e) {
    // Update preference
    preferHighResWebP = e.target.checked;
    
    // Store preference in localStorage
    localStorage.setItem('preferHighResWebP', preferHighResWebP);
    
    // Update label
    this.nextElementSibling.textContent = preferHighResWebP ? 'High Resolution' : 'Low Resolution';
    
    // Reload current DEM with new resolution preference if we have a DEM loaded
    if (lastLoadedDemId) {
        // Clear existing DEM layer to force reload
        demLayer.clearLayers();
        
        // Call handleDEMSelection to reload with new preference
        handleDEMSelection(lastLoadedDemId);
    }
});

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialize any tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Add event listener for baselayerchange to ensure DEM layer stays visible
map.on('baselayerchange', function(e) {
    // If we have a DEM layer visible and it contains a GeoTIFF, refresh it
    if (map.hasLayer(demLayer) && demLayer.getLayers().length > 0 && currentGeoRaster) {
        // Get the current layer
        const currentLayer = demLayer.getLayers()[0];
        
        // Get the current opacity
        const currentOpacity = currentLayer.getOpacity ? currentLayer.getOpacity() : 0.7;
        
        // Clear and recreate the layer
        demLayer.clearLayers();
        
        // Recreate with the same settings but ensure correct z-index and pane
        const refreshedLayer = new GeoRasterLayer({
            georaster: currentGeoRaster,
            opacity: currentOpacity,
            pane: 'overlayPane',
            zIndex: 650
        });
        
        // Add back to the map
        refreshedLayer.addTo(demLayer);
    }
});

// Handle map clicks to show information
map.on('click', function(e) {
    const latlng = e.latlng;
    console.log('Map clicked at:', latlng);
    
    // Initialize info content with location data
    let infoContent = `
        <p><strong>Clicked Location:</strong></p>
        <p>Latitude: ${latlng.lat.toFixed(6)}</p>
        <p>Longitude: ${latlng.lng.toFixed(6)}</p>
    `;
    
    // Check if we have a georaster to query for elevation
    console.log('Current georaster available:', currentGeoRaster !== null);
    if (currentGeoRaster) {
        console.log('GeoRaster properties:', {
            width: currentGeoRaster.width,
            height: currentGeoRaster.height,
            noDataValue: currentGeoRaster.noDataValue,
            xmin: currentGeoRaster.xmin,
            xmax: currentGeoRaster.xmax,
            ymin: currentGeoRaster.ymin,
            ymax: currentGeoRaster.ymax
        });
        
        try {
            // Alternative approach to get elevation value
            // Convert lat/lng to pixel coordinates
            const x = Math.round((latlng.lng - currentGeoRaster.xmin) / currentGeoRaster.pixelWidth);
            const y = Math.round((currentGeoRaster.ymax - latlng.lat) / currentGeoRaster.pixelHeight);
            
            console.log('Converted to pixel coordinates:', { x, y });
            
            // Check if coordinates are within bounds
            if (x >= 0 && x < currentGeoRaster.width && y >= 0 && y < currentGeoRaster.height) {
                // Get value at pixel coordinates
                const value = currentGeoRaster.values[0][y][x];
                console.log('Elevation value retrieved from pixel coordinates:', value);
                
                // Only display if we have a valid value
                if (value !== null && value !== undefined && 
                    value !== currentGeoRaster.noDataValue && 
                    value !== -9999 && value !== -3.4028234663852886e+38) {
                    infoContent += `
                        <p><strong>Elevation:</strong> ${value.toFixed(2)} meters</p>
                    `;
                    console.log('Valid elevation value displayed:', value);
                } else {
                    infoContent += `
                        <p><strong>Elevation:</strong> No data available at this point</p>
                    `;
                    console.log('Invalid elevation value:', value);
                }
            } else {
                console.log('Coordinates out of bounds:', { x, y, width: currentGeoRaster.width, height: currentGeoRaster.height });
                infoContent += `
                    <p><strong>Elevation:</strong> Location outside DEM coverage area</p>
                `;
            }
        } catch (error) {
            console.error('Error getting elevation value:', error);
            console.error('Error name:', error.name);
            console.error('Error message:', error.message);
            console.error('Error stack:', error.stack);
            
            // Check if the georaster has the expected methods and properties
            console.log('GeoRaster methods:', Object.getOwnPropertyNames(Object.getPrototypeOf(currentGeoRaster)));
            
            infoContent += `
                <p><strong>Elevation:</strong> Error retrieving data</p>
                <p><small>Error: ${error.message}</small></p>
            `;
        }
    } else {
        console.log('No georaster available for elevation query');
        infoContent += `
            <p>Click on DEM areas for elevation details.</p>
        `;
    }
    
    // Update the info panel with the content
    document.getElementById('info-content').innerHTML = infoContent;
});
