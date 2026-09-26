import math
from datetime import datetime
from database import get_db_connection

def compute_stock_status(quantity):
    qty = int(quantity) if quantity is not None else 0
    if qty > 10:
        return {
            'code': 'available',
            'label': 'Available',
            'badge_class': 'badge bg-success',
            'icon': 'bi-check-circle-fill',
            'color': '#10b981'
        }
    elif qty >= 1:
        return {
            'code': 'low_stock',
            'label': 'Low Stock',
            'badge_class': 'badge bg-warning text-dark',
            'icon': 'bi-exclamation-triangle-fill',
            'color': '#f59e0b'
        }
    else:
        return {
            'code': 'out_of_stock',
            'label': 'Out of Stock',
            'badge_class': 'badge bg-danger',
            'icon': 'bi-x-circle-fill',
            'color': '#ef4444'
        }

def haversine_distance(lat1, lon1, lat2, lon2):
    try:
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return None
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(R * c, 2)
    except Exception:
        return None

def format_timestamp(ts_str):
    if not ts_str:
        return "Unknown"
    try:
        dt = datetime.strptime(str(ts_str).split('.')[0], '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%d %b %Y, %I:%M %p')
    except Exception:
        return str(ts_str)

def check_pharmacies_exist_in_city(city):
    """Checks if any approved pharmacy is registered in the given city dynamically."""
    if not city or not city.strip():
        return True, 0
    conn = get_db_connection()
    clean_city = city.strip().lower()
    row = conn.execute("""
    SELECT COUNT(*) as c FROM pharmacies 
    WHERE status = 'approved' AND LOWER(TRIM(city)) = ?
    """, (clean_city,)).fetchone()
    conn.close()
    count = row['c'] if row else 0
    return count > 0, count

