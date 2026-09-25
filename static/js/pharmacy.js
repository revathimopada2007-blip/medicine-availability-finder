// Pharmacy Dashboard & Inventory Management
document.addEventListener('DOMContentLoaded', function () {
  // Add inventory form submission
  const addInvForm = document.getElementById('add-inventory-form');
  if (addInvForm) {
    addInvForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const medicineId = document.getElementById('inv-medicine-select').value;
      const price = document.getElementById('inv-price').value;
      const quantity = document.getElementById('inv-quantity').value;
      const expiry = document.getElementById('inv-expiry').value;

      const payload = {
        medicine_id: medicineId,
        price: parseFloat(price),
        quantity: parseInt(quantity, 10),
        expiry_date: expiry || null
      };

      const submitBtn = addInvForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.innerText = 'Saving...';

      fetch('/api/pharmacy/inventory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
        .then(res => res.json())
        .then(data => {
          submitBtn.disabled = false;
          submitBtn.innerText = 'Add to Inventory';
          if (data.success) {
            showToast('Medicine added to inventory successfully!', 'success');
            // Close modal and reload page
            const modalEl = document.getElementById('addMedicineModal');
            if (modalEl) {
              const modal = bootstrap.Modal.getInstance(modalEl);
              if (modal) modal.hide();
            }
            setTimeout(() => window.location.reload(), 600);
          } else {
            showToast(data.message || 'Failed to add medicine', 'danger');
          }
        })
        .catch(err => {
          submitBtn.disabled = false;
          submitBtn.innerText = 'Add to Inventory';
          showToast('Error saving inventory', 'danger');
        });
    });
  }

  // Quick filter for inventory table
  const invSearchInput = document.getElementById('inventory-table-search');
  if (invSearchInput) {
    invSearchInput.addEventListener('keyup', function () {
      const filter = invSearchInput.value.toLowerCase();
      const rows = document.querySelectorAll('#inventory-table-body tr');
      rows.forEach(row => {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(filter) ? '' : 'none';
      });
    });
  }
});

// Inline / Modal Edit Inventory Item
function openEditInventoryModal(id, medName, price, quantity, expiry) {
  document.getElementById('edit-inv-id').value = id;
  document.getElementById('edit-inv-med-name').innerText = medName;
  document.getElementById('edit-inv-price').value = price;
  document.getElementById('edit-inv-quantity').value = quantity;
  document.getElementById('edit-inv-expiry').value = expiry || '';

  const editModal = new bootstrap.Modal(document.getElementById('editInventoryModal'));
  editModal.show();
}

function saveInventoryEdit() {
  const id = document.getElementById('edit-inv-id').value;
  const price = document.getElementById('edit-inv-price').value;
  const quantity = document.getElementById('edit-inv-quantity').value;
  const expiry = document.getElementById('edit-inv-expiry').value;

  const payload = {
    price: parseFloat(price),
    quantity: parseInt(quantity, 10),
    expiry_date: expiry || null
  };

  fetch(`/api/pharmacy/inventory/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast('Inventory updated successfully!', 'success');
        const modalEl = document.getElementById('editInventoryModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
        setTimeout(() => window.location.reload(), 500);
      } else {
        showToast(data.message || 'Update failed', 'danger');
      }
    })
    .catch(err => {
      showToast('Error updating inventory', 'danger');
    });
}

// Delete inventory item
function deleteInventoryItem(id, medName) {
  if (!confirm(`Are you sure you want to remove "${medName}" from your pharmacy inventory?`)) {
    return;
  }

  fetch(`/api/pharmacy/inventory/${id}`, {
    method: 'DELETE'
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast(`"${medName}" removed from inventory.`, 'info');
        const row = document.getElementById(`inv-row-${id}`);
        if (row) row.remove();
        setTimeout(() => window.location.reload(), 500);
      } else {
        showToast(data.message || 'Delete failed', 'danger');
      }
    })
    .catch(err => {
      showToast('Error deleting item', 'danger');
    });
}
