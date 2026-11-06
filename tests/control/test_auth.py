from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from arp_control.foundation.models import AuditEvent, User


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('synthetic-login', password='Synthetic!Secret-2026')
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf(self):
        return self.client.get('/api/v1/auth/csrf').data['csrf_token']

    def login(self, **kwargs):
        return self.client.post('/api/v1/auth/login', {
            'username': 'synthetic-login', 'password': kwargs.pop('password', 'Synthetic!Secret-2026'),
        }, format='json', **kwargs)

    def test_login_requires_csrf_even_when_anonymous(self):
        response = self.login()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'csrf_failed')
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_session_rotation_logout_and_csrf(self):
        self.client.force_login(self.user)
        old_key = self.client.session.session_key
        token = self.csrf()
        response = self.login(HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(old_key, self.client.session.session_key)
        self.assertEqual(self.client.get('/api/v1/auth/me').data['id'], str(self.user.id))
        self.assertEqual(self.client.post('/api/v1/auth/logout').status_code, 403)
        token = self.csrf()
        self.assertEqual(self.client.post('/api/v1/auth/logout', HTTP_X_CSRFTOKEN=token).status_code, 204)
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code, 403)

    def test_authenticated_write_requires_csrf(self):
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post('/api/v1/projects', {'name': 'Synthetic'}, format='json',
                                    HTTP_IDEMPOTENCY_KEY='csrf-missing')
        self.assertEqual(response.status_code, 403)

    @override_settings(LOGIN_MAX_FAILURES=2)
    def test_database_backed_throttle_and_no_forwarded_ip_bypass(self):
        token = self.csrf()
        for _ in range(2):
            self.assertEqual(self.login(password='incorrect', HTTP_X_CSRFTOKEN=token).status_code, 403)
        response = self.login(HTTP_X_CSRFTOKEN=token, HTTP_X_FORWARDED_FOR='192.0.2.44')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertEqual(AuditEvent.objects.filter(action='auth.login_failed').count(), 2)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        response = self.login(HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 403)

    def test_untrusted_origin_rejected(self):
        response = self.login(HTTP_X_CSRFTOKEN=self.csrf(), HTTP_ORIGIN='https://not-authorized.invalid')
        self.assertEqual(response.status_code, 403)
