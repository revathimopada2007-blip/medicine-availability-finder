import unittest
import os
import shutil
import tempfile
import sqlite3
from app import create_app
from database import init_db, seed_demo_data, get_db_connection
from models.inventory import (
    search_nearby_pharmacies_with_medicine, 
    haversine_distance, 
    compute_stock_status,
    add_inventory_item,
    update_inventory_item,
    delete_inventory_item,
    check_pharmacies_exist_in_city
)
from models.medicine import search_medicines

class MedicineFinderTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.environ['DATABASE_PATH'] = self.temp_db_path
        
        self.app = create_app()
        self.app.config['DATABASE_PATH'] = self.temp_db_path
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            init_db(self.temp_db_path)
            seed_demo_data(self.temp_db_path)

    def tearDown(self):
        os.close(self.db_fd)
        try:
            os.unlink(self.temp_db_path)
        except Exception:
            pass

    def test_database_initialization_and_seeding(self):
        """Test DB creates all tables and seeds chronic catalog and multi-city demo records."""
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT count(*) FROM medicines")
        med_count = cursor.fetchone()[0]
        self.assertGreaterEqual(med_count, 60, "Should have expanded catalog with chronic condition medicines")

        cursor.execute("SELECT count(*) FROM pharmacies")
        pharm_count = cursor.fetchone()[0]
        self.assertGreaterEqual(pharm_count, 20, "Should have seeded multi-city demo pharmacies")

        cursor.execute("SELECT count(*) FROM inventory")
        inv_count = cursor.fetchone()[0]
        self.assertGreaterEqual(inv_count, 500, "Should have populated pharmacy inventories")
        conn.close()

    def test_chronic_condition_categories_and_rx_marking(self):
        """Test that chronic condition medicines (BP, Diabetes, Heart, Thyroid, Asthma) are seeded and marked Rx."""
        with self.app.app_context():
            # Test BP medicine
            bp_results = search_nearby_pharmacies_with_medicine("Amlodipine")
            self.assertGreater(len(bp_results), 0)
            self.assertEqual(bp_results[0]['prescription_required'], 1)
            self.assertEqual(bp_results[0]['medicine_category'], 'Blood Pressure & Hypertension')

            # Test Diabetes medicine
            diab_results = search_nearby_pharmacies_with_medicine("Metformin")
            self.assertGreater(len(diab_results), 0)
            self.assertEqual(diab_results[0]['prescription_required'], 1)
            self.assertEqual(diab_results[0]['medicine_category'], 'Diabetes & Blood Sugar')

            # Test Heart medicine
            heart_results = search_nearby_pharmacies_with_medicine("Clopidogrel")
            self.assertGreater(len(heart_results), 0)
            self.assertEqual(heart_results[0]['prescription_required'], 1)

            # Test Thyroid medicine
            thyroid_results = search_nearby_pharmacies_with_medicine("Levothyroxine")
            self.assertGreater(len(thyroid_results), 0)
            self.assertEqual(thyroid_results[0]['prescription_required'], 1)

            # Test Asthma inhaler
            asthma_results = search_nearby_pharmacies_with_medicine("Salbutamol")
            self.assertGreater(len(asthma_results), 0)
            self.assertEqual(asthma_results[0]['prescription_required'], 1)

    def test_city_based_search_and_no_leakage(self):
        """CITY-BASED SEARCH REQUIREMENT: Metformin in Guntur must ONLY return Guntur pharmacies, not Hyderabad or Vizianagaram."""
        with self.app.app_context():
            # 1. Search Metformin in Guntur
            guntur_res = search_nearby_pharmacies_with_medicine("Metformin", user_city="Guntur")
            self.assertGreater(len(guntur_res), 0, "Guntur should have Metformin")
            for item in guntur_res:
                self.assertEqual(item['pharmacy_city'].lower(), 'guntur', f"Expected Guntur, got {item['pharmacy_city']}")

            # 2. Search Amlodipine in Hyderabad
            hyd_res = search_nearby_pharmacies_with_medicine("Amlodipine", user_city="Hyderabad")
            self.assertGreater(len(hyd_res), 0, "Hyderabad should have Amlodipine")
            for item in hyd_res:
                self.assertIn(item['pharmacy_city'].lower(), ['hyderabad', 'secunderabad'])

            # 3. Search Telmisartan in Vizianagaram
            vzm_res = search_nearby_pharmacies_with_medicine("Telmisartan", user_city="Vizianagaram")
            self.assertGreater(len(vzm_res), 0, "Vizianagaram should have Telmisartan")
            for item in vzm_res:
                self.assertEqual(item['pharmacy_city'].lower(), 'vizianagaram')

            # 4. Check city with NO participating pharmacies (e.g. Tenali)
            has_pharmacies, count = check_pharmacies_exist_in_city("Tenali")
            self.assertFalse(has_pharmacies)
            self.assertEqual(count, 0)

    def test_empty_city_ui_message(self):
        """Test that searching in a city without registered pharmacies shows the required empty message."""
        response = self.client.get('/search?q=Metformin&city=Tenali')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No Participating Pharmacies Found", response.data)
        self.assertIn(b"There are currently no pharmacies registered with Medicine Availability Finder in", response.data)

    def test_safety_disclaimer_rendered(self):
        """Test that the safety disclaimer is present in the search results and details page."""
        response = self.client.get('/search?q=Metformin')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Medicine Availability Finder provides availability information only.", response.data)
        self.assertIn(b"Prescription medicines should be used only under the guidance of a qualified healthcare professional.", response.data)

    def test_haversine_distance_calculation(self):
        """Test exact geometric distance calculation using Haversine formula."""
        # Distance from Brodipet Guntur (16.3067, 80.4365) to Arundalpet Guntur (16.3120, 80.4420) ~ 0.84 km
        d = haversine_distance(16.3067, 80.4365, 16.3120, 80.4420)
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 0.84, delta=0.2)

    def test_end_to_end_inventory_flow(self):
        """Test creating, updating, and deleting inventory items."""
        with self.app.app_context():
            inv_id, err = add_inventory_item(pharmacy_id=1, medicine_id=5, price=88.50, quantity=35)
            self.assertIsNone(err)
            self.assertIsNotNone(inv_id)

            success, err = update_inventory_item(inv_id, pharmacy_id=1, price=92.00, quantity=8)
            self.assertTrue(success)

            success, err = delete_inventory_item(inv_id, pharmacy_id=1)
            self.assertTrue(success)

    def test_stock_status_computation(self):
        """Test dynamic calculation of stock status."""
        self.assertEqual(compute_stock_status(15)['code'], 'available')
        self.assertEqual(compute_stock_status(5)['code'], 'low_stock')
        self.assertEqual(compute_stock_status(0)['code'], 'out_of_stock')

if __name__ == '__main__':
    unittest.main()
