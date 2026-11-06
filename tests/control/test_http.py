"""Real loopback HTTP against a disposable Django test server, not a deployed platform."""
from http.cookiejar import CookieJar
import json
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request

from django.test import LiveServerTestCase, override_settings

from arp_control.foundation.models import User


# An API-only app has no static/media routes. Give Django's test-only file
# wrappers explicit external base URLs so they neither parse None nor serve CWD.
@override_settings(STATIC_URL='https://static.invalid/', MEDIA_URL='https://media.invalid/')
class ControlHTTPTests(LiveServerTestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('synthetic-http', password='Synthetic!HTTP-2026')
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, path, method='GET', body=None, csrf=None, key=None):
        headers = {}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        if csrf:
            headers['X-CSRFToken'] = csrf
        if key:
            headers['Idempotency-Key'] = key
        request = Request(self.live_server_url + path,
                          data=json.dumps(body).encode() if body is not None else None,
                          method=method, headers=headers)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            content = response.read()
            return response.status, json.loads(content) if content else None, response.headers

    def test_real_http_session_csrf_project_and_replay(self):
        status, data, _ = self.request('/api/v1/auth/csrf')
        self.assertEqual(status, 200)
        status, _, _ = self.request('/api/v1/auth/login', 'POST', {
            'username': self.user.username, 'password': 'Synthetic!HTTP-2026',
        }, csrf=data['csrf_token'])
        self.assertEqual(status, 200)
        _, token, _ = self.request('/api/v1/auth/csrf')
        body = {'name': 'Synthetic HTTP project'}
        status, project, headers = self.request('/api/v1/projects', 'POST', body,
                                                csrf=token['csrf_token'], key='http-project-key')
        self.assertEqual(status, 201)
        self.assertEqual(project['description'], '')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        status, replay, headers = self.request('/api/v1/projects', 'POST', body,
                                               csrf=token['csrf_token'], key='http-project-key')
        self.assertEqual(status, 201)
        self.assertEqual(project, replay)
        self.assertEqual(headers['Idempotent-Replay'], 'true')
        status, _, _ = self.request('/api/v1/projects', 'POST', body, key='http-csrf-missing')
        self.assertEqual(status, 403)

    def test_liveness_works_without_claiming_readiness(self):
        status, data, _ = self.request('/health/live')
        self.assertEqual(status, 200)
        self.assertEqual(data['phase'], 'P0')
