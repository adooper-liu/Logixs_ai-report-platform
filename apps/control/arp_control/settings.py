from .config import load_config

CONFIG = load_config()
SECRET_KEY = CONFIG.secret_key
DEBUG = False
ALLOWED_HOSTS = list(CONFIG.allowed_hosts)
CSRF_TRUSTED_ORIGINS = list(CONFIG.csrf_origins)
DATABASES = {'default': CONFIG.database}
ROOT_URLCONF = 'arp_control.urls'
WSGI_APPLICATION = 'arp_control.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'foundation.User'
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'rest_framework', 'arp_control.foundation',
]
MIDDLEWARE = [
    'arp_control.http.TraceMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'EXCEPTION_HANDLER': 'arp_control.http.exception_handler',
}
USE_TZ = True
TIME_ZONE = 'UTC'
LANGUAGE_CODE = 'zh-hans'
APPEND_SLASH = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = CONFIG.secure_cookies
SESSION_COOKIE_AGE = 28800
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_SECURE = CONFIG.secure_cookies
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'arp_control.http.csrf_failure'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = CONFIG.environment == 'production'
SECURE_HSTS_SECONDS = 31536000 if CONFIG.environment == 'production' else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = CONFIG.environment == 'production'
SECURE_HSTS_PRELOAD = False
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 1048576
BLOB_ROOT = CONFIG.blob_root
REDIS_URL = CONFIG.redis_url
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 900
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'json': {'()': 'arp_control.http.SafeJSONFormatter'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'json'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
