from flask import Blueprint, render_template, request, session, jsonify
from models.medicine import search_medicines, get_medicine_by_id, get_all_medicines
from models.inventory import (
    search_nearby_pharmacies_with_medicine, get_medicine_stock_across_pharmacies, 
    get_inventory_by_pharmacy, check_pharmacies_exist_in_city
)
from models.pharmacy import get_pharmacy_by_id, search_locations
from models.user import get_user_by_id
from models.search_history import save_search_query
from models.favourite import is_favourite

medicine_bp = Blueprint('medicine', __name__)

@medicine_bp.route('/')
def index():
    user = None
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
    sample_medicines = search_medicines('Paracetamol', limit=8)
    if not sample_medicines:
        sample_medicines = search_medicines('', limit=8)
    return render_template('index.html', user=user, sample_medicines=sample_medicines)

@medicine_bp.route('/search')
def search():
    query = request.args.get('q', '').strip()
    user_city = request.args.get('city', '').strip()
    user_lat = request.args.get('lat')
    user_lng = request.args.get('lng')
    user_area = request.args.get('area')
    user_pincode = request.args.get('pincode')

    current_user = None
    if 'user_id' in session:
        current_user = get_user_by_id(session['user_id'])
        if current_user:
            if not user_city and current_user.get('city'):
                user_city = current_user['city']
            if not user_lat and current_user.get('latitude'):
                user_lat = current_user['latitude']
            if not user_lng and current_user.get('longitude'):
                user_lng = current_user['longitude']
            if not user_area and current_user.get('area'):
                user_area = current_user['area']
            if not user_pincode and current_user.get('pincode'):
                user_pincode = current_user['pincode']

        if query:
            save_search_query(session['user_id'], query)

    results = []
    has_searched = bool(query)
    no_pharmacies_in_city = False

    if query:
        # Check if city filter is provided and whether any pharmacy is registered in that city
        if user_city:
            has_pharmacies, count = check_pharmacies_exist_in_city(user_city)
            if not has_pharmacies:
                no_pharmacies_in_city = True

        if not no_pharmacies_in_city:
            results = search_nearby_pharmacies_with_medicine(
                medicine_query=query,
                user_lat=user_lat,
                user_lng=user_lng,
                user_city=user_city,
                user_area=user_area,
                user_pincode=user_pincode
            )

        if 'user_id' in session:
            for r in results:
                r['is_fav'] = is_favourite(session['user_id'], r['pharmacy_id'])
        else:
            for r in results:
                r['is_fav'] = False

    return render_template(
        'search.html',
        query=query,
        results=results,
        has_searched=has_searched,
        no_pharmacies_in_city=no_pharmacies_in_city,
        user_lat=user_lat,
        user_lng=user_lng,
        user_city=user_city,
        user_area=user_area,
        user_pincode=user_pincode,
        current_user=current_user
    )

@medicine_bp.route('/medicine/<int:medicine_id>')
def medicine_details(medicine_id):
    med = get_medicine_by_id(medicine_id)
    if not med:
        return render_template('search.html', error_msg="Medicine not found.", has_searched=True)

    user_lat = session.get('user_lat')
    user_lng = session.get('user_lng')
    if 'user_id' in session:
        u = get_user_by_id(session['user_id'])
        if u:
            user_lat = u.get('latitude')
            user_lng = u.get('longitude')

    pharmacies_stock = get_medicine_stock_across_pharmacies(medicine_id, user_lat=user_lat, user_lng=user_lng)
    
    if 'user_id' in session:
        for p in pharmacies_stock:
            p['is_fav'] = is_favourite(session['user_id'], p['pharmacy_id'])
    else:
        for p in pharmacies_stock:
            p['is_fav'] = False

    return render_template('medicine_details.html', medicine=med, pharmacies_stock=pharmacies_stock)

@medicine_bp.route('/pharmacy/<int:pharmacy_id>')
def pharmacy_details(pharmacy_id):
    pharmacy = get_pharmacy_by_id(pharmacy_id)
    if not pharmacy or pharmacy['status'] != 'approved':
        return render_template('search.html', error_msg="Pharmacy not found or not currently active.", has_searched=True)

    inventory = get_inventory_by_pharmacy(pharmacy_id)
    is_fav = False
    if 'user_id' in session:
        is_fav = is_favourite(session['user_id'], pharmacy_id)

    if pharmacy['latitude'] and pharmacy['longitude']:
        directions_url = f"https://www.google.com/maps/dir/?api=1&destination={pharmacy['latitude']},{pharmacy['longitude']}"
    else:
        import urllib.parse
        encoded = urllib.parse.quote_plus(f"{pharmacy['pharmacy_name']}, {pharmacy['address']}, {pharmacy['city']}")
        directions_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded}"

    return render_template('pharmacy_details.html', pharmacy=pharmacy, inventory=inventory, is_fav=is_fav, directions_url=directions_url)

# REST APIs for frontend dynamic lookups & autocomplete
@medicine_bp.route('/api/medicines/autocomplete')
@medicine_bp.route('/api/medicines/search')
def api_medicine_autocomplete():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    meds = search_medicines(query, limit=12)
    return jsonify(meds)

@medicine_bp.route('/api/locations/autocomplete')
@medicine_bp.route('/api/locations/search')
def api_location_autocomplete():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    locations = search_locations(query, limit=10)
    return jsonify(locations)

@medicine_bp.route('/api/medicines/nearby')
def api_nearby_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': [], 'message': 'Search query is required.'})

    user_city = request.args.get('city', '').strip()
    user_lat = request.args.get('lat')
    user_lng = request.args.get('lng')
    user_area = request.args.get('area')
    user_pincode = request.args.get('pincode')

    if 'user_id' in session:
        u = get_user_by_id(session['user_id'])
        if u:
            if not user_city and u.get('city'):
                user_city = u['city']
            user_lat = user_lat or u.get('latitude')
            user_lng = user_lng or u.get('longitude')
            user_area = user_area or u.get('area')
            user_pincode = user_pincode or u.get('pincode')
        save_search_query(session['user_id'], query)

    no_pharmacies_in_city = False
    if user_city:
        has_pharmacies, count = check_pharmacies_exist_in_city(user_city)
        if not has_pharmacies:
            no_pharmacies_in_city = True

    results = []
    if not no_pharmacies_in_city:
        results = search_nearby_pharmacies_with_medicine(
            medicine_query=query,
            user_lat=user_lat,
            user_lng=user_lng,
            user_city=user_city,
            user_area=user_area,
            user_pincode=user_pincode
        )

    if 'user_id' in session:
        for r in results:
            r['is_fav'] = is_favourite(session['user_id'], r['pharmacy_id'])

    return jsonify({
        'query': query,
        'city': user_city,
        'no_pharmacies_in_city': no_pharmacies_in_city,
        'count': len(results),
        'results': results
    })

@medicine_bp.route('/api/medicines/<int:medicine_id>')
def api_medicine_by_id(medicine_id):
    med = get_medicine_by_id(medicine_id)
    if not med:
        return jsonify({'error': 'Medicine not found'}), 404
    stocks = get_medicine_stock_across_pharmacies(medicine_id)
    return jsonify({'medicine': med, 'availability': stocks})
