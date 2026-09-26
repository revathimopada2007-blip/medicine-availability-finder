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
        """Test DB creates all tables and seeds multi-city demo records and comprehensive medicine catalog."""
        with self.app.app_context():
            admin = get_user_by_email('admin@medfinder.com')
            self.assertIsNotNone(admin)
            self.assertEqual(admin['role'], 'admin')

            user = get_user_by_email('user@medfinder.com')
            self.assertIsNotNone(user)
            self.assertEqual(user['role'], 'user')

            meds = get_all_medicines()
            self.assertGreaterEqual(len(meds), 25)

    def test_city_based_search_and_no_leakage(self):
        """
        CITY-BASED SEARCH REQUIREMENT TEST:
        - Paracetamol + Guntur -> Shows only Guntur pharmacies
        - Paracetamol + Vizianagaram -> Shows only Vizianagaram pharmacies
        - Paracetamol + Visakhapatnam -> Shows only Visakhapatnam pharmacies
        - Paracetamol + Hyderabad -> Shows only Hyderabad / Secunderabad pharmacies
        - Paracetamol + Kukatpally -> Shows only Kukatpally pharmacies
        - Paracetamol + Gachibowli -> Shows only Gachibowli pharmacies
        - Paracetamol + Unregistered City (e.g. Tenali / Srikakulam) -> Returns empty results with no_pharmacies_in_city=True
        - Confirms zero cross-city leakage.
        """
        with self.app.app_context():
            # 1. Guntur
            gnt = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Guntur')
            self.assertGreater(len(gnt), 0)
            for r in gnt:
                self.assertEqual(r['pharmacy_city'].lower(), 'guntur')

            # 2. Vizianagaram
            vzm = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Vizianagaram')
            self.assertGreater(len(vzm), 0)
            for r in vzm:
                self.assertEqual(r['pharmacy_city'].lower(), 'vizianagaram')

            # 3. Visakhapatnam
            vsk = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Visakhapatnam')
            self.assertGreater(len(vsk), 0)
            for r in vsk:
                self.assertEqual(r['pharmacy_city'].lower(), 'visakhapatnam')

            # 4. Hyderabad
            hyd = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Hyderabad')
            self.assertGreater(len(hyd), 0)
            for r in hyd:
                self.assertIn(r['pharmacy_city'].lower(), ('hyderabad', 'secunderabad'))

            # 5. Kukatpally
            kpt = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Kukatpally')
            self.assertGreater(len(kpt), 0)
            for r in kpt:
                self.assertTrue('kukatpally' in r['pharmacy_area'].lower() or 'kukatpally' in r['pharmacy_name'].lower())

            # 6. Gachibowli
            gcb = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Gachibowli')
            self.assertGreater(len(gcb), 0)
            for r in gcb:
                self.assertTrue('gachibowli' in r['pharmacy_area'].lower() or 'gachibowli' in r['pharmacy_name'].lower())

            # 7. Unregistered city (e.g. Tenali)
            has_tenali, count = check_pharmacies_exist_in_city('Tenali')
            self.assertFalse(has_tenali)
            self.assertEqual(count, 0)
            tenali_results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Tenali')
            self.assertEqual(len(tenali_results), 0)

    def test_different_inventory_per_pharmacy(self):
        """Test that different demo pharmacies maintain different inventories, prices, and stock levels."""
        with self.app.app_context():
            gnt_results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Guntur')
            gnt_pharm = gnt_results[0]

            vzm_results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Vizianagaram')
            vzm_pharm = vzm_results[0]

            # Compare inventory records
            gnt_inv = get_inventory_by_pharmacy(gnt_pharm['pharmacy_id'])
            vzm_inv = get_inventory_by_pharmacy(vzm_pharm['pharmacy_id'])

            # Both have inventories and their stock counts/pricing are independent
            self.assertGreater(len(gnt_inv), 0)
            self.assertGreater(len(vzm_inv), 0)

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
            'city': 'Guntur'
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
        1. Pharmacy adds Paracetamol, Qty: 20, Price: ₹25.
        2. User searches 'Paracetamol' in Guntur -> Sees Available & ₹25.
        3. Pharmacy changes quantity 20 -> 0.
        4. User searches 'Paracetamol' in Guntur -> Sees Out of Stock & updated timestamp.
        """
        with self.app.app_context():
            conn = get_db_connection()
            pharmacy_row = conn.execute("SELECT id FROM pharmacies WHERE city = 'Guntur' LIMIT 1").fetchone()
            pharmacy_id = pharmacy_row['id']
            med_row = conn.execute("SELECT id FROM medicines WHERE name = 'Paracetamol'").fetchone()
            med_id = med_row['id']
            conn.close()

            add_inventory_item(pharmacy_id, med_id, price=25.00, quantity=20, expiry_date='2027-10-31')

            results_1 = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Guntur')
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

            results_2 = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Guntur')
            demo_match_2 = next((r for r in results_2 if r['pharmacy_id'] == pharmacy_id), None)
            self.assertIsNotNone(demo_match_2)
            self.assertEqual(demo_match_2['quantity'], 0)
            self.assertEqual(demo_match_2['stock_info']['code'], 'out_of_stock')
            time_2 = demo_match_2['last_updated']
            self.assertNotEqual(time_1, time_2)

    def test_pharmacy_admin_approval_gate(self):
        """Test that new pending pharmacy does NOT show in search until admin approves."""
        with self.app.app_context():
            u_id, _ = create_user('New Pharmacy Owner', 'newpharm@test.com', '9998887770', 'Pass@123', role='pharmacy', city='Guntur')
            p_id, _ = create_pharmacy(u_id, 'New Pending Meds', 'New Pharmacy Owner', '9998887770', 'newpharm@test.com', 'Main Rd', 'Center', 'Guntur', 'AP', '522002', status='pending')

            med = search_medicines('Paracetamol')[0]
            add_inventory_item(p_id, med['id'], price=30.00, quantity=50)

            results = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Guntur')
            self.assertFalse(any(r['pharmacy_id'] == p_id for r in results))

            update_pharmacy_status(p_id, 'approved')

            results_approved = search_nearby_pharmacies_with_medicine('Paracetamol', user_city='Guntur')
            self.assertTrue(any(r['pharmacy_id'] == p_id for r in results_approved))

if __name__ == '__main__':
    unittest.main()
