"""Explicit SQLite-only test profile. Never selected as a runtime fallback."""
import os
from pathlib import Path
import tempfile

os.environ.setdefault('DJANGO_SECRET_KEY', 'synthetic-test-key-not-for-runtime-' * 3)
os.environ.setdefault('CONTROL_DATABASE_URL', 'postgresql://synthetic:synthetic@127.0.0.1/control_test')
os.environ.setdefault('REDIS_URL', 'redis://127.0.0.1:6379/15')
os.environ.setdefault('BLOB_ROOT', str(Path(tempfile.gettempdir()) / 'arp-test-objects'))

from .settings import *  # noqa: F403,E402

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
