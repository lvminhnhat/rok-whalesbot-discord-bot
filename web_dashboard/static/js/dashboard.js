/**
 * WhaleBots Dashboard JavaScript
 */

// Global variables
let refreshTimer = null;
let refreshInterval = 10000; // Default 10 seconds
let refreshCountdown = 0;

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const toastEl = document.getElementById('toast');
    const toastBody = document.getElementById('toast-message');
    
    // Set message
    toastBody.textContent = message;
    
    // Set color based on type
    toastEl.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'bg-info');
    toastEl.classList.add(`bg-${type}`, 'text-white');
    
    // Show toast
    const toast = new bootstrap.Toast(toastEl, {
        autohide: true,
        delay: 3000
    });
    toast.show();
}

/**
 * Get status badge HTML
 */
function getStatusBadge(status) {
    const badges = {
        'RUNNING': '<span class="badge badge-status-running">🟢 Running</span>',
        'STOPPED': '<span class="badge badge-status-stopped">⚪ Stopped</span>',
        'EXPIRED': '<span class="badge badge-status-expired">🟡 Expired</span>',
        'ERROR': '<span class="badge badge-status-error">🔴 Error</span>'
    };
    
    return badges[status] || `<span class="badge bg-secondary">${status}</span>`;
}

/**
 * Format relative time (e.g., "5 minutes ago")
 */
function formatRelativeTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) {
        return `${diffSec}s ago`;
    } else if (diffMin < 60) {
        return `${diffMin}m ago`;
    } else if (diffHour < 24) {
        return `${diffHour}h ago`;
    } else {
        return `${diffDay}d ago`;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Setup auto-refresh for a page
 */
function setupAutoRefresh(refreshFunction, interval = 10000) {
    refreshInterval = interval;
    refreshCountdown = interval / 1000;
    
    // Clear existing timer
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    
    // Update countdown display
    const timerDisplay = document.getElementById('refresh-timer');
    if (timerDisplay) {
        timerDisplay.textContent = refreshCountdown;
    }
    
    // Start countdown
    refreshTimer = setInterval(() => {
        refreshCountdown--;
        
        if (timerDisplay) {
            timerDisplay.textContent = refreshCountdown;
        }
        
        if (refreshCountdown <= 0) {
            refreshCountdown = interval / 1000;
            refreshFunction();
        }
    }, 1000);
}

/**
 * Manual refresh function (called by refresh button)
 */
function refreshData() {
    // Reset countdown
    refreshCountdown = refreshInterval / 1000;
    
    // Call page-specific refresh function if exists
    if (typeof loadOverviewData === 'function') {
        loadOverviewData();
    } else if (typeof loadUsers === 'function') {
        loadUsers();
    } else if (typeof loadInstances === 'function') {
        loadInstances();
    } else if (typeof loadConfig === 'function') {
        loadConfig();
    } else if (typeof loadLogs === 'function') {
        loadLogs();
    }
    
    showToast('Data refreshed', 'success');
}

/**
 * Format uptime seconds to human readable
 */
function formatUptime(seconds) {
    if (!seconds) return '--';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else {
        return `${minutes}m`;
    }
}

/**
 * Format date to local string
 */
function formatDate(dateString) {
    if (!dateString) return '--';
    
    try {
        const date = new Date(dateString);
        return date.toLocaleString();
    } catch (e) {
        return dateString;
    }
}

/**
 * Format date to short format (YYYY-MM-DD)
 */
function formatDateShort(dateString) {
    if (!dateString) return '--';
    
    try {
        const date = new Date(dateString);
        return date.toISOString().split('T')[0];
    } catch (e) {
        return dateString;
    }
}

/**
 * Confirm dialog helper
 */
function confirmAction(message) {
    return confirm(message);
}

/**
 * Handle API errors
 */
function handleApiError(error) {
    console.error('API Error:', error);
    showToast('An error occurred: ' + error.message, 'danger');
}

/**
 * Fetch with error handling
 */
async function fetchApi(url, options = {}) {
    try {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        handleApiError(error);
        throw error;
    }
}

/**
 * Initialize page
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('WhaleBots Dashboard loaded');
    
    // Add click handlers for sidebar nav
    document.querySelectorAll('.sidebar .nav-link').forEach(link => {
        link.addEventListener('click', function() {
            // Clear refresh timer when navigating
            if (refreshTimer) {
                clearInterval(refreshTimer);
                refreshTimer = null;
            }
        });
    });
});

/**
 * Cleanup on page unload
 */
window.addEventListener('beforeunload', function() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
});

