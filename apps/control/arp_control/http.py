import json
import logging
import uuid

from django.http import JsonResponse
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = 'Revision or request conflict.'
    default_code = 'conflict'


def error_body(code, message, trace_id, *, retryable=False, details=None):
    body = {
        'code': code, 'message': message, 'object_ref': None,
        'stage': 'control', 'retryable': retryable, 'trace_id': str(trace_id),
    }
    if details is not None:
        body['details'] = details
    return body


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    request = context.get('request')
    trace_id = getattr(request, 'trace_id', uuid.uuid4())
    if response is None:
        # Do not include exception strings: database errors may contain secrets.
        logging.getLogger('arp').error('unhandled_control_error', extra={'trace_id': str(trace_id)})
        from rest_framework.response import Response
        return Response(error_body('internal_error', 'Internal control-plane error.', trace_id), status=500)
    codes = {400: 'invalid_request', 401: 'unauthenticated', 403: 'forbidden', 404: 'not_found',
             405: 'method_not_allowed', 409: 'conflict', 415: 'unsupported_media_type', 429: 'throttled'}
    message = str(exc.detail) if isinstance(getattr(exc, 'detail', None), str) else 'Request validation failed.'
    details = response.data if response.status_code == 400 else None
    response.data = error_body(codes.get(response.status_code, 'request_failed'), message, trace_id, details=details)
    return response


def csrf_failure(request, reason=''):
    return JsonResponse(error_body('csrf_failed', 'CSRF verification failed.',
                                   getattr(request, 'trace_id', uuid.uuid4())), status=403)


def not_found(request, exception=None):
    return JsonResponse(error_body('not_found', 'Endpoint not found.',
                                   getattr(request, 'trace_id', uuid.uuid4())), status=404)


def server_error(request):
    return JsonResponse(error_body('internal_error', 'Internal control-plane error.',
                                   getattr(request, 'trace_id', uuid.uuid4())), status=500)


class TraceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.trace_id = uuid.uuid4()
        response = self.get_response(request)
        response['X-Trace-ID'] = str(request.trace_id)
        response['Cache-Control'] = 'no-store'
        return response


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        # Deliberately allowlist fields; no request bodies, URLs, exception text or SQL.
        return json.dumps({
            'level': record.levelname,
            'logger': record.name,
            'event': record.msg if record.name == 'arp' else 'framework_event',
            'trace_id': getattr(record, 'trace_id', None),
        })
