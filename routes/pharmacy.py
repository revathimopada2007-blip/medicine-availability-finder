from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from routes.auth import login_required, role_required
from models.pharmacy import get_pharmacy_by_user_id, update_pharmacy_profile
from models.inventory import (
    get_inventory_by_pharmacy, get_inventory_item, add_inventory_item, update_inventory_item,
    delete_inventory_item, get_pharmacy_dashboard_stats
)
from models.medicine import get_all_medicines, create_medicine

pharmacy_bp = Blueprint('pharmacy', __name__)

def get_current_pharmacy():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return get_pharmacy_by_user_id(user_id)

@pharmacy_bp.route('/pharmacy/dashboard')
@login_required
@role_required(['pharmacy'])
def dashboard():
    pharm = get_current_pharmacy()
    if not pharm:
        flash('Pharmacy record not found.', 'danger')
        return redirect(url_for('medicine.index'))

    stats = get_pharmacy_dashboard_stats(pharm['id'])
    inventory = get_inventory_by_pharmacy(pharm['id'])
    all_meds = get_all_medicines()
    return render_template('pharmacy_dashboard.html', pharmacy=pharm, stats=stats, inventory=inventory[:8], all_medicines=all_meds)

@pharmacy_bp.route('/pharmacy/inventory')
@login_required
@role_required(['pharmacy'])
def inventory():
    pharm = get_current_pharmacy()
    if not pharm:
        return redirect(url_for('medicine.index'))

    inventory_list = get_inventory_by_pharmacy(pharm['id'])
    all_meds = get_all_medicines()
    stats = get_pharmacy_dashboard_stats(pharm['id'])
    return render_template('pharmacy_dashboard.html', pharmacy=pharm, stats=stats, inventory=inventory_list, all_medicines=all_meds, view_all_inventory=True)

@pharmacy_bp.route('/pharmacy/profile', methods=['GET', 'POST'])
@login_required
@role_required(['pharmacy'])
def profile():
    pharm = get_current_pharmacy()
    if not pharm:
        return redirect(url_for('medicine.index'))

    if request.method == 'POST':
        pharmacy_name = request.form.get('pharmacy_name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        area = request.form.get('area', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        operating_hours = request.form.get('operating_hours', '').strip()
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()

        if not pharmacy_name or not owner_name or not phone or not address or not city:
            flash('All required fields must be filled.', 'danger')
            return render_template('pharmacy_dashboard.html', pharmacy=pharm, active_tab='profile')

        success, err = update_pharmacy_profile(
            pharmacy_id=pharm['id'],
            pharmacy_name=pharmacy_name,
            owner_name=owner_name,
            phone=phone,
            address=address,
            area=area,
            city=city,
            state=state,
            pincode=pincode,
            operating_hours=operating_hours,
            latitude=latitude if latitude else None,
            longitude=longitude if longitude else None
        )

        if success:
            flash('Pharmacy profile updated successfully!', 'success')
            return redirect(url_for('pharmacy.dashboard'))
        else:
            flash(f'Failed to update profile: {err}', 'danger')

    return render_template('pharmacy_dashboard.html', pharmacy=pharm, active_tab='profile')

# Pharmacy Inventory APIs (REST)
@pharmacy_bp.route('/api/pharmacy/inventory', methods=['GET', 'POST'])
@login_required
@role_required(['pharmacy'])
def api_inventory():
    pharm = get_current_pharmacy()
    if not pharm:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    if request.method == 'GET':
        items = get_inventory_by_pharmacy(pharm['id'])
        return jsonify({'items': items})

    # Add new inventory item
    data = request.get_json() or request.form
    medicine_id = data.get('medicine_id')
    price = data.get('price')
    quantity = data.get('quantity')
    expiry_date = data.get('expiry_date')

    # If medicine doesn't exist, create it if new medicine details provided
    if not medicine_id and data.get('new_medicine_name'):
        new_med_id, err = create_medicine(
            name=data.get('new_medicine_name'),
            generic_name=data.get('new_generic_name'),
            brand_name=data.get('new_brand_name'),
            strength=data.get('new_strength'),
            form=data.get('new_form', 'Tablet'),
            description=data.get('new_description', ''),
            prescription_required=1 if str(data.get('new_prescription_required')).lower() in ('1', 'true', 'yes') else 0
        )
        if err:
            return jsonify({'success': False, 'message': f'Error creating medicine: {err}'}), 400
        medicine_id = new_med_id

    if not medicine_id or price is None or quantity is None:
        return jsonify({'success': False, 'message': 'Medicine, price, and quantity are required.'}), 400

    try:
        price_val = float(price)
        qty_val = int(quantity)
        if price_val < 0 or qty_val < 0:
            return jsonify({'success': False, 'message': 'Price and quantity must be non-negative.'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid price or quantity format.'}), 400

    inv_id, err = add_inventory_item(pharm['id'], medicine_id, price_val, qty_val, expiry_date)
    if err:
        return jsonify({'success': False, 'message': err}), 400

    return jsonify({'success': True, 'message': 'Inventory added / updated successfully.', 'inventory_id': inv_id})

@pharmacy_bp.route('/api/pharmacy/inventory/<int:inventory_id>', methods=['PUT', 'DELETE'])
@login_required
@role_required(['pharmacy'])
def api_inventory_item(inventory_id):
    pharm = get_current_pharmacy()
    if not pharm:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    if request.method == 'PUT':
        data = request.get_json() or {}
        price = data.get('price')
        quantity = data.get('quantity')
        expiry_date = data.get('expiry_date')

        if price is None or quantity is None:
            return jsonify({'success': False, 'message': 'Price and quantity are required.'}), 400

        try:
            price_val = float(price)
            qty_val = int(quantity)
            if price_val < 0 or qty_val < 0:
                return jsonify({'success': False, 'message': 'Price and quantity must be non-negative.'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid price or quantity format.'}), 400

        success, err = update_inventory_item(inventory_id, pharm['id'], price_val, qty_val, expiry_date)
        if success:
            return jsonify({'success': True, 'message': 'Inventory updated successfully.'})
        return jsonify({'success': False, 'message': err}), 400

    elif request.method == 'DELETE':
        success, err = delete_inventory_item(inventory_id, pharm['id'])
        if success:
            return jsonify({'success': True, 'message': 'Inventory item deleted successfully.'})
        return jsonify({'success': False, 'message': err}), 400

@pharmacy_bp.route('/api/pharmacy/dashboard-stats', methods=['GET'])
@login_required
@role_required(['pharmacy'])
def api_dashboard_stats():
    pharm = get_current_pharmacy()
    if not pharm:
        return jsonify({'error': 'Unauthorized'}), 401
    stats = get_pharmacy_dashboard_stats(pharm['id'])
    return jsonify(stats)
