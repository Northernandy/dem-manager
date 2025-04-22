// Client-side logging system
const Logger = {
    logs: [],
    maxLogs: 100,
    
    // Log levels
    INFO: 'info',
    WARNING: 'warning',
    ERROR: 'error',
    DEBUG: 'debug',
    
    // Log a message
    log: function(level, message, data = null) {
        const logEntry = {
            timestamp: new Date().toISOString(),
            level: level,
            message: message,
            data: data
        };
        
        // Add to in-memory logs
        this.logs.unshift(logEntry);
        
        // Trim logs if they exceed max size
        if (this.logs.length > this.maxLogs) {
            this.logs = this.logs.slice(0, this.maxLogs);
        }
        
        // Log to console with appropriate styling
        const styles = {
            [this.INFO]: 'color: #0d6efd',
            [this.WARNING]: 'color: #ffc107; font-weight: bold',
            [this.ERROR]: 'color: #dc3545; font-weight: bold',
            [this.DEBUG]: 'color: #6c757d'
        };
        
        console.log(`%c[${level.toUpperCase()}] ${message}`, styles[level]);
        if (data) {
            console.log(data);
        }
        
        // Send to server for persistent logging
        this.sendToServer(logEntry);
        
        return logEntry;
    },
    
    // Convenience methods
    info: function(message, data = null) {
        return this.log(this.INFO, message, data);
    },
    
    warning: function(message, data = null) {
        return this.log(this.WARNING, message, data);
    },
    
    error: function(message, data = null) {
        return this.log(this.ERROR, message, data);
    },
    
    debug: function(message, data = null) {
        return this.log(this.DEBUG, message, data);
    },
    
    // Send log to server
    sendToServer: function(logEntry) {
        fetch('/api/log', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(logEntry)
        }).catch(err => {
            console.error('Failed to send log to server:', err);
        });
    },
    
    // Show logs in UI
    showLogs: function() {
        // Create a modal for displaying logs
        const modalId = 'logsModal' + Date.now();
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = modalId;
        modal.setAttribute('tabindex', '-1');
        modal.setAttribute('aria-hidden', 'true');
        
        let logsHtml = '';
        this.logs.forEach(log => {
            const levelClass = {
                [this.INFO]: 'text-info',
                [this.WARNING]: 'text-warning',
                [this.ERROR]: 'text-danger',
                [this.DEBUG]: 'text-secondary'
            }[log.level];
            
            logsHtml += `
                <div class="log-entry mb-2">
                    <div class="d-flex">
                        <span class="me-2 text-muted">${new Date(log.timestamp).toLocaleTimeString()}</span>
                        <span class="me-2 ${levelClass}">[${log.level.toUpperCase()}]</span>
                        <span>${log.message}</span>
                    </div>
                    ${log.data ? `<pre class="mt-1 p-2 bg-light small">${JSON.stringify(log.data, null, 2)}</pre>` : ''}
                </div>
            `;
        });
        
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Application Logs</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
                        ${logsHtml || '<p class="text-muted">No logs available</p>'}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" id="download-logs-${modalId}">Download Logs</button>
                        <button type="button" class="btn btn-danger" id="clear-logs-${modalId}">Clear Logs</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Show the modal
        const modalObj = new bootstrap.Modal(modal);
        modalObj.show();
        
        // Handle download logs button
        document.getElementById(`download-logs-${modalId}`).addEventListener('click', () => {
            const logsJson = JSON.stringify(this.logs, null, 2);
            const blob = new Blob([logsJson], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = `dem-app-logs-${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            
            setTimeout(() => {
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }, 100);
        });
        
        // Handle clear logs button
        document.getElementById(`clear-logs-${modalId}`).addEventListener('click', () => {
            if (confirm('Are you sure you want to clear all logs?')) {
                this.logs = [];
                modalObj.hide();
            }
        });
        
        // Remove modal from DOM when hidden
        modal.addEventListener('hidden.bs.modal', function() {
            modal.remove();
        });
    }
};

// Add a logs button to the navbar
document.addEventListener('DOMContentLoaded', function() {
    // Don't add logs button to navbar, but keep the Logger functionality
    /*
    const navbarNav = document.querySelector('.navbar-nav');
    const logsLi = document.createElement('li');
    logsLi.className = 'nav-item';
    logsLi.innerHTML = '<a class="nav-link" href="#" id="show-logs-btn"><i class="bi bi-journal-text"></i> Logs</a>';
    navbarNav.appendChild(logsLi);
    
    document.getElementById('show-logs-btn').addEventListener('click', function(e) {
        e.preventDefault();
        Logger.showLogs();
    });
    */
});

// Show DEM description based on selection
document.getElementById('dem-type').addEventListener('change', function() {
    const selectedOption = this.options[this.selectedIndex];
    const description = selectedOption.getAttribute('data-description') || '';
    document.getElementById('dem-description').textContent = description;
});

// Trigger the change event to show the initial description
document.getElementById('dem-type').dispatchEvent(new Event('change'));

// Update zoom value display
document.getElementById('default-zoom').addEventListener('input', function() {
    document.getElementById('zoom-value').textContent = this.value;
    
    // Update slider background gradient to reflect current value
    const min = parseInt(this.min) || 5;
    const max = parseInt(this.max) || 18;
    const val = parseInt(this.value);
    const percentage = ((val - min) / (max - min)) * 100;
    
    this.style.background = `linear-gradient(to right, #3498db 0%, #3498db ${percentage}%, #e0e0e0 ${percentage}%, #e0e0e0 100%)`;
});

// Initialize slider background on page load
window.addEventListener('DOMContentLoaded', function() {
    const zoomSlider = document.getElementById('default-zoom');
    if (zoomSlider) {
        const min = parseInt(zoomSlider.min) || 5;
        const max = parseInt(zoomSlider.max) || 18;
        const val = parseInt(zoomSlider.value);
        const percentage = ((val - min) / (max - min)) * 100;
        
        zoomSlider.style.background = `linear-gradient(to right, #3498db 0%, #3498db ${percentage}%, #e0e0e0 ${percentage}%, #e0e0e0 100%)`;
    }
});

// Function to fetch a new DEM
function fetchDEM() {
    const demType = document.getElementById('dem-type').value;
    const demName = document.getElementById('dem-name').value;
    const minX = parseFloat(document.getElementById('minx').value);
    const minY = parseFloat(document.getElementById('miny').value);
    const maxX = parseFloat(document.getElementById('maxx').value);
    const maxY = parseFloat(document.getElementById('maxy').value);
    
    // Get selected download data type
    const selectedDataType = document.querySelector('input[name="downloadDataType"]:checked').value;

    // Validate inputs
    if (isNaN(minX) || isNaN(minY) || isNaN(maxX) || isNaN(maxY)) {
        showAlert('Please enter valid coordinates for the bounding box.', 'danger');
        return;
    }
    
    // Create bbox array
    const bbox = [minX, minY, maxX, maxY];
    
    // Log fetch attempt with details
    Logger.info(`Initiating DEM fetch: type=${demType}, name=${demName}, bbox=${bbox.join(',')}`);
    
    // Disable button and show spinner
    const fetchBtn = document.getElementById('fetch-dem-btn');
    fetchBtn.disabled = true;
    fetchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" id="fetch-spinner" role="status"></span> Fetching...';
    
    // Show progress container
    const progressContainer = document.getElementById('fetch-progress-container');
    progressContainer.classList.remove('d-none');
    
    // Clear previous logs
    const logsElement = document.getElementById('fetch-logs');
    logsElement.textContent = '';
    logsElement.style.display = 'block';
    
    // Make API request
    fetch('/api/fetch-dem', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            dem_type: demType,
            dem_name: demName,
            bbox: bbox,
            dataType: selectedDataType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // If DEM already exists, show success and refresh list
            if (data.status === 'exists') {
                completeDownload(data);
                return;
            }
            
            // Otherwise, start polling for status updates
            const filename = data.filename;
            Logger.info(`DEM fetch initiated: ${filename}`);
            startStatusPolling(filename);
        } else {
            // Handle error
            Logger.error(`Failed to fetch DEM: ${data.message}`);
            completeDownload({
                success: false,
                message: 'Failed to fetch DEM: ' + data.message
            });
        }
    })
    .catch(error => {
        // Handle network error
        Logger.error(`Error fetching DEM: ${error.message}`);
        completeDownload({
            success: false,
            message: 'Error fetching DEM: ' + error.message
        });
        showAlert(`Error fetching DEM: ${error.message}`, 'danger');
    });
}

// Function to poll for status updates
function startStatusPolling(filename) {
    const logsElement = document.getElementById('fetch-logs');
    
    // Make sure the log element is visible
    logsElement.style.display = 'block';
    
    // Track completion time for timeout
    let completionTime = null;
    
    // Poll every second
    const pollInterval = setInterval(() => {
        fetch(`/api/check-dem-status/${filename}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Network response was not ok: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    const statusData = data.status_data;
                    
                    // Update logs if available
                    if (statusData.logs && statusData.logs.length > 0) {
                        logsElement.textContent = statusData.logs.join('\n');
                        
                        // Auto-scroll to bottom
                        logsElement.scrollTop = logsElement.scrollHeight;
                    }
                    
                    // Check if the download is complete or failed
                    if (statusData.status === 'complete' || statusData.status === 'completed') {
                        // Record completion time if not already set
                        if (!completionTime) {
                            completionTime = new Date();
                            Logger.info(`DEM download completed at ${completionTime.toISOString()}`);
                        }
                        
                        // Check if 8 seconds have passed since completion
                        const currentTime = new Date();
                        const elapsedSinceCompletion = (currentTime - completionTime) / 1000;
                        
                        if (elapsedSinceCompletion >= 8) {
                            clearInterval(pollInterval);
                            Logger.info(`Stopped polling after 8 seconds of completion`);
                            completeDownload({
                                success: true,
                                message: 'DEM download completed successfully',
                                filename: filename
                            });
                        }
                    } else if (statusData.status === 'error') {
                        // Record completion time if not already set
                        if (!completionTime) {
                            completionTime = new Date();
                            Logger.error(`DEM download failed at ${completionTime.toISOString()}`);
                        }
                        
                        // Check if 8 seconds have passed since completion
                        const currentTime = new Date();
                        const elapsedSinceCompletion = (currentTime - completionTime) / 1000;
                        
                        if (elapsedSinceCompletion >= 8) {
                            clearInterval(pollInterval);
                            Logger.info(`Stopped polling after 8 seconds of error`);
                            completeDownload({
                                success: false,
                                message: statusData.message || 'An error occurred during DEM download'
                            });
                        }
                    }
                } else {
                    // Error checking status
                    const errorMsg = 'Error checking status: ' + data.message;
                    Logger.error(errorMsg);
                }
            })
            .catch(error => {
                const errorMsg = 'Error checking status: ' + error.message;
                Logger.error(errorMsg);
            });
    }, 1000);
}

// Function to complete the download process
function completeDownload(data) {
    const spinner = document.getElementById('fetch-spinner');
    const fetchBtn = document.getElementById('fetch-dem-btn');
    
    // Hide spinner
    spinner.classList.add('d-none');
    fetchBtn.disabled = false;
    fetchBtn.textContent = 'Fetch DEM Data';
    
    // Make sure the progress container and logs remain visible
    const progressContainer = document.getElementById('fetch-progress-container');
    const logsElement = document.getElementById('fetch-logs');
    
    if (progressContainer) {
        // Remove d-none class if it was added
        progressContainer.classList.remove('d-none');
    }
    
    if (logsElement) {
        // Make sure logs remain visible
        logsElement.style.display = 'block';
    }
    
    // Show result
    let type = data.success ? 'success' : 'danger';
    showAlert(data.message, type);
    
    // Refresh the DEMs list if successful
    if (data.success) {
        refreshDEMsList();
    }
}

// Function to refresh the DEMs list
function refreshDEMsList() {
    fetch('/api/list-dems')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const demsContainer = document.getElementById('dems-container');
                
                if (data.dems.length === 0) {
                    demsContainer.innerHTML = '<div class="alert alert-info">No DEMs available. Fetch a DEM to get started.</div>';
                    return;
                }
                
                let html = '';
                data.dems.forEach(dem => {
                    html += `
                        <div class="card dem-card" data-dem-id="${dem.id}">
                            <div class="card-body">
                                <h5 class="card-title">${dem.display_name}</h5>
                                <h6 class="card-subtitle mb-2 text-muted">${dem.name}</h6>
                                <p class="card-text">
                                    <small>Resolution: ${dem.resolution}m</small><br>
                                    <small>Coverage: ${dem.coverage}</small><br>
                                    <small>Size: ${dem.size}</small><br>
                                    <small>Type: <span class="badge ${dem.data_type === 'Elevation Data' ? 'bg-success' : 'bg-danger'}">${dem.data_type}</span></small>
                                </p>
                                <div class="d-flex justify-content-between">
                                    <button class="btn btn-sm btn-outline-danger delete-dem-btn" data-dem-filename="${dem.name}">Delete</button>
                                    <a href="/" class="btn btn-sm btn-outline-primary view-dem-btn" data-dem-id="${dem.id}">View on Map</a>
                                </div>
                                <div class="d-flex justify-content-between mt-2">
                                    <button class="btn btn-sm btn-outline-secondary rename-dem-btn" data-dem-filename="${dem.name}" data-dem-display-name="${dem.display_name}">Rename</button>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                demsContainer.innerHTML = html;
                
                // Attach event listeners to the newly created buttons
                attachDemButtonEventListeners();
            }
        })
        .catch(error => {
            showAlert('Error refreshing DEMs list: ' + error.message, 'danger');
        });
}

// Function to attach event listeners to DEM buttons
function attachDemButtonEventListeners() {
    // Attach event listeners to rename buttons
    document.querySelectorAll('.rename-dem-btn').forEach(button => {
        button.addEventListener('click', function() {
            const filename = this.dataset.demFilename;
            const currentName = this.dataset.demDisplayName;
            
            // Create a modal for renaming
            const modalId = 'renameModal' + Date.now();
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.id = modalId;
            modal.setAttribute('tabindex', '-1');
            modal.setAttribute('aria-hidden', 'true');
            
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Rename DEM</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="rename-form-${modalId}">
                                <div class="mb-3">
                                    <label for="new-name-${modalId}" class="form-label">New Display Name</label>
                                    <input type="text" class="form-control" id="new-name-${modalId}" value="${currentName}" required>
                                    <div class="form-text">Original filename: ${filename}</div>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="submit" form="rename-form-${modalId}" class="btn btn-primary">Save</button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Show the modal
            const modalObj = new bootstrap.Modal(modal);
            modalObj.show();
            
            // Handle form submission
            document.getElementById(`rename-form-${modalId}`).addEventListener('submit', function(event) {
                event.preventDefault();
                
                const newName = document.getElementById(`new-name-${modalId}`).value;
                
                if (!newName) {
                    return;
                }
                
                // Send rename request
                fetch('/api/rename-dem', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        filename: filename,
                        display_name: newName
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // Hide modal
                    modalObj.hide();
                    
                    // Show result
                    let type = data.success ? 'success' : 'danger';
                    showAlert(data.message, type);
                    
                    // Refresh the DEMs list if successful
                    if (data.success) {
                        refreshDEMsList();
                    }
                })
                .catch(error => {
                    // Hide modal
                    modalObj.hide();
                    
                    // Show error
                    showAlert('Error: ' + error.message, 'danger');
                });
            });
            
            // Remove modal from DOM when hidden
            modal.addEventListener('hidden.bs.modal', function() {
                modal.remove();
            });
        });
    });
}

