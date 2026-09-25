from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from routes.auth import login_required, role_required
from models.user import get_user_by_id, update_user_profile, update_user_location
from models.search_history import get_user_search_history, clear_user_search_history
from models.favourite import get_user_favourites, add_favourite, remove_favourite, is_favourite

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
@role_required(['user'])
def dashboard():
    user = get_user_by_id(session['user_id'])
    history = get_user_search_history(session['user_id'], limit=6)
    favourites = get_user_favourites(session['user_id'], user_lat=user.get('latitude'), user_lng=user.get('longitude'))
    return render_template('user_dashboard.html', user=user, history=history, favourites=favourites)

@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@role_required(['user'])
def profile():
    user = get_user_by_id(session['user_id'])
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        area = request.form.get('area', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()

        if not name or not phone:
            flash('Name and phone number are required.', 'danger')
            return render_template('profile.html', user=user)

        success, err = update_user_profile(
            user_id=session['user_id'],
            name=name,
            phone=phone,
            address=address,
            area=area,
            city=city,
            state=state,
            pincode=pincode
        )

        if success:
            session['user_name'] = name
            session['user_city'] = city
            session['user_area'] = area
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('user.profile'))
        else:
            flash(f'Failed to update profile: {err}', 'danger')

    return render_template('profile.html', user=user)

@user_bp.route('/location-settings', methods=['GET', 'POST'])
@login_required
@role_required(['user'])
def location_settings():
    user = get_user_by_id(session['user_id'])
    if request.method == 'POST':
        address = request.form.get('address', '').strip()
        area = request.form.get('area', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()

        success, err = update_user_location(
            user_id=session['user_id'],
            latitude=latitude if latitude else None,
            longitude=longitude if longitude else None,
            address=address if address else None,
            area=area if area else None,
            city=city if city else None,
            state=state if state else None,
            pincode=pincode if pincode else None
        )

        if success:
            session['user_city'] = city
            session['user_area'] = area
            session['user_lat'] = float(latitude) if latitude else None
            session['user_lng'] = float(longitude) if longitude else None
            flash('Location settings updated successfully!', 'success')
            return redirect(url_for('user.dashboard'))
        else:
            flash(f'Failed to update location: {err}', 'danger')

    return render_template('location_settings.html', user=user)

@user_bp.route('/search-history')
@login_required
@role_required(['user'])
def search_history():
    history = get_user_search_history(session['user_id'], limit=50)
    return render_template('search_history.html', history=history)

@user_bp.route('/search-history/clear', methods=['POST'])
@login_required
@role_required(['user'])
def clear_history():
    clear_user_search_history(session['user_id'])
    flash('Search history cleared.', 'info')
    return redirect(url_for('user.search_history'))

@user_bp.route('/favourites')
@login_required
@role_required(['user'])
def favourites():
    user = get_user_by_id(session['user_id'])
    favs = get_user_favourites(session['user_id'], user_lat=user.get('latitude'), user_lng=user.get('longitude'))
    return render_template('favourites.html', favourites=favs)

# User API Endpoints
@user_bp.route('/api/user/profile', methods=['GET', 'PUT'])
@login_required
def api_profile():
    if request.method == 'GET':
        user = get_user_by_id(session['user_id'])
        if user:
            user.pop('password_hash', None)
        return jsonify(user)

    data = request.get_json() or {}
    success, err = update_user_profile(
        session['user_id'],
        data.get('name', ''),
        data.get('phone', ''),
        data.get('address'),
        data.get('area'),
        data.get('city'),
        data.get('state'),
        data.get('pincode')
    )
    if success:
        return jsonify({'success': True, 'message': 'Profile updated'})
    return jsonify({'success': False, 'message': err}), 400

@user_bp.route('/api/user/location', methods=['PUT'])
@login_required
def api_location():
    data = request.get_json() or {}
    lat = data.get('latitude')
    lng = data.get('longitude')
    address = data.get('address')
    area = data.get('area')
    city = data.get('city')
    state = data.get('state')
    pincode = data.get('pincode')

    success, err = update_user_location(
        session['user_id'],
        latitude=lat,
        longitude=lng,
        address=address,
        area=area,
        city=city,
        state=state,
        pincode=pincode
    )
    if success:
        session['user_lat'] = float(lat) if lat else None
        session['user_lng'] = float(lng) if lng else None
        session['user_city'] = city
        session['user_area'] = area
        return jsonify({'success': True, 'message': 'Location updated'})
    return jsonify({'success': False, 'message': err}), 400

@user_bp.route('/api/user/favourites', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_favourites():
    user = get_user_by_id(session['user_id'])
    if request.method == 'GET':
        favs = get_user_favourites(session['user_id'], user_lat=user.get('latitude'), user_lng=user.get('longitude'))
        return jsonify({'favourites': favs})

    data = request.get_json() or {}
    pharmacy_id = data.get('pharmacy_id') or request.args.get('pharmacy_id')
    if not pharmacy_id:
        return jsonify({'success': False, 'message': 'Pharmacy ID is required'}), 400

    if request.method == 'POST':
        success, err = add_favourite(session['user_id'], pharmacy_id)
        return jsonify({'success': success, 'is_favourite': True, 'message': err or 'Added to favourites'})
    elif request.method == 'DELETE':
        success, err = remove_favourite(session['user_id'], pharmacy_id)
        return jsonify({'success': success, 'is_favourite': False, 'message': err or 'Removed from favourites'})
