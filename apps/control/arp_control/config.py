"""Fail-closed runtime configuration. No implicit .env reads or database fallback."""
from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    secret_key: str
    allowed_hosts: tuple
    csrf_origins: tuple
    database: dict
    redis_url: str
    blob_root: Path
    secure_cookies: bool


def database_config(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('postgres', 'postgresql'):
            raise ValueError
        if not parsed.hostname or not parsed.username or not parsed.password:
            raise ValueError
        if not parsed.path or parsed.path == '/' or parsed.fragment:
            raise ValueError
        # Accept only one explicit transport option, not arbitrary libpq parameters.
        from urllib.parse import parse_qs
        options = parse_qs(parsed.query, strict_parsing=True)
        if set(options) - {'sslmode'} or any(len(v) != 1 for v in options.values()):
            raise ValueError
        sslmode = options.get('sslmode', ['prefer'])[0]
        if sslmode not in ('disable', 'prefer', 'require', 'verify-ca', 'verify-full'):
            raise ValueError
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed.path[1:]),
            'USER': unquote(parsed.username),
            'PASSWORD': unquote(parsed.password),
            'HOST': parsed.hostname,
            'PORT': parsed.port or 5432,
            'CONN_MAX_AGE': 60,
            'OPTIONS': {'connect_timeout': 3, 'sslmode': sslmode},
        }
    except (ValueError, TypeError):
        raise ImproperlyConfigured('CONTROL_DATABASE_URL must be a valid PostgreSQL URL (value redacted).') from None


def load_config(environ=None):
    env = os.environ if environ is None else environ
    mode = env.get('APP_ENV', 'development')
    if mode not in ('development', 'production'):
        raise ImproperlyConfigured('APP_ENV must be development or production.')
    secret = env.get('DJANGO_SECRET_KEY', '')
    if len(secret) < 50 or secret.startswith('change-me'):
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be independently generated, at least 50 characters.')
    hosts = tuple(h.strip() for h in env.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip())
    if not hosts or '*' in hosts:
        raise ImproperlyConfigured('ALLOWED_HOSTS must explicitly name allowed hosts.')
    origins = tuple(o.strip() for o in env.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip())
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path
                or parsed.query or parsed.fragment or '*' in origin):
            raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS must contain exact HTTP(S) origins.')
        if mode == 'production' and parsed.scheme != 'https':
            raise ImproperlyConfigured('Production CSRF origins must use HTTPS.')
    redis_url = env.get('REDIS_URL', '')
    try:
        redis = urlsplit(redis_url)
        if redis.scheme not in ('redis', 'rediss') or not redis.hostname or redis.fragment:
            raise ValueError
        if redis.port is not None and not 1 <= redis.port <= 65535:
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured('REDIS_URL must be an explicit Redis URL (value redacted).') from None
    if env.get('BLOB_BACKEND', 'local') != 'local':
        raise ImproperlyConfigured('Only the local BlobStore backend is implemented in P0.')
    root = Path(env.get('BLOB_ROOT', '.local/objects'))
    if not root.is_absolute():
        raise ImproperlyConfigured('BLOB_ROOT must be absolute and outside application code.')
    for flag in ('AI_ENABLED', 'AI_ALLOW_RAW_SAMPLE_EGRESS'):
        if env.get(flag, 'false').lower() != 'false':
            raise ImproperlyConfigured(f'{flag} must remain false in P0.')
    database = database_config(env.get('CONTROL_DATABASE_URL', ''))
    if mode == 'production':
        if database['OPTIONS']['sslmode'] not in ('require', 'verify-ca', 'verify-full'):
            raise ImproperlyConfigured('Production PostgreSQL requires explicit TLS.')
        if redis.scheme != 'rediss' or not redis.password:
            raise ImproperlyConfigured('Production Redis requires TLS and authentication.')
    return RuntimeConfig(mode, secret, hosts, origins, database, redis_url, root, mode == 'production')
