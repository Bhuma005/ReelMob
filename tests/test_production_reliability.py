import unittest
import urllib.request
import json

BASE_URL = "http://localhost:8000"

class ProductionReliabilityTest(unittest.TestCase):
    def test_01_health_endpoints(self):
        req = urllib.request.Request(f"{BASE_URL}/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertEqual(data.get("status"), "healthy")
            self.assertIn("services", data)
            print("  [OK] /api/health passed")

        req_ai = urllib.request.Request(f"{BASE_URL}/api/health/ai", method="GET")
        with urllib.request.urlopen(req_ai, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            ai_data = json.loads(resp.read().decode())
            self.assertIn("available", ai_data)
            print("  [OK] /api/health/ai passed")

    def test_02_async_ai_job_lifecycle(self):
        payload = json.dumps({
            "title": "Test Viral Reel",
            "description": "Testing async AI background processing and progress polling.",
            "url": "https://www.instagram.com/reel/C_test_123/"
        }).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/metadata/analyze", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            init_res = json.loads(resp.read().decode())
            self.assertIn("job_id", init_res)
            print(f"  [OK] AI Job initiated with ID: {init_res['job_id']}")

    def test_03_dashboard_pagination(self):
        req = urllib.request.Request(f"{BASE_URL}/api/dashboard/videos?page=1&limit=5", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertIn("videos", data)
            self.assertIn("total", data)
            print(f"  [OK] Dashboard pagination query passed (total={data['total']})")

if __name__ == '__main__':
    unittest.main()
