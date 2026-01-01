// Register Service Worker for PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((registration) => {
        console.log('ServiceWorker registered:', registration.scope);
      })
      .catch((error) => {
        console.log('ServiceWorker registration failed:', error);
      });
  });
}

// Format currency helper
function formatTZS(amount) {
  return 'TZS ' + Number(amount).toLocaleString();
}

// Show toast notification
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
  toast.style.zIndex = '9999';
  toast.innerHTML = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3000);
}

// Confirm before destructive actions
function confirmAction(message) {
  return confirm(message);
}// Takwimu+ Main JavaScript

// ==========================================
// Service Worker Registration for PWA
// ==========================================
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((registration) => {
        console.log('ServiceWorker registered successfully:', registration.scope);

        // Check for updates
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          console.log('ServiceWorker update found');

          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // New content available, show update notification
              showToast('Update available! Refresh to get the latest version.', 'info');
            }
          });
        });
      })
      .catch((error) => {
        console.error('ServiceWorker registration failed:', error);
      });
  });
}

// ==========================================
// PWA Install Prompt
// ==========================================
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;

  // Show install button if not already installed
  const installButton = document.getElementById('install-app-btn');
  if (installButton) {
    installButton.style.display = 'block';
    installButton.addEventListener('click', installApp);
  }
});

function installApp() {
  if (!deferredPrompt) return;

  deferredPrompt.prompt();
  deferredPrompt.userChoice.then((choiceResult) => {
    if (choiceResult.outcome === 'accepted') {
      console.log('User accepted the install prompt');
      showToast('App installed successfully!', 'success');
    }
    deferredPrompt = null;
  });
}

window.addEventListener('appinstalled', () => {
  console.log('PWA was installed');
  deferredPrompt = null;
});

// ==========================================
// Toast Notifications
// ==========================================
function showToast(message, type = 'info') {
  // Remove existing toasts
  const existingToasts = document.querySelectorAll('.custom-toast');
  existingToasts.forEach(t => t.remove());

  // Create toast element
  const toast = document.createElement('div');
  toast.className = `alert alert-${type === 'error' ? 'danger' : type} custom-toast fade-in`;
  toast.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    min-width: 250px;
    max-width: 400px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  `;

  const icon = type === 'success' ? 'check-circle' :
               type === 'error' ? 'exclamation-circle' :
               type === 'warning' ? 'exclamation-triangle' : 'info-circle';

  toast.innerHTML = `
    <div class="d-flex align-items-center">
      <i class="bi bi-${icon} me-2"></i>
      <span class="flex-grow-1">${message}</span>
      <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()"></button>
    </div>
  `;

  document.body.appendChild(toast);

  // Auto remove after 5 seconds
  setTimeout(() => {
    if (toast.parentElement) {
      toast.classList.add('fade-out');
      setTimeout(() => toast.remove(), 300);
    }
  }, 5000);
}

// ==========================================
// Utility Functions
// ==========================================

// Format currency (TZS)
function formatTZS(amount) {
  return 'TZS ' + Number(amount).toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  });
}

// Format date
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });
}

// Format date and time
function formatDateTime(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

// Confirm action with custom message
function confirmAction(message) {
  return confirm(message);
}

// ==========================================
// API Helper Functions
// ==========================================

async function apiGet(endpoint) {
  try {
    const response = await fetch(endpoint);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('API GET Error:', error);
    showToast('Error fetching data. Please try again.', 'error');
    throw error;
  }
}

async function apiPost(endpoint, data) {
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('API POST Error:', error);
    showToast(error.message || 'Error saving data. Please try again.', 'error');
    throw error;
  }
}

async function apiPut(endpoint, data) {
  try {
    const response = await fetch(endpoint, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('API PUT Error:', error);
    showToast('Error updating data. Please try again.', 'error');
    throw error;
  }
}

async function apiDelete(endpoint) {
  try {
    const response = await fetch(endpoint, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('API DELETE Error:', error);
    showToast('Error deleting item. Please try again.', 'error');
    throw error;
  }
}

// ==========================================
// Offline Detection
// ==========================================
window.addEventListener('online', () => {
  showToast('You are back online!', 'success');
  document.body.classList.remove('offline-mode');
});

window.addEventListener('offline', () => {
  showToast('You are offline. Some features may not work.', 'warning');
  document.body.classList.add('offline-mode');
});

// ==========================================
// Form Validation Helpers
// ==========================================
function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

function validatePhone(phone) {
  // Tanzania phone format: +255 or 0 followed by 9 digits
  const re = /^(\+255|0)[67]\d{8}$/;
  return re.test(phone.replace(/\s/g, ''));
}

// ==========================================
// Loading State Helpers
// ==========================================
function showLoading(button) {
  button.disabled = true;
  button.dataset.originalText = button.innerHTML;
  button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
}

function hideLoading(button) {
  button.disabled = false;
  button.innerHTML = button.dataset.originalText || button.innerHTML;
}

// ==========================================
// Initialize
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
  console.log('Takwimu+ initialized');

  // Add fade-in animation to main content
  const main = document.querySelector('main');
  if (main) {
    main.classList.add('fade-in');
  }
});