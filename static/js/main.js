// Main Global Utilities
document.addEventListener('DOMContentLoaded', function () {
  // Auto-dismiss alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 6000);
  });
});

// Browser Geolocation Helper
function detectUserLocation(callback) {
  if (!navigator.geolocation) {
    if (callback) callback(null, 'Geolocation is not supported by your browser.');
    return;
  }

  const options = {
    enableHighAccuracy: true,
    timeout: 10000,
    maximumAge: 300000 // 5 minutes cache
  };

  navigator.geolocation.getCurrentPosition(
    function (position) {
      const coords = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude
      };
      // Save locally
      localStorage.setItem('medfinder_user_lat', coords.latitude);
      localStorage.setItem('medfinder_user_lng', coords.longitude);
      if (callback) callback(coords, null);
    },
    function (error) {
      let msg = 'Unable to retrieve location.';
      switch (error.code) {
        case error.PERMISSION_DENIED:
          msg = 'Location access permission was denied. You can manually enter your city or area.';
          break;
        case error.POSITION_UNAVAILABLE:
          msg = 'Location information is currently unavailable.';
          break;
        case error.TIMEOUT:
          msg = 'Location request timed out.';
          break;
      }
      if (callback) callback(null, msg);
    },
    options
  );
}

// Show Toast notification
function showToast(message, type = 'success') {
  let toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    toastContainer.style.zIndex = '1100';
    document.body.appendChild(toastContainer);
  }

  const toastId = 'toast-' + Date.now();
  const bgClass = type === 'success' ? 'bg-success text-white' : (type === 'danger' ? 'bg-danger text-white' : 'bg-primary text-white');
  const toastHtml = `
    <div id="${toastId}" class="toast align-items-center ${bgClass} border-0 shadow" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">
          ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;
  toastContainer.insertAdjacentHTML('beforeend', toastHtml);
  const toastElement = document.getElementById(toastId);
  const bsToast = new bootstrap.Toast(toastElement, { delay: 4000 });
  bsToast.show();
}
