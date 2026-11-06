"""These tests must run on PostgreSQL; SQLite success cannot substitute for them."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import unittest

from django.conf import settings
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from redis import Redis
from rest_framework.test import APIClient

from arp_control.foundation.models import Project, User


@unittest.skipUnless(connection.vendor == 'postgresql', 'Requires real PostgreSQL; not validated by SQLite.')
class PostgreSQLTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('synthetic-pg-admin', password='Synthetic!Secret-2026')

    def race(self, method, path, bodies, keys):
        barrier = threading.Barrier(2)
        user_id = self.user.id

        def send(index):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=user_id))
                barrier.wait(timeout=10)
                response = getattr(client, method)(path, bodies[index], format='json',
                                                    HTTP_IDEMPOTENCY_KEY=keys[index])
                return response.status_code, response.data
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(send, range(2)))

    def test_concurrent_idempotent_creation_commits_once(self):
        results = self.race('post', '/api/v1/projects', [{'name': 'Synthetic race'}] * 2, ['pg-same-key'] * 2)
        self.assertEqual([r[0] for r in results], [201, 201])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(Project.objects.count(), 1)

    def test_concurrent_cas_allows_only_one_write(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post('/api/v1/projects', {'name': 'Synthetic CAS'}, format='json',
                               HTTP_IDEMPOTENCY_KEY='pg-create-key')
        url = '/api/v1/projects/' + response.data['id']
        results = self.race('patch', url, [
            {'expected_revision': 1, 'name': 'A'}, {'expected_revision': 1, 'name': 'B'},
        ], ['pg-change-a', 'pg-change-b'])
        self.assertEqual(sorted(r[0] for r in results), [200, 409])
        self.assertEqual(Project.objects.get().revision, 2)

    def test_foundation_migration_reversible_on_empty_isolated_database(self):
        # Only the test database is touched; no runtime/production invocation.
        self.user.delete()
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('foundation', None)])
            self.assertNotIn('foundation_project', connection.introspection.table_names())
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(targets)
        self.assertIn('foundation_project', connection.introspection.table_names())


@unittest.skipUnless(os.environ.get('P0_REQUIRE_SERVICES') == '1', 'Requires explicitly enabled Redis integration.')
class RedisIntegrationTests(TransactionTestCase):
    def test_actual_redis_ping(self):
        with Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2) as redis:
            self.assertTrue(redis.ping())
