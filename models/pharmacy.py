from database import get_db_connection

def get_pharmacy_by_id(pharmacy_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM pharmacies WHERE id = ?", (pharmacy_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_pharmacy_by_user_id(user_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM pharmacies WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def search_locations(query, limit=10):
    """
    Database-backed location autocomplete:
    Searches distinct registered pharmacy cities and areas.
    Case-insensitive, supports partial typing (e.g. G, Gu, Vi, Hy).
    """
    if not query or not query.strip():
        return []
    
    conn = get_db_connection()
    term = f"%{query.strip().lower()}%"
    prefix_term = f"{query.strip().lower()}%"
    cursor = conn.cursor()
    
    # 1. Distinct cities from approved pharmacies
    city_rows = cursor.execute("""
        SELECT DISTINCT city, state 
        FROM pharmacies 
        WHERE status = 'approved' AND LOWER(city) LIKE ?
        ORDER BY CASE WHEN LOWER(city) LIKE ? THEN 0 ELSE 1 END, city ASC
        LIMIT ?
    """, (term, prefix_term, limit)).fetchall()
    
    # 2. Distinct areas/localities from approved pharmacies
    area_rows = cursor.execute("""
        SELECT DISTINCT area, city, state 
        FROM pharmacies 
        WHERE status = 'approved' AND LOWER(area) LIKE ? AND LOWER(area) != LOWER(city)
        ORDER BY CASE WHEN LOWER(area) LIKE ? THEN 0 ELSE 1 END, area ASC
        LIMIT ?
    """, (term, prefix_term, limit)).fetchall()
    
    conn.close()
    
    seen = set()
    results = []
    
    for r in city_rows:
        c_name = r['city'].strip()
        c_key = c_name.lower()
        if c_key not in seen:
            seen.add(c_key)
            results.append({
                'name': c_name,
                'type': 'City',
                'state': r['state'] or 'Andhra Pradesh',
                'display': f"{c_name}, {r['state']}" if r['state'] else c_name
            })
            
    for r in area_rows:
        a_name = r['area'].strip()
        a_key = a_name.lower()
        if a_key not in seen:
            seen.add(a_key)
            results.append({
                'name': a_name,
                'type': 'Area / Locality',
                'city': r['city'],
                'state': r['state'] or '',
                'display': f"{a_name}, {r['city']}"
            })
            
    q_lower = query.strip().lower()
    results.sort(key=lambda x: (
        0 if x['name'].lower().startswith(q_lower) else 1,
        0 if x['type'] == 'City' else 1,
        x['name'].lower()
    ))
    
    return results[:limit]

def create_pharmacy(user_id, pharmacy_name, owner_name, phone, email, address, area, city, state, pincode, latitude=None, longitude=None, operating_hours='8:00 AM - 10:00 PM', status='pending', is_demo=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        lat = float(latitude) if latitude is not None and str(latitude).strip() != '' else None
        lng = float(longitude) if longitude is not None and str(longitude).strip() != '' else None
        cursor.execute("""
        INSERT INTO pharmacies (user_id, pharmacy_name, owner_name, phone, email, address, area, city, state, pincode, latitude, longitude, operating_hours, status, is_demo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            pharmacy_name.strip(),
            owner_name.strip(),
            phone.strip(),
            email.strip().lower(),
            address.strip(),
            area.strip(),
            city.strip(),
            state.strip(),
            pincode.strip(),
            lat,
            lng,
            operating_hours.strip() if operating_hours else '8:00 AM - 10:00 PM',
            status,
            is_demo
        ))
        conn.commit()
        pharmacy_id = cursor.lastrowid
        return pharmacy_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def update_pharmacy_profile(pharmacy_id, pharmacy_name, owner_name, phone, address, area, city, state, pincode, operating_hours, latitude=None, longitude=None):
    conn = get_db_connection()
    try:
        lat = float(latitude) if latitude is not None and str(latitude).strip() != '' else None
        lng = float(longitude) if longitude is not None and str(longitude).strip() != '' else None
        conn.execute("""
        UPDATE pharmacies
        SET pharmacy_name = ?, owner_name = ?, phone = ?, address = ?, area = ?, city = ?, state = ?, pincode = ?, operating_hours = ?, latitude = COALESCE(?, latitude), longitude = COALESCE(?, longitude)
        WHERE id = ?
        """, (
            pharmacy_name.strip(),
            owner_name.strip(),
            phone.strip(),
            address.strip(),
            area.strip(),
            city.strip(),
            state.strip(),
            pincode.strip(),
            operating_hours.strip(),
            lat,
            lng,
            pharmacy_id
        ))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_all_pharmacies(status=None):
    conn = get_db_connection()
    if status:
        rows = conn.execute("SELECT * FROM pharmacies WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM pharmacies ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_pharmacy_status(pharmacy_id, status):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE pharmacies SET status = ? WHERE id = ?", (status, pharmacy_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
