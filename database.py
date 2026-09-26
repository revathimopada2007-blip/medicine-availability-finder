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
        category TEXT DEFAULT 'General',
        generic_name TEXT,
        brand_name TEXT,
        manufacturer TEXT,
        strength TEXT,
        form TEXT,
        description TEXT,
        prescription_required INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Migration: add category & manufacturer if upgrading existing DB
    cursor.execute("PRAGMA table_info(medicines);")
    cols = [c[1] for c in cursor.fetchall()]
    if 'category' not in cols:
        cursor.execute("ALTER TABLE medicines ADD COLUMN category TEXT DEFAULT 'General';")
    if 'manufacturer' not in cols:
        cursor.execute("ALTER TABLE medicines ADD COLUMN manufacturer TEXT;")

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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pharmacies_area ON pharmacies(area);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicines_name ON medicines(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicines_generic ON medicines(generic_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicines_category ON medicines(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_pharmacy ON inventory(pharmacy_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_medicine ON inventory(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON search_history(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fav_user ON favourites(user_id);")

    conn.commit()
    conn.close()

def seed_demo_data(db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Admin Account
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

    # 2. Demo User
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

    # 3. Comprehensive Master Medicine Catalog
    all_medicines = [
        # Pain / Fever
        ('Paracetamol', 'Pain/Fever', 'Acetaminophen', 'Dolo 650 / Calpol', 'Micro Labs / GSK', '650mg', 'Tablet', 'Fast-acting analgesic and antipyretic for fever, headache, body aches, and post-vaccination discomfort.', 0),
        ('Paracetamol 500mg', 'Pain/Fever', 'Acetaminophen', 'Crocin 500', 'GlaxoSmithKline', '500mg', 'Tablet', 'Standard pain and fever relief tablet for mild to moderate discomfort.', 0),
        ('Ibuprofen', 'Pain/Fever', 'Ibuprofen', 'Brufen 400', 'Abbott Healthcare', '400mg', 'Tablet', 'Nonsteroidal anti-inflammatory drug (NSAID) for muscle pain, toothache, arthritis, and fever.', 1),
        ('Diclofenac', 'Pain/Fever', 'Diclofenac Sodium', 'Voveran 50', 'Novartis India', '50mg', 'Tablet', 'Potent anti-inflammatory and painkiller for severe joint pain, sprains, and post-operative pain.', 1),
        ('Naproxen', 'Pain/Fever', 'Naproxen', 'Naprosyn 500', 'RPG Life Sciences', '500mg', 'Tablet', 'Long-acting NSAID for chronic pain, tendinitis, gout flares, and ankylosing spondylitis.', 1),
        ('Aceclofenac', 'Pain/Fever', 'Aceclofenac + Paracetamol', 'Zerodol-P', 'IPCA Laboratories', '100mg/325mg', 'Tablet', 'Combination painkiller that reduces inflammation and acute painful joint conditions.', 1),

        # Cold / Allergy
        ('Cetirizine', 'Cold/Allergy', 'Cetirizine Hydrochloride', 'Cetzine 10', 'Dr. Reddy Labs', '10mg', 'Tablet', 'Antihistamine for runny nose, sneezing, itchy watery eyes, and allergic skin hives.', 0),
        ('Levocetirizine', 'Cold/Allergy', 'Levocetirizine Dihydrochloride', 'Levocet 5', 'Hetero Healthcare', '5mg', 'Tablet', 'Active enantiomer antihistamine providing non-sedating relief from chronic allergic rhinitis.', 0),
        ('Loratadine', 'Cold/Allergy', 'Loratadine', 'Lorfast 10', 'Cadila Pharmaceuticals', '10mg', 'Tablet', '24-hour non-drowsy allergy relief from pollen, dust, and seasonal allergies.', 0),
        ('Fexofenadine', 'Cold/Allergy', 'Fexofenadine HCl', 'Allegra 120', 'Sanofi India', '120mg', 'Tablet', 'Second-generation antihistamine with zero sedative effect for severe allergies and urticaria.', 0),

        # Acidity / Digestion
        ('Omeprazole', 'Acidity/Digestion', 'Omeprazole', 'Omez 20', 'Dr. Reddy Labs', '20mg', 'Capsule', 'Proton-pump inhibitor that inhibits stomach acid secretion to treat ulcers and GERD.', 0),
        ('Pantoprazole', 'Acidity/Digestion', 'Pantoprazole Sodium', 'Pan 40', 'Alkem Laboratories', '40mg', 'Tablet', 'Suppresses gastric acid production for heartburn, peptic ulcers, and acid reflux.', 0),
        ('Esomeprazole', 'Acidity/Digestion', 'Esomeprazole Magnesium', 'Nexpro 40', 'Torrent Pharmaceuticals', '40mg', 'Tablet', 'Advanced S-enantiomer acid inhibitor for erosive esophagitis and severe acid regurgitation.', 0),
        ('Famotidine', 'Acidity/Digestion', 'Famotidine', 'Famocid 40', 'Sun Pharma', '40mg', 'Tablet', 'H2 blocker for rapid relief of indigestion, stomach acidity, and nighttime heartburn.', 0),
        ('Antacid', 'Acidity/Digestion', 'Aluminium + Magnesium Hydroxide + Simethicone', 'Digene Gel', 'Abbott India', '200ml', 'Syrup', 'Fast-acting soothing liquid suspension for instant relief from acidity, gas, and stomach burn.', 0),
        ('ORS', 'Acidity/Digestion', 'Oral Rehydration Salts', 'Electral Sachet', 'FDC Limited', '21.8g Sachet', 'Powder', 'WHO-recommended balanced electrolyte powder for rapid rehydration in diarrhea or vomiting.', 0),

        # Vitamins & Supplements
        ('Vitamin C', 'Vitamins', 'Ascorbic Acid + Sodium Ascorbate', 'Limcee 500', 'Abbott Healthcare', '500mg', 'Tablet', 'Chewable antioxidant supplement that strengthens immunity, collagen synthesis, and wound healing.', 0),
        ('Vitamin D3', 'Vitamins', 'Cholecalciferol', 'Calcirol 60K', 'Cadila Healthcare', '60000 IU', 'Capsule', 'High-dose weekly supplement for bone mineralization, calcium absorption, and deficiency treatment.', 0),
        ('Vitamin B12', 'Vitamins', 'Methylcobalamin', 'Nurokind-LC', 'Mankind Pharma', '1500mcg', 'Tablet', 'Essential neurotropic vitamin for nerve health, red blood cell formation, and energy metabolism.', 0),
        ('Multivitamin', 'Vitamins', 'Multivitamins + Minerals + Ginseng', 'Becadexamin', 'GlaxoSmithKline', 'Standard Dose', 'Capsule', 'Daily nutritional support capsule to prevent deficiencies and combat fatigue.', 0),
        ('Calcium', 'Vitamins', 'Calcium Carbonate + Vitamin D3', 'Shelcal 500', 'Torrent Pharmaceuticals', '500mg', 'Tablet', 'Calcium and vitamin D3 combination for strong bones, teeth, and osteoporosis prevention.', 0),
        ('Iron', 'Vitamins', 'Ferrous Ascorbate + Folic Acid', 'Orofer-XT', 'Emcure Pharmaceuticals', '100mg/1.5mg', 'Tablet', 'Hematinic supplement for rapid recovery from iron-deficiency anemia and fatigue.', 0),
        ('Folic Acid', 'Vitamins', 'Folic Acid', 'Folvite 5mg', 'Pfizer India', '5mg', 'Tablet', 'Essential prenatal and cellular growth vitamin for healthy red blood cell production.', 0),

        # Cough / Cold
        ('Cough Syrup', 'Cough/Cold', 'Dextromethorphan + CPM', 'Benadryl DR', 'Johnson & Johnson', '100ml', 'Syrup', 'Antitussive and antihistamine liquid that silences dry tickly coughs and throat irritation.', 0),
        ('Ambroxol Syrup', 'Cough/Cold', 'Ambroxol + Levosalbutamol + Guaifenesin', 'Ascoril LS', 'Glenmark Pharmaceuticals', '100ml', 'Syrup', 'Mucolytic and bronchodilator expectorant for productive wet cough with chest congestion.', 1),
        ('Guaifenesin Syrup', 'Cough/Cold', 'Guaifenesin + Bromhexine + Terbutaline', 'Grilinctus-BM', 'Franco-Indian Pharma', '100ml', 'Syrup', 'Chest phlegm liquefier and airway relaxant for persistent productive cough.', 0),

        # Common Antibiotics & Chronic Care
        ('Azithromycin', 'Antibiotics', 'Azithromycin', 'Azee 500', 'Cipla Ltd', '500mg', 'Tablet', 'Broad-spectrum macrolide antibiotic for throat, chest, ear, and skin bacterial infections.', 1),
        ('Amoxicillin', 'Antibiotics', 'Amoxicillin Trihydrate', 'Mox 500', 'Sun Pharma', '500mg', 'Capsule', 'Penicillin antibiotic used against broad range of gram-positive and gram-negative bacteria.', 1),
        ('Amoxicillin-Clavulanate', 'Antibiotics', 'Amoxicillin + Potassium Clavulanate', 'Augmentin 625 Duo', 'GlaxoSmithKline', '625mg', 'Tablet', 'Potent beta-lactamase resistant antibiotic for resistant respiratory, dental, and urinary infections.', 1),
        ('Metformin', 'Diabetes', 'Metformin Hydrochloride', 'Glycomet 500', 'USV Private Ltd', '500mg', 'Tablet', 'First-line anti-diabetic medication to regulate blood sugar levels in type-2 diabetes.', 1),
        ('Amlodipine', 'Cardiovascular', 'Amlodipine Besylate', 'Amlong 5', 'Micro Labs', '5mg', 'Tablet', 'Calcium channel blocker to reduce high blood pressure and prevent cardiovascular episodes.', 1),
        ('Losartan', 'Cardiovascular', 'Losartan Potassium', 'Losar 50', 'Unichem Laboratories', '50mg', 'Tablet', 'Angiotensin receptor blocker (ARB) to lower blood pressure and protect kidneys.', 1),
        ('Atorvastatin', 'Cardiovascular', 'Atorvastatin Calcium', 'Atorva 10', 'Zydus Cadila', '10mg', 'Tablet', 'Statin medication to lower LDL bad cholesterol, triglycerides, and heart disease risk.', 1)
    ]

    for med in all_medicines:
        name, category, generic, brand, mfg, strength, form, desc, rx = med
        cursor.execute("SELECT id FROM medicines WHERE name = ? AND strength = ?", (name, strength))
        existing = cursor.fetchone()
        if existing is None:
            cursor.execute("""
            INSERT INTO medicines (name, category, generic_name, brand_name, manufacturer, strength, form, description, prescription_required)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, category, generic, brand, mfg, strength, form, desc, rx))
        else:
            cursor.execute("""
            UPDATE medicines 
            SET category = ?, generic_name = ?, brand_name = ?, manufacturer = ?, form = ?, description = ?, prescription_required = ?
            WHERE id = ?
            """, (category, generic, brand, mfg, form, desc, rx, existing['id']))

    # 4. Multi-City & Hyderabad Localities Demo Pharmacies
    demo_pharmacies = [
        # Vizianagaram
        {
            'user_email': 'democare@pharmacy.com',
            'name': 'Dr. Rajesh Kumar',
            'phone': '+91 8912345678',
            'pharmacy_name': 'Demo Pharmacy – Vizianagaram (DemoCare)',
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
            'pharmacy_name': 'Demo Pharmacy – Vizianagaram (City Health)',
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
            'user_email': 'studenthealth@pharmacy.com',
            'name': 'P. Venkat',
            'phone': '+91 8917654321',
            'pharmacy_name': 'Demo Pharmacy – Vizianagaram (Campus)',
            'address': 'Near Engineering College Gate, Campus Road',
            'area': 'College Campus Road',
            'city': 'Vizianagaram',
            'state': 'Andhra Pradesh',
            'pincode': '535005',
            'lat': 18.1250,
            'lng': 83.3850,
            'hours': '8:00 AM - 10:00 PM',
            'status': 'approved'
        },
        # Visakhapatnam
        {
            'user_email': 'vsk_siripuram@pharmacy.com',
            'name': 'K. Satish',
            'phone': '+91 8912556677',
            'pharmacy_name': 'Demo Pharmacy – Visakhapatnam (Siripuram)',
            'address': 'Shop 8, Siripuram Junction',
            'area': 'Siripuram',
            'city': 'Visakhapatnam',
            'state': 'Andhra Pradesh',
            'pincode': '530003',
            'lat': 17.7231,
            'lng': 83.3156,
            'hours': '24 Hours Open',
            'status': 'approved'
        },
        {
            'user_email': 'vsk_beach@pharmacy.com',
            'name': 'P. Lakshmi',
            'phone': '+91 8912778899',
            'pharmacy_name': 'Demo Pharmacy – Visakhapatnam (Beach Road)',
            'address': 'D.No 4-50, Beach Road Walkway',
            'area': 'Beach Road',
            'city': 'Visakhapatnam',
            'state': 'Andhra Pradesh',
            'pincode': '530002',
            'lat': 17.7120,
            'lng': 83.3240,
            'hours': '8:00 AM - 11:00 PM',
            'status': 'approved'
        },
        # Vijayawada
        {
            'user_email': 'vja_mgroad@pharmacy.com',
            'name': 'B. Venkateswara Rao',
            'phone': '+866 2445566',
            'pharmacy_name': 'Demo Pharmacy – Vijayawada (MG Road)',
            'address': 'D.No 28-10-15, MG Road, Governorpet',
            'area': 'MG Road',
            'city': 'Vijayawada',
            'state': 'Andhra Pradesh',
            'pincode': '520002',
            'lat': 16.5062,
            'lng': 80.6480,
            'hours': '7:00 AM - 11:30 PM',
            'status': 'approved'
        },
        {
            'user_email': 'vja_benzcircle@pharmacy.com',
            'name': 'T. Srinivasa Murthy',
            'phone': '+866 2557788',
            'pharmacy_name': 'Demo Pharmacy – Vijayawada (Benz Circle)',
            'address': 'Shop 4, Near Benz Circle Flyover',
            'area': 'Benz Circle',
            'city': 'Vijayawada',
            'state': 'Andhra Pradesh',
            'pincode': '520010',
            'lat': 16.4980,
            'lng': 80.6550,
            'hours': '8:00 AM - 10:00 PM',
            'status': 'approved'
        },
        # Guntur
        {
            'user_email': 'gnt_lakshmipuram@pharmacy.com',
            'name': 'M. Srinivasa Rao',
            'phone': '+91 8632334455',
            'pharmacy_name': 'Demo Pharmacy – Guntur (Lakshmipuram)',
            'address': '12-1-4, Lakshmipuram Main Road',
            'area': 'Lakshmipuram',
            'city': 'Guntur',
            'state': 'Andhra Pradesh',
            'pincode': '522007',
            'lat': 16.3067,
            'lng': 80.4365,
            'hours': '7:00 AM - 11:00 PM',
            'status': 'approved'
        },
        {
            'user_email': 'gnt_brodipet@pharmacy.com',
            'name': 'K. Anjaneyulu',
            'phone': '+91 8632448899',
            'pharmacy_name': 'Demo Pharmacy – Guntur (Brodipet)',
            'address': '4th Lane, Brodipet Center',
            'area': 'Brodipet',
            'city': 'Guntur',
            'state': 'Andhra Pradesh',
            'pincode': '522002',
            'lat': 16.3120,
            'lng': 80.4420,
            'hours': '8:00 AM - 10:00 PM',
            'status': 'approved'
        },
        # Tirupati
        {
            'user_email': 'tpt_alipiri@pharmacy.com',
            'name': 'G. Madhava Swamy',
            'phone': '+91 8772233445',
            'pharmacy_name': 'Demo Pharmacy – Tirupati (Alipiri)',
            'address': 'Shop 15, Alipiri Bypass Road',
            'area': 'Alipiri',
            'city': 'Tirupati',
            'state': 'Andhra Pradesh',
            'pincode': '517507',
            'lat': 13.6520,
            'lng': 79.4010,
            'hours': '24 Hours Open',
            'status': 'approved'
        },
        # Kurnool
        {
            'user_email': 'knl_parkroad@pharmacy.com',
            'name': 'Y. Raghavendra',
            'phone': '+91 8518223344',
            'pharmacy_name': 'Demo Pharmacy – Kurnool (Park Road)',
            'address': 'Park Road, Raj Vihar Circle',
            'area': 'Park Road',
            'city': 'Kurnool',
            'state': 'Andhra Pradesh',
            'pincode': '518001',
            'lat': 15.8281,
            'lng': 78.0373,
            'hours': '7:30 AM - 10:30 PM',
            'status': 'approved'
        },
        # Nellore
        {
            'user_email': 'nlr_trunkroad@pharmacy.com',
            'name': 'V. Subrahmanyam',
            'phone': '+91 8612334455',
            'pharmacy_name': 'Demo Pharmacy – Nellore (Trunk Road)',
            'address': 'Grand Trunk Road, Gandhi Nagar',
            'area': 'Trunk Road',
            'city': 'Nellore',
            'state': 'Andhra Pradesh',
            'pincode': '524001',
            'lat': 14.4426,
            'lng': 79.9865,
            'hours': '8:00 AM - 10:00 PM',
            'status': 'approved'
        },
        # Rajahmundry
        {
            'user_email': 'rjy_kotipalli@pharmacy.com',
            'name': 'C. Ramakrishna',
            'phone': '+91 8832445566',
            'pharmacy_name': 'Demo Pharmacy – Rajahmundry (Kotipalli)',
            'address': 'Kotipalli Bus Stand Road',
            'area': 'Kotipalli Road',
            'city': 'Rajahmundry',
            'state': 'Andhra Pradesh',
            'pincode': '533101',
            'lat': 17.0005,
            'lng': 81.8040,
            'hours': '8:00 AM - 10:30 PM',
            'status': 'approved'
        },
        # Kakinada
        {
            'user_email': 'ktd_mainroad@pharmacy.com',
            'name': 'P. Satyanarayana',
            'phone': '+91 8842334455',
            'pharmacy_name': 'Demo Pharmacy – Kakinada (Main Road)',
            'address': 'Cinema Road, Main Market Center',
            'area': 'Main Road',
            'city': 'Kakinada',
            'state': 'Andhra Pradesh',
            'pincode': '533001',
            'lat': 16.9891,
            'lng': 82.2475,
            'hours': '8:00 AM - 10:00 PM',
            'status': 'approved'
        },
        # Kadapa
        {
            'user_email': 'kdp_sevenroads@pharmacy.com',
            'name': 'N. Obul Reddy',
            'phone': '+91 8562244556',
            'pharmacy_name': 'Demo Pharmacy – Kadapa (Seven Roads)',
            'address': 'Seven Roads Circle, Main Bazar',
            'area': 'Seven Roads',
            'city': 'Kadapa',
            'state': 'Andhra Pradesh',
            'pincode': '516001',
            'lat': 14.4673,
            'lng': 78.8242,
            'hours': '8:00 AM - 10:00 PM',
            'status': 'approved'
        },
        # Anantapur
        {
            'user_email': 'atp_clocktower@pharmacy.com',
            'name': 'K. Ramanjaneyulu',
            'phone': '+91 8554223344',
            'pharmacy_name': 'Demo Pharmacy – Anantapur (Clock Tower)',
            'address': 'Clock Tower Junction, Subhash Road',
            'area': 'Clock Tower',
            'city': 'Anantapur',
            'state': 'Andhra Pradesh',
            'pincode': '515001',
            'lat': 14.6819,
            'lng': 77.6006,
            'hours': '7:30 AM - 10:00 PM',
            'status': 'approved'
        },
        # Hyderabad & Key Hyderabad Localities
        {
            'user_email': 'hyd_central@pharmacy.com',
            'name': 'Syed Mohiuddin',
            'phone': '+91 4024556677',
            'pharmacy_name': 'Demo Pharmacy – Hyderabad (Central)',
            'address': 'Abids Road, Near GPO, Koti',
            'area': 'Abids',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500001',
            'lat': 17.3850,
            'lng': 78.4867,
            'hours': '24 Hours Open',
            'status': 'approved'
        },
        {
            'user_email': 'hyd_kukatpally@pharmacy.com',
            'name': 'R. Koteswara Rao',
            'phone': '+91 4023112233',
            'pharmacy_name': 'Demo Pharmacy – Kukatpally (KPHB)',
            'address': 'Plot 42, KPHB Colony Phase 3, Road No 1',
            'area': 'Kukatpally',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500072',
            'lat': 17.4875,
            'lng': 78.3953,
            'hours': '7:00 AM - 11:30 PM',
            'status': 'approved'
        },
        {
            'user_email': 'hyd_gachibowli@pharmacy.com',
            'name': 'Vikram Reddy',
            'phone': '+91 4029887766',
            'pharmacy_name': 'Demo Pharmacy – Gachibowli (Tech Zone)',
            'address': 'Telecom Nagar, Gachibowli X Roads',
            'area': 'Gachibowli',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500032',
            'lat': 17.4401,
            'lng': 78.3489,
            'hours': '24 Hours Open',
            'status': 'approved'
        },
        {
            'user_email': 'hyd_madhapur@pharmacy.com',
            'name': 'A. Sandeep',
            'phone': '+91 4028994433',
            'pharmacy_name': 'Demo Pharmacy – Madhapur (Hitech City)',
            'address': 'Cyber Hills, Hitech City Main Road',
            'area': 'Madhapur',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500081',
            'lat': 17.4483,
            'lng': 78.3915,
            'hours': '8:00 AM - 11:00 PM',
            'status': 'approved'
        },
        {
            'user_email': 'hyd_banjarahills@pharmacy.com',
            'name': 'N. Praveen',
            'phone': '+91 4023558899',
            'pharmacy_name': 'Demo Pharmacy – Banjara Hills',
            'address': 'Road No. 12, MLA Colony, Banjara Hills',
            'area': 'Banjara Hills',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500034',
            'lat': 17.4156,
            'lng': 78.4350,
            'hours': '8:00 AM - 11:00 PM',
            'status': 'approved'
        },
        {
            'user_email': 'hyd_secunderabad@pharmacy.com',
            'name': 'K. Joseph',
            'phone': '+91 4027889900',
            'pharmacy_name': 'Demo Pharmacy – Secunderabad (Paradise)',
            'address': 'MG Road, Near Paradise Circle',
            'area': 'Secunderabad',
            'city': 'Secunderabad',
            'state': 'Telangana',
            'pincode': '500003',
            'lat': 17.4399,
            'lng': 78.4983,
            'hours': '7:30 AM - 11:00 PM',
            'status': 'approved'
        },
        {
            'user_email': 'hyd_miyapur@pharmacy.com',
            'name': 'B. Naveen',
            'phone': '+91 4024991122',
            'pharmacy_name': 'Demo Pharmacy – Miyapur',
            'address': 'Allwyn X Roads, Miyapur Junction',
            'area': 'Miyapur',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500049',
            'lat': 17.4968,
            'lng': 78.3546,
            'hours': '8:00 AM - 10:30 PM',
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
        else:
            cursor.execute("""
            UPDATE pharmacies 
            SET pharmacy_name = ?, area = ?, city = ?, address = ?, operating_hours = ?, status = 'approved', is_demo = 1
            WHERE user_id = ?
            """, (p['pharmacy_name'], p['area'], p['city'], p['address'], p['hours'], user_id))

    cursor.execute("SELECT id, pharmacy_name FROM pharmacies")
    pharmacies_map = {row['pharmacy_name']: row['id'] for row in cursor.fetchall()}

    cursor.execute("SELECT id, name FROM medicines")
    meds_map = {row['name']: row['id'] for row in cursor.fetchall()}

    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Varied, realistic inventory for different pharmacies
    initial_inventory = [
        # Vizianagaram - DemoCare
        ('Demo Pharmacy – Vizianagaram (DemoCare)', 'Paracetamol', 25.00, 25, '2027-10-31'),
        ('Demo Pharmacy – Vizianagaram (DemoCare)', 'Cetirizine', 18.00, 50, '2027-08-15'),
        ('Demo Pharmacy – Vizianagaram (DemoCare)', 'Vitamin C', 22.00, 45, '2028-01-30'),
        ('Demo Pharmacy – Vizianagaram (DemoCare)', 'Pantoprazole', 45.00, 0, '2027-04-20'), # Out of stock
        ('Demo Pharmacy – Vizianagaram (DemoCare)', 'Ibuprofen', 35.00, 6, '2026-12-31'),   # Low stock
        ('Demo Pharmacy – Vizianagaram (DemoCare)', 'ORS', 22.00, 40, '2028-05-30'),

        # Vizianagaram - City Health
        ('Demo Pharmacy – Vizianagaram (City Health)', 'Paracetamol', 28.00, 5, '2027-09-30'), # Low stock
        ('Demo Pharmacy – Vizianagaram (City Health)', 'Amoxicillin', 75.00, 15, '2027-03-31'),
        ('Demo Pharmacy – Vizianagaram (City Health)', 'Azithromycin', 110.00, 12, '2027-06-30'),
        ('Demo Pharmacy – Vizianagaram (City Health)', 'Vitamin D3', 95.00, 20, '2027-11-15'),

        # Guntur - Lakshmipuram
        ('Demo Pharmacy – Guntur (Lakshmipuram)', 'Paracetamol', 23.00, 30, '2027-10-15'),     # In Stock
        ('Demo Pharmacy – Guntur (Lakshmipuram)', 'Cetirizine', 17.00, 8, '2027-07-30'),       # Low Stock
        ('Demo Pharmacy – Guntur (Lakshmipuram)', 'Vitamin C', 20.00, 50, '2028-03-15'),      # In Stock
        ('Demo Pharmacy – Guntur (Lakshmipuram)', 'ORS', 21.00, 60, '2028-04-20'),
        ('Demo Pharmacy – Guntur (Lakshmipuram)', 'Omeprazole', 38.00, 18, '2027-09-10'),

        # Guntur - Brodipet
        ('Demo Pharmacy – Guntur (Brodipet)', 'Paracetamol', 24.00, 15, '2027-11-20'),
        ('Demo Pharmacy – Guntur (Brodipet)', 'Levocetirizine', 28.00, 25, '2027-08-30'),
        ('Demo Pharmacy – Guntur (Brodipet)', 'Pantoprazole', 42.00, 30, '2027-06-15'),
        ('Demo Pharmacy – Guntur (Brodipet)', 'Cough Syrup', 85.00, 12, '2027-02-28'),

        # Vijayawada - MG Road
        ('Demo Pharmacy – Vijayawada (MG Road)', 'Paracetamol', 24.00, 40, '2027-12-31'),
        ('Demo Pharmacy – Vijayawada (MG Road)', 'Cetirizine', 18.50, 35, '2027-09-15'),
        ('Demo Pharmacy – Vijayawada (MG Road)', 'Vitamin C', 21.00, 60, '2028-02-28'),
        ('Demo Pharmacy – Vijayawada (MG Road)', 'Diclofenac', 45.00, 20, '2027-05-30'),

        # Visakhapatnam - Siripuram
        ('Demo Pharmacy – Visakhapatnam (Siripuram)', 'Paracetamol', 24.50, 45, '2027-12-15'),
        ('Demo Pharmacy – Visakhapatnam (Siripuram)', 'Cetirizine', 19.00, 30, '2027-09-20'),
        ('Demo Pharmacy – Visakhapatnam (Siripuram)', 'Fexofenadine', 115.00, 22, '2027-10-10'),
        ('Demo Pharmacy – Visakhapatnam (Siripuram)', 'Vitamin B12', 130.00, 18, '2027-08-15'),

        # Visakhapatnam - Beach Road
        ('Demo Pharmacy – Visakhapatnam (Beach Road)', 'Paracetamol', 26.00, 15, '2027-11-10'),
        ('Demo Pharmacy – Visakhapatnam (Beach Road)', 'Pantoprazole', 42.00, 20, '2027-08-15'),
        ('Demo Pharmacy – Visakhapatnam (Beach Road)', 'Amoxicillin-Clavulanate', 180.00, 10, '2027-04-30'),

        # Tirupati - Alipiri
        ('Demo Pharmacy – Tirupati (Alipiri)', 'Paracetamol', 22.00, 50, '2027-10-25'),
        ('Demo Pharmacy – Tirupati (Alipiri)', 'ORS', 20.00, 100, '2028-06-30'),
        ('Demo Pharmacy – Tirupati (Alipiri)', 'Vitamin C', 20.00, 40, '2028-01-20'),
        ('Demo Pharmacy – Tirupati (Alipiri)', 'Antacid', 75.00, 25, '2027-07-15'),

        # Kurnool - Park Road
        ('Demo Pharmacy – Kurnool (Park Road)', 'Paracetamol', 23.50, 20, '2027-09-15'),
        ('Demo Pharmacy – Kurnool (Park Road)', 'Cetirizine', 18.00, 25, '2027-10-10'),
        ('Demo Pharmacy – Kurnool (Park Road)', 'Metformin', 35.00, 30, '2027-11-30'),

        # Nellore - Trunk Road
        ('Demo Pharmacy – Nellore (Trunk Road)', 'Paracetamol', 24.00, 30, '2027-08-20'),
        ('Demo Pharmacy – Nellore (Trunk Road)', 'Pantoprazole', 40.00, 15, '2027-12-10'),
        ('Demo Pharmacy – Nellore (Trunk Road)', 'Vitamin D3', 90.00, 12, '2027-05-15'),

        # Rajahmundry - Kotipalli
        ('Demo Pharmacy – Rajahmundry (Kotipalli)', 'Paracetamol', 24.00, 25, '2027-10-05'),
        ('Demo Pharmacy – Rajahmundry (Kotipalli)', 'Cetirizine', 17.50, 30, '2027-08-25'),
        ('Demo Pharmacy – Rajahmundry (Kotipalli)', 'Calcium', 85.00, 20, '2027-12-15'),

        # Kakinada - Main Road
        ('Demo Pharmacy – Kakinada (Main Road)', 'Paracetamol', 23.00, 35, '2027-11-15'),
        ('Demo Pharmacy – Kakinada (Main Road)', 'Amoxicillin', 72.00, 14, '2027-06-20'),
        ('Demo Pharmacy – Kakinada (Main Road)', 'Multivitamin', 65.00, 28, '2028-02-10'),

        # Kadapa - Seven Roads
        ('Demo Pharmacy – Kadapa (Seven Roads)', 'Paracetamol', 25.00, 18, '2027-09-25'),
        ('Demo Pharmacy – Kadapa (Seven Roads)', 'Aceclofenac', 55.00, 20, '2027-07-15'),

        # Anantapur - Clock Tower
        ('Demo Pharmacy – Anantapur (Clock Tower)', 'Paracetamol', 23.00, 25, '2027-10-30'),
        ('Demo Pharmacy – Anantapur (Clock Tower)', 'Amlodipine', 32.00, 30, '2027-05-25'),

        # Hyderabad - Central
        ('Demo Pharmacy – Hyderabad (Central)', 'Paracetamol', 25.00, 60, '2027-12-31'),
        ('Demo Pharmacy – Hyderabad (Central)', 'Cetirizine', 18.00, 50, '2027-11-20'),
        ('Demo Pharmacy – Hyderabad (Central)', 'Vitamin C', 22.00, 80, '2028-05-15'),
        ('Demo Pharmacy – Hyderabad (Central)', 'Pantoprazole', 44.00, 40, '2027-08-30'),
        ('Demo Pharmacy – Hyderabad (Central)', 'Atorvastatin', 95.00, 25, '2027-06-15'),

        # Hyderabad - Kukatpally (KPHB)
        ('Demo Pharmacy – Kukatpally (KPHB)', 'Paracetamol', 24.00, 50, '2027-11-30'),
        ('Demo Pharmacy – Kukatpally (KPHB)', 'Cetirizine', 17.50, 40, '2027-10-15'),
        ('Demo Pharmacy – Kukatpally (KPHB)', 'Vitamin C', 20.00, 60, '2028-03-30'),
        ('Demo Pharmacy – Kukatpally (KPHB)', 'Amoxicillin-Clavulanate', 175.00, 15, '2027-09-10'),
        ('Demo Pharmacy – Kukatpally (KPHB)', 'Ambroxol Syrup', 92.00, 20, '2027-04-15'),

        # Hyderabad - Gachibowli (Tech Zone)
        ('Demo Pharmacy – Gachibowli (Tech Zone)', 'Paracetamol', 26.00, 70, '2028-01-15'),
        ('Demo Pharmacy – Gachibowli (Tech Zone)', 'Levocetirizine', 30.00, 35, '2027-10-20'),
        ('Demo Pharmacy – Gachibowli (Tech Zone)', 'Vitamin C', 22.00, 90, '2028-04-10'),
        ('Demo Pharmacy – Gachibowli (Tech Zone)', 'Esomeprazole', 65.00, 25, '2027-07-20'),
        ('Demo Pharmacy – Gachibowli (Tech Zone)', 'Iron', 110.00, 30, '2027-11-05'),

        # Hyderabad - Madhapur
        ('Demo Pharmacy – Madhapur (Hitech City)', 'Paracetamol', 25.50, 40, '2027-12-10'),
        ('Demo Pharmacy – Madhapur (Hitech City)', 'Fexofenadine', 120.00, 30, '2027-09-15'),
        ('Demo Pharmacy – Madhapur (Hitech City)', 'Vitamin D3', 95.00, 40, '2028-02-20'),

        # Hyderabad - Banjara Hills
        ('Demo Pharmacy – Banjara Hills', 'Paracetamol', 26.00, 35, '2027-10-25'),
        ('Demo Pharmacy – Banjara Hills', 'Naproxen', 60.00, 15, '2027-06-30'),
        ('Demo Pharmacy – Banjara Hills', 'Calcium', 90.00, 25, '2027-12-20'),

        # Secunderabad - Paradise
        ('Demo Pharmacy – Secunderabad (Paradise)', 'Paracetamol', 24.00, 45, '2027-11-15'),
        ('Demo Pharmacy – Secunderabad (Paradise)', 'Cetirizine', 18.00, 35, '2027-08-30'),
        ('Demo Pharmacy – Secunderabad (Paradise)', 'ORS', 21.00, 50, '2028-05-10'),

        # Hyderabad - Miyapur
        ('Demo Pharmacy – Miyapur', 'Paracetamol', 23.50, 30, '2027-10-10'),
        ('Demo Pharmacy – Miyapur', 'Omeprazole', 36.00, 20, '2027-07-25'),
        ('Demo Pharmacy – Miyapur', 'Cough Syrup', 80.00, 15, '2027-03-20')
    ]

    for p_name, m_name, price, qty, expiry in initial_inventory:
        p_id = pharmacies_map.get(p_name)
        m_id = meds_map.get(m_name)
        if p_id and m_id:
            cursor.execute("SELECT id FROM inventory WHERE pharmacy_id = ? AND medicine_id = ?", (p_id, m_id))
            if cursor.fetchone() is None:
                cursor.execute("""
                INSERT INTO inventory (pharmacy_id, medicine_id, price, quantity, expiry_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (p_id, m_id, price, qty, expiry, now_iso))
            else:
                cursor.execute("""
                UPDATE inventory
                SET price = ?, quantity = ?, expiry_date = ?, last_updated = ?
                WHERE pharmacy_id = ? AND medicine_id = ?
                """, (price, qty, expiry, now_iso, p_id, m_id))

    conn.commit()
    conn.close()
