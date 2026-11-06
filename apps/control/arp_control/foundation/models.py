import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class VersionedObject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True


class Project(VersionedObject):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')


class Role(models.TextChoices):
    VIEWER = 'viewer'
    OPERATOR = 'operator'
    MODELER = 'modeler'
    PUBLISHER = 'publisher'
    PROJECT_ADMIN = 'project_admin'


class Membership(VersionedObject):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='memberships')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'user'], name='unique_project_member')]


class RoleGrant(models.Model):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='grants')
    role = models.CharField(max_length=24, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['membership', 'role'], name='unique_member_role'),
            models.CheckConstraint(condition=Q(role__in=Role.values), name='valid_project_role'),
        ]


class ProjectConfigVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='config_versions')
    version = models.PositiveIntegerField()
    schema_version = models.CharField(max_length=20, default='1.0.0')
    payload = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'version'], name='unique_project_config_version')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Configuration versions are immutable; create a new version.')
        return super().save(*args, **kwargs)


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, null=True, on_delete=models.PROTECT, related_name='audit_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    object_ref = models.CharField(max_length=160)
    trace_id = models.UUIDField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class IdempotentRequest(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    scope = models.CharField(max_length=240)
    key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    response_body = models.JSONField(null=True)
    response_status = models.PositiveSmallIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'scope', 'key'], name='unique_request_identity')]


class LoginBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window_start = models.DateTimeField()
    failures = models.PositiveIntegerField(default=0)
