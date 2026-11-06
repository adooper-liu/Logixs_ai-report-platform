from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from .models import Project, Role


CAPABILITIES = {
    Role.VIEWER: {'project.read', 'data.read'},
    Role.OPERATOR: {'project.read', 'ingestion.write', 'run.retry'},
    Role.MODELER: {'project.read', 'rules.write', 'model.write'},
    Role.PUBLISHER: {'project.read', 'release.publish'},
    Role.PROJECT_ADMIN: {'project.read', 'project.write', 'membership.write', 'config.write', 'audit.read'},
}


def is_platform_admin(user):
    return user.is_authenticated and user.is_active and user.is_superuser


def require_platform_admin(user):
    if not is_platform_admin(user):
        raise PermissionDenied('Platform administrator permission required.')


def authorized_projects(user):
    if is_platform_admin(user):
        return Project.objects.all()
    return Project.objects.filter(memberships__user=user).distinct()


def get_project(user, project_id, capability='project.read', lock=False):
    # Filter before lookup: a foreign project's existence is not disclosed.
    queryset = authorized_projects(user)
    if lock:
        # DISTINCT + FOR UPDATE is not supported by PostgreSQL. Lock the base row
        # after the membership-filtered lookup, then recheck roles under that lock.
        project = get_object_or_404(queryset, pk=project_id)
        project = Project.objects.select_for_update().get(pk=project.id)
    else:
        project = get_object_or_404(queryset, pk=project_id)
    if not is_platform_admin(user):
        roles = project.memberships.filter(user=user).values_list('grants__role', flat=True)
        permissions = set().union(*(CAPABILITIES.get(role, set()) for role in roles))
        if capability not in permissions:
            raise PermissionDenied('Project capability not granted.')
    return project
