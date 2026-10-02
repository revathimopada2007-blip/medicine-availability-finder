// Medicine & Location Autocomplete and Search Page Logic
document.addEventListener('DOMContentLoaded', function () {
  // Setup Autocomplete for Search Page
  setupMedicineAutocomplete('search-query-input', 'search-suggestions', 'medicine-search-form');
  setupLocationAutocomplete('search-city-input', 'city-suggestions');

  // Setup Autocomplete for Home Page Hero
  setupMedicineAutocomplete('hero-query-input', 'hero-search-suggestions', 'hero-search-form');
  setupLocationAutocomplete('hero-city-input', 'hero-city-suggestions');

  // GPS Click handlers
  setupGpsHandler('detect-gps-btn', 'search-lat', 'search-lng', 'location-status-text', 'medicine-search-form', 'search-query-input');
  setupGpsHandler('hero-gps-btn', 'hero-lat', 'hero-lng', null, null, null);
});

/**
 * STRICT STARTING-LETTER / PREFIX MATCHING Medicine Autocomplete:
 * Suggestions match only the beginning of the medicine name.
 */
function setupMedicineAutocomplete(inputId, boxId, formId) {
  const input = document.getElementById(inputId);
  const box = document.getElementById(boxId);
  if (!input || !box) return;

  let debounceTimer = null;
  let activeIndex = -1;

  input.addEventListener('input', function () {
    const query = input.value.trim();
    clearTimeout(debounceTimer);
    activeIndex = -1;

    if (query.length < 1) {
      box.style.display = 'none';
      box.innerHTML = '';
      return;
    }

    debounceTimer = setTimeout(function () {
      fetch(`/api/medicines/autocomplete?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
          // Client-side strict prefix filter
          const qLower = query.toLowerCase();
          const filtered = (data || []).filter(med => med.name && med.name.toLowerCase().startsWith(qLower));

          if (!filtered || filtered.length === 0) {
            box.innerHTML = `
              <div class="p-3 text-muted text-center small">
                <i class="bi bi-info-circle me-1"></i>No matching medicines found
              </div>`;
            box.style.display = 'block';
            return;
          }

          let html = '';
          filtered.forEach((med, idx) => {
            const rxBadge = med.prescription_required 
              ? '<span class="badge bg-danger ms-2" style="font-size: 0.7rem;">Rx</span>' 
              : '<span class="badge bg-success-subtle text-success ms-2 border" style="font-size: 0.7rem;">OTC</span>';
            
            const categoryTag = med.category 
              ? `<span class="badge bg-light text-secondary border me-1">${escapeHtml(med.category)}</span>` 
              : '';

            const subInfo = med.brand_name 
              ? `Brand: ${med.brand_name}` 
              : (med.generic_name ? `Generic: ${med.generic_name}` : (med.manufacturer || ''));

            html += `
              <div class="suggestion-item" data-index="${idx}" data-name="${escapeHtml(med.name)}">
                <div>
                  <div class="d-flex align-items-center flex-wrap">
                    <strong class="text-dark">${highlightPrefixMatch(med.name, query)}</strong>
                    ${rxBadge}
                  </div>
                  <div class="small text-muted mt-1">
                    ${categoryTag}
                    <span>${escapeHtml(subInfo)}</span>
                  </div>
                </div>
                <i class="bi bi-search text-muted ms-2"></i>
              </div>
            `;
          });

          box.innerHTML = html;
          box.style.display = 'block';

          box.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', function () {
              const medName = this.getAttribute('data-name');
              input.value = medName;
              box.style.display = 'none';
              if (formId) {
                const form = document.getElementById(formId);
                if (form) form.submit();
              }
            });
          });
        })
        .catch(err => {
          console.error('Error fetching medicine autocomplete:', err);
        });
    }, 150);
  });

  // Keyboard navigation (ArrowUp, ArrowDown, Enter, Escape)
  input.addEventListener('keydown', function (e) {
    const items = box.querySelectorAll('.suggestion-item');
    if (!items || items.length === 0 || box.style.display === 'none') {
      if (e.key === 'Enter' && formId) {
        return;
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % items.length;
      updateActiveItem(items, activeIndex);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + items.length) % items.length;
      updateActiveItem(items, activeIndex);
    } else if (e.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < items.length) {
        e.preventDefault();
        items[activeIndex].click();
      }
    } else if (e.key === 'Escape') {
      box.style.display = 'none';
      activeIndex = -1;
    }
  });

  // Hide on click outside
  document.addEventListener('click', function (e) {
    if (!input.contains(e.target) && !box.contains(e.target)) {
      box.style.display = 'none';
      activeIndex = -1;
    }
  });
}

/**
 * STRICT STARTING-LETTER / PREFIX MATCHING Location Autocomplete:
 * Suggestions match only the beginning of the city/area name.
 */
function setupLocationAutocomplete(inputId, boxId) {
  const input = document.getElementById(inputId);
  const box = document.getElementById(boxId);
  if (!input || !box) return;

  let debounceTimer = null;
  let activeIndex = -1;

  input.addEventListener('input', function () {
    const query = input.value.trim();
    clearTimeout(debounceTimer);
    activeIndex = -1;

    if (query.length < 1) {
      box.style.display = 'none';
      box.innerHTML = '';
      return;
    }

    debounceTimer = setTimeout(function () {
      fetch(`/api/locations/autocomplete?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
          // Client-side strict prefix filter
          const qLower = query.toLowerCase();
          const filtered = (data || []).filter(loc => loc.name && loc.name.toLowerCase().startsWith(qLower));

          if (!filtered || filtered.length === 0) {
            box.innerHTML = `
              <div class="p-3 text-muted text-center small">
                <i class="bi bi-geo-alt me-1"></i>No matching locations found in registered pharmacies
              </div>`;
            box.style.display = 'block';
            return;
          }

          let html = '';
          filtered.forEach((loc, idx) => {
            const isCity = loc.type === 'City';
            const icon = isCity ? 'bi-geo-alt-fill text-danger' : 'bi-pin-map-fill text-primary';
            const badge = isCity 
              ? '<span class="badge bg-success-subtle text-success border ms-2">City</span>' 
              : '<span class="badge bg-info-subtle text-info border ms-2">Locality</span>';

            html += `
              <div class="suggestion-item" data-index="${idx}" data-name="${escapeHtml(loc.name)}">
                <div class="d-flex align-items-center">
                  <i class="bi ${icon} me-2 fs-5"></i>
                  <div>
                    <strong class="text-dark">${highlightPrefixMatch(loc.name, query)}</strong>
                    ${badge}
                    <div class="small text-muted">${escapeHtml(loc.display || loc.state)}</div>
                  </div>
                </div>
                <i class="bi bi-arrow-right-short text-muted fs-4"></i>
              </div>
            `;
          });

          box.innerHTML = html;
          box.style.display = 'block';

          box.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', function () {
              const locName = this.getAttribute('data-name');
              input.value = locName;
              box.style.display = 'none';
            });
          });
        })
        .catch(err => {
          console.error('Error fetching location autocomplete:', err);
        });
    }, 150);
  });

  input.addEventListener('keydown', function (e) {
    const items = box.querySelectorAll('.suggestion-item');
    if (!items || items.length === 0 || box.style.display === 'none') return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % items.length;
      updateActiveItem(items, activeIndex);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + items.length) % items.length;
      updateActiveItem(items, activeIndex);
    } else if (e.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < items.length) {
        e.preventDefault();
        items[activeIndex].click();
      }
    } else if (e.key === 'Escape') {
      box.style.display = 'none';
      activeIndex = -1;
    }
  });

  document.addEventListener('click', function (e) {
    if (!input.contains(e.target) && !box.contains(e.target)) {
      box.style.display = 'none';
      activeIndex = -1;
    }
  });
}

