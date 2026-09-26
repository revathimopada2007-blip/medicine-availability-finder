import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from werkzeug.security import generate_password_hash
from config import Config, BASE_DIR

def get_db_connection(db_path=None):
    if db_path is None:
        try:
            from flask import current_app
            if current_app and 'DATABASE_PATH' in current_app.config:
                db_path = current_app.config['DATABASE_PATH']
            else:
                db_path = Config.DATABASE_PATH
        except Exception:
            db_path = Config.DATABASE_PATH

    # On Vercel serverless environment, copy pre-seeded database to /tmp if not present
    is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or os.environ.get('VERCEL_ENV'))
    if is_serverless and not os.path.exists(db_path):
        bundled_db = os.path.join(BASE_DIR, 'instance', 'medicine_finder.db')
        target_dir = os.path.dirname(db_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        if os.path.exists(bundled_db) and os.path.getsize(bundled_db) > 0:
            try:
                shutil.copy2(bundled_db, db_path)
            except Exception:
                pass
        if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
            init_db(db_path)
            seed_demo_data(db_path)

    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        address TEXT,
        area TEXT,
        city TEXT,
        state TEXT,
        pincode TEXT,
        latitude REAL,
        longitude REAL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pharmacies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        pharmacy_name TEXT NOT NULL,
        owner_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT NOT NULL,
        address TEXT NOT NULL,
        area TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        pincode TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        operating_hours TEXT NOT NULL DEFAULT '8:00 AM - 10:00 PM',
        status TEXT NOT NULL DEFAULT 'pending',
        is_demo INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        generic_name TEXT,
        brand_name TEXT,
        strength TEXT,
        form TEXT,
        description TEXT,
        prescription_required INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pharmacy_id INTEGER NOT NULL,
        medicine_id INTEGER NOT NULL,
        price REAL NOT NULL CHECK(price >= 0),
        quantity INTEGER NOT NULL CHECK(quantity >= 0),
        expiry_date TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(pharmacy_id, medicine_id),
        FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id) ON DELETE CASCADE,
        FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        search_query TEXT NOT NULL,
        searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favourites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        pharmacy_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, pharmacy_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pharmacies_status ON pharmacies(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pharmacies_city ON pharmacies(city);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicines_name ON medicines(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicines_generic ON medicines(generic_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_pharmacy ON inventory(pharmacy_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_medicine ON inventory(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON search_history(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fav_user ON favourites(user_id);")

    conn.commit()
    conn.close()

def seed_demo_data(db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", ('admin@medfinder.com',))
    if cursor.fetchone() is None:
        cursor.execute("""
        INSERT INTO users (name, email, phone, password_hash, role, address, area, city, state, pincode, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'System Administrator',
            'admin@medfinder.com',
            '+91 9876543210',
            generate_password_hash('Admin@123'),
            'admin',
            'Admin HQ, Tech Park',
            'Central Tech Zone',
            'Vizianagaram',
            'Andhra Pradesh',
            '535002',
            18.1100,
            83.4000
        ))

    cursor.execute("SELECT id FROM users WHERE email = ?", ('user@medfinder.com',))
    if cursor.fetchone() is None:
        cursor.execute("""
        INSERT INTO users (name, email, phone, password_hash, role, address, area, city, state, pincode, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'Mohan Malicherla',
            'user@medfinder.com',
            '+91 9848012345',
            generate_password_hash('User@123'),
            'user',
            'House No. 4-12, Phool Baugh',
            'Phool Baugh',
            'Vizianagaram',
            'Andhra Pradesh',
            '535002',
            18.1067,
            83.3956
        ))

    demo_pharmacies = [
        {
            'user_email': 'democare@pharmacy.com',
            'name': 'Dr. Rajesh Kumar',
            'phone': '+91 8912345678',
            'pharmacy_name': 'DemoCare Pharmacy',
            'address': 'D.No 12-4-5, Cantonment Main Road',
            'area': 'Cantonment',
            'city': 'Vizianagaram',
            'state': 'Andhra Pradesh',
            'pincode': '535003',
            'lat': 18.1120,
            'lng': 83.4010,
            'hours': '7:30 AM - 11:00 PM',
            'status': 'approved'
        },
        {
            'user_email': 'cityhealth@pharmacy.com',
            'name': 'Suresh Varma',
            'phone': '+91 8919876543',
            'pharmacy_name': 'City Health Pharmacy',
            'address': 'Opposite RTC Complex, Station Road',
            'area': 'RTC Complex Road',
            'city': 'Vizianagaram',
            'state': 'Andhra Pradesh',
            'pincode': '535002',
            'lat': 18.1170,
            'lng': 83.3910,
            'hours': '8:00 AM - 10:30 PM',
            'status': 'approved'
        },
        {
            'user_email': 'community@pharmacy.com',
            'name': 'Anita Reddy',
            'phone': '+91 8914567890',
            'pharmacy_name': 'Community Medicals',
            'address': 'Plot 45, Ring Road Junction',
            'area': 'Ring Road',
            'city': 'Vizianagaram',
            'state': 'Andhra Pradesh',
            'pincode': '535004',
            'lat': 18.0980,
            'lng': 83.4120,
            'hours': '9:00 AM - 9:00 PM',
            'status': 'approved'
        },
        {
            'user_email': 'studenthealth@pharmacy.com',
            'name': 'P. Venkat',
            'phone': '+91 8917654321',
            'pharmacy_name': 'Student Health Pharmacy',
            'address': 'Near Engineering College Gate, Campus Road',
            'area': 'College Campus Road',
            'city': 'Vizianagaram',
            'state': 'Andhra Pradesh',
            'pincode': '535005',
            'lat': 18.1250,
            'lng': 83.3850,
            'hours': '8:00 AM - 10:00 PM',
            'status': 'approved'
        }
    ]

    for p in demo_pharmacies:
        cursor.execute("SELECT id FROM users WHERE email = ?", (p['user_email'],))
        user_row = cursor.fetchone()
        if user_row is None:
            cursor.execute("""
            INSERT INTO users (name, email, phone, password_hash, role, address, area, city, state, pincode, latitude, longitude)
            VALUES (?, ?, ?, ?, 'pharmacy', ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['name'],
                p['user_email'],
                p['phone'],
                generate_password_hash('Demo@123'),
                p['address'],
                p['area'],
                p['city'],
                p['state'],
                p['pincode'],
                p['lat'],
                p['lng']
            ))
            user_id = cursor.lastrowid
        else:
            user_id = user_row['id']

        cursor.execute("SELECT id FROM pharmacies WHERE user_id = ?", (user_id,))
        if cursor.fetchone() is None:
            cursor.execute("""
            INSERT INTO pharmacies (user_id, pharmacy_name, owner_name, phone, email, address, area, city, state, pincode, latitude, longitude, operating_hours, status, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                user_id,
                p['pharmacy_name'],
                p['name'],
                p['phone'],
                p['user_email'],
                p['address'],
                p['area'],
                p['city'],
                p['state'],
                p['pincode'],
                p['lat'],
                p['lng'],
                p['hours'],
                p['status']
            ))

    demo_medicines = [
        ('Paracetamol', 'Acetaminophen', 'Dolo 650 / Crocin', '500mg', 'Tablet', 'Analgesic and antipyretic medicine for fast relief from fever, headache, and body aches.', 0),
        ('Cetirizine', 'Cetirizine Hydrochloride', 'Cetzine', '10mg', 'Tablet', 'Non-drowsy antihistamine for allergic rhinitis, cold symptoms, sneezing, and skin hives.', 0),
        ('Ibuprofen', 'Ibuprofen', 'Brufen', '400mg', 'Tablet', 'Nonsteroidal anti-inflammatory drug (NSAID) used for pain, toothache, and inflammation.', 1),
        ('ORS', 'Oral Rehydration Salts', 'Electral', '21.8g Sachet', 'Powder', 'WHO-formulated electrolyte powder for rehydration during dehydration, diarrhea, or heat exhaustion.', 0),
        ('Amoxicillin', 'Amoxicillin Trihydrate', 'Mox 500', '500mg', 'Capsule', 'Broad-spectrum antibiotic used to treat bacterial ear, throat, urinary tract, and chest infections.', 1),
        ('Azithromycin', 'Azithromycin', 'Azee 500', '500mg', 'Tablet', 'Macrolide antibiotic commonly prescribed for respiratory and bacterial skin infections.', 1),
        ('Pantoprazole', 'Pantoprazole Sodium', 'Pan 40', '40mg', 'Tablet', 'Proton-pump inhibitor (PPI) that reduces excess stomach acid, heartburn, and GERD symptoms.', 0),
        ('Cough Syrup', 'Dextromethorphan + CPM', 'Benadryl DR', '100ml', 'Syrup', 'Soothing cough relief syrup for persistent dry allergic coughs and throat tickle.', 0),
        ('Metformin', 'Metformin Hydrochloride', 'Glycomet 500', '500mg', 'Tablet', 'Oral anti-diabetic medicine used to manage blood glucose levels in type 2 diabetes mellitus.', 1),
        ('Amlodipine', 'Amlodipine Besylate', 'Amlong 5', '5mg', 'Tablet', 'Calcium channel blocker used to lower high blood pressure and prevent chest pain (angina).', 1)
    ]

    for med in demo_medicines:
        cursor.execute("SELECT id FROM medicines WHERE name = ? AND strength = ?", (med[0], med[3]))
        if cursor.fetchone() is None:
            cursor.execute("""
            INSERT INTO medicines (name, generic_name, brand_name, strength, form, description, prescription_required)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, med)

    cursor.execute("SELECT id, pharmacy_name FROM pharmacies")
    pharmacies_map = {row['pharmacy_name']: row['id'] for row in cursor.fetchall()}

    cursor.execute("SELECT id, name, strength FROM medicines")
    meds_map = {(row['name'], row['strength']): row['id'] for row in cursor.fetchall()}

    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    initial_inventory = [
        ('DemoCare Pharmacy', 'Paracetamol', '500mg', 25.00, 20, '2027-10-31'),
        ('DemoCare Pharmacy', 'Cetirizine', '10mg', 18.00, 50, '2027-08-15'),
        ('DemoCare Pharmacy', 'Ibuprofen', '400mg', 35.00, 8, '2026-12-31'),
        ('DemoCare Pharmacy', 'ORS', '21.8g Sachet', 22.00, 40, '2028-05-30'),
        ('DemoCare Pharmacy', 'Pantoprazole', '40mg', 45.00, 0, '2027-04-20'),

        ('City Health Pharmacy', 'Paracetamol', '500mg', 28.00, 5, '2027-09-30'),
        ('City Health Pharmacy', 'Amoxicillin', '500mg', 75.00, 15, '2027-03-31'),
        ('City Health Pharmacy', 'Azithromycin', '500mg', 110.00, 12, '2027-06-30'),
        ('City Health Pharmacy', 'ORS', '21.8g Sachet', 21.50, 30, '2028-01-15'),

        ('Community Medicals', 'Paracetamol', '500mg', 24.00, 0, '2027-11-30'),
        ('Community Medicals', 'Cetirizine', '10mg', 17.50, 25, '2027-07-20'),
        ('Community Medicals', 'Cough Syrup', '100ml', 85.00, 14, '2027-02-28'),

        ('Student Health Pharmacy', 'Paracetamol', '500mg', 22.00, 35, '2027-12-31'),
        ('Student Health Pharmacy', 'ORS', '21.8g Sachet', 20.00, 100, '2028-08-30'),
        ('Student Health Pharmacy', 'Cetirizine', '10mg', 16.00, 15, '2027-10-15'),
        ('Student Health Pharmacy', 'Amlodipine', '5mg', 32.00, 20, '2027-05-15')
    ]

    for p_name, m_name, m_strength, price, qty, expiry in initial_inventory:
        p_id = pharmacies_map.get(p_name)
        m_id = meds_map.get((m_name, m_strength))
        if p_id and m_id:
            cursor.execute("SELECT id FROM inventory WHERE pharmacy_id = ? AND medicine_id = ?", (p_id, m_id))
            if cursor.fetchone() is None:
                cursor.execute("""
                INSERT INTO inventory (pharmacy_id, medicine_id, price, quantity, expiry_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (p_id, m_id, price, qty, expiry, now_iso))

    conn.commit()
    conn.close()