// Initial attachment of event listeners
document.addEventListener('DOMContentLoaded', function() {
    attachDemButtonEventListeners();
});

// Handle DEM deletion
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('delete-dem-btn')) {
        if (confirm('Are you sure you want to delete this DEM?')) {
            const filename = e.target.dataset.demFilename;
            const deleteBtn = e.target;
            
            // Log deletion attempt
            Logger.info(`Attempting to delete DEM: ${filename}`);
            
            // Disable button and show loading state
            deleteBtn.disabled = true;
            deleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Deleting...';
            
            fetch(`/api/delete-dem/${filename}`, {
                method: 'POST'
            })
            .then(response => {
                // Log the raw response for debugging
                Logger.debug(`Delete response status: ${response.status}`, {
                    statusText: response.statusText,
                    headers: Object.fromEntries([...response.headers.entries()])
                });
                
                return response.json();
            })
            .then(data => {
                // Re-enable button
                deleteBtn.disabled = false;
                deleteBtn.textContent = 'Delete';
                
                // Log the response data
                if (data.success) {
                    Logger.info(`Successfully deleted DEM: ${filename}`, data);
                } else {
                    Logger.error(`Failed to delete DEM: ${filename}`, data);
                }
                
                let type = data.success ? 'success' : 'danger';
                showAlert(data.message, type);
                
                if (data.success) {
                    // Remove the card from the UI
                    const card = e.target.closest('.dem-card');
                    card.remove();
                    
                    // If no DEMs left, show the "No DEMs" message
                    if (document.querySelectorAll('.dem-card').length === 0) {
                        document.getElementById('dems-container').innerHTML = 
                            '<div class="alert alert-info">No DEMs available. Fetch a DEM to get started.</div>';
                    }
                } else {
                    // If error contains "in use", show a more helpful message
                    if (data.message.includes('in use')) {
                        Logger.warning(`DEM file is in use: ${filename}`, {
                            message: data.message,
                            userAgent: navigator.userAgent,
                            timestamp: new Date().toISOString()
                        });
                        
                        showAlert(`
                            <div>
                                <p>This DEM file is currently in use by another application. Please close any map views or applications that might be using this DEM and try again.</p>
                            </div>
                        `, 'warning', 15000);
                    }
                }
            })
            .catch(error => {
                // Re-enable button
                deleteBtn.disabled = false;
                deleteBtn.textContent = 'Delete';
                
                // Log the error
                Logger.error(`Error during DEM deletion: ${filename}`, {
                    error: error.toString(),
                    stack: error.stack,
                    userAgent: navigator.userAgent,
                    timestamp: new Date().toISOString()
                });
                
                showAlert('Error: ' + error.message, 'danger');
            });
        }
    }
});

