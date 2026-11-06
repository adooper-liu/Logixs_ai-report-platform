"""Real PostgreSQL/Redis integration profile; credentials must be supplied by the caller."""
from .settings import *  # noqa: F403

ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
# CI uses an isolated database owner that can create the Django test database.
# Never point this profile at production.
