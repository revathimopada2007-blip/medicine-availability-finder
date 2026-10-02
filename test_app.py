import unittest
import os
import shutil
import tempfile
import sqlite3
import json
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
from models.pharmacy import search_locations

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
        self.assertGreaterEqual(med_count, 60)

        cursor.execute("SELECT count(*) FROM pharmacies")
        pharm_count = cursor.fetchone()[0]
        self.assertGreaterEqual(pharm_count, 20)

        cursor.execute("SELECT count(*) FROM inventory")
        inv_count = cursor.fetchone()[0]
        self.assertGreaterEqual(inv_count, 500)
        conn.close()

    def test_strict_medicine_autocomplete_prefix_matching(self):
        """
        STRICT PREFIX MATCHING TEST FOR MEDICINES:
        - Typing 'P' -> only medicines whose NAME starts with 'P'
        - Typing 'Pa' -> only medicines whose NAME starts with 'Pa'
        - Typing 'Par' -> Paracetamol (MUST NOT include Dolo 650, Sinarest, Combiflam)
        - Typing 'Met' -> Metformin, Metoprolol, Methotrexate
        - Typing 'Aml' -> Amlodipine
        - Typing 'Ator' -> Atorvastatin (MUST NOT include Bilastine or Budesonide)
        """
        with self.app.app_context():
            # 1. Test 'P'
            res_p = search_medicines("P")
            self.assertGreater(len(res_p), 0)
            for m in res_p:
                self.assertTrue(m['name'].lower().startswith('p'), f"'{m['name']}' does not start with 'P'")

            # 2. Test 'Pa'
            res_pa = search_medicines("Pa")
            self.assertGreater(len(res_pa), 0)
            for m in res_pa:
                self.assertTrue(m['name'].lower().startswith('pa'), f"'{m['name']}' does not start with 'Pa'")

            # 3. Test 'Par' -> Paracetamol ONLY
            res_par = search_medicines("Par")
            self.assertGreater(len(res_par), 0)
            names_par = [m['name'] for m in res_par]
            for name in names_par:
                self.assertTrue(name.lower().startswith('par'), f"'{name}' does not start with 'Par'")
            # Crucial assertion: no category bleed / unrelated medicines
            self.assertNotIn("Dolo 650 Tablet", names_par)
            self.assertNotIn("Sinarest Tablet", names_par)
            self.assertNotIn("Combiflam Tablet", names_par)

            # 4. Test 'Met'
            res_met = search_medicines("Met")
            self.assertGreater(len(res_met), 0)
            for m in res_met:
                self.assertTrue(m['name'].lower().startswith('met'), f"'{m['name']}' does not start with 'Met'")

            # 5. Test 'Aml'
            res_aml = search_medicines("Aml")
            self.assertGreater(len(res_aml), 0)
            for m in res_aml:
                self.assertTrue(m['name'].lower().startswith('aml'), f"'{m['name']}' does not start with 'Aml'")

            # 6. Test 'Ator' -> Atorvastatin ONLY
            res_ator = search_medicines("Ator")
            self.assertGreater(len(res_ator), 0)
            names_ator = [m['name'] for m in res_ator]
            for name in names_ator:
                self.assertTrue(name.lower().startswith('ator'), f"'{name}' does not start with 'Ator'")
            self.assertNotIn("Bilastine 20mg (Bilaxten 20)", names_ator)
            self.assertNotIn("Budesonide + Formoterol Inhaler (Foracort 200)", names_ator)

    def test_strict_location_autocomplete_prefix_matching(self):
        """
        STRICT PREFIX MATCHING TEST FOR LOCATIONS:
        - 'T' -> locations starting with T
        - 'Ti' -> Tirupati (MUST NOT contain Mayuri Junction or Kotipalli)
        - 'Vi' -> Vijayawada, Visakhapatnam, Vizianagaram
        - 'Gu' -> Guntur (MUST NOT contain Korlagunta)
        - 'Hy' -> Hyderabad
        """
        with self.app.app_context():
            # 1. Test 'T'
            res_t = search_locations("T")
            self.assertGreater(len(res_t), 0)
            for l in res_t:
                self.assertTrue(l['name'].lower().startswith('t'), f"Location '{l['name']}' does not start with 'T'")

            # 2. Test 'Ti' -> Tirupati
            res_ti = search_locations("Ti")
            self.assertGreater(len(res_ti), 0)
            names_ti = [l['name'] for l in res_ti]
            for name in names_ti:
                self.assertTrue(name.lower().startswith('ti'), f"Location '{name}' does not start with 'Ti'")
            self.assertNotIn("Mayuri Junction", names_ti)
            self.assertNotIn("Kotipalli Road", names_ti)

            # 3. Test 'Vi' -> Vijayawada, Visakhapatnam, Vizianagaram
            res_vi = search_locations("Vi")
            self.assertGreater(len(res_vi), 0)
            names_vi = [l['name'] for l in res_vi]
            for name in names_vi:
                self.assertTrue(name.lower().startswith('vi'), f"Location '{name}' does not start with 'Vi'")
            self.assertTrue(any(c in names_vi for c in ["Vijayawada", "Visakhapatnam", "Vizianagaram"]))

            # 4. Test 'Gu' -> Guntur (NO Korlagunta)
            res_gu = search_locations("Gu")
            self.assertGreater(len(res_gu), 0)
            names_gu = [l['name'] for l in res_gu]
            for name in names_gu:
                self.assertTrue(name.lower().startswith('gu'), f"Location '{name}' does not start with 'Gu'")
            self.assertIn("Guntur", names_gu)
            self.assertNotIn("Korlagunta", names_gu)

            # 5. Test 'Hy' -> Hyderabad
            res_hy = search_locations("Hy")
            self.assertGreater(len(res_hy), 0)
            names_hy = [l['name'] for l in res_hy]
            for name in names_hy:
                self.assertTrue(name.lower().startswith('hy'), f"Location '{name}' does not start with 'Hy'")
            self.assertIn("Hyderabad", names_hy)

    def test_city_specific_search_and_no_leakage(self):
        """Test city search zero-leakage behavior."""
        with self.app.app_context():
            par_guntur = search_nearby_pharmacies_with_medicine("Paracetamol", user_city="Guntur")
            self.assertGreater(len(par_guntur), 0)
            for item in par_guntur:
                self.assertEqual(item['pharmacy_city'].lower(), 'guntur')

            par_vzm = search_nearby_pharmacies_with_medicine("Paracetamol", user_city="Vizianagaram")
            self.assertGreater(len(par_vzm), 0)
            for item in par_vzm:
                self.assertEqual(item['pharmacy_city'].lower(), 'vizianagaram')

            par_vizag = search_nearby_pharmacies_with_medicine("Paracetamol", user_city="Visakhapatnam")
            self.assertGreater(len(par_vizag), 0)
            for item in par_vizag:
                self.assertEqual(item['pharmacy_city'].lower(), 'visakhapatnam')

            met_guntur = search_nearby_pharmacies_with_medicine("Metformin", user_city="Guntur")
            self.assertGreater(len(met_guntur), 0)
            for item in met_guntur:
                self.assertEqual(item['pharmacy_city'].lower(), 'guntur')

            amlo_hyd = search_nearby_pharmacies_with_medicine("Amlodipine", user_city="Hyderabad")
            self.assertGreater(len(amlo_hyd), 0)
            for item in amlo_hyd:
                self.assertIn(item['pharmacy_city'].lower(), ['hyderabad', 'secunderabad'])

            ator_vja = search_nearby_pharmacies_with_medicine("Atorvastatin", user_city="Vijayawada")
            self.assertGreater(len(ator_vja), 0)
            for item in ator_vja:
                self.assertEqual(item['pharmacy_city'].lower(), 'vijayawada')

    def test_unregistered_and_new_city_handling(self):
        """Test empty state message for unregistered city."""
        response = self.client.get('/search?q=Paracetamol&city=Tenali')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No Participating Pharmacies Found", response.data)
        self.assertIn(b"There are currently no pharmacies registered with Medicine Availability Finder in", response.data)

    def test_chronic_condition_categories_and_rx_marking(self):
        """Test chronic categories and Rx status."""
        with self.app.app_context():
            bp_results = search_nearby_pharmacies_with_medicine("Amlodipine")
            self.assertGreater(len(bp_results), 0)
            self.assertEqual(bp_results[0]['prescription_required'], 1)

    def test_haversine_distance_calculation(self):
        """Test Haversine formula distance."""
        d = haversine_distance(16.3067, 80.4365, 16.3120, 80.4420)
        self.assertIsNotNone(d)
        self.assertAlmostEqual(d, 0.84, delta=0.2)

    def test_end_to_end_inventory_flow(self):
        """Test inventory CRUD operations."""
        with self.app.app_context():
            inv_id, err = add_inventory_item(pharmacy_id=1, medicine_id=5, price=88.50, quantity=35)
            self.assertIsNone(err)
            self.assertIsNotNone(inv_id)

            success, err = update_inventory_item(inv_id, pharmacy_id=1, price=92.00, quantity=8)
            self.assertTrue(success)

            success, err = delete_inventory_item(inv_id, pharmacy_id=1)
            self.assertTrue(success)

    def test_stock_status_computation(self):
        """Test stock computation."""
        self.assertEqual(compute_stock_status(15)['code'], 'available')
        self.assertEqual(compute_stock_status(5)['code'], 'low_stock')
        self.assertEqual(compute_stock_status(0)['code'], 'out_of_stock')

if __name__ == '__main__':
    unittest.main()
