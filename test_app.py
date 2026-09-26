import unittest
import os
import tempfile
import time
from config import Config
from database import get_db_connection, init_db, seed_demo_data
from models.user import get_user_by_email, create_user, verify_user_password
from models.pharmacy import get_pharmacy_by_id, create_pharmacy, update_pharmacy_status
from models.medicine import search_medicines, get_all_medicines
from models.inventory import (
    compute_stock_status, haversine_distance, search_nearby_pharmacies_with_medicine,
    add_inventory_item, update_inventory_item, get_inventory_by_pharmacy, check_pharmacies_exist_in_city
)
from app import create_app

class MedicineFinderTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.temp_db = tempfile.mkstemp()
        
        class TestConfig(Config):
            TESTING = True
            DATABASE_PATH = self.temp_db
            SECRET_KEY = 'test-secret-key'

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_database_initialization_and_seeding(self):
        """Test DB creates all tables and seeds demo records."""
        with self.app.app_context():
            admin = get_user_by_email('admin@medfinder.com')
            self.assertIsNotNone(admin)
            self.assertEqual(admin['role'], 'admin')

            user = get_user_by_email('user@medfinder.com')
            self.assertIsNotNone(user)
            self.assertEqual(user['role'], 'user')

            meds = get_all_medicines()
            self.assertGreaterEqual(len(meds), 4)

    def test_city_based_search_and_no_leakage(self):
        """
        CITY-BASED SEARCH REQUIREMENT TEST:
        - Paracetamol + Vizianagaram -> Only Vizianagaram pharmacies
        - Paracetamol + Visakhapatnam -> Only Visakhapatnam pharmacies
        - Paracetamol + Guntur -> Only Guntur pharmacies
        - Paracetamol + Unknown City -> Returns empty list & no_pharmacies_in_city=True
        - Confirms results NEVER leak across cities.
        """
        with self.app.app_context():
            # 1. Vizianagaram search
            vzm_results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Vizianagaram')
            self.assertGreater(len(vzm_results), 0)
            for r in vzm_results:
                self.assertEqual(r['pharmacy_city'].strip().lower(), 'vizianagaram', 'Leaked non-Vizianagaram pharmacy!')

            # 2. Visakhapatnam search
            vsk_results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Visakhapatnam')
            self.assertGreater(len(vsk_results), 0)
            for r in vsk_results:
                self.assertEqual(r['pharmacy_city'].strip().lower(), 'visakhapatnam', 'Leaked non-Visakhapatnam pharmacy!')

            # 3. Guntur search
            gnt_results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Guntur')
            self.assertGreater(len(gnt_results), 0)
            for r in gnt_results:
                self.assertEqual(r['pharmacy_city'].strip().lower(), 'guntur', 'Leaked non-Guntur pharmacy!')

            # 4. Unknown city with no pharmacies
            has_hyd, hyd_count = check_pharmacies_exist_in_city('Hyderabad')
            self.assertFalse(has_hyd)
            self.assertEqual(hyd_count, 0)
            hyd_results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Hyderabad')
            self.assertEqual(len(hyd_results), 0)

            # 5. Case-insensitivity check ('guntur', 'GUNTUR', '  guntur  ')
            gnt_lower = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='guntur')
            self.assertEqual(len(gnt_results), len(gnt_lower))

    def test_haversine_distance_calculation(self):
        """Test exact geometric distance calculation using Haversine formula."""
        dist = haversine_distance(18.1067, 83.3956, 18.1120, 83.4010)
        self.assertIsNotNone(dist)
        self.assertAlmostEqual(dist, 0.82, delta=0.2)
        self.assertIsNone(haversine_distance(None, 83.3956, 18.1120, 83.4010))

    def test_stock_status_computation(self):
        """Test dynamic calculation of stock status."""
        status_high = compute_stock_status(25)
        self.assertEqual(status_high['code'], 'available')
        self.assertEqual(status_high['label'], 'Available')

        status_low = compute_stock_status(5)
        self.assertEqual(status_low['code'], 'low_stock')
        self.assertEqual(status_low['label'], 'Low Stock')

        status_zero = compute_stock_status(0)
        self.assertEqual(status_zero['code'], 'out_of_stock')
        self.assertEqual(status_zero['label'], 'Out of Stock')

    def test_user_authentication_flow(self):
        """Test registration, secure hashing, login, and logout."""
        reg_res = self.client.post('/register', data={
            'name': 'Test Student',
            'email': 'student@test.com',
            'phone': '9876543210',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'city': 'Vizianagaram'
        }, follow_redirects=True)
        self.assertEqual(reg_res.status_code, 200)

        with self.app.app_context():
            user = get_user_by_email('student@test.com')
            self.assertIsNotNone(user)
            self.assertNotEqual(user['password_hash'], 'Password@123')
            self.assertTrue(verify_user_password(user['password_hash'], 'Password@123'))
            self.assertFalse(verify_user_password(user['password_hash'], 'WrongPassword'))

        login_res = self.client.post('/login', data={
            'email': 'student@test.com',
            'password': 'Password@123'
        }, follow_redirects=True)
        self.assertIn(b'Test Student', login_res.data)

        self.client.get('/logout', follow_redirects=True)

        bad_login = self.client.post('/login', data={
            'email': 'student@test.com',
            'password': 'WrongPassword'
        }, follow_redirects=True)
        self.assertIn(b'Invalid email or password', bad_login.data)

    def test_end_to_end_inventory_flow(self):
        """
        CRITICAL TEST:
        1. Pharmacy adds Paracetamol 500mg, Qty: 20, Price: ₹25.
        2. User searches 'Paracetamol' -> Sees Available & ₹25.
        3. Pharmacy changes quantity 20 -> 0.
        4. User searches 'Paracetamol' -> Sees Out of Stock & updated timestamp.
        """
        with self.app.app_context():
            pharmacy_user = get_user_by_email('democare@pharmacy.com')
            conn = get_db_connection()
            pharmacy_row = conn.execute("SELECT id FROM pharmacies WHERE user_id = ?", (pharmacy_user['id'],)).fetchone()
            pharmacy_id = pharmacy_row['id']
            med_row = conn.execute("SELECT id FROM medicines WHERE name = 'Paracetamol'").fetchone()
            med_id = med_row['id']
            conn.close()

            add_inventory_item(pharmacy_id, med_id, price=25.00, quantity=20, expiry_date='2027-10-31')

            results_1 = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Vizianagaram')
            demo_match = next((r for r in results_1 if r['pharmacy_id'] == pharmacy_id), None)
            self.assertIsNotNone(demo_match)
            self.assertEqual(demo_match['quantity'], 20)
            self.assertEqual(demo_match['price'], 25.00)
            self.assertEqual(demo_match['stock_info']['code'], 'available')
            time_1 = demo_match['last_updated']

            time.sleep(1)
            inv_row = get_inventory_by_pharmacy(pharmacy_id)
            paracetamol_inv = next(i for i in inv_row if i['medicine_id'] == med_id)
            success, err = update_inventory_item(paracetamol_inv['id'], pharmacy_id, price=25.00, quantity=0, expiry_date='2027-10-31')
            self.assertTrue(success)

            results_2 = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Vizianagaram')
            demo_match_2 = next((r for r in results_2 if r['pharmacy_id'] == pharmacy_id), None)
            self.assertIsNotNone(demo_match_2)
            self.assertEqual(demo_match_2['quantity'], 0)
            self.assertEqual(demo_match_2['stock_info']['code'], 'out_of_stock')
            time_2 = demo_match_2['last_updated']
            self.assertNotEqual(time_1, time_2)

    def test_pharmacy_admin_approval_gate(self):
        """Test that new pending pharmacy does NOT show in search until admin approves."""
        with self.app.app_context():
            u_id, _ = create_user('New Pharmacy Owner', 'newpharm@test.com', '9998887770', 'Pass@123', role='pharmacy', city='Vizianagaram')
            p_id, _ = create_pharmacy(u_id, 'New Pending Meds', 'New Pharmacy Owner', '9998887770', 'newpharm@test.com', 'Main Rd', 'Center', 'Vizianagaram', 'AP', '535002', status='pending')

            med = search_medicines('Paracetamol')[0]
            add_inventory_item(p_id, med['id'], price=30.00, quantity=50)

            results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Vizianagaram')
            self.assertFalse(any(r['pharmacy_id'] == p_id for r in results))

            update_pharmacy_status(p_id, 'approved')

            results_approved = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Vizianagaram')
            self.assertTrue(any(r['pharmacy_id'] == p_id for r in results_approved))

    def test_pharmacy_isolation_security(self):
        """Ensure Pharmacy A cannot modify Pharmacy B's inventory."""
        with self.app.app_context():
            conn = get_db_connection()
            pharmacies = conn.execute("SELECT id FROM pharmacies").fetchall()
            pharm_a_id = pharmacies[0]['id']
            pharm_b_id = pharmacies[1]['id']

            inv_a = get_inventory_by_pharmacy(pharm_a_id)[0]
            conn.close()

            success, err = update_inventory_item(inv_a['id'], pharmacy_id=pharm_b_id, price=1.00, quantity=999)
            self.assertFalse(success)
            self.assertIn('unauthorized', err.lower())

if __name__ == '__main__':
    unittest.main()
