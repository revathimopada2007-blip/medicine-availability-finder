from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from routes.auth import login_required, role_required
from database import get_db_connection
from models.user import get_all_users, set_user_status
from models.pharmacy import get_all_pharmacies, update_pharmacy_status
from models.medicine import get_all_medicines, create_medicine, update_medicine, delete_medicine

admin_bp = Blueprint('admin', __name__)

def get_admin_system_stats():
    conn = get_db_connection()
    total_users = conn.execute("SELECT COUNT(*) as c FROM users WHERE role = 'user'").fetchone()['c']
    total_pharmacies = conn.execute("SELECT COUNT(*) as c FROM pharmacies").fetchone()['c']
    approved_pharmacies = conn.execute("SELECT COUNT(*) as c FROM pharmacies WHERE status = 'approved'").fetchone()['c']
    pending_pharmacies = conn.execute("SELECT COUNT(*) as c FROM pharmacies WHERE status = 'pending'").fetchone()['c']
    total_medicines = conn.execute("SELECT COUNT(*) as c FROM medicines").fetchone()['c']
    total_inventory = conn.execute("SELECT COUNT(*) as c FROM inventory").fetchone()['c']
    conn.close()

    return {
        'total_users': total_users,
        'total_pharmacies': total_pharmacies,
        'approved_pharmacies': approved_pharmacies,
        'pending_pharmacies': pending_pharmacies,
        'total_medicines': total_medicines,
        'total_inventory': total_inventory
    }

@admin_bp.route('/admin/dashboard')
@login_required
@role_required(['admin'])
def dashboard():
    stats = get_admin_system_stats()
    users = get_all_users()
    pharmacies = get_all_pharmacies()
    medicines = get_all_medicines()
    return render_template('admin_dashboard.html', stats=stats, users=users, pharmacies=pharmacies, medicines=medicines)

@admin_bp.route('/admin/users')
@login_required
@role_required(['admin'])
def manage_users():
    users = get_all_users()
    stats = get_admin_system_stats()
    return render_template('admin_dashboard.html', active_tab='users', stats=stats, users=users, pharmacies=get_all_pharmacies(), medicines=get_all_medicines())

@admin_bp.route('/admin/pharmacies')
@login_required
@role_required(['admin'])
def manage_pharmacies():
    pharmacies = get_all_pharmacies()
    stats = get_admin_system_stats()
    return render_template('admin_dashboard.html', active_tab='pharmacies', stats=stats, pharmacies=pharmacies, users=get_all_users(), medicines=get_all_medicines())

@admin_bp.route('/admin/medicines')
@login_required
@role_required(['admin'])
def manage_medicines():
    medicines = get_all_medicines()
    stats = get_admin_system_stats()
    return render_template('admin_dashboard.html', active_tab='medicines', stats=stats, medicines=medicines, users=get_all_users(), pharmacies=get_all_pharmacies())

# Admin Action Endpoints (Web Form or AJAX)
@admin_bp.route('/admin/pharmacy/<int:pharmacy_id>/<action>', methods=['POST'])
@login_required
@role_required(['admin'])
def pharmacy_action(pharmacy_id, action):
    valid_actions = {
        'approve': 'approved',
        'reject': 'rejected',
        'deactivate': 'deactivated'
    }
    if action not in valid_actions:
        flash('Invalid action.', 'danger')
        return redirect(url_for('admin.manage_pharmacies'))

    new_status = valid_actions[action]
    update_pharmacy_status(pharmacy_id, new_status)
    flash(f'Pharmacy status updated to: {new_status.capitalize()}', 'success')
    return redirect(url_for('admin.manage_pharmacies'))

@admin_bp.route('/admin/user/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@role_required(['admin'])
def toggle_user_status(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        new_active = 0 if user['is_active'] else 1
        set_user_status(user_id, new_active)
        status_text = 'activated' if new_active else 'deactivated'
        flash(f'User has been {status_text}.', 'info')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/admin/medicine/add', methods=['POST'])
@login_required
@role_required(['admin'])
def add_medicine():
    name = request.form.get('name', '').strip()
    generic_name = request.form.get('generic_name', '').strip()
    brand_name = request.form.get('brand_name', '').strip()
    strength = request.form.get('strength', '').strip()
    form = request.form.get('form', 'Tablet').strip()
    description = request.form.get('description', '').strip()
    prescription_required = 1 if request.form.get('prescription_required') else 0

    if not name:
        flash('Medicine name is required.', 'danger')
        return redirect(url_for('admin.manage_medicines'))

    med_id, err = create_medicine(name, generic_name, brand_name, strength, form, description, prescription_required)
    if err:
        flash(f'Failed to add medicine: {err}', 'danger')
    else:
        flash(f'Medicine "{name}" added to master catalog.', 'success')
    return redirect(url_for('admin.manage_medicines'))

@admin_bp.route('/admin/medicine/<int:medicine_id>/edit', methods=['POST'])
@login_required
@role_required(['admin'])
def edit_medicine(medicine_id):
    name = request.form.get('name', '').strip()
    generic_name = request.form.get('generic_name', '').strip()
    brand_name = request.form.get('brand_name', '').strip()
    strength = request.form.get('strength', '').strip()
    form = request.form.get('form', 'Tablet').strip()
    description = request.form.get('description', '').strip()
    prescription_required = 1 if request.form.get('prescription_required') else 0

    success, err = update_medicine(medicine_id, name, generic_name, brand_name, strength, form, description, prescription_required)
    if success:
        flash(f'Medicine "{name}" updated successfully.', 'success')
    else:
        flash(f'Failed to update medicine: {err}', 'danger')
    return redirect(url_for('admin.manage_medicines'))

@admin_bp.route('/admin/medicine/<int:medicine_id>/delete', methods=['POST'])
@login_required
@role_required(['admin'])
def remove_medicine(medicine_id):
    success, err = delete_medicine(medicine_id)
    if success:
        flash('Medicine deleted from catalog.', 'info')
    else:
        flash(f'Failed to delete medicine: {err}', 'danger')
    return redirect(url_for('admin.manage_medicines'))

# REST API for Admin
@admin_bp.route('/api/admin/stats')
@login_required
@role_required(['admin'])
def api_stats():
    return jsonify(get_admin_system_stats())

@admin_bp.route('/api/admin/pharmacies/<int:pharmacy_id>/approve', methods=['POST'])
@login_required
@role_required(['admin'])
def api_approve_pharmacy(pharmacy_id):
    success = update_pharmacy_status(pharmacy_id, 'approved')
    return jsonify({'success': success, 'message': 'Pharmacy approved'})

@admin_bp.route('/api/admin/pharmacies/<int:pharmacy_id>/reject', methods=['POST'])
@login_required
@role_required(['admin'])
def api_reject_pharmacy(pharmacy_id):
    success = update_pharmacy_status(pharmacy_id, 'rejected')
    return jsonify({'success': success, 'message': 'Pharmacy rejected'})

@admin_bp.route('/api/admin/pharmacies/<int:pharmacy_id>/deactivate', methods=['POST'])
@login_required
@role_required(['admin'])
def api_deactivate_pharmacy(pharmacy_id):
    success = update_pharmacy_status(pharmacy_id, 'deactivated')
    return jsonify({'success': success, 'message': 'Pharmacy deactivated'})
