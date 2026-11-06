from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import AuthenticationFailed, Throttled
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditEvent, LoginBucket
from .serializers import LoginInput


def user_data(user):
    return {'id': str(user.id), 'username': user.username, 'platform_admin': user.is_superuser}


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'csrf_token': get_token(request)})


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        # REMOTE_ADDR is supplied by the server; do not trust X-Forwarded-For.
        identities = sorted([
            'user:' + values['username'].casefold(),
            'ip:' + request.META.get('REMOTE_ADDR', 'unknown'),
        ])
        now = timezone.now()
        with transaction.atomic():
            buckets = []
            for identity in identities:
                key = salted_hmac('arp.login', identity, algorithm='sha256').hexdigest()
                LoginBucket.objects.get_or_create(key=key, defaults={'window_start': now})
                bucket = LoginBucket.objects.select_for_update().get(pk=key)
                if bucket.window_start <= now - timedelta(seconds=settings.LOGIN_WINDOW_SECONDS):
                    bucket.window_start, bucket.failures = now, 0
                if bucket.failures >= settings.LOGIN_MAX_FAILURES:
                    raise Throttled(wait=max(1, int(settings.LOGIN_WINDOW_SECONDS - (now - bucket.window_start).total_seconds())))
                buckets.append(bucket)
            user = authenticate(request=request, **values)
            for bucket in buckets:
                bucket.failures = bucket.failures + 1 if user is None else 0
                bucket.save()
            # No submitted username/password/IP in audit details.
            AuditEvent.objects.create(
                actor=user, action='auth.login_failed' if user is None else 'auth.login',
                object_ref='session', trace_id=request.trace_id,
            )
        if user is None:
            raise AuthenticationFailed('Invalid credentials.')
        login(request, user)
        request.session.cycle_key()
        return Response(user_data(user))


class LogoutView(APIView):
    def post(self, request):
        AuditEvent.objects.create(actor=request.user, action='auth.logout', object_ref='session', trace_id=request.trace_id)
        logout(request)
        return Response(status=204)


class MeView(APIView):
    def get(self, request):
        return Response(user_data(request.user))
