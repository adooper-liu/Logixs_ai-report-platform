import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from arp_control.foundation.models import User
from arp_control.health import dependencies_ready


class HealthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_liveness_is_not_readiness(self):
        response = self.client.get('/health/live')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'alive')
        with patch('arp_control.health.dependencies_ready', return_value={
            'database': True, 'migrations': True, 'redis': False, 'blobstore': True,
        }):
            response = self.client.get('/health/ready')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {'status': 'not_ready'})

    def test_only_admin_sees_dependency_details(self):
        user = User.objects.create_superuser('synthetic-health', password='Synthetic!Secret-2026')
        self.client.force_login(user)
        with patch('arp_control.health.dependencies_ready', return_value={'database': True, 'redis': True}):
            response = self.client.get('/health/ready')
        self.assertEqual(response.status_code, 200)
        self.assertIn('checks', response.data)

    def test_real_db_and_blob_probe_with_redis_unavailable(self):
        with tempfile.TemporaryDirectory() as root, override_settings(BLOB_ROOT=__import__('pathlib').Path(root)):
            with patch('arp_control.health.Redis.from_url', side_effect=ValueError('secret-redis-url')):
                checks = dependencies_ready()
        self.assertTrue(checks['database'])
        self.assertTrue(checks['migrations'])
        self.assertTrue(checks['blobstore'])
        self.assertFalse(checks['redis'])
