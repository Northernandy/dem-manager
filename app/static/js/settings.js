// Brisbane Flood Visualization - Settings Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the DEM fetch form
    initDEMFetchForm();
    
    // Initialize the default bounding box button
    initDefaultBBoxButton();
    
    // Initialize delete DEM buttons
    initDeleteDEMButtons();
});

// Initialize the DEM fetch form
function initDEMFetchForm() {
    const fetchDEMForm = document.getElementById('fetch-dem-form');
    if (!fetchDEMForm) return;
    
    fetchDEMForm.addEventListener('submit', function(event) {
        event.preventDefault();
        
        // Get form values
        const demType = document.getElementById('dem-type').value;
        const demName = document.getElementById('dem-name').value;
        const minX = parseFloat(document.getElementById('minx').value);
        const minY = parseFloat(document.getElementById('miny').value);
        const maxX = parseFloat(document.getElementById('maxx').value);
        const maxY = parseFloat(document.getElementById('maxy').value);
        
        // Get selected data type (raw or rgb)
        const dataType = document.querySelector('input[name="downloadDataType"]:checked').value;
        
        // Validate inputs
        if (isNaN(minX) || isNaN(minY) || isNaN(maxX) || isNaN(maxY)) {
            showAlert('Please enter valid coordinates for the bounding box.', 'danger');
            return;
        }
        
        // Show progress indicators
        const progressContainer = document.getElementById('fetch-progress-container');
        const progressBar = document.getElementById('fetch-progress-bar');
        const statusMessage = document.getElementById('fetch-status-message');
        
        progressContainer.classList.remove('d-none');
        progressBar.style.width = '5%';
        progressBar.textContent = '5%';
        statusMessage.textContent = 'Initializing DEM fetch...';
        
        // Disable the submit button
        const submitButton = document.getElementById('fetch-dem-btn');
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Fetching...';
        
        // Prepare the request data
        const requestData = {
            dem_type: demType,
            dem_name: demName,
            bbox: [minX, minY, maxX, maxY],
            dataType: dataType
        };
        
        // Send the fetch request
        fetch('/api/fetch-dem', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Start polling for status updates
                const filename = data.filename;
                pollDEMStatus(filename);
            } else {
                // Show error
                showAlert(`Failed to start DEM fetch: ${data.message}`, 'danger');
                resetFetchForm();
            }
        })
        .catch(error => {
            console.error('Error fetching DEM:', error);
            showAlert('An error occurred while fetching the DEM. Please try again.', 'danger');
            resetFetchForm();
        });
    });
}

// Poll for DEM fetch status
function pollDEMStatus(filename) {
    const progressBar = document.getElementById('fetch-progress-bar');
    const statusMessage = document.getElementById('fetch-status-message');
    
    // Set up polling interval
    const pollInterval = setInterval(() => {
        fetch(`/api/check-dem-status/${filename}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update progress
                    const progress = data.status_data.progress || 0;
                    progressBar.style.width = `${progress}%`;
                    progressBar.textContent = `${progress}%`;
                    statusMessage.textContent = data.status_data.message || 'Processing...';
                    
                    // Check if completed
                    if (data.status_data.status === 'completed') {
                        clearInterval(pollInterval);
                        showAlert('DEM fetched successfully!', 'success');
                        resetFetchForm();
                        
                        // Refresh the page to show the new DEM in the list
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    }
                    // Check if error
                    else if (data.status_data.status === 'error') {
                        clearInterval(pollInterval);
                        showAlert(`Error fetching DEM: ${data.status_data.message}`, 'danger');
                        resetFetchForm();
                    }
                } else {
                    // Handle error in status check
                    console.error('Error checking DEM status:', data.message);
                }
            })
            .catch(error => {
                console.error('Error polling DEM status:', error);
                clearInterval(pollInterval);
                showAlert('Lost connection while fetching DEM. The process may still be running in the background.', 'warning');
                resetFetchForm();
            });
    }, 2000); // Poll every 2 seconds
}

// Reset the fetch form
function resetFetchForm() {
    const submitButton = document.getElementById('fetch-dem-btn');
    submitButton.disabled = false;
    submitButton.textContent = 'Fetch DEM Data';
}

// Initialize the default bounding box button
function initDefaultBBoxButton() {
    const defaultBBoxButton = document.getElementById('load-default-bbox');
    if (!defaultBBoxButton) return;
    
    defaultBBoxButton.addEventListener('click', function(event) {
        event.preventDefault();
        
        // Set default bounding box values (Brisbane area)
        document.getElementById('minx').value = '152.0';
        document.getElementById('miny').value = '-28.0';
        document.getElementById('maxx').value = '153.5';
        document.getElementById('maxy').value = '-27.0';
    });
}

// Initialize delete DEM buttons
function initDeleteDEMButtons() {
    const deleteButtons = document.querySelectorAll('.delete-dem-btn');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filename = this.getAttribute('data-dem-filename');
            if (!filename) return;
            
            if (confirm(`Are you sure you want to delete this DEM: ${filename}?`)) {
                fetch(`/api/delete-dem/${filename}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showAlert('DEM deleted successfully!', 'success');
                        // Remove the card from the UI
                        const card = button.closest('.dem-card');
                        if (card) {
                            card.remove();
                        }
                        
                        // If no more DEMs, show a message
                        const demsContainer = document.getElementById('dems-container');
                        if (demsContainer && demsContainer.children.length === 0) {
                            demsContainer.innerHTML = '<div class="alert alert-info">No DEMs available. Fetch a DEM to get started.</div>';
                        }
                    } else {
                        showAlert(`Failed to delete DEM: ${data.message}`, 'danger');
                    }
                })
                .catch(error => {
                    console.error('Error deleting DEM:', error);
                    showAlert('An error occurred while deleting the DEM.', 'danger');
                });
            }
        });
    });
}

// Show an alert message
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) return;
    
    const alertElement = document.createElement('div');
    alertElement.className = `alert alert-${type} alert-dismissible fade show`;
    alertElement.role = 'alert';
    
    alertElement.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertContainer.appendChild(alertElement);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertElement.classList.remove('show');
        setTimeout(() => {
            alertContainer.removeChild(alertElement);
        }, 150);
    }, 5000);
}
