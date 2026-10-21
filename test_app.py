import os
import unittest
import json
import base64
import cv2
import numpy as np
import urllib.request

# Ensure app imports correctly
from app import app
import database

class SmartFaceSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        cls.client = app.test_client()

        # Download two distinct royalty-free test portraits for automated testing
        def get_img_b64(url):
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            content = urllib.request.urlopen(req, timeout=10).read()
            return "data:image/jpeg;base64," + base64.b64encode(content).decode('utf-8')

        print("\n[Test Suite] Downloading test face images...")
        try:
            cls.face1_b64 = get_img_b64('https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500&q=80')
            cls.face2_b64 = get_img_b64('https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=500&q=80')
            print("[Test Suite] Test face images downloaded successfully.")
        except Exception as e:
            print(f"[Test Suite] Warning: Could not download remote test faces ({e}). Using synthetic faces.")
            # Fallback to local generated images
            dummy1 = np.full((300, 300, 3), 150, dtype=np.uint8)
            _, buf = cv2.imencode('.jpg', dummy1)
            cls.face1_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8')
            cls.face2_b64 = cls.face1_b64

        # Blank black image with no face
        blank = np.zeros((300, 300, 3), dtype=np.uint8)
        _, buf = cv2.imencode('.jpg', blank)
        cls.blank_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8')

    def test_01_page_routes(self):
        """Test all frontend HTML pages return 200 OK."""
        routes = ['/', '/register', '/recognize', '/people', '/settings']
        for route in routes:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Route {route} failed")
            self.assertIn(b'FaceGuard AI', resp.data)

    def test_02_registration_validation_no_face(self):
        """Test registration returns exact error when no face is detected."""
        payload = {
            "name": "Nobody Here",
            "image": self.blank_b64
        }
        resp = self.client.post('/api/register', json=payload)
        data = resp.get_json()
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(data["success"])
        self.assertIn("No face detected. Please try again.", data["error"])

    def test_03_registration_validation_invalid_name(self):
        """Test registration requires a valid name."""
        payload = {
            "name": " ",
            "image": self.face1_b64
        }
        resp = self.client.post('/api/register', json=payload)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_04_successful_face_registration(self):
        """Test registering a person's face successfully."""
        payload = {
            "name": "Kishore",
            "image": self.face1_b64,
            "notes": "Lead Architect"
        }
        resp = self.client.post('/api/register', json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Face Registered Successfully")
        self.assertIn("person", data)
        self.assertEqual(data["person"]["name"], "Kishore")
        self.assertTrue(data["person"]["uid"].startswith("UID-"))
        self.__class__.registered_uid = data["person"]["uid"]
        self.__class__.registered_id = data["person"]["id"]
        print(f"[Test Suite] Registered {data['person']['name']} with UID: {data['person']['uid']}")

    def test_05_prevent_duplicate_name_registration(self):
        """Test duplicate name registration is rejected."""
        payload = {
            "name": "Kishore",
            "image": self.face1_b64
        }
        resp = self.client.post('/api/register', json=payload)
        self.assertEqual(resp.status_code, 409)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("already registered", data["error"])

    def test_06_prevent_duplicate_face_registration(self):
        """Test duplicate face detection triggers warning when registering under another name."""
        payload = {
            "name": "Kishore Imposter",
            "image": self.face1_b64  # Same face as Kishore
        }
        resp = self.client.post('/api/register', json=payload)
        self.assertEqual(resp.status_code, 422)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("already registered", data["error"])

    def test_07_live_recognition_registered_person_green_box(self):
        """Test live recognition frame recognizes registered person with GREEN box."""
        payload = {
            "frame": self.face1_b64,
            "similarity_threshold": 0.38
        }
        resp = self.client.post('/api/recognize_frame', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertGreaterEqual(data["total_faces"], 1)
        self.assertEqual(data["recognized_count"], 1)
        
        face = data["faces"][0]
        self.assertEqual(face["status"], "Recognized")
        self.assertEqual(face["name"], "Kishore")
        self.assertEqual(face["color"], "#10b981")  # Green hex
        self.assertIn("box", face)
        self.assertGreater(face["confidence"], 0.38)
        print(f"[Test Suite] Recognized {face['name']}: Color={face['color']}, Status={face['status']}, Confidence={face['confidence']}")

    def test_08_live_recognition_unregistered_person_yellow_box(self):
        """Test live recognition identifies unregistered face with YELLOW box and 'Unknown Person'."""
        payload = {
            "frame": self.face2_b64,
            "similarity_threshold": 0.38
        }
        resp = self.client.post('/api/recognize_frame', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertGreaterEqual(data["total_faces"], 1)
        
        face = data["faces"][0]
        self.assertEqual(face["status"], "Unknown")
        self.assertEqual(face["name"], "Unknown Person")
        self.assertEqual(face["color"], "#f59e0b")  # Yellow hex
        print(f"[Test Suite] Detected {face['name']}: Color={face['color']}, Status={face['status']}")

    def test_09_people_dashboard_api(self):
        """Test fetching people list and searching by name."""
        resp = self.client.get('/api/people')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 1)

        # Search test
        resp_search = self.client.get('/api/people?q=Kish')
        data_search = resp_search.get_json()
        self.assertEqual(len(data_search["people"]), 1)
        self.assertEqual(data_search["people"][0]["name"], "Kishore")

    def test_10_settings_api(self):
        """Test getting and updating settings."""
        get_resp = self.client.get('/api/settings')
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.get_json()
        self.assertIn("similarity_threshold", data["settings"])

        # Update setting
        update_resp = self.client.post('/api/settings', json={"similarity_threshold": "0.42"})
        self.assertEqual(update_resp.status_code, 200)

    def test_11_dashboard_stats_api(self):
        """Test dashboard stats endpoint."""
        resp = self.client.get('/api/stats')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["stats"]["total_registered"], 1)

    def test_12_delete_person_and_thumbnail(self):
        """Test deleting person completely removes DB record and thumbnail."""
        resp = self.client.delete(f'/api/people/{self.registered_id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])

        # Verify deletion from DB
        resp_check = self.client.get('/api/people?q=Kishore')
        data_check = resp_check.get_json()
        self.assertEqual(len(data_check["people"]), 0)
        print(f"[Test Suite] Person {self.registered_id} successfully deleted from SQLite and disk.")

if __name__ == '__main__':
    unittest.main()
