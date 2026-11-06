from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from arp_contracts.policy import DEFAULT_POLICY, fingerprint, policy_schema
from arp_control.http import Conflict
from .auth import user_data
from .models import Membership, Project, ProjectConfigVersion, Role, RoleGrant, User
from .permissions import authorized_projects, get_project, require_platform_admin
from .serializers import (
    ConfigInput, MembershipInput, ProjectCreate, ProjectOutput, ProjectUpdate, RevisionInput, UserCreate,
)
from .services import audit, check_revision, mutate


def paginated(request, queryset, serialize):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([serialize(item) for item in page])


def validate(serializer_type, request):
    serializer = serializer_type(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def membership_data(member):
    return {
        'id': str(member.id), 'user_id': str(member.user_id), 'revision': member.revision,
        'roles': sorted(grant.role for grant in member.grants.all()),
    }


def config_data(config):
    return {
        'id': str(config.id), 'version': config.version, 'schema_version': config.schema_version,
        'policy': config.payload, 'fingerprint': config.fingerprint,
        'created_by': str(config.created_by_id), 'created_at': config.created_at.isoformat(),
    }


class UsersView(APIView):
    def get(self, request):
        require_platform_admin(request.user)
        return paginated(request, User.objects.order_by('username'), user_data)

    def post(self, request):
        require_platform_admin(request.user)

        def operation():
            data = validate(UserCreate, request)
            user = User.objects.create_user(**data)
            audit(request, 'account.create', user.id)
            return user_data(user), 201
        return mutate(request, operation)


class ProjectsView(APIView):
    def get(self, request):
        return paginated(request, authorized_projects(request.user).order_by('created_at', 'id'),
                         lambda p: ProjectOutput(p).data)

    def post(self, request):
        require_platform_admin(request.user)

        def operation():
            project = Project.objects.create(**validate(ProjectCreate, request))
            membership = Membership.objects.create(project=project, user=request.user)
            RoleGrant.objects.create(membership=membership, role=Role.PROJECT_ADMIN)
            ProjectConfigVersion.objects.create(
                project=project, version=1, payload=DEFAULT_POLICY,
                fingerprint=fingerprint(DEFAULT_POLICY), created_by=request.user,
            )
            audit(request, 'project.create', project.id, project)
            return ProjectOutput(project).data, 201
        return mutate(request, operation)


class ProjectView(APIView):
    def get(self, request, project_id):
        return Response(ProjectOutput(get_project(request.user, project_id)).data)

    @transaction.atomic
    def patch(self, request, project_id):
        project = get_project(request.user, project_id, 'project.write', lock=True)

        def operation():
            data = validate(ProjectUpdate, request)
            check_revision(project, data.pop('expected_revision'))
            if not data:
                raise ValidationError('At least one change is required.')
            for field, value in data.items():
                setattr(project, field, value)
            project.revision += 1
            project.save()
            audit(request, 'project.update', project.id, project, {'revision': project.revision})
            return ProjectOutput(project).data, 200
        return mutate(request, operation)


class MembershipsView(APIView):
    def get(self, request, project_id):
        project = get_project(request.user, project_id, 'membership.write')
        return paginated(request, project.memberships.prefetch_related('grants').order_by('created_at', 'id'),
                         membership_data)


class MembershipView(APIView):
    @transaction.atomic
    def put(self, request, project_id, user_id):
        project = get_project(request.user, project_id, 'membership.write', lock=True)

        def operation():
            data = validate(MembershipInput, request)
            user = get_object_or_404(User, pk=user_id, is_active=True)
            member = Membership.objects.filter(project=project, user=user).first()
            if member is None:
                if data['expected_revision'] != 0:
                    raise Conflict('A new membership requires expected_revision=0.')
                member = Membership.objects.create(project=project, user=user)
            else:
                check_revision(member, data['expected_revision'])
                self.check_last_admin(project, member, data['roles'])
                member.revision += 1
                member.save()
                member.grants.all().delete()
            RoleGrant.objects.bulk_create([RoleGrant(membership=member, role=r) for r in data['roles']])
            audit(request, 'membership.set_roles', member.id, project, {'roles': data['roles'], 'revision': member.revision})
            return membership_data(member), 200
        return mutate(request, operation)

    @transaction.atomic
    def delete(self, request, project_id, user_id):
        project = get_project(request.user, project_id, 'membership.write', lock=True)

        def operation():
            data = validate(RevisionInput, request)
            member = get_object_or_404(Membership, project=project, user_id=user_id)
            check_revision(member, data['expected_revision'])
            self.check_last_admin(project, member, [])
            audit(request, 'membership.remove', member.id, project)
            member.delete()
            return None, 204
        return mutate(request, operation)

    @staticmethod
    def check_last_admin(project, member, new_roles):
        if member.grants.filter(role=Role.PROJECT_ADMIN).exists() and Role.PROJECT_ADMIN not in new_roles:
            others = project.memberships.exclude(pk=member.pk).filter(user__is_active=True, grants__role=Role.PROJECT_ADMIN)
            if not others.exists():
                raise Conflict('Cannot remove the last active project administrator.')


class ConfigsView(APIView):
    def get(self, request, project_id):
        project = get_project(request.user, project_id)
        return paginated(request, project.config_versions.order_by('-version'), config_data)

    @transaction.atomic
    def post(self, request, project_id):
        project = get_project(request.user, project_id, 'config.write', lock=True)

        def operation():
            data = validate(ConfigInput, request)
            check_revision(project, data['expected_revision'])
            version = (project.config_versions.aggregate(value=Max('version'))['value'] or 0) + 1
            config = ProjectConfigVersion.objects.create(
                project=project, version=version, payload=data['policy'],
                fingerprint=fingerprint(data['policy']), created_by=request.user,
            )
            project.revision += 1
            project.save()
            audit(request, 'project.config_version', config.id, project, {'version': version, 'revision': project.revision})
            body = config_data(config)
            body['project_revision'] = project.revision
            return body, 201
        return mutate(request, operation)


class AuditView(APIView):
    def get(self, request, project_id):
        project = get_project(request.user, project_id, 'audit.read')
        return paginated(request, project.audit_events.order_by('-created_at', 'id'), lambda event: {
            'id': str(event.id), 'actor_id': str(event.actor_id), 'action': event.action,
            'object_ref': event.object_ref, 'details': event.details, 'trace_id': str(event.trace_id),
            'created_at': event.created_at.isoformat(),
        })


class PolicySchemaView(APIView):
    def get(self, request):
        return Response(policy_schema())
