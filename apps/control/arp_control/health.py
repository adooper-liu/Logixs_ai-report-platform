import hashlib
import io
import uuid

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from redis import Redis
from redis.exceptions import RedisError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .blobstore import LocalBlobStore
from .foundation.permissions import is_platform_admin


def dependencies_ready():
    checks = {'database': False, 'migrations': False, 'redis': False, 'blobstore': False}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            checks['database'] = cursor.fetchone()[0] == 1
        executor = MigrationExecutor(connection)
        checks['migrations'] = not executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception:
        pass
    try:
        with Redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2) as redis:
            checks['redis'] = bool(redis.ping())
    except (RedisError, ValueError):
        pass
    try:
        # Probe only a new private health object, never an existing business object.
        store = LocalBlobStore(settings.BLOB_ROOT)
        project_id = uuid.UUID('00000000-0000-0000-0000-000000000000')
        ref = store.put(project_id, io.BytesIO(b'arp-health'),
                        expected_sha256=hashlib.sha256(b'arp-health').hexdigest(), max_bytes=32)
        checks['blobstore'] = store.verify(ref)
        store.path(ref.project_id, ref.object_id).unlink()
    except (OSError, ValueError):
        pass
    return checks


class LiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'status': 'alive', 'component': 'control', 'phase': 'P0'})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        checks = dependencies_ready()
        ready = all(checks.values())
        body = {'status': 'ready' if ready else 'not_ready'}
        if is_platform_admin(request.user):
            body['checks'] = checks
        return Response(body, status=200 if ready else 503)
