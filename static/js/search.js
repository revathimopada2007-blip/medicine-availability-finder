// Search Page & Auto-suggestions Logic
document.addEventListener('DOMContentLoaded', function () {
  const searchInput = document.getElementById('search-query-input');
  const suggestionsBox = document.getElementById('search-suggestions');
  const gpsBtn = document.getElementById('detect-gps-btn');
  const latInput = document.getElementById('search-lat');
  const lngInput = document.getElementById('search-lng');
  const locationText = document.getElementById('location-status-text');

  // GPS Click handler
  if (gpsBtn) {
    gpsBtn.addEventListener('click', function () {
      gpsBtn.disabled = true;
      gpsBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Locating...';

      detectUserLocation(function (coords, err) {
        gpsBtn.disabled = false;
        gpsBtn.innerHTML = '<i class="bi bi-crosshair me-1"></i>Use My Current Location';

        if (err) {
          alert(err);
          return;
        }

        if (coords) {
          if (latInput) latInput.value = coords.latitude;
          if (lngInput) lngInput.value = coords.longitude;
          if (locationText) {
            locationText.innerHTML = `<span class="badge bg-success"><i class="bi bi-geo-alt-fill me-1"></i>GPS Detected (${coords.latitude.toFixed(4)}, ${coords.longitude.toFixed(4)})</span>`;
          }
          showToast('GPS coordinates acquired successfully!', 'success');

          // If on search page and query present, trigger search form submission
          const form = document.getElementById('medicine-search-form');
          if (form && searchInput && searchInput.value.trim().length > 0) {
            form.submit();
          }
        }
      });
    });
  }

  // Live Auto-suggest on search input
  if (searchInput && suggestionsBox) {
    let debounceTimer = null;

    searchInput.addEventListener('input', function () {
      const q = searchInput.value.trim();
      clearTimeout(debounceTimer);

      if (q.length < 2) {
        suggestionsBox.style.display = 'none';
        suggestionsBox.innerHTML = '';
        return;
      }

      debounceTimer = setTimeout(function () {
        fetch(`/api/medicines/search?q=${encodeURIComponent(q)}`)
          .then(res => res.json())
          .then(data => {
            if (!data || data.length === 0) {
              suggestionsBox.style.display = 'none';
              return;
            }

            let html = '';
            data.forEach(med => {
              const rxBadge = med.prescription_required ? '<span class="badge bg-danger ms-2">Rx</span>' : '';
              html += `
                <div class="suggestion-item" onclick="selectSuggestion('${med.name.replace(/'/g, "\\'")}')">
                  <div>
                    <strong>${med.name}</strong> <span class="text-muted">(${med.strength || ''} ${med.form || ''})</span>
                    ${rxBadge}
                    <div class="small text-muted">${med.brand_name ? 'Brand: ' + med.brand_name : (med.generic_name ? 'Generic: ' + med.generic_name : '')}</div>
                  </div>
                  <i class="bi bi-search text-muted"></i>
                </div>
              `;
            });
            suggestionsBox.innerHTML = html;
            suggestionsBox.style.display = 'block';
          })
          .catch(err => {
            console.error('Error fetching suggestions:', err);
          });
      }, 250);
    });

    // Hide suggestions on outside click
    document.addEventListener('click', function (e) {
      if (!searchInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
        suggestionsBox.style.display = 'none';
      }
    });
  }
});

function selectSuggestion(medicineName) {
  const searchInput = document.getElementById('search-query-input');
  const suggestionsBox = document.getElementById('search-suggestions');
  if (searchInput) {
    searchInput.value = medicineName;
  }
  if (suggestionsBox) {
    suggestionsBox.style.display = 'none';
  }
  const form = document.getElementById('medicine-search-form');
  if (form) {
    form.submit();
  }
}

// Toggle favourite pharmacy
function toggleFavourite(pharmacyId, btnElement) {
  if (!pharmacyId) return;

  const isFav = btnElement.classList.contains('active') || btnElement.getAttribute('data-fav') === 'true';
  const method = isFav ? 'DELETE' : 'POST';

  fetch('/api/user/favourites', {
    method: method,
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ pharmacy_id: pharmacyId })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        if (!isFav) {
          btnElement.classList.add('active', 'btn-danger');
          btnElement.classList.remove('btn-outline-danger');
          btnElement.setAttribute('data-fav', 'true');
          btnElement.innerHTML = '<i class="bi bi-heart-fill"></i>';
          showToast('Added to favourite pharmacies!', 'success');
        } else {
          btnElement.classList.remove('active', 'btn-danger');
          btnElement.classList.add('btn-outline-danger');
          btnElement.setAttribute('data-fav', 'false');
          btnElement.innerHTML = '<i class="bi bi-heart"></i>';
          showToast('Removed from favourites', 'info');
        }
      } else {
        if (data.message && data.message.includes('login')) {
          window.location.href = '/login';
        } else {
          showToast(data.message || 'Action failed', 'danger');
        }
      }
    })
    .catch(err => {
      console.error(err);
      showToast('Please log in to save favourite pharmacies.', 'warning');
    });
}
