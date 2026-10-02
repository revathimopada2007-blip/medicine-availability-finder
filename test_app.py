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
        self.assertGreaterEqual(med_count, 60, "Should have expanded catalog with chronic condition medicines")

        cursor.execute("SELECT count(*) FROM pharmacies")
        pharm_count = cursor.fetchone()[0]
        self.assertGreaterEqual(pharm_count, 20, "Should have seeded multi-city demo pharmacies")

        cursor.execute("SELECT count(*) FROM inventory")
        inv_count = cursor.fetchone()[0]
        self.assertGreaterEqual(inv_count, 500, "Should have populated pharmacy inventories")
        conn.close()

    def test_medicine_autocomplete(self):
        """
        REQUIREMENT 1: Test medicine autocomplete suggestions using:
        P, Pa, Par, Met, Aml, Ator (and no match case).
        """
        with self.app.app_context():
            # Test prefix 'P'
            res_p = search_medicines("P")
            self.assertGreater(len(res_p), 0)
            names_p = [m['name'] for m in res_p]
            self.assertTrue(any("Paracetamol" in n or "Pantocid" in n or "Pan" in n or "PTU" in n or "Pioz" in n for n in names_p))

            # Test prefix 'Pa'
            res_pa = search_medicines("Pa")
            self.assertGreater(len(res_pa), 0)
            names_pa = [m['name'] for m in res_pa]
            self.assertTrue(any("Paracetamol" in n or "Pantocid" in n or "Pan" in n for n in names_pa))

            # Test prefix 'Par' -> Paracetamol
            res_par = search_medicines("Par")
            self.assertGreater(len(res_par), 0)
            names_par = [m['name'] for m in res_par]
            self.assertTrue(any("Paracetamol" in n for n in names_par))

            # Test prefix 'Met' -> Metformin / Metoprolol / Methotrexate
            res_met = search_medicines("Met")
            self.assertGreater(len(res_met), 0)
            names_met = [m['name'] for m in res_met]
            self.assertTrue(any("Metformin" in n or "Metoprolol" in n for n in names_met))

            # Test prefix 'Aml' -> Amlodipine
            res_aml = search_medicines("Aml")
            self.assertGreater(len(res_aml), 0)
            names_aml = [m['name'] for m in res_aml]
            self.assertTrue(any("Amlodipine" in n for n in names_aml))

            # Test prefix 'Ator' -> Atorvastatin
            res_ator = search_medicines("Ator")
            self.assertGreater(len(res_ator), 0)
            names_ator = [m['name'] for m in res_ator]
            self.assertTrue(any("Atorvastatin" in n for n in names_ator))

            # Test API endpoint response
            response = self.client.get('/api/medicines/autocomplete?q=Par')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertGreater(len(data), 0)

            # Test non-matching query
            res_none = search_medicines("XyzNonExistent999")
            self.assertEqual(len(res_none), 0)

    def test_location_autocomplete(self):
        """
        REQUIREMENT 2: Test location autocomplete suggestions using:
        G, Gu, Vi, Hy (and no match case).
        """
        with self.app.app_context():
            # Test 'G' -> Guntur, Gachibowli, Gajuwaka
            res_g = search_locations("G")
            self.assertGreater(len(res_g), 0)
            names_g = [loc['name'] for loc in res_g]
            self.assertTrue("Guntur" in names_g or any("G" in n for n in names_g))

            # Test 'Gu' -> Guntur
            res_gu = search_locations("Gu")
            self.assertGreater(len(res_gu), 0)
            names_gu = [loc['name'] for loc in res_gu]
            self.assertIn("Guntur", names_gu)

            # Test 'Vi' -> Vizianagaram, Visakhapatnam, Vijayawada
            res_vi = search_locations("Vi")
            self.assertGreater(len(res_vi), 0)
            names_vi = [loc['name'] for loc in res_vi]
            self.assertTrue(any(c in names_vi for c in ["Vijayawada", "Visakhapatnam", "Vizianagaram"]))

            # Test 'Hy' -> Hyderabad
            res_hy = search_locations("Hy")
            self.assertGreater(len(res_hy), 0)
            names_hy = [loc['name'] for loc in res_hy]
            self.assertIn("Hyderabad", names_hy)

            # Test API endpoint
            response = self.client.get('/api/locations/autocomplete?q=Gu')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertGreater(len(data), 0)
            self.assertEqual(data[0]['name'], 'Guntur')

            # Test non-matching query
            res_none = search_locations("NonExistentCity999")
            self.assertEqual(len(res_none), 0)

    def test_city_specific_search_and_no_leakage(self):
        """
        REQUIREMENT 3 & 11:
        Test city-based search and strict ZERO CROSS-CITY LEAKAGE:
        - Paracetamol + Guntur
        - Paracetamol + Vizianagaram
        - Paracetamol + Visakhapatnam
        - Metformin + Guntur
        - Amlodipine + Hyderabad
        - Atorvastatin + Vijayawada
        """
        with self.app.app_context():
            # 1. Paracetamol + Guntur -> ONLY Guntur pharmacies
            par_guntur = search_nearby_pharmacies_with_medicine("Paracetamol", user_city="Guntur")
            self.assertGreater(len(par_guntur), 0, "Guntur should have Paracetamol")
            for item in par_guntur:
                self.assertEqual(item['pharmacy_city'].lower(), 'guntur', f"Cross-city leakage! Got {item['pharmacy_city']}")

            # 2. Paracetamol + Vizianagaram -> ONLY Vizianagaram pharmacies
            par_vzm = search_nearby_pharmacies_with_medicine("Paracetamol", user_city="Vizianagaram")
            self.assertGreater(len(par_vzm), 0, "Vizianagaram should have Paracetamol")
            for item in par_vzm:
                self.assertEqual(item['pharmacy_city'].lower(), 'vizianagaram')

            # 3. Paracetamol + Visakhapatnam -> ONLY Visakhapatnam pharmacies
            par_vizag = search_nearby_pharmacies_with_medicine("Paracetamol", user_city="Visakhapatnam")
            self.assertGreater(len(par_vizag), 0, "Visakhapatnam should have Paracetamol")
            for item in par_vizag:
                self.assertEqual(item['pharmacy_city'].lower(), 'visakhapatnam')

            # 4. Metformin + Guntur -> ONLY Guntur pharmacies
            met_guntur = search_nearby_pharmacies_with_medicine("Metformin", user_city="Guntur")
            self.assertGreater(len(met_guntur), 0)
            for item in met_guntur:
                self.assertEqual(item['pharmacy_city'].lower(), 'guntur')

            # 5. Amlodipine + Hyderabad -> ONLY Hyderabad/Secunderabad pharmacies
            amlo_hyd = search_nearby_pharmacies_with_medicine("Amlodipine", user_city="Hyderabad")
            self.assertGreater(len(amlo_hyd), 0)
            for item in amlo_hyd:
                self.assertIn(item['pharmacy_city'].lower(), ['hyderabad', 'secunderabad'])

            # 6. Atorvastatin + Vijayawada -> ONLY Vijayawada pharmacies
            ator_vja = search_nearby_pharmacies_with_medicine("Atorvastatin", user_city="Vijayawada")
            self.assertGreater(len(ator_vja), 0)
            for item in ator_vja:
                self.assertEqual(item['pharmacy_city'].lower(), 'vijayawada')

    def test_unregistered_and_new_city_handling(self):
        """
        REQUIREMENT 4:
        Test city with no participating pharmacies (e.g. Tenali) or a completely new city.
        Displays required exact messages without claiming pharmacies don't exist.
        """
        # Test registered city with pharmacies
        has_guntur, count_guntur = check_pharmacies_exist_in_city("Guntur")
        self.assertTrue(has_guntur)
        self.assertGreater(count_guntur, 0)

        # Test unregistered city (Tenali)
        has_tenali, count_tenali = check_pharmacies_exist_in_city("Tenali")
        self.assertFalse(has_tenali)
        self.assertEqual(count_tenali, 0)

        # Test completely new city (Tiruvuru)
        has_new, count_new = check_pharmacies_exist_in_city("Tiruvuru")
        self.assertFalse(has_new)
        self.assertEqual(count_new, 0)

        # Verify Search page renders required message
        response = self.client.get('/search?q=Paracetamol&city=Tenali')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No Participating Pharmacies Found", response.data)
        self.assertIn(b"There are currently no pharmacies registered with Medicine Availability Finder in", response.data)

    def test_chronic_condition_categories_and_rx_marking(self):
        """Test chronic condition categories and Rx prescription status."""
        with self.app.app_context():
            bp_results = search_nearby_pharmacies_with_medicine("Amlodipine")
            self.assertGreater(len(bp_results), 0)
            self.assertEqual(bp_results[0]['prescription_required'], 1)

            diab_results = search_nearby_pharmacies_with_medicine("Metformin")
            self.assertGreater(len(diab_results), 0)
            self.assertEqual(diab_results[0]['prescription_required'], 1)

            chol_results = search_nearby_pharmacies_with_medicine("Atorvastatin")
            self.assertGreater(len(chol_results), 0)
            self.assertEqual(chol_results[0]['prescription_required'], 1)

    def test_haversine_distance_calculation(self):
        """Test exact geometric distance calculation using Haversine formula."""
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
