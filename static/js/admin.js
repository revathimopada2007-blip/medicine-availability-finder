// Admin Dashboard Actions
function approvePharmacy(id) {
  if (!confirm('Approve this pharmacy registration?')) return;
  fetch(`/api/admin/pharmacies/${id}/approve`, { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast('Pharmacy approved successfully!', 'success');
        setTimeout(() => window.location.reload(), 500);
      } else {
        showToast(data.message, 'danger');
      }
    });
}

function rejectPharmacy(id) {
  if (!confirm('Reject this pharmacy registration?')) return;
  fetch(`/api/admin/pharmacies/${id}/reject`, { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast('Pharmacy registration rejected.', 'warning');
        setTimeout(() => window.location.reload(), 500);
      } else {
        showToast(data.message, 'danger');
      }
    });
}

function openEditMedicineModal(id, name, generic, brand, strength, form, desc, rx) {
  document.getElementById('edit-med-id').value = id;
  document.getElementById('edit-med-name').value = name;
  document.getElementById('edit-med-generic').value = generic || '';
  document.getElementById('edit-med-brand').value = brand || '';
  document.getElementById('edit-med-strength').value = strength || '';
  document.getElementById('edit-med-form').value = form || 'Tablet';
  document.getElementById('edit-med-desc').value = desc || '';
  document.getElementById('edit-med-rx').checked = Boolean(rx && rx !== '0');

  const formEl = document.getElementById('edit-medicine-form');
  formEl.action = `/admin/medicine/${id}/edit`;

  const modal = new bootstrap.Modal(document.getElementById('editMedicineModal'));
  modal.show();
}
