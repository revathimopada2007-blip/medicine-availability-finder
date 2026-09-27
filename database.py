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

    # Migration check
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

    conn.commit()
    conn.close()

def seed_demo_data(db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
    row = cursor.fetchone()
    if row and row['count'] > 0:
        conn.close()
        return

    # 1. ADMIN USER
    admin_pw = generate_password_hash("Admin@123")
    cursor.execute("""
    INSERT INTO users (name, email, phone, password_hash, role, address, area, city, state, pincode, latitude, longitude)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("System Administrator", "admin@medfinder.com", "9876543210", admin_pw, "admin", "Health HQ, Sector 1", "Banjara Hills", "Hyderabad", "Telangana", "500034", 17.4156, 78.4350))

    # 2. PHARMACIES ACROSS ANDHRA PRADESH & HYDERABAD
    pharmacies_seed = [
        # GUNTUR
        ("Kavitha Rao", "guntur.apollo@medfinder.com", "9848011221", "Apollo Pharmacy Brodipet", "Brodipet 4/2", "Brodipet", "Guntur", "Andhra Pradesh", "522002", 16.3067, 80.4365, "24 Hours"),
        ("Siva Reddy", "guntur.medplus@medfinder.com", "9848011222", "MedPlus Pharmacy Arundalpet", "Arundalpet Main Road", "Arundalpet", "Guntur", "Andhra Pradesh", "522002", 16.3120, 80.4420, "7:00 AM - 11:00 PM"),
        ("Ramesh Naidu", "guntur.sanjivani@medfinder.com", "9848011223", "Sanjivani Medical & General Stores", "Kothapet Center", "Kothapet", "Guntur", "Andhra Pradesh", "522001", 16.2990, 80.4510, "8:00 AM - 10:30 PM"),
        # VIJAYAWADA
        ("Suresh Babu", "vja.apollo@medfinder.com", "9848022331", "Apollo Pharmacy Benz Circle", "MG Road, Near Benz Circle", "Benz Circle", "Vijayawada", "Andhra Pradesh", "520010", 16.5062, 80.6480, "24 Hours"),
        ("Venkat Rao", "vja.medplus@medfinder.com", "9848022332", "MedPlus Governorpet", "Prakasam Road", "Governorpet", "Vijayawada", "Andhra Pradesh", "520002", 16.5135, 80.6285, "7:00 AM - 11:00 PM"),
        ("Radha Krishna", "vja.krishna@medfinder.com", "9848022333", "Sri Krishna Medical Agencies", "Besant Road", "Besant Road", "Vijayawada", "Andhra Pradesh", "520003", 16.5160, 80.6320, "8:30 AM - 10:30 PM"),
        # VIZIANAGARAM
        ("Satyanarayana Varma", "vzm.balaji@medfinder.com", "9848033441", "Sri Balaji Medicals Vizianagaram", "Main Road, RTC Complex Area", "RTC Complex Area", "Vizianagaram", "Andhra Pradesh", "535002", 18.1124, 83.3970, "8:00 AM - 10:30 PM"),
        ("Appala Raju", "vzm.apollo@medfinder.com", "9848033442", "Apollo Pharmacy Cantonment VZM", "Cantonment Road", "Cantonment", "Vizianagaram", "Andhra Pradesh", "535003", 18.1215, 83.4045, "24 Hours"),
        ("Lakshman Rao", "vzm.medplus@medfinder.com", "9848033443", "MedPlus Mayuri Junction", "Mayuri Junction, Station Road", "Mayuri Junction", "Vizianagaram", "Andhra Pradesh", "535001", 18.1160, 83.3920, "7:00 AM - 11:00 PM"),
        # VISAKHAPATNAM
        ("Bhanu Prakash", "vizag.apollo@medfinder.com", "9848044551", "Apollo Pharmacy Siripuram", "Siripuram Junction", "Siripuram", "Visakhapatnam", "Andhra Pradesh", "530003", 17.7214, 83.3159, "24 Hours"),
        ("Murali Mohan", "vizag.medplus@medfinder.com", "9848044552", "MedPlus Gajuwaka", "High School Road, Gajuwaka", "Gajuwaka", "Visakhapatnam", "Andhra Pradesh", "530026", 17.6890, 83.2120, "7:00 AM - 11:00 PM"),
        ("Chandra Sekhar", "vizag.care@medfinder.com", "9848044553", "Care Plus Pharmacy MVP Colony", "Sector 3, MVP Colony", "MVP Colony", "Visakhapatnam", "Andhra Pradesh", "530017", 17.7420, 83.3360, "8:00 AM - 11:00 PM"),
        # TIRUPATI
        ("Govindarajulu", "tpt.apollo@medfinder.com", "9848055661", "Apollo Pharmacy Tirupati", "Beside SVIMS Hospital Road", "Alipiri Road", "Tirupati", "Andhra Pradesh", "517507", 13.6288, 79.4192, "24 Hours"),
        ("Venkatesh S", "tpt.medplus@medfinder.com", "9848055662", "MedPlus Korlagunta", "Korlagunta Main Road", "Korlagunta", "Tirupati", "Andhra Pradesh", "517501", 13.6350, 79.4260, "7:30 AM - 10:30 PM"),
        # KURNOOL
        ("Naveen Kumar", "kurnool.apollo@medfinder.com", "9848066771", "Apollo Pharmacy Kurnool", "Near Government General Hospital", "Budhawarapeta", "Kurnool", "Andhra Pradesh", "518002", 15.8281, 78.0373, "24 Hours"),
        ("Rajendra Prasad", "kurnool.medplus@medfinder.com", "9848066772", "MedPlus Park Road Kurnool", "Park Road", "Park Road", "Kurnool", "Andhra Pradesh", "518001", 15.8320, 78.0410, "8:00 AM - 11:00 PM"),
        # NELLORE
        ("Kalyan Chakravarthy", "nellore.apollo@medfinder.com", "9848077881", "Apollo Pharmacy Nellore", "Trunk Road, Gandhi Nagar", "Gandhi Nagar", "Nellore", "Andhra Pradesh", "524001", 14.4426, 79.9865, "24 Hours"),
        ("Sai Krishna", "nellore.medplus@medfinder.com", "9848077882", "MedPlus Pogathota Nellore", "Pogathota", "Pogathota", "Nellore", "Andhra Pradesh", "524001", 14.4470, 79.9820, "7:00 AM - 11:00 PM"),
        # RAJAHMUNDRY
        ("Subba Raju", "rjy.apollo@medfinder.com", "9848088991", "Apollo Pharmacy Rajahmundry", "Danavaipeta Main Road", "Danavaipeta", "Rajahmundry", "Andhra Pradesh", "533103", 17.0005, 81.7800, "24 Hours"),
        ("Venkata Ratnam", "rjy.medplus@medfinder.com", "9848088992", "MedPlus Kotipalli Bus Stand", "Kotipalli Road", "Innespeta", "Rajahmundry", "Andhra Pradesh", "533101", 16.9940, 81.7750, "8:00 AM - 10:30 PM"),
        # KAKINADA
        ("Prasad Varma", "kakinada.apollo@medfinder.com", "9848099001", "Apollo Pharmacy Kakinada", "Main Road, Surya Rao Peta", "Surya Rao Peta", "Kakinada", "Andhra Pradesh", "533001", 16.9890, 82.2475, "24 Hours"),
        ("Satish Kumar", "kakinada.medplus@medfinder.com", "9848099002", "MedPlus Cinema Road Kakinada", "Cinema Road", "Cinema Road", "Kakinada", "Andhra Pradesh", "533001", 16.9820, 82.2410, "7:30 AM - 10:30 PM"),
        # KADAPA
        ("Obul Reddy", "kadapa.apollo@medfinder.com", "9848100111", "Apollo Pharmacy Kadapa", "Nagarajupalli Main Road", "Nagarajupalli", "Kadapa", "Andhra Pradesh", "516001", 14.4673, 78.8242, "24 Hours"),
        ("Madhusudhan", "kadapa.medplus@medfinder.com", "9848100112", "MedPlus RIMS Road Kadapa", "RIMS Hospital Road", "RIMS Area", "Kadapa", "Andhra Pradesh", "516002", 14.4750, 78.8310, "8:00 AM - 11:00 PM"),
        # ANANTAPUR
        ("Venkatesh Prasad", "atp.apollo@medfinder.com", "9848111221", "Apollo Pharmacy Anantapur", "Subhash Road", "Subhash Road", "Anantapur", "Andhra Pradesh", "515001", 14.6819, 77.6006, "24 Hours"),
        ("Sreeramulu", "atp.medplus@medfinder.com", "9848111222", "MedPlus Clock Tower Anantapur", "Near Clock Tower", "Clock Tower Area", "Anantapur", "Andhra Pradesh", "515001", 14.6860, 77.5980, "7:30 AM - 10:30 PM"),
        # HYDERABAD - KUKATPALLY
        ("Vijay Kumar", "hyd.kphb@medfinder.com", "9848122331", "MedPlus KPHB Colony", "Road No 1, KPHB Phase 1", "Kukatpally", "Hyderabad", "Telangana", "500072", 17.4938, 78.3995, "7:00 AM - 11:30 PM"),
        ("Srinivas Rao", "hyd.kukatpally.apollo@medfinder.com", "9848122332", "Apollo Pharmacy Kukatpally", "Opposite BJP Office, Main Road", "Kukatpally", "Hyderabad", "Telangana", "500072", 17.4875, 78.4060, "24 Hours"),
        # HYDERABAD - GACHIBOWLI
        ("Anand Reddy", "hyd.gachibowli@medfinder.com", "9848133441", "Apollo Pharmacy Gachibowli", "DLF Cybercity Road", "Gachibowli", "Hyderabad", "Telangana", "500032", 17.4401, 78.3489, "24 Hours"),
        ("Manoj Sharma", "hyd.gachibowli.medplus@medfinder.com", "9848133442", "MedPlus Telecom Nagar", "Telecom Nagar Main Road", "Gachibowli", "Hyderabad", "Telangana", "500032", 17.4445, 78.3540, "7:00 AM - 11:00 PM"),
        # HYDERABAD - MADHAPUR
        ("Harish Patel", "hyd.madhapur@medfinder.com", "9848144551", "Apollo Pharmacy Madhapur", "Ayyappa Society Main Road", "Madhapur", "Hyderabad", "Telangana", "500081", 17.4483, 78.3915, "24 Hours"),
        # HYDERABAD - BANJARA HILLS
        ("Deepak Chawla", "hyd.banjara@medfinder.com", "9848155661", "Apollo Pharmacy Banjara Hills", "Road No 2, Near Lv Prasad", "Banjara Hills", "Hyderabad", "Telangana", "500034", 17.4180, 78.4310, "24 Hours"),
        # HYDERABAD - SECUNDERABAD
        ("Praveen Kumar", "hyd.secunderabad@medfinder.com", "9848166771", "Apollo Pharmacy Secunderabad", "MG Road, Near Clock Tower", "Secunderabad", "Secunderabad", "Telangana", "500003", 17.4399, 78.4983, "24 Hours"),
        # HYDERABAD - MIYAPUR
        ("Sunil Varma", "hyd.miyapur@medfinder.com", "9848177881", "MedPlus Miyapur Allwyn X Road", "Allwyn X Road", "Miyapur", "Hyderabad", "Telangana", "500049", 17.4968, 78.3614, "7:30 AM - 11:00 PM")
    ]

    pharmacy_ids = []
    pw = generate_password_hash("Pharmacy@123")

    for p in pharmacies_seed:
        owner_name, email, phone, pharm_name, address, area, city, state, pincode, lat, lng, hours = p
        cursor.execute("""
        INSERT INTO users (name, email, phone, password_hash, role, address, area, city, state, pincode, latitude, longitude)
        VALUES (?, ?, ?, ?, 'pharmacy', ?, ?, ?, ?, ?, ?, ?)
        """, (owner_name, email, phone, pw, address, area, city, state, pincode, lat, lng))
        user_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO pharmacies (user_id, pharmacy_name, owner_name, phone, email, address, area, city, state, pincode, latitude, longitude, operating_hours, status, is_demo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', 1)
        """, (user_id, pharm_name, owner_name, phone, email, address, area, city, state, pincode, lat, lng, hours))
        pharmacy_ids.append(cursor.lastrowid)

    # 3. COMPREHENSIVE MASTER MEDICINE CATALOG (CHRONIC & ACUTE CARE)
    medicines_seed = [
        # --- BLOOD PRESSURE / HYPERTENSION ---
        ("Amlodipine 5mg (Amlokind 5)", "Blood Pressure & Hypertension", "Amlodipine Besylate", "Amlokind 5", "Mankind Pharma", "5mg", "Tablet", "Antihypertensive calcium channel blocker for blood pressure management.", 1),
        ("Losartan 50mg (Losar 50)", "Blood Pressure & Hypertension", "Losartan Potassium", "Losar 50", "Unichem Laboratories", "50mg", "Tablet", "Angiotensin II receptor blocker (ARB) for hypertension.", 1),
        ("Telmisartan 40mg (Telma 40)", "Blood Pressure & Hypertension", "Telmisartan", "Telma 40", "Glenmark Pharmaceuticals", "40mg", "Tablet", "Angiotensin II receptor antagonist for blood pressure control.", 1),
        ("Olmesartan 20mg (Olmat 20)", "Blood Pressure & Hypertension", "Olmesartan Medoxomil", "Olmat 20", "Micro Labs", "20mg", "Tablet", "Antihypertensive medication for high blood pressure.", 1),
        ("Valsartan 80mg (Valzaar 80)", "Blood Pressure & Hypertension", "Valsartan", "Valzaar 80", "Torrent Pharmaceuticals", "80mg", "Tablet", "Angiotensin receptor blocker for cardiovascular and BP management.", 1),
        ("Enalapril 5mg (Envas 5)", "Blood Pressure & Hypertension", "Enalapril Maleate", "Envas 5", "Cadila Healthcare", "5mg", "Tablet", "ACE inhibitor antihypertensive medication.", 1),
        ("Lisinopril 5mg (Lipril 5)", "Blood Pressure & Hypertension", "Lisinopril", "Lipril 5", "Lupin Ltd", "5mg", "Tablet", "ACE inhibitor for blood pressure and heart health.", 1),
        ("Ramipril 2.5mg (Cardace 2.5)", "Blood Pressure & Hypertension", "Ramipril", "Cardace 2.5", "Sanofi India", "2.5mg", "Tablet", "ACE inhibitor for hypertension and cardiovascular risk reduction.", 1),
        ("Hydrochlorothiazide 12.5mg (Aquazide 12.5)", "Blood Pressure & Hypertension", "Hydrochlorothiazide", "Aquazide 12.5", "Sun Pharma", "12.5mg", "Tablet", "Thiazide diuretic medication for blood pressure control.", 1),
        ("Chlorthalidone 12.5mg (Thalidone 12.5)", "Blood Pressure & Hypertension", "Chlorthalidone", "Thalidone 12.5", "Torrent Pharmaceuticals", "12.5mg", "Tablet", "Long-acting thiazide-like diuretic for hypertension.", 1),
        ("Atenolol 50mg (Aten 50)", "Blood Pressure & Hypertension", "Atenolol", "Aten 50", "Zydus Cadila", "50mg", "Tablet", "Beta-blocker for hypertension and cardiovascular care.", 1),
        ("Metoprolol 25mg (Metolar 25)", "Blood Pressure & Hypertension", "Metoprolol Succinate", "Metolar 25", "Cipla Ltd", "25mg", "Tablet", "Selective beta-1 receptor blocker for heart and BP care.", 1),
        ("Bisoprolol 5mg (Concor 5)", "Blood Pressure & Hypertension", "Bisoprolol Fumarate", "Concor 5", "Merck Ltd", "5mg", "Tablet", "Cardioselective beta-blocker for blood pressure and cardiac rhythm.", 1),
        ("Carvedilol 3.125mg (Cardivas 3.125)", "Blood Pressure & Hypertension", "Carvedilol", "Cardivas 3.125", "Sun Pharma", "3.125mg", "Tablet", "Non-selective beta and alpha-1 blocker for cardiovascular support.", 1),
        ("Nifedipine 10mg (Nicardia Retard 10)", "Blood Pressure & Hypertension", "Nifedipine", "Nicardia Retard 10", "J.B. Chemicals", "10mg", "Tablet", "Calcium channel blocker for hypertension and angina.", 1),

        # --- DIABETES / BLOOD SUGAR ---
        ("Metformin 500mg (Glycomet 500)", "Diabetes & Blood Sugar", "Metformin Hydrochloride", "Glycomet 500", "USV Ltd", "500mg", "Tablet", "Biguanide oral antidiabetic medicine for glycemic control.", 1),
        ("Glimepiride 1mg (Amaryl 1mg)", "Diabetes & Blood Sugar", "Glimepiride", "Amaryl 1mg", "Sanofi India", "1mg", "Tablet", "Sulfonylurea class antidiabetic medication.", 1),
        ("Gliclazide 60mg (Diamicron 60 MR)", "Diabetes & Blood Sugar", "Gliclazide", "Diamicron 60 MR", "Dr. Reddy's Laboratories", "60mg", "Tablet", "Modified release sulfonylurea for glycemic management.", 1),
        ("Glipizide 5mg (Glynase 5)", "Diabetes & Blood Sugar", "Glipizide", "Glynase 5", "USV Ltd", "5mg", "Tablet", "Short-acting sulfonylurea oral hypoglycemic.", 1),
        ("Sitagliptin 100mg (Januvia 100)", "Diabetes & Blood Sugar", "Sitagliptin Phosphate", "Januvia 100", "MSD Pharmaceuticals", "100mg", "Tablet", "DPP-4 inhibitor for type 2 diabetes management.", 1),
        ("Linagliptin 5mg (Trajenta 5)", "Diabetes & Blood Sugar", "Linagliptin", "Trajenta 5", "Boehringer Ingelheim", "5mg", "Tablet", "DPP-4 inhibitor with non-renal excretion pathway.", 1),
        ("Empagliflozin 10mg (Jardiance 10)", "Diabetes & Blood Sugar", "Empagliflozin", "Jardiance 10", "Boehringer Ingelheim", "10mg", "Tablet", "SGLT2 inhibitor for blood sugar control and cardio-renal support.", 1),
        ("Dapagliflozin 10mg (Forxiga 10)", "Diabetes & Blood Sugar", "Dapagliflozin", "Forxiga 10", "AstraZeneca", "10mg", "Tablet", "SGLT2 inhibitor for glycemic regulation.", 1),
        ("Canagliflozin 100mg (Invokana 100)", "Diabetes & Blood Sugar", "Canagliflozin", "Invokana 100", "Janssen Pharmaceuticals", "100mg", "Tablet", "SGLT2 inhibitor for type 2 diabetes.", 1),
        ("Pioglitazone 15mg (Pioz 15)", "Diabetes & Blood Sugar", "Pioglitazone Hydrochloride", "Pioz 15", "USV Ltd", "15mg", "Tablet", "Thiazolidinedione insulin sensitizer.", 1),
        ("Human Insulin Mixtard 30/70 (100 IU/ml)", "Diabetes & Blood Sugar", "Recombinant Human Insulin (30% soluble / 70% isophane)", "Human Mixtard 30/70", "Novo Nordisk", "100 IU/ml", "Injectable Vial", "Premixed human insulin for diabetes care.", 1),
        ("Insulin Glargine Pen (Lantus Solostar)", "Diabetes & Blood Sugar", "Insulin Glargine", "Lantus SoloStar", "Sanofi India", "100 IU/ml", "Prefilled Pen", "Long-acting basal insulin analog.", 1),

        # --- HEART & CARDIOVASCULAR ---
        ("Aspirin 75mg (Ecosprin 75)", "Heart & Cardiovascular", "Acetylsalicylic Acid", "Ecosprin 75", "USV Ltd", "75mg", "Tablet", "Antiplatelet agent for cardiovascular protection.", 1),
        ("Clopidogrel 75mg (Clopilet 75)", "Heart & Cardiovascular", "Clopidogrel Bisulfate", "Clopilet 75", "Sun Pharma", "75mg", "Tablet", "Antiplatelet medication preventing arterial thrombi.", 1),
        ("Isosorbide Mononitrate 20mg (Monotrate 20)", "Heart & Cardiovascular", "Isosorbide Mononitrate", "Monotrate 20", "Sun Pharma", "20mg", "Tablet", "Nitrate vasodilator for coronary angina management.", 1),
        ("Nitroglycerin Sublingual 5mg (Sorbitrate 5)", "Heart & Cardiovascular", "Isosorbide Dinitrate / Nitroglycerin", "Sorbitrate 5", "Abbott Healthcare", "5mg", "Sublingual Tablet", "Rapid-acting sublingual vasodilator for angina.", 1),
        ("Furosemide 40mg (Lasix 40)", "Heart & Cardiovascular", "Furosemide", "Lasix 40", "Sanofi India", "40mg", "Tablet", "Loop diuretic for fluid retention and cardiac volume overload.", 1),
        ("Spironolactone 25mg (Aldactone 25)", "Heart & Cardiovascular", "Spironolactone", "Aldactone 25", "RPG Life Sciences", "25mg", "Tablet", "Aldosterone antagonist potassium-sparing diuretic.", 1),
        ("Sacubitril / Valsartan 50mg (Vymada 50)", "Heart & Cardiovascular", "Sacubitril + Valsartan Sodium", "Vymada 50", "Novartis / Cipla", "50mg", "Tablet", "Angiotensin receptor-neprilysin inhibitor (ARNI) for heart failure care.", 1),

        # --- CHOLESTEROL & LIPIDS ---
        ("Atorvastatin 10mg (Atorva 10)", "Cholesterol & Lipids", "Atorvastatin Calcium", "Atorva 10", "Zydus Cadila", "10mg", "Tablet", "HMG-CoA reductase inhibitor (statin) for lipid management.", 1),
        ("Rosuvastatin 10mg (Rosuvas 10)", "Cholesterol & Lipids", "Rosuvastatin Calcium", "Rosuvas 10", "Sun Pharma", "10mg", "Tablet", "Potent statin for cholesterol regulation and cardiac risk reduction.", 1),
        ("Simvastatin 10mg (Simvotin 10)", "Cholesterol & Lipids", "Simvastatin", "Simvotin 10", "Sun Pharma", "10mg", "Tablet", "Lipid-lowering statin medication.", 1),
        ("Ezetimibe 10mg (Ezentia 10)", "Cholesterol & Lipids", "Ezetimibe", "Ezentia 10", "Sun Pharma", "10mg", "Tablet", "Cholesterol absorption inhibitor.", 1),
        ("Fenofibrate 160mg (Lipicard 160)", "Cholesterol & Lipids", "Fenofibrate", "Lipicard 160", "USV Ltd", "160mg", "Capsule", "Fibric acid derivative for triglyceride and lipid reduction.", 1),

        # --- THYROID CARE ---
        ("Levothyroxine 50mcg (Thyronorm 50)", "Thyroid Care", "Levothyroxine Sodium", "Thyronorm 50", "Abbott Healthcare", "50mcg", "Tablet", "Synthetic thyroid hormone T4 for thyroid hormone replacement.", 1),
        ("Levothyroxine 100mcg (Eltroxin 100)", "Thyroid Care", "Levothyroxine Sodium", "Eltroxin 100", "GSK India", "100mcg", "Tablet", "Thyroid hormone supplementation.", 1),
        ("Carbimazole 5mg (Neo-Mercazole 5)", "Thyroid Care", "Carbimazole", "Neo-Mercazole 5", "Abbott Healthcare", "5mg", "Tablet", "Antithyroid medicine for hyperthyroidism.", 1),
        ("Propylthiouracil 50mg (PTU 50)", "Thyroid Care", "Propylthiouracil", "PTU 50", "Macleods Pharmaceuticals", "50mg", "Tablet", "Antithyroid agent reducing thyroid hormone synthesis.", 1),

        # --- ASTHMA & RESPIRATORY CONDITIONS ---
        ("Salbutamol Inhaler 100mcg (Asthalin)", "Asthma & Respiratory", "Salbutamol / Albuterol Sulfate", "Asthalin Inhaler", "Cipla Ltd", "100mcg (200 doses)", "Inhaler", "Short-acting beta-2 agonist (SABA) bronchodilator.", 1),
        ("Budesonide Inhaler 200mcg (Budecort 200)", "Asthma & Respiratory", "Budesonide", "Budecort 200 Inhaler", "Cipla Ltd", "200mcg (200 doses)", "Inhaler", "Inhaled corticosteroid (ICS) for airway inflammation.", 1),
        ("Budesonide + Formoterol Inhaler (Foracort 200)", "Asthma & Respiratory", "Budesonide 200mcg + Formoterol 6mcg", "Foracort 200 Inhaler", "Cipla Ltd", "200mcg/6mcg", "Inhaler / Rotacaps", "Combination ICS/LABA maintenance inhaler.", 1),
        ("Fluticasone Inhaler 125mcg (Flohale 125)", "Asthma & Respiratory", "Fluticasone Propionate", "Flohale 125 Inhaler", "Cipla Ltd", "125mcg", "Inhaler", "Inhaled corticosteroid for chronic respiratory management.", 1),
        ("Montelukast 10mg (Montair 10)", "Asthma & Respiratory", "Montelukast Sodium", "Montair 10", "Cipla Ltd", "10mg", "Tablet", "Leukotriene receptor antagonist for allergic airway support.", 1),
        ("Ipratropium Inhaler 20mcg (Ipravent)", "Asthma & Respiratory", "Ipratropium Bromide", "Ipravent Inhaler", "Cipla Ltd", "20mcg", "Inhaler", "Anticholinergic bronchodilator for respiratory airways.", 1),

        # --- OTHER COMMON CHRONIC CONDITIONS ---
        ("Torsemide 10mg (Dytor 10)", "Kidney Care", "Torsemide", "Dytor 10", "Torrent Pharmaceuticals", "10mg", "Tablet", "Loop diuretic for edema and fluid management.", 1),
        ("Febuxostat 40mg (Febuget 40)", "Kidney Care", "Febuxostat", "Febuget 40", "Sun Pharma", "40mg", "Tablet", "Xanthine oxidase inhibitor for hyperuricemia and gout management.", 1),
        ("Sodium Bicarbonate 500mg (Soda Mint)", "Kidney Care", "Sodium Bicarbonate", "Soda Mint 500", "Apex Laboratories", "500mg", "Tablet", "Systemic alkalizer and antacid.", 0),

        ("Pantoprazole 40mg (Pantocid 40)", "Gastric & Acidity", "Pantoprazole Sodium", "Pantocid 40", "Sun Pharma", "40mg", "Tablet", "Proton pump inhibitor (PPI) for gastric acid reduction.", 1),
        ("Rabeprazole 20mg (Razo 20)", "Gastric & Acidity", "Rabeprazole Sodium", "Razo 20", "Dr. Reddy's Laboratories", "20mg", "Tablet", "Gastric proton pump inhibitor.", 1),
        ("Esomeprazole 40mg (Nexpro 40)", "Gastric & Acidity", "Esomeprazole Magnesium", "Nexpro 40", "Torrent Pharmaceuticals", "40mg", "Tablet", "S-isomer PPI for acid reflux and peptic care.", 1),
        ("Sucralfate Suspension (Sucrafil 100ml)", "Gastric & Acidity", "Sucralfate", "Sucrafil Suspension", "Fourrts India", "1000mg/10ml", "Syrup/Suspension", "Mucosal protective agent for gastric ulcers.", 1),

        ("Methotrexate 7.5mg (Folitrax 7.5)", "Arthritis & Joint Care", "Methotrexate", "Folitrax 7.5", "IPCA Laboratories", "7.5mg", "Tablet", "Disease-modifying antirheumatic drug (DMARD) for rheumatoid arthritis.", 1),
        ("Hydroxychloroquine 200mg (HCQS 200)", "Arthritis & Joint Care", "Hydroxychloroquine Sulfate", "HCQS 200", "IPCA Laboratories", "200mg", "Tablet", "DMARD for autoimmune and rheumatic joint conditions.", 1),
        ("Sulfasalazine 500mg (Saaz 500)", "Arthritis & Joint Care", "Sulfasalazine", "Saaz 500", "IPCA Laboratories", "500mg", "Tablet", "Anti-inflammatory DMARD for arthritis and bowel inflammation.", 1),
        ("Etoricoxib 90mg (Nucoxia 90)", "Arthritis & Joint Care", "Etoricoxib", "Nucoxia 90", "Zydus Cadila", "90mg", "Tablet", "Selective COX-2 inhibitor for joint inflammation.", 1),

        ("Alendronate 70mg (Osteofos 70)", "Osteoporosis & Bone Health", "Alendronate Sodium", "Osteofos 70", "Cipla Ltd", "70mg", "Tablet", "Bisphosphonate for bone density preservation.", 1),
        ("Shelcal HD (Calcium 500mg + Vitamin D3 500IU)", "Osteoporosis & Bone Health", "Calcium Carbonate + Cholecalciferol", "Shelcal HD", "Torrent Pharmaceuticals", "500mg/500IU", "Tablet", "Calcium and high-dose Vitamin D3 bone nutrition.", 0),

        ("Sumatriptan 50mg (Suminat 50)", "Migraine Care", "Sumatriptan Succinate", "Suminat 50", "Sun Pharma", "50mg", "Tablet", "5-HT1 receptor agonist triptan for acute migraine episodes.", 1),
        ("Rizatriptan 10mg (Rizact 10)", "Migraine Care", "Rizatriptan Benzoate", "Rizact 10", "Cipla Ltd", "10mg", "Tablet", "Triptan class medication for acute migraine.", 1),
        ("Propranolol 40mg (Inderal 40)", "Migraine Care", "Propranolol Hydrochloride", "Inderal 40", "Abbott Healthcare", "40mg", "Tablet", "Non-selective beta-blocker used for migraine prophylaxis.", 1),
        ("Flunarizine 5mg (Sibelium 5)", "Migraine Care", "Flunarizine Hydrochloride", "Sibelium 5", "Janssen / Torrent", "5mg", "Tablet", "Calcium entry blocker for migraine prevention.", 1),

        ("Levetiracetam 500mg (Levipil 500)", "Epilepsy & Neurological", "Levetiracetam", "Levipil 500", "Sun Pharma", "500mg", "Tablet", "Broad-spectrum antiepileptic medicine for seizure control.", 1),
        ("Sodium Valproate 300mg (Encorate Chrono 300)", "Epilepsy & Neurological", "Sodium Valproate + Valproic Acid", "Encorate Chrono 300", "Sun Pharma", "300mg", "Tablet", "Controlled release anticonvulsant and mood stabilizer.", 1),
        ("Carbamazepine 200mg (Tegretol 200)", "Epilepsy & Neurological", "Carbamazepine", "Tegretol 200", "Novartis India", "200mg", "Tablet", "Anticonvulsant for neural and seizure disorders.", 1),

        ("Bilastine 20mg (Bilaxten 20)", "Allergies & Skin Care", "Bilastine", "Bilaxten 20", "Dr. Reddy's Laboratories", "20mg", "Tablet", "Non-sedating second-generation antihistamine.", 1),
        ("Desloratadine 5mg (Deslor 5)", "Allergies & Skin Care", "Desloratadine", "Deslor 5", "Sun Pharma", "5mg", "Tablet", "Long-acting antihistamine for allergic rhinitis and urticaria.", 1),
        ("Hydroxyzine 25mg (Atarax 25)", "Allergies & Skin Care", "Hydroxyzine Hydrochloride", "Atarax 25", "Dr. Reddy's Laboratories", "25mg", "Tablet", "First-generation antihistamine for pruritus and urticaria.", 1),
        ("Clobetasol Propionate Cream 0.05% (Tenovate)", "Allergies & Skin Care", "Clobetasol Propionate", "Tenovate Cream", "GSK India", "0.05% (30g)", "Cream", "High-potency topical corticosteroid for dermatological conditions.", 1),

        # --- PAIN, FEVER, COLD & GENERAL OTC ---
        ("Dolo 650 Tablet", "Pain & Fever Relief", "Paracetamol / Acetaminophen", "Dolo 650", "Micro Labs", "650mg", "Tablet", "Antipyretic and analgesic for fever and body aches.", 0),
        ("Paracetamol 500mg (Crocin Advance)", "Pain & Fever Relief", "Paracetamol / Acetaminophen", "Crocin Advance", "GSK India", "500mg", "Tablet", "Fast-acting analgesic and fever reducer.", 0),
        ("Combiflam Tablet", "Pain & Fever Relief", "Ibuprofen 400mg + Paracetamol 325mg", "Combiflam", "Sanofi India", "400mg/325mg", "Tablet", "Non-steroidal anti-inflammatory and pain relief.", 0),
        ("Meftal Spas Tablet", "Pain & Fever Relief", "Mefenamic Acid 250mg + Dicyclomine 10mg", "Meftal Spas", "Blue Cross Labs", "250mg/10mg", "Tablet", "Antispasmodic and analgesic for abdominal cramps.", 1),
        ("Cetirizine 10mg (Cetzine)", "Cold & Allergy", "Cetirizine Hydrochloride", "Cetzine", "Dr. Reddy's Laboratories", "10mg", "Tablet", "Antihistamine for runny nose, sneezing, and allergy symptoms.", 0),
        ("Levocetirizine 5mg (Levocet)", "Cold & Allergy", "Levocetirizine Dihydrochloride", "Levocet", "Glenmark Pharmaceuticals", "5mg", "Tablet", "Second-generation antihistamine for allergy relief.", 0),
        ("Allegra 120mg Tablet", "Cold & Allergy", "Fexofenadine Hydrochloride", "Allegra 120", "Sanofi India", "120mg", "Tablet", "Non-drowsy antihistamine for seasonal allergic rhinitis.", 1),
        ("Benadryl Cough Syrup 100ml", "Cough & Cold Syrups", "Diphenhydramine Hydrochloride", "Benadryl", "Johnson & Johnson", "100ml", "Syrup", "Cough syrup for throat irritation and dry cough.", 0),
        ("Ascoril D Plus Syrup 100ml", "Cough & Cold Syrups", "Dextromethorphan + Phenylephrine + CPM", "Ascoril D Plus", "Glenmark Pharmaceuticals", "100ml", "Syrup", "Cough suppressant and decongestant formulation.", 1),
        ("Sinarest Tablet", "Cold & Allergy", "Paracetamol + Phenylephrine + Chlorpheniramine", "Sinarest", "Centaur Pharma", "Standard", "Tablet", "Decongestant and antipyretic for cold and flu symptoms.", 0),
        ("Pan D Capsule", "Acidity & Digestion", "Pantoprazole 40mg + Domperidone 30mg", "Pan D", "Alkem Laboratories", "40mg/30mg", "Capsule", "Antacid and prokinetic for gastroesophageal reflux.", 1),
        ("Omez 20mg Capsule", "Acidity & Digestion", "Omeprazole", "Omez 20", "Dr. Reddy's Laboratories", "20mg", "Capsule", "Proton pump inhibitor for heartburn and acidity.", 1),
        ("Digene Gel Antacid Liquid 200ml", "Acidity & Digestion", "Magnesium Hydroxide + Aluminium Hydroxide + Simethicone", "Digene Gel Mint", "Abbott Healthcare", "200ml", "Liquid Gel", "Soothing antacid for rapid relief from heartburn.", 0),
        ("Gelusil MPS Liquid 200ml", "Acidity & Digestion", "Aluminium Hydroxide + Magnesium Hydroxide + Dimethicone", "Gelusil MPS", "Pfizer India", "200ml", "Liquid", "Antacid with antiflatulent action.", 0),
        ("Eno Fruit Salt Regular Lemon 5g", "Acidity & Digestion", "Sodium Bicarbonate + Citric Acid", "Eno Regular Lemon", "GSK India", "5g", "Sachet/Powder", "Effervescent instant antacid.", 0),
        ("ORS Electral 21.8g Sachet", "Acidity & Digestion", "WHO Oral Rehydration Salts", "Electral", "FDC Ltd", "21.8g", "Sachet", "Oral electrolyte rehydration formula.", 0),
        ("Shelcal 500 Tablet", "Vitamins & Supplements", "Calcium Carbonate 500mg + Vitamin D3 250IU", "Shelcal 500", "Torrent Pharmaceuticals", "500mg", "Tablet", "Calcium and vitamin D3 nutritional supplement.", 0),
        ("Becosules Z Capsule", "Vitamins & Supplements", "Vitamin B-Complex + Vitamin C + Zinc", "Becosules Z", "Pfizer India", "Standard", "Capsule", "Essential B-complex vitamins with zinc.", 0),
        ("Limcee 500mg Chewable Tablet", "Vitamins & Supplements", "Ascorbic Acid (Vitamin C)", "Limcee 500", "Abbott Healthcare", "500mg", "Chewable Tablet", "Vitamin C antioxidant supplement.", 0),
        ("Neurobion Forte Tablet", "Vitamins & Supplements", "Mecobalamin + Pyridoxine + Nicotinamide", "Neurobion Forte", "Procter & Gamble Health", "Standard", "Tablet", "B-vitamin neurotropic support formula.", 0),
        ("Zincovit Tablet", "Vitamins & Supplements", "Multivitamins and Essential Minerals + Zinc", "Zincovit", "Apex Laboratories", "Standard", "Tablet", "Comprehensive daily multivitamin with zinc.", 0),
        ("Augmentin 625 Duo Tablet", "Antibiotics", "Amoxicillin 500mg + Potassium Clavulanate 125mg", "Augmentin 625 Duo", "GSK India", "625mg", "Tablet", "Broad-spectrum penicillin antibiotic with beta-lactamase inhibitor.", 1),
        ("Azithral 500mg Tablet", "Antibiotics", "Azithromycin", "Azithral 500", "Alembic Pharmaceuticals", "500mg", "Tablet", "Macrolide antibiotic for bacterial infections.", 1),
        ("Taxim O 200mg Tablet", "Antibiotics", "Cefixime", "Taxim O 200", "Alkem Laboratories", "200mg", "Tablet", "Third-generation cephalosporin oral antibiotic.", 1),
        ("Ciplox 500mg Tablet", "Antibiotics", "Ciprofloxacin Hydrochloride", "Ciplox 500", "Cipla Ltd", "500mg", "Tablet", "Fluoroquinolone broad-spectrum antibacterial agent.", 1)
    ]

    medicine_ids = []
    for med in medicines_seed:
        name, cat, generic, brand, mfg, strength, form, desc, rx = med
        cursor.execute("""
        INSERT INTO medicines (name, category, generic_name, brand_name, manufacturer, strength, form, description, prescription_required)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, cat, generic, brand, mfg, strength, form, desc, rx))
        medicine_ids.append(cursor.lastrowid)

    # 4. SEED REALISTIC DEMO INVENTORIES WITH VARYING STOCK & PRICES
    import random
    random.seed(42) # Deterministic for consistent test assertions

    # Base price guidelines per category
    price_ranges = {
        "Blood Pressure & Hypertension": (25.0, 110.0),
        "Diabetes & Blood Sugar": (30.0, 240.0),
        "Heart & Cardiovascular": (20.0, 180.0),
        "Cholesterol & Lipids": (45.0, 160.0),
        "Thyroid Care": (40.0, 140.0),
        "Asthma & Respiratory": (85.0, 380.0),
        "Kidney Care": (35.0, 190.0),
        "Gastric & Acidity": (28.0, 125.0),
        "Arthritis & Joint Care": (50.0, 220.0),
        "Osteoporosis & Bone Health": (65.0, 195.0),
        "Migraine Care": (45.0, 180.0),
        "Epilepsy & Neurological": (70.0, 260.0),
        "Allergies & Skin Care": (35.0, 140.0),
        "Pain & Fever Relief": (15.0, 55.0),
        "Cold & Allergy": (18.0, 65.0),
        "Cough & Cold Syrups": (65.0, 135.0),
        "Acidity & Digestion": (20.0, 95.0),
        "Vitamins & Supplements": (25.0, 110.0),
        "Antibiotics": (85.0, 240.0)
    }

    dates = ["2026-08-31", "2026-11-30", "2027-03-31", "2027-06-30", "2027-12-31"]
    now_ts = "2026-09-27 10:00:00"

    for p_idx, p_id in enumerate(pharmacy_ids):
        # Each pharmacy stocks 70% to 90% of medicines, with different quantities and prices
        for m_idx, m_id in enumerate(medicine_ids):
            # Deterministic selection so every city has good coverage of chronic & acute medicines
            stock_decision = (p_idx * 7 + m_idx * 13) % 100
            
            # Key essentials (Metformin, Amlodipine, Telmisartan, Paracetamol, Dolo, Atorvastatin, Levothyroxine, Salbutamol)
            # are stocked in virtually every pharmacy
            is_essential = m_idx in (0, 1, 2, 15, 16, 26, 27, 33, 34, 38, 41, 71, 72)
            
            if stock_decision < 75 or is_essential:
                cat = medicines_seed[m_idx][1]
                p_min, p_max = price_ranges.get(cat, (20.0, 100.0))
                # Base price + slight pharmacy-specific variation (+/- 10%)
                var = ((p_idx * 3 + m_idx * 5) % 15) - 7
                base_calc = (p_min + p_max) / 2.0
                price = round(max(5.0, base_calc + var * 1.5), 2)

                # Quantity variation: some available (>10), some low stock (1-10), some out of stock (0)
                qty_seed = (p_idx * 11 + m_idx * 17) % 60
                if qty_seed < 5:
                    quantity = 0 # Out of stock
                elif qty_seed < 15:
                    quantity = (qty_seed % 8) + 1 # Low stock 1-8
                else:
                    quantity = 15 + (qty_seed % 40) # Healthy stock 15-54

                expiry = dates[(p_idx + m_idx) % len(dates)]

                cursor.execute("""
                INSERT INTO inventory (pharmacy_id, medicine_id, price, quantity, expiry_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(pharmacy_id, medicine_id) DO UPDATE SET
                    price = excluded.price,
                    quantity = excluded.quantity,
                    expiry_date = excluded.expiry_date,
                    last_updated = excluded.last_updated
                """, (p_id, m_id, price, quantity, expiry, now_ts))

    conn.commit()
    conn.close()
    print("Database initialization and chronic catalog demo seeding complete.")

if __name__ == '__main__':
    init_db()
    seed_demo_data()
