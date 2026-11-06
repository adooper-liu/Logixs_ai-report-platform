import json
import re

from django.db import IntegrityError, transaction
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from arp_contracts.policy import canonical_json
from arp_control.http import Conflict
from .models import AuditEvent, IdempotentRequest


def audit(request, action, object_ref, project=None, details=None):
    AuditEvent.objects.create(
        project=project, actor=request.user, action=action, object_ref=str(object_ref),
        trace_id=request.trace_id, details=details or {},
    )


def check_revision(obj, expected):
    if obj.revision != expected:
        raise Conflict('Revision changed; reload before retrying with a new Idempotency-Key.')


def mutate(request, operation):
    """Caller must authorize and hold any project lock before entering this function."""
    key = request.headers.get('Idempotency-Key', '')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{8,128}', key):
        raise ValidationError('Idempotency-Key must contain 8-128 safe ASCII characters.')
    scope = f'{request.method}:{request.path}'
    # Keyed, not plain SHA256: bodies may contain account passwords.
    digest = salted_hmac('arp.request', canonical_json(request.data), algorithm='sha256').hexdigest()
    with transaction.atomic():
        try:
            with transaction.atomic():
                receipt = IdempotentRequest.objects.create(
                    actor=request.user, scope=scope, key=key, request_hash=digest,
                )
        except IntegrityError:
            receipt = IdempotentRequest.objects.select_for_update().get(actor=request.user, scope=scope, key=key)
            if receipt.request_hash != digest:
                raise Conflict('Idempotency-Key was already used with a different request.') from None
            if receipt.response_status is None:
                raise Conflict('Request is still in progress.') from None
            response = Response(receipt.response_body, status=receipt.response_status)
            response['Idempotent-Replay'] = 'true'
            return response
        body, status = operation()
        body = json.loads(JSONRenderer().render(body)) if body is not None else None
        receipt.response_body = body
        receipt.response_status = status
        receipt.save(update_fields=['response_body', 'response_status'])
        return Response(body, status=status)
