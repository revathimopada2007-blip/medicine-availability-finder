from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(name, email, phone, password, role='user', address=None, area=None, city=None, state=None, pincode=None, latitude=None, longitude=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    try:
        cursor.execute("""
        INSERT INTO users (name, email, phone, password_hash, role, address, area, city, state, pincode, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name.strip(),
            email.strip().lower(),
            phone.strip(),
            password_hash,
            role,
            address.strip() if address else None,
            area.strip() if area else None,
            city.strip() if city else None,
            state.strip() if state else None,
            pincode.strip() if pincode else None,
            float(latitude) if latitude is not None and str(latitude).strip() != '' else None,
            float(longitude) if longitude is not None and str(longitude).strip() != '' else None
        ))
        conn.commit()
        user_id = cursor.lastrowid
        return user_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def update_user_profile(user_id, name, phone, address=None, area=None, city=None, state=None, pincode=None):
    conn = get_db_connection()
    try:
        conn.execute("""
        UPDATE users
        SET name = ?, phone = ?, address = ?, area = ?, city = ?, state = ?, pincode = ?
        WHERE id = ?
        """, (name.strip(), phone.strip(), address, area, city, state, pincode, user_id))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def update_user_location(user_id, latitude=None, longitude=None, address=None, area=None, city=None, state=None, pincode=None):
    conn = get_db_connection()
    try:
        lat = float(latitude) if latitude is not None and str(latitude).strip() != '' else None
        lng = float(longitude) if longitude is not None and str(longitude).strip() != '' else None
        
        conn.execute("""
        UPDATE users
        SET latitude = ?, longitude = ?,
            address = COALESCE(?, address),
            area = COALESCE(?, area),
            city = COALESCE(?, city),
            state = COALESCE(?, state),
            pincode = COALESCE(?, pincode)
        WHERE id = ?
        """, (lat, lng, address, area, city, state, pincode, user_id))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def verify_user_password(password_hash, password):
    return check_password_hash(password_hash, password)

def get_all_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, name, email, phone, role, city, area, is_active, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(u) for u in users]

def set_user_status(user_id, is_active):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
