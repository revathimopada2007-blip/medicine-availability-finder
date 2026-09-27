from database import get_db_connection

def get_medicine_by_id(medicine_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM medicines WHERE id = ?", (medicine_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_medicines():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM medicines ORDER BY name ASC, strength ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def search_medicines(query, limit=60):
    conn = get_db_connection()
    term = f"%{query.strip()}%"
    rows = conn.execute("""
    SELECT * FROM medicines
    WHERE name LIKE ? OR generic_name LIKE ? OR brand_name LIKE ? OR category LIKE ? OR manufacturer LIKE ? OR strength LIKE ? OR form LIKE ?
    ORDER BY name ASC
    LIMIT ?
    """, (term, term, term, term, term, term, term, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_medicine(name, category='General', generic_name=None, brand_name=None, manufacturer=None, strength=None, form='Tablet', description=None, prescription_required=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO medicines (name, category, generic_name, brand_name, manufacturer, strength, form, description, prescription_required)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name.strip(),
            category.strip() if category else 'General',
            generic_name.strip() if generic_name else None,
            brand_name.strip() if brand_name else None,
            manufacturer.strip() if manufacturer else None,
            strength.strip() if strength else None,
            form.strip() if form else 'Tablet',
            description.strip() if description else None,
            1 if prescription_required else 0
        ))
        conn.commit()
        med_id = cursor.lastrowid
        return med_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def update_medicine(medicine_id, name, category='General', generic_name=None, brand_name=None, manufacturer=None, strength=None, form='Tablet', description=None, prescription_required=0):
    conn = get_db_connection()
    try:
        conn.execute("""
        UPDATE medicines
        SET name = ?, category = ?, generic_name = ?, brand_name = ?, manufacturer = ?, strength = ?, form = ?, description = ?, prescription_required = ?
        WHERE id = ?
        """, (
            name.strip(),
            category.strip() if category else 'General',
            generic_name.strip() if generic_name else None,
            brand_name.strip() if brand_name else None,
            manufacturer.strip() if manufacturer else None,
            strength.strip() if strength else None,
            form.strip() if form else 'Tablet',
            description.strip() if description else None,
            1 if prescription_required else 0,
            medicine_id
        ))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_medicine(medicine_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM medicines WHERE id = ?", (medicine_id,))
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()
