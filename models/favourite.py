from database import get_db_connection
from models.inventory import haversine_distance

def add_favourite(user_id, pharmacy_id):
    conn = get_db_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO favourites (user_id, pharmacy_id) VALUES (?, ?)", (user_id, pharmacy_id))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def remove_favourite(user_id, pharmacy_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM favourites WHERE user_id = ? AND pharmacy_id = ?", (user_id, pharmacy_id))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def is_favourite(user_id, pharmacy_id):
    if not user_id:
        return False
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM favourites WHERE user_id = ? AND pharmacy_id = ?", (user_id, pharmacy_id)).fetchone()
    conn.close()
    return row is not None

def get_user_favourites(user_id, user_lat=None, user_lng=None):
    conn = get_db_connection()
    sql = """
    SELECT f.id as fav_id, f.created_at as fav_created_at, p.*
    FROM favourites f
    JOIN pharmacies p ON f.pharmacy_id = p.id
    WHERE f.user_id = ?
    ORDER BY f.created_at DESC
    """
    rows = conn.execute(sql, (user_id,)).fetchall()
    conn.close()

    results = []
    has_user_coords = user_lat is not None and user_lng is not None and str(user_lat).strip() != '' and str(user_lng).strip() != ''

    for r in rows:
        item = dict(r)
        dist = None
        if has_user_coords and item['latitude'] is not None and item['longitude'] is not None:
            dist = haversine_distance(user_lat, user_lng, item['latitude'], item['longitude'])
        item['distance_km'] = dist
        
        if item['latitude'] and item['longitude']:
            item['map_url'] = f"https://www.google.com/maps/search/?api=1&query={item['latitude']},{item['longitude']}"
            item['directions_url'] = f"https://www.google.com/maps/dir/?api=1&destination={item['latitude']},{item['longitude']}"
        else:
            import urllib.parse
            encoded = urllib.parse.quote_plus(f"{item['pharmacy_name']}, {item['address']}, {item['city']}")
            item['map_url'] = f"https://www.google.com/maps/search/?api=1&query={encoded}"
            item['directions_url'] = f"https://www.google.com/maps/dir/?api=1&destination={encoded}"

        results.append(item)
    return results
