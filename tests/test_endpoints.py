import unittest
from app import create_app
from services.db import get_db

class TestOrvynEndpoints(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_login_page_renders(self):
        """Verify the login page returns HTTP 200."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Orvyn', response.data)

    def test_register_page_renders(self):
        """Verify the register page returns HTTP 200."""
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Create Account', response.data)

    def test_protected_route_redirects(self):
        """Verify accessing home without authentication redirects to login."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login'))

    def test_api_route_unauthorized(self):
        """Verify accessing api endpoints without session returns 401 JSON error."""
        response = self.client.get('/api/feed')
        self.assertEqual(response.status_code, 401)
        json_data = response.get_json()
        self.assertIn('error', json_data)

    def test_pwa_assets_serving(self):
        """Verify service worker and manifest files are served at the root path."""
        sw_response = self.client.get('/service-worker.js')
        self.assertEqual(sw_response.status_code, 200)
        self.assertEqual(sw_response.content_type, 'application/javascript')
        
        manifest_response = self.client.get('/manifest.json')
        self.assertEqual(manifest_response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
