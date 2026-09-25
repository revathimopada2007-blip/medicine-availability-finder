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
