from django.urls import path

from .foundation.auth import CsrfView, LoginView, LogoutView, MeView
from .foundation.views import (
    AuditView, ConfigsView, MembershipsView, MembershipView, PolicySchemaView,
    ProjectsView, ProjectView, UsersView,
)
from .health import LiveView, ReadyView

urlpatterns = [
    path('health/live', LiveView.as_view()),
    path('health/ready', ReadyView.as_view()),
    path('api/v1/auth/csrf', CsrfView.as_view()),
    path('api/v1/auth/login', LoginView.as_view()),
    path('api/v1/auth/logout', LogoutView.as_view()),
    path('api/v1/auth/me', MeView.as_view()),
    path('api/v1/users', UsersView.as_view()),
    path('api/v1/projects', ProjectsView.as_view()),
    path('api/v1/projects/<uuid:project_id>', ProjectView.as_view()),
    path('api/v1/projects/<uuid:project_id>/memberships', MembershipsView.as_view()),
    path('api/v1/projects/<uuid:project_id>/memberships/<uuid:user_id>', MembershipView.as_view()),
    path('api/v1/projects/<uuid:project_id>/config-versions', ConfigsView.as_view()),
    path('api/v1/projects/<uuid:project_id>/audit-events', AuditView.as_view()),
    path('api/v1/contracts/project-policy/v1', PolicySchemaView.as_view()),
]
handler404 = 'arp_control.http.not_found'
handler500 = 'arp_control.http.server_error'
