/**
 * WebP Tile Handler for Brisbane Flood Visualization
 * 
 * This module provides utility functions for detecting and loading WebP tiles.
 * It's designed to work alongside the main.js file without modifying existing functionality.
 * 
 * Version: 1.0.0
 * Date: 2025-04-21
 */

// Global object to cache WebP availability results
const webpAvailabilityCache = {};

/**
 * Check if WebP tiles are available for a given DEM
 * 
 * @param {string} demId - The ID of the DEM to check
 * @param {Object} demData - The DEM data object from the API
 * @returns {Object} Object with has_high_res_webp and has_low_res_webp flags
 */
function checkWebPAvailability(demId, demData) {
    console.log(`[WebP] Checking WebP availability for DEM: ${demId}`);
    
    // If we already checked this DEM, return cached result
    if (webpAvailabilityCache[demId]) {
        console.log(`[WebP] Using cached WebP availability for ${demId}:`, webpAvailabilityCache[demId]);
        return webpAvailabilityCache[demId];
    }
    
    // If demData includes WebP availability info, use that
    if (demData && typeof demData.has_high_res_webp !== 'undefined' && typeof demData.has_low_res_webp !== 'undefined') {
        const result = {
            has_high_res_webp: Boolean(demData.has_high_res_webp),
            has_low_res_webp: Boolean(demData.has_low_res_webp)
        };
        console.log(`[WebP] Using API-provided WebP availability for ${demId}:`, result);
        webpAvailabilityCache[demId] = result;
        return result;
    }
    
    // Default to no WebP available if we can't determine
    console.log(`[WebP] Could not determine WebP availability for ${demId}, assuming none available`);
    return {
        has_high_res_webp: false,
        has_low_res_webp: false
    };
}

/**
 * Get the path to the WebP JSON metadata file
 * 
 * @param {string} baseName - The base name of the DEM file (without extension)
 * @param {string} quality - The quality level ('lossless' or 'q75')
 * @returns {string} The path to the JSON metadata file
 */
function getWebPJsonPath(baseName, quality) {
    return `/dem/${baseName}_tiles_${quality}.json`;
}

/**
 * Load WebP tile metadata from JSON file
 * 
 * @param {string} baseName - The base name of the DEM file (without extension)
 * @param {string} quality - The quality level ('lossless' or 'q75')
 * @returns {Promise} Promise that resolves to the tile metadata
 */
function loadWebPTileMetadata(baseName, quality) {
    const jsonPath = getWebPJsonPath(baseName, quality);
    console.log(`[WebP] Loading WebP tile metadata from: ${jsonPath}`);
    
    return fetch(jsonPath)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to load WebP tile metadata: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(`[WebP] Successfully loaded WebP tile metadata: ${data.length} tiles`);
            return data;
        })
        .catch(error => {
            console.error(`[WebP] Error loading WebP tile metadata:`, error);
            throw error;
        });
}

/**
 * Create a Leaflet layer group from WebP tiles
 * 
 * @param {Array} tilesData - Array of tile metadata objects
 * @param {string} baseName - The base name of the DEM file (without extension)
 * @param {string} quality - The quality level ('lossless' or 'q75')
 * @param {Array} bounds - The bounds of the DEM [minLat, minLon, maxLat, maxLon]
 * @returns {L.LayerGroup} Leaflet layer group containing all tile image overlays
 */
function createWebPTileLayer(tilesData, baseName, quality, bounds) {
    console.log(`[WebP] Creating WebP tile layer for ${baseName} with quality ${quality}`);
    
    const layerGroup = L.layerGroup();
    
    // Process each tile and add it to the layer group
    tilesData.forEach(tile => {
        try {
            // Get the tile path
            const tilePath = `/dem/${baseName}_tiles_${quality}/${tile.tile}`;
            
            // Get the tile bounds
            const tileBounds = [
                [tile.bounds[0][0], tile.bounds[0][1]], // [south, west]
                [tile.bounds[1][0], tile.bounds[1][1]]  // [north, east]
            ];
            
            // Create an image overlay for this tile
            const tileOverlay = L.imageOverlay(tilePath, tileBounds, {
                opacity: 0.7,
                interactive: false
            });
            
            // Add the tile to the layer group
            layerGroup.addLayer(tileOverlay);
        } catch (error) {
            console.error(`[WebP] Error creating overlay for tile ${tile.tile}:`, error);
        }
    });
    
    console.log(`[WebP] Created WebP tile layer with ${tilesData.length} tiles`);
    return layerGroup;
}

/**
 * Load WebP tiles for a DEM and create a Leaflet layer
 * 
 * @param {string} baseName - The base name of the DEM file (without extension)
 * @param {string} quality - The quality level ('lossless' or 'q75')
 * @param {Array} bounds - The bounds of the DEM [minLat, minLon, maxLat, maxLon]
 * @returns {Promise} Promise that resolves to a Leaflet layer
 */
