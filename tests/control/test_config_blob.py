import copy
import hashlib
import io
from pathlib import Path
import tempfile
import uuid
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from jsonschema import ValidationError

from arp_contracts.policy import DEFAULT_POLICY, fingerprint, policy_schema, validate_policy
from arp_control.blobstore import LocalBlobStore
from arp_control.config import load_config


class ConfigurationTests(SimpleTestCase):
    def setUp(self):
        self.env = {
            'DJANGO_SECRET_KEY': 'synthetic-config-secret-' * 4,
            'CONTROL_DATABASE_URL': 'postgresql://control:synthetic@localhost:5432/control',
            'REDIS_URL': 'redis://localhost:6379/0',
            'BLOB_ROOT': str(Path(tempfile.gettempdir()) / 'arp-config-test'),
        }

    def test_explicit_postgres_and_safe_defaults(self):
        config = load_config(self.env)
        self.assertEqual(config.database['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config.database['NAME'], 'control')
        self.assertFalse(config.secure_cookies)

    def test_missing_parameters_never_fall_back_to_sqlite(self):
        for key in ('DJANGO_SECRET_KEY', 'CONTROL_DATABASE_URL', 'REDIS_URL', 'BLOB_ROOT'):
            env = {k: v for k, v in self.env.items() if k != key}
            with self.subTest(key=key), self.assertRaises(ImproperlyConfigured):
                load_config(env)

    def test_invalid_configuration_rejected_without_secret_echo(self):
        for key, value in (
            ('CONTROL_DATABASE_URL', 'sqlite:///wrong'),
            ('CONTROL_DATABASE_URL', 'postgresql://control:secret-not-to-print@host/control?options=bad'),
            ('REDIS_URL', 'https://secret-not-to-print.invalid'),
            ('AI_ENABLED', 'true'), ('AI_ALLOW_RAW_SAMPLE_EGRESS', 'true'),
            ('ALLOWED_HOSTS', '*'), ('BLOB_ROOT', 'relative'), ('BLOB_BACKEND', 's3'),
            ('APP_ENV', 'test'), ('CSRF_TRUSTED_ORIGINS', 'https://example.invalid/path'),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ImproperlyConfigured) as cm:
                load_config({**self.env, key: value})
            self.assertNotIn('secret-not-to-print', str(cm.exception))

    def test_production_tls_and_cookies(self):
        env = {**self.env, 'APP_ENV': 'production'}
        with self.assertRaises(ImproperlyConfigured):
            load_config(env)
        env.update(CONTROL_DATABASE_URL=env['CONTROL_DATABASE_URL'] + '?sslmode=verify-full',
                   REDIS_URL='rediss://control:synthetic@localhost:6380/0')
        self.assertTrue(load_config(env).secure_cookies)

    def test_versioned_contract(self):
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(policy_schema())
        policy = validate_policy(DEFAULT_POLICY)
        policy['storage']['retention_days'] = 10
        self.assertIsNone(DEFAULT_POLICY['storage']['retention_days'])
        for mutation in ('version', 'ai', 'sql', 'size', 'bool'):
            bad = copy.deepcopy(DEFAULT_POLICY)
            if mutation == 'version':
                bad['schema_version'] = '2.0.0'
            elif mutation == 'ai':
                bad['ai']['enabled'] = True
            elif mutation == 'sql':
                bad['sql'] = 'untrusted'
            else:
                bad['storage']['max_object_bytes'] = 0 if mutation == 'size' else True
            with self.assertRaises(ValidationError):
                validate_policy(bad)
        self.assertEqual(fingerprint(DEFAULT_POLICY), fingerprint(dict(reversed(list(DEFAULT_POLICY.items())))))


class BlobStoreTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalBlobStore(Path(self.temp.name))
        self.project = uuid.uuid4()
        self.content = b'synthetic-only\x00\x01'
        self.checksum = hashlib.sha256(self.content).hexdigest()

    def put(self, **kwargs):
        return self.store.put(self.project, io.BytesIO(self.content),
                              expected_sha256=kwargs.get('checksum', self.checksum),
                              max_bytes=kwargs.get('limit', 1024))

    def test_roundtrip_and_content_identity_is_not_object_identity(self):
        first, second = self.put(), self.put()
        self.assertNotEqual(first.object_id, second.object_id)
        self.assertEqual(first.sha256, second.sha256)
        self.assertTrue(self.store.verify(first))
        with self.store.open(first.project_id, first.object_id) as source:
            self.assertEqual(source.read(), self.content)
        self.assertFalse(list(Path(self.temp.name).rglob('*.partial')))

    def test_size_and_checksum_failure_leave_no_objects(self):
        for kwargs in ({'limit': 1}, {'checksum': '0' * 64}):
            with self.assertRaises(ValueError):
                self.put(**kwargs)
        self.assertEqual(list((Path(self.temp.name) / str(self.project)).iterdir()), [])

    def test_no_path_traversal_or_cross_project_read(self):
        ref = self.put()
        for bad in ('../outside', '/tmp/outside', 'C:\\outside', '../../arp_control/settings.py'):
            with self.assertRaises(ValueError):
                self.store.open(self.project, bad)
            with self.assertRaises(ValueError):
                self.store.open(bad, ref.object_id)
        with self.assertRaises(FileNotFoundError):
            self.store.open(uuid.uuid4(), ref.object_id)

    def test_atomic_finalize_cannot_overwrite(self):
        ref = self.put()
        with patch('arp_control.blobstore.uuid.uuid4', return_value=ref.object_id):
            with self.assertRaises(FileExistsError):
                self.put()
        self.assertTrue(self.store.verify(ref))

    def test_stream_failure_cleans_partial_object(self):
        class Broken:
            def read(self, size):
                raise OSError('synthetic source failure')
        with self.assertRaises(OSError):
            self.store.put(self.project, Broken(), expected_sha256=self.checksum, max_bytes=1024)
        self.assertFalse(list(Path(self.temp.name).rglob('*.partial')))

    def test_empty_raw_object_is_not_silently_discarded(self):
        ref = self.store.put(self.project, io.BytesIO(b''), expected_sha256=hashlib.sha256(b'').hexdigest(), max_bytes=1)
        self.assertEqual(ref.size, 0)
        self.assertTrue(self.store.verify(ref))

    def test_symlink_rejected_where_supported(self):
        other = Path(self.temp.name) / 'external'
        other.mkdir()
        project = Path(self.temp.name) / str(self.project)
        try:
            project.symlink_to(other, target_is_directory=True)
        except OSError:
            self.skipTest('OS does not permit symlink creation for the current account.')
        with self.assertRaises(ValueError):
            self.put()
