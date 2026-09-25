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
    add_inventory_item, update_inventory_item, get_inventory_by_pharmacy
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

    def test_haversine_distance_calculation(self):
        """Test exact geometric distance calculation using Haversine formula."""
        # Vizianagaram (18.1067, 83.3956) to Cantonment (18.1120, 83.4010) ~ 0.82 km
        dist = haversine_distance(18.1067, 83.3956, 18.1120, 83.4010)
        self.assertIsNotNone(dist)
        self.assertAlmostEqual(dist, 0.82, delta=0.2)

        # None handling
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
        # Register new user
        reg_res = self.client.post('/register', data={
            'name': 'Test Student',
            'email': 'student@test.com',
            'phone': '9876543210',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'city': 'Vizianagaram'
        }, follow_redirects=True)
        self.assertEqual(reg_res.status_code, 200)

        # Verify password is encrypted in database
        with self.app.app_context():
            user = get_user_by_email('student@test.com')
            self.assertIsNotNone(user)
            self.assertNotEqual(user['password_hash'], 'Password@123')
            self.assertTrue(verify_user_password(user['password_hash'], 'Password@123'))
            self.assertFalse(verify_user_password(user['password_hash'], 'WrongPassword'))

        # Login with valid credentials
        login_res = self.client.post('/login', data={
            'email': 'student@test.com',
            'password': 'Password@123'
        }, follow_redirects=True)
        self.assertIn(b'Test Student', login_res.data)

        # Logout
        self.client.get('/logout', follow_redirects=True)

        # Login with invalid credentials
        bad_login = self.client.post('/login', data={
            'email': 'student@test.com',
            'password': 'WrongPassword'
        }, follow_redirects=True)
        self.assertIn(b'Invalid email or password', bad_login.data)

    def test_end_to_end_inventory_flow(self):
        """
        CRITICAL TEST (Problem 20 & 42):
        1. Pharmacy adds Paracetamol 500mg, Qty: 20, Price: ₹25.
        2. User searches 'Paracetamol' -> Sees Available & ₹25.
        3. Pharmacy changes quantity 20 -> 0.
        4. User searches 'Paracetamol' -> Sees Out of Stock & updated timestamp.
        """
        with self.app.app_context():
            # Step 1: Pharmacy Democare (id 1)
            pharmacy_user = get_user_by_email('democare@pharmacy.com')
            conn = get_db_connection()
            pharmacy_row = conn.execute("SELECT id FROM pharmacies WHERE user_id = ?", (pharmacy_user['id'],)).fetchone()
            pharmacy_id = pharmacy_row['id']
            med_row = conn.execute("SELECT id FROM medicines WHERE name = 'Paracetamol'").fetchone()
            med_id = med_row['id']
            conn.close()

            # Set initial stock: Qty 20, Price 25.00
            add_inventory_item(pharmacy_id, med_id, price=25.00, quantity=20, expiry_date='2027-10-31')

            # Step 2: Search Paracetamol from user perspective
            results_1 = search_nearby_pharmacies_with_medicine('Paracetamol')
            demo_match = next((r for r in results_1 if r['pharmacy_id'] == pharmacy_id), None)
            self.assertIsNotNone(demo_match)
            self.assertEqual(demo_match['quantity'], 20)
            self.assertEqual(demo_match['price'], 25.00)
            self.assertEqual(demo_match['stock_info']['code'], 'available')
            time_1 = demo_match['last_updated']

            # Step 3: Pharmacy changes quantity 20 -> 0
            time.sleep(1) # Ensure timestamp tick
            inv_row = get_inventory_by_pharmacy(pharmacy_id)
            paracetamol_inv = next(i for i in inv_row if i['medicine_id'] == med_id)
            success, err = update_inventory_item(paracetamol_inv['id'], pharmacy_id, price=25.00, quantity=0, expiry_date='2027-10-31')
            self.assertTrue(success)

            # Step 4: User searches Paracetamol again
            results_2 = search_nearby_pharmacies_with_medicine('Paracetamol')
            demo_match_2 = next((r for r in results_2 if r['pharmacy_id'] == pharmacy_id), None)
            self.assertIsNotNone(demo_match_2)
            self.assertEqual(demo_match_2['quantity'], 0)
            self.assertEqual(demo_match_2['stock_info']['code'], 'out_of_stock')
            time_2 = demo_match_2['last_updated']
            self.assertNotEqual(time_1, time_2, "Last updated timestamp must be refreshed on change")

    def test_pharmacy_admin_approval_gate(self):
        """Test that new pending pharmacy does NOT show in search until admin approves."""
        with self.app.app_context():
            # Create user and pending pharmacy
            u_id, _ = create_user('New Pharmacy Owner', 'newpharm@test.com', '9998887770', 'Pass@123', role='pharmacy', city='Vizianagaram')
            p_id, _ = create_pharmacy(u_id, 'New Pending Meds', 'New Pharmacy Owner', '9998887770', 'newpharm@test.com', 'Main Rd', 'Center', 'Vizianagaram', 'AP', '535002', status='pending')

            # Add medicine to its inventory
            med = search_medicines('Paracetamol')[0]
            add_inventory_item(p_id, med['id'], price=30.00, quantity=50)

            # Search Paracetamol -> New Pending Meds should NOT appear
            results = search_nearby_pharmacies_with_medicine('Paracetamol')
            self.assertFalse(any(r['pharmacy_id'] == p_id for r in results))

            # Admin approves pharmacy
            update_pharmacy_status(p_id, 'approved')

            # Search Paracetamol again -> New Pending Meds SHOULD appear now
            results_approved = search_nearby_pharmacies_with_medicine('Paracetamol')
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

            # Attempt Pharmacy B updating Pharmacy A's item
            success, err = update_inventory_item(inv_a['id'], pharmacy_id=pharm_b_id, price=1.00, quantity=999)
            self.assertFalse(success)
            self.assertIn('unauthorized', err.lower())

if __name__ == '__main__':
    unittest.main()