function loadWebPTileLayer(baseName, quality, bounds) {
    console.log(`[WebP] Loading WebP tile layer for ${baseName} with quality ${quality}`);
    
    return loadWebPTileMetadata(baseName, quality)
        .then(tilesData => {
            return createWebPTileLayer(tilesData, baseName, quality, bounds);
        })
        .catch(error => {
            console.error(`[WebP] Failed to load WebP tile layer:`, error);
            throw error;
        });
}

/**
 * Attempt to load WebP tiles with fallback to lower quality or PNG
 * 
 * This function implements the priority logic:
 * 1. Try high-resolution WebP tiles first
 * 2. Fall back to low-resolution WebP tiles if high-res isn't available
 * 3. Return null if no WebP tiles are available (caller should fall back to PNG)
 * 
 * @param {string} demId - The ID of the DEM
 * @param {Object} demData - The DEM data object from the API
 * @param {Array} bounds - The bounds of the DEM [minLat, minLon, maxLat, maxLon]
 * @param {boolean} preferHighRes - Whether to prefer high resolution tiles (default: true)
 * @returns {Promise} Promise that resolves to a Leaflet layer or null if no WebP available
 */
function tryLoadWebPWithFallback(demId, demData, bounds, preferHighRes = true) {
    console.log(`[WebP] Attempting to load WebP tiles for ${demId} with fallback logic (prefer high res: ${preferHighRes})`);
    
    // Check WebP availability
    const webpAvailability = checkWebPAvailability(demId, demData);
    
    // Extract base name from the DEM name (remove extension)
    const baseName = demData.name.replace(/\.[^/.]+$/, "");
    
    // If user prefers high res and it's available, try that first
    if (preferHighRes && webpAvailability.has_high_res_webp) {
        console.log(`[WebP] High-resolution WebP tiles available for ${demId}, attempting to load`);
        
        return loadWebPTileLayer(baseName, 'lossless', bounds)
            .then(layer => {
                console.log(`[WebP] Successfully loaded high-resolution WebP tiles for ${demId}`);
                return {
                    layer: layer,
                    quality: 'high'
                };
            })
            .catch(error => {
                console.warn(`[WebP] Failed to load high-resolution WebP tiles, falling back to low-resolution:`, error);
                
                // If low-resolution WebP is available, try that as fallback
                if (webpAvailability.has_low_res_webp) {
                    return loadWebPTileLayer(baseName, 'q75', bounds)
                        .then(layer => {
                            console.log(`[WebP] Successfully loaded low-resolution WebP tiles for ${demId}`);
                            return {
                                layer: layer,
                                quality: 'low'
                            };
                        })
                        .catch(fallbackError => {
                            console.error(`[WebP] Failed to load low-resolution WebP tiles:`, fallbackError);
                            return null; // No WebP available or loadable
                        });
                } else {
                    console.log(`[WebP] No low-resolution WebP tiles available for ${demId}`);
                    return null; // No fallback WebP available
                }
            });
    }
    // If user prefers low res or high res isn't available, try low res
    else if (webpAvailability.has_low_res_webp) {
        console.log(`[WebP] Loading low-resolution WebP tiles for ${demId}`);
        
        return loadWebPTileLayer(baseName, 'q75', bounds)
            .then(layer => {
                console.log(`[WebP] Successfully loaded low-resolution WebP tiles for ${demId}`);
                return {
                    layer: layer,
                    quality: 'low'
                };
            })
            .catch(error => {
                console.error(`[WebP] Failed to load low-resolution WebP tiles:`, error);
                
                // If high-resolution WebP is available and we didn't try it first, try it as fallback
                if (!preferHighRes && webpAvailability.has_high_res_webp) {
                    console.log(`[WebP] Falling back to high-resolution WebP tiles for ${demId}`);
                    return loadWebPTileLayer(baseName, 'lossless', bounds)
                        .then(layer => {
                            console.log(`[WebP] Successfully loaded high-resolution WebP tiles for ${demId}`);
                            return {
                                layer: layer,
                                quality: 'high'
                            };
                        })
                        .catch(fallbackError => {
                            console.error(`[WebP] Failed to load high-resolution WebP tiles:`, fallbackError);
                            return null; // No WebP available or loadable
                        });
                }
                
                return null; // No WebP loadable
            });
    }
    // No WebP available
    else {
        console.log(`[WebP] No WebP tiles available for ${demId}`);
        return Promise.resolve(null); // No WebP available
    }
}

// Export functions for use in other modules
window.WebPHandler = {
    checkWebPAvailability,
    loadWebPTileMetadata,
    createWebPTileLayer,
    loadWebPTileLayer,
    tryLoadWebPWithFallback
};