// Handle WebP tile regeneration
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('regenerate-webp-btn')) {
        const filename = e.target.dataset.demFilename;
        const btn = e.target;
        
        // Disable the button and show loading state
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Regenerating...';
        
        // Import the WebP tile generation function from the server
        fetch(`/api/regenerate-webp/${filename}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            // Re-enable button
            btn.disabled = false;
            btn.textContent = 'Regenerate WebP';
            
            if (data.success) {
                showAlert('WebP tile generation started in the background. The files will be available shortly.', 'success');
            } else {
                showAlert('Error: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            // Re-enable button
            btn.disabled = false;
            btn.textContent = 'Regenerate WebP';
            
            showAlert('Error: ' + error.message, 'danger');
        });
    }
});

// Function to format bbox inputs to always show 3 decimal places
function formatBboxInputs() {
    // Get all bbox input fields
    const bboxInputs = [
        document.getElementById('minx'),
        document.getElementById('miny'),
        document.getElementById('maxx'),
        document.getElementById('maxy'),
        document.getElementById('default-minx'),
        document.getElementById('default-miny'),
        document.getElementById('default-maxx'),
        document.getElementById('default-maxy')
    ];
    
    // For each input, add event listeners to format the value
    bboxInputs.forEach(input => {
        if (!input) return; // Skip if input doesn't exist
        
        // Format initial value
        if (input.value) {
            input.value = parseFloat(input.value).toFixed(3);
        }
        
        // Format on blur (when user leaves the field)
        input.addEventListener('blur', function() {
            if (this.value) {
                this.value = parseFloat(this.value).toFixed(3);
            }
        });
    });
}

// Function to show alerts with optional timeout
function showAlert(message, type = 'success', timeout = 5000) {
    const alertContainer = document.getElementById('alert-container');
    
    // Create the alert element
    const alertElement = document.createElement('div');
    alertElement.className = `alert alert-${type} alert-dismissible fade show`;
    alertElement.setAttribute('role', 'alert');
    
    // Set the message
    alertElement.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Clear any existing alerts
    while (alertContainer.firstChild) {
        alertContainer.removeChild(alertContainer.firstChild);
    }
    
    // Add the alert to the container
    alertContainer.appendChild(alertElement);
    
    // Auto-dismiss after specified timeout
    setTimeout(() => {
        if (alertElement.parentNode === alertContainer) {
            alertContainer.removeChild(alertElement);
        }
    }, timeout);
}

// Handle map settings form submission
document.getElementById('map-settings-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Get form values
    const defaultLat = parseFloat(document.getElementById('default-lat').value);
    const defaultLon = parseFloat(document.getElementById('default-lon').value);
    const defaultZoom = parseInt(document.getElementById('default-zoom').value);
    const defaultBasemap = document.getElementById('default-basemap').value;
    const defaultMinX = parseFloat(document.getElementById('default-minx').value);
    const defaultMinY = parseFloat(document.getElementById('default-miny').value);
    const defaultMaxX = parseFloat(document.getElementById('default-maxx').value);
    const defaultMaxY = parseFloat(document.getElementById('default-maxy').value);
    
    // Save settings to localStorage
    const mapSettings = {
        center: [defaultLat, defaultLon],
        zoom: defaultZoom,
        basemap: defaultBasemap,
        bbox: [defaultMinX, defaultMinY, defaultMaxX, defaultMaxY]
    };
    
    localStorage.setItem('mapSettings', JSON.stringify(mapSettings));
    
    // Show success message
    showAlert('Map settings saved successfully!', 'success');
});

// Load saved map settings on page load
document.addEventListener('DOMContentLoaded', function() {
    formatBboxInputs();
    
    const savedSettings = localStorage.getItem('mapSettings');
    if (savedSettings) {
        const settings = JSON.parse(savedSettings);
        
        // Apply saved settings to form
        if (settings.center) {
            document.getElementById('default-lat').value = settings.center[0];
            document.getElementById('default-lon').value = settings.center[1];
        }
        
        if (settings.zoom) {
            document.getElementById('default-zoom').value = settings.zoom;
            document.getElementById('zoom-value').textContent = settings.zoom;
        }
        
        if (settings.basemap) {
            document.getElementById('default-basemap').value = settings.basemap;
        }
        
        if (settings.bbox) {
            document.getElementById('default-minx').value = settings.bbox[0];
            document.getElementById('default-miny').value = settings.bbox[1];
            document.getElementById('default-maxx').value = settings.bbox[2];
            document.getElementById('default-maxy').value = settings.bbox[3];
        }
    }
    
    // Load default bounding box values for DEM fetching form
    const loadDefaultBoundingBox = document.getElementById('load-default-bbox');
    if (loadDefaultBoundingBox) {
        loadDefaultBoundingBox.addEventListener('click', function(e) {
            e.preventDefault();
            const savedSettings = localStorage.getItem('mapSettings');
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);
                if (settings.bbox) {
                    document.getElementById('minx').value = settings.bbox[0];
                    document.getElementById('miny').value = settings.bbox[1];
                    document.getElementById('maxx').value = settings.bbox[2];
                    document.getElementById('maxy').value = settings.bbox[3];
                }
            }
        });
    }
});

// Handle DEM fetch form submission
document.getElementById('fetch-dem-form').addEventListener('submit', function(e) {
    e.preventDefault();
    fetchDEM();
});

// Initialize popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});