def get_inventory_by_pharmacy(pharmacy_id):
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT i.*, m.name as medicine_name, m.generic_name, m.brand_name, m.strength, m.form, m.description, m.prescription_required
    FROM inventory i
    JOIN medicines m ON i.medicine_id = m.id
    WHERE i.pharmacy_id = ?
    ORDER BY m.name ASC
    """, (pharmacy_id,)).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        d['stock_info'] = compute_stock_status(d['quantity'])
        d['formatted_updated'] = format_timestamp(d['last_updated'])
        results.append(d)
    return results

def get_inventory_item(inventory_id):
    conn = get_db_connection()
    row = conn.execute("""
    SELECT i.*, m.name as medicine_name, m.generic_name, m.brand_name, m.strength, m.form, m.description, m.prescription_required,
           p.pharmacy_name, p.address as pharmacy_address, p.phone as pharmacy_phone, p.city as pharmacy_city
    FROM inventory i
    JOIN medicines m ON i.medicine_id = m.id
    JOIN pharmacies p ON i.pharmacy_id = p.id
    WHERE i.id = ?
    """, (inventory_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d['stock_info'] = compute_stock_status(d['quantity'])
    d['formatted_updated'] = format_timestamp(d['last_updated'])
    return d

def add_inventory_item(pharmacy_id, medicine_id, price, quantity, expiry_date=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute("""
        INSERT INTO inventory (pharmacy_id, medicine_id, price, quantity, expiry_date, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(pharmacy_id, medicine_id) DO UPDATE SET
            price = excluded.price,
            quantity = excluded.quantity,
            expiry_date = excluded.expiry_date,
            last_updated = excluded.last_updated
        """, (pharmacy_id, medicine_id, float(price), int(quantity), expiry_date, now_iso))
        conn.commit()
        inv_id = cursor.lastrowid
        return inv_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def update_inventory_item(inventory_id, pharmacy_id, price, quantity, expiry_date=None):
    conn = get_db_connection()
    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE inventory
        SET price = ?, quantity = ?, expiry_date = ?, last_updated = ?
        WHERE id = ? AND pharmacy_id = ?
        """, (float(price), int(quantity), expiry_date, now_iso, inventory_id, pharmacy_id))
        conn.commit()
        if cursor.rowcount == 0:
            return False, "Record not found or unauthorized"
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_inventory_item(inventory_id, pharmacy_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inventory WHERE id = ? AND pharmacy_id = ?", (inventory_id, pharmacy_id))
        conn.commit()
        if cursor.rowcount == 0:
            return False, "Record not found or unauthorized"
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_pharmacy_dashboard_stats(pharmacy_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT quantity FROM inventory WHERE pharmacy_id = ?", (pharmacy_id,)).fetchall()
    conn.close()
    
    total = len(rows)
    available = sum(1 for r in rows if r['quantity'] > 10)
    low_stock = sum(1 for r in rows if 1 <= r['quantity'] <= 10)
    out_of_stock = sum(1 for r in rows if r['quantity'] == 0)

    return {
        'total_medicines': total,
        'available_count': available,
        'low_stock_count': low_stock,
        'out_of_stock_count': out_of_stock
    }

def search_nearby_pharmacies_with_medicine(medicine_query, user_lat=None, user_lng=None, user_city=None, user_area=None, user_pincode=None):
    """
    DYNAMIC CITY-BASED SEARCH ENGINE:
    - Queries database by BOTH medicine query and pharmacy city dynamically.
    - If user_city is provided, STRICTLY filters by that city in SQL: NO cross-city leakage.
    - If no city is specified, queries across approved pharmacies and sorts by proximity/stock.
    """
    conn = get_db_connection()
    term = f"%{medicine_query.strip()}%"

    base_sql = """
    SELECT 
        i.id as inventory_id,
        i.price,
        i.quantity,
        i.expiry_date,
        i.last_updated,
        m.id as medicine_id,
        m.name as medicine_name,
        m.generic_name,
        m.brand_name,
        m.strength,
        m.form,
        m.description,
        m.prescription_required,
        p.id as pharmacy_id,
        p.pharmacy_name,
        p.owner_name,
        p.phone as pharmacy_phone,
        p.email as pharmacy_email,
        p.address as pharmacy_address,
        p.area as pharmacy_area,
        p.city as pharmacy_city,
        p.state as pharmacy_state,
        p.pincode as pharmacy_pincode,
        p.latitude as pharmacy_lat,
        p.longitude as pharmacy_lng,
        p.operating_hours,
        p.is_demo
    FROM inventory i
    JOIN medicines m ON i.medicine_id = m.id
    JOIN pharmacies p ON i.pharmacy_id = p.id
    WHERE p.status = 'approved'
      AND (m.name LIKE ? OR m.generic_name LIKE ? OR m.brand_name LIKE ? OR m.strength LIKE ? OR m.form LIKE ?)
    """

    params = [term, term, term, term, term]

    # Strict dynamic city filter when city is specified by user
    if user_city and user_city.strip():
        base_sql += " AND LOWER(TRIM(p.city)) = LOWER(TRIM(?))"
        params.append(user_city.strip())

    rows = conn.execute(base_sql, tuple(params)).fetchall()
    conn.close()

    results = []
    has_user_coords = user_lat is not None and user_lng is not None and str(user_lat).strip() != '' and str(user_lng).strip() != ''

    for r in rows:
        item = dict(r)
        item['stock_info'] = compute_stock_status(item['quantity'])
        item['formatted_updated'] = format_timestamp(item['last_updated'])

        dist = None
        if has_user_coords and item['pharmacy_lat'] is not None and item['pharmacy_lng'] is not None:
            dist = haversine_distance(user_lat, user_lng, item['pharmacy_lat'], item['pharmacy_lng'])
        
        item['distance_km'] = dist
        item['has_exact_distance'] = dist is not None

        is_area_match = False
        is_city_match = False
        if user_area and item['pharmacy_area'] and user_area.strip().lower() in item['pharmacy_area'].strip().lower():
            is_area_match = True
        if user_city and item['pharmacy_city'] and user_city.strip().lower() in item['pharmacy_city'].strip().lower():
            is_city_match = True

        item['is_area_match'] = is_area_match
        item['is_city_match'] = is_city_match

        if item['pharmacy_lat'] and item['pharmacy_lng']:
            item['map_url'] = f"https://www.google.com/maps/search/?api=1&query={item['pharmacy_lat']},{item['pharmacy_lng']}"
            item['directions_url'] = f"https://www.google.com/maps/dir/?api=1&destination={item['pharmacy_lat']},{item['pharmacy_lng']}"
        else:
            query_str = f"{item['pharmacy_name']}, {item['pharmacy_address']}, {item['pharmacy_city']}, {item['pharmacy_pincode']}"
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query_str)
            item['map_url'] = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
            item['directions_url'] = f"https://www.google.com/maps/dir/?api=1&destination={encoded_query}"

        results.append(item)

    def sort_key(x):
        stock_rank = 0 if x['quantity'] > 10 else (1 if x['quantity'] > 0 else 2)
        dist_rank = x['distance_km'] if x['distance_km'] is not None else 999999.0
        area_rank = 0 if (x['is_area_match'] or x['is_city_match']) else 1
        return (stock_rank, dist_rank, area_rank, x['price'])

    results.sort(key=sort_key)
    return results

def get_medicine_stock_across_pharmacies(medicine_id, user_lat=None, user_lng=None):
    conn = get_db_connection()
    sql = """
    SELECT 
        i.id as inventory_id,
        i.price,
        i.quantity,
        i.expiry_date,
        i.last_updated,
        p.id as pharmacy_id,
        p.pharmacy_name,
        p.owner_name,
        p.phone as pharmacy_phone,
        p.email as pharmacy_email,
        p.address as pharmacy_address,
        p.area as pharmacy_area,
        p.city as pharmacy_city,
        p.state as pharmacy_state,
        p.pincode as pharmacy_pincode,
        p.latitude as pharmacy_lat,
        p.longitude as pharmacy_lng,
        p.operating_hours,
        p.is_demo
    FROM inventory i
    JOIN pharmacies p ON i.pharmacy_id = p.id
    WHERE i.medicine_id = ? AND p.status = 'approved'
    """
    rows = conn.execute(sql, (medicine_id,)).fetchall()
    conn.close()

    results = []
    has_user_coords = user_lat is not None and user_lng is not None and str(user_lat).strip() != '' and str(user_lng).strip() != ''

    for r in rows:
        item = dict(r)
        item['stock_info'] = compute_stock_status(item['quantity'])
        item['formatted_updated'] = format_timestamp(item['last_updated'])

        dist = None
        if has_user_coords and item['pharmacy_lat'] is not None and item['pharmacy_lng'] is not None:
            dist = haversine_distance(user_lat, user_lng, item['pharmacy_lat'], item['pharmacy_lng'])
        item['distance_km'] = dist

        if item['pharmacy_lat'] and item['pharmacy_lng']:
            item['map_url'] = f"https://www.google.com/maps/search/?api=1&query={item['pharmacy_lat']},{item['pharmacy_lng']}"
            item['directions_url'] = f"https://www.google.com/maps/dir/?api=1&destination={item['pharmacy_lat']},{item['pharmacy_lng']}"
        else:
            import urllib.parse
            encoded = urllib.parse.quote_plus(f"{item['pharmacy_name']}, {item['pharmacy_address']}, {item['pharmacy_city']}")
            item['map_url'] = f"https://www.google.com/maps/search/?api=1&query={encoded}"
            item['directions_url'] = f"https://www.google.com/maps/dir/?api=1&destination={encoded}"

        results.append(item)

    results.sort(key=lambda x: (0 if x['quantity'] > 0 else 1, x['distance_km'] if x['distance_km'] is not None else 999999.0, x['price']))
    return results