function updateActiveItem(items, index) {
  items.forEach((item, i) => {
    if (i === index) {
      item.classList.add('active');
      item.scrollIntoView({ block: 'nearest' });
    } else {
      item.classList.remove('active');
    }
  });
}

function highlightPrefixMatch(text, query) {
  if (!text || !query) return escapeHtml(text);
  const qLower = query.toLowerCase();
  const tLower = text.toLowerCase();
  if (tLower.startsWith(qLower)) {
    const matchPart = escapeHtml(text.slice(0, query.length));
    const restPart = escapeHtml(text.slice(query.length));
    return `<span class="text-success fw-bold text-decoration-underline">${matchPart}</span>${restPart}`;
  }
  return escapeHtml(text);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function setupGpsHandler(btnId, latInputId, lngInputId, statusTextId, formId, searchInputId) {
  const gpsBtn = document.getElementById(btnId);
  const latInput = document.getElementById(latInputId);
  const lngInput = document.getElementById(lngInputId);
  const locationText = statusTextId ? document.getElementById(statusTextId) : null;
  const searchInput = searchInputId ? document.getElementById(searchInputId) : null;

  if (gpsBtn) {
    gpsBtn.addEventListener('click', function () {
      gpsBtn.disabled = true;
      gpsBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Locating...';

      detectUserLocation(function (coords, err) {
        gpsBtn.disabled = false;
        gpsBtn.innerHTML = '<i class="bi bi-crosshair me-1"></i>Use GPS Location';

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

          if (formId && searchInput && searchInput.value.trim().length > 0) {
            const form = document.getElementById(formId);
            if (form) form.submit();
          }
        }
      });
    });
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
      console.error('Favourite action error:', err);
      showToast('Network error while updating favourites', 'danger');
    });
}
