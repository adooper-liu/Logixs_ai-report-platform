import copy
import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from arp_contracts.policy import DEFAULT_POLICY
from arp_control.foundation.models import (
    AuditEvent, IdempotentRequest, Membership, Project, ProjectConfigVersion, RoleGrant, User,
)
from arp_control.foundation.permissions import CAPABILITIES


class FoundationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('synthetic-admin', password='Synthetic!Secret-2026')
        self.user = User.objects.create_user('synthetic-viewer', password='Synthetic!Secret-2026')
        self.outsider = User.objects.create_user('synthetic-outsider', password='Synthetic!Secret-2026')
        self.client = APIClient()
        self.client.force_login(self.admin)
        response = self.send('post', '/api/v1/projects', {'name': 'Synthetic sales'}, key='create-sales')
        self.assertEqual(response.status_code, 201, response.data)
        self.project_id = response.data['id']
        self.url = f'/api/v1/projects/{self.project_id}'

    def send(self, method, url, data, key=None):
        return getattr(self.client, method)(url, data, format='json',
                                           HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))

    def grant(self, user=None, roles=None, revision=0):
        return self.send('put', self.url + f'/memberships/{(user or self.user).id}', {
            'expected_revision': revision, 'roles': roles or ['viewer'],
        })

    def test_optional_description_and_initial_policy(self):
        project = Project.objects.get(pk=self.project_id)
        self.assertEqual(project.description, '')
        self.assertEqual(project.config_versions.get().payload, DEFAULT_POLICY)
        self.assertEqual(project.config_versions.get().version, 1)
        self.assertEqual(AuditEvent.objects.filter(action='project.create').count(), 1)

    def test_anonymous_denied(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/v1/projects').status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_membership_filtered_before_object_lookup(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get('/api/v1/projects').data['count'], 0)
        for suffix in ('', '/config-versions', '/memberships', '/audit-events'):
            response = self.client.get(self.url + suffix)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(self.project_id, str(response.data))

    def test_viewer_cannot_write_or_administer(self):
        self.assertEqual(self.grant().status_code, 200)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(self.url + '/config-versions').status_code, 200)
        self.assertEqual(self.send('patch', self.url, {'expected_revision': 1, 'name': 'bad'}).status_code, 403)
        self.assertEqual(self.grant(self.outsider).status_code, 403)
        self.assertEqual(self.send('post', '/api/v1/projects', {'name': 'bad'}).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/users').status_code, 403)
        self.assertEqual(self.client.get(self.url + '/audit-events').status_code, 403)

    def test_project_admin_does_not_implicitly_read_data_or_publish(self):
        self.assertNotIn('data.read', CAPABILITIES['project_admin'])
        self.assertNotIn('release.publish', CAPABILITIES['project_admin'])
        self.assertNotIn('data.read', CAPABILITIES['operator'])
        self.assertIn('data.read', CAPABILITIES['viewer'])
        self.assertIn('release.publish', CAPABILITIES['publisher'])

    def test_project_admin_cannot_become_platform_admin(self):
        self.grant(roles=['project_admin'])
        self.client.force_login(self.user)
        self.assertEqual(self.send('post', '/api/v1/users', {
            'username': 'injected', 'password': 'Synthetic!New-2026', 'is_superuser': True,
        }).status_code, 403)
        self.assertEqual(self.grant(self.outsider, ['platform_admin']).status_code, 400)
        self.assertEqual(self.send('patch', self.url, {
            'expected_revision': 1, 'is_superuser': True,
        }).status_code, 400)

    def test_revision_cas_and_idempotency(self):
        body = {'expected_revision': 1, 'name': 'Sales revised'}
        response = self.send('patch', self.url, body, key='same-request')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['revision'], 2)
        replay = self.send('patch', self.url, body, key='same-request')
        self.assertEqual(replay.data, response.data)
        self.assertEqual(replay['Idempotent-Replay'], 'true')
        self.assertEqual(self.send('patch', self.url, body).status_code, 409)
        self.assertEqual(self.send('patch', self.url, {**body, 'name': 'different'}, key='same-request').status_code, 409)
        self.assertEqual(AuditEvent.objects.filter(action='project.update').count(), 1)

    def test_replay_after_permission_revocation_is_denied(self):
        self.grant(roles=['project_admin'])
        self.client.force_login(self.user)
        body = {'expected_revision': 1, 'name': 'Authorized change'}
        self.assertEqual(self.send('patch', self.url, body, key='revoke-test').status_code, 200)
        self.client.force_login(self.admin)
        self.grant(roles=['viewer'], revision=1)
        self.client.force_login(self.user)
        self.assertEqual(self.send('patch', self.url, body, key='revoke-test').status_code, 403)

    def test_project_creation_replay_does_not_duplicate(self):
        data = {'name': 'Synthetic support'}
        first = self.send('post', '/api/v1/projects', data, key='support-key')
        second = self.send('post', '/api/v1/projects', data, key='support-key')
        self.assertEqual(first.data, second.data)
        self.assertEqual(Project.objects.count(), 2)

    def test_missing_idempotency_key_rejected(self):
        response = self.client.post('/api/v1/projects', {'name': 'bad'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Project.objects.count(), 1)

    def test_atomic_audit_and_receipt_rollback(self):
        count = IdempotentRequest.objects.count()
        with patch('arp_control.foundation.views.audit', side_effect=RuntimeError('secret-not-to-leak')):
            response = self.send('post', '/api/v1/projects', {'name': 'Must roll back'})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('secret-not-to-leak', str(response.data))
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(IdempotentRequest.objects.count(), count)

    def test_config_versions_immutable_and_schema_checked(self):
        policy = copy.deepcopy(DEFAULT_POLICY)
        policy['storage']['retention_days'] = 90
        response = self.send('post', self.url + '/config-versions', {'expected_revision': 1, 'policy': policy})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['version'], 2)
        self.assertEqual(response.data['project_revision'], 2)
        first = ProjectConfigVersion.objects.get(project_id=self.project_id, version=1)
        self.assertIsNone(first.payload['storage']['retention_days'])
        first.payload = policy
        with self.assertRaisesRegex(ValueError, 'immutable'):
            first.save()
        policy['ai']['enabled'] = True
        self.assertEqual(self.send('post', self.url + '/config-versions', {
            'expected_revision': 2, 'policy': policy,
        }).status_code, 400)
        self.assertEqual(self.client.patch(self.url + '/config-versions', {}, format='json').status_code, 405)

    def test_last_admin_and_membership_revision(self):
        response = self.send('delete', self.url + f'/memberships/{self.admin.id}', {'expected_revision': 1})
        self.assertEqual(response.status_code, 409)
        self.grant(roles=['project_admin'])
        response = self.send('delete', self.url + f'/memberships/{self.admin.id}', {'expected_revision': 1})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Membership.objects.filter(project_id=self.project_id).count(), 1)
        self.assertEqual(self.grant(roles=['viewer'], revision=1).status_code, 409)

    def test_unknown_fields_and_cross_project_payload_rejected(self):
        response = self.send('post', '/api/v1/projects', {'name': 'bad', 'project_id': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.grant(roles=['viewer', 'viewer']).status_code, 400)
        self.assertEqual(RoleGrant.objects.count(), 1)

    def test_account_creation_password_policy_and_no_secret_response(self):
        self.assertEqual(self.send('post', '/api/v1/users', {
            'username': 'weak', 'password': '12345',
        }).status_code, 400)
        body = {'username': 'synthetic-new', 'password': 'Independent!Test-0497'}
        response = self.send('post', '/api/v1/users', body, key='new-user-key')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('password', response.data)
        self.assertEqual(self.send('post', '/api/v1/users', body, key='new-user-key').data, response.data)
        user = User.objects.get(username='synthetic-new')
        self.assertTrue(user.check_password(body['password']))
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertNotIn(body['password'], str(list(AuditEvent.objects.values())))
        self.assertNotIn(body['password'], str(list(IdempotentRequest.objects.values())))

    def test_trace_envelope_and_no_store(self):
        response = self.client.get('/api/v1/missing')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['trace_id'], response['X-Trace-ID'])
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response.json()['stage'], 'control')

    def test_contract_endpoint_and_nonfinite_or_unknown_policy(self):
        response = self.client.get('/api/v1/contracts/project-policy/v1')
        self.assertEqual(response.data['properties']['schema_version']['const'], '1.0.0')
        policy = copy.deepcopy(DEFAULT_POLICY)
        policy['sql'] = 'select anything'
        self.assertEqual(self.send('post', self.url + '/config-versions', {
            'expected_revision': 1, 'policy': policy,
        }).status_code, 400)
