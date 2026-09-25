// User Dashboard & Profile Logic
document.addEventListener('DOMContentLoaded', function () {
  const userGpsBtn = document.getElementById('user-gps-detect-btn');
  if (userGpsBtn) {
    userGpsBtn.addEventListener('click', function () {
      userGpsBtn.disabled = true;
      userGpsBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Detecting GPS...';

      detectUserLocation(function (coords, err) {
        userGpsBtn.disabled = false;
        userGpsBtn.innerHTML = '<i class="bi bi-geo-alt-fill me-1"></i>Use My Current Location';

        if (err) {
          alert(err);
          return;
        }

        if (coords) {
          const latInput = document.getElementById('loc-latitude');
          const lngInput = document.getElementById('loc-longitude');
          if (latInput) latInput.value = coords.latitude;
          if (lngInput) lngInput.value = coords.longitude;

          showToast('GPS coordinates captured! Save your settings below.', 'success');
        }
      });
    });
  }
});
