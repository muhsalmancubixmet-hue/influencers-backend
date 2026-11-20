import os
from datetime import timedelta
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load local environment variables from .env file
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        # Allow system environment variables to take precedence over local .env
        load_dotenv(_env_file, override=False)
    except ImportError:
        # Fallback pure-Python parser ensuring .env works even without python-dotenv package
        with open(_env_file, 'r', encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    _k = _k.strip()
                    _v = _v.strip().strip('"').strip("'")
                    if _k not in os.environ:
                        os.environ[_k] = _v

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# Cryptographic signing key loaded from environment; mandatory, fails closed if missing
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("SECRET_KEY environment variable is mandatory and cannot be empty.")

# Debug mode flag (enables verbose tracebacks in dev; defaults to False when unset)
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')

# Deployment environment flag: 'development' (SQLite default) | 'production' (PostgreSQL enforced)
DJANGO_ENV = (
    os.environ.get('DJANGO_ENV')
    or os.environ.get('ENVIRONMENT')
    or ('development' if DEBUG else 'production')
).strip().lower()

# Optional explicit database engine flag: 'sqlite' | 'postgres'
DB_ENGINE = os.environ.get('DB_ENGINE', '').strip().lower()

# Permitted host headers loaded strictly from environment (12-Factor standard; wildcard '*' prohibited)
raw_allowed = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in raw_allowed.split(',') if h.strip() and h.strip() != '*']
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# -----------------------------------------------------------------------------
# Production HTTPS, HSTS & Cookie Security
# -----------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 'yes')  # Enforce HTTPS redirect
    SESSION_COOKIE_SECURE = True  # Transmit session cookies only over HTTPS
    CSRF_COOKIE_SECURE = True  # Transmit CSRF tokens only over HTTPS
    SECURE_BROWSER_XSS_FILTER = True  # Enable browser XSS filtering header
    SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME-type sniffing
    X_FRAME_OPTIONS = 'DENY'  # Block clickjacking via iframe embedding
    SECURE_HSTS_SECONDS = 31536000  # Enforce HSTS for 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # Apply HSTS to all subdomains
    SECURE_HSTS_PRELOAD = True  # Allow HSTS preload list inclusion
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Trust reverse-proxy HTTPS header


# Application definition

INSTALLED_APPS = [
    # Daphne ASGI server must come before django.contrib.staticfiles
    'daphne',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third Party
    'channels',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',

    # Local Apps
    'apps.common',
    'apps.accounts',
    'apps.taxonomies',
    'apps.creators',
    'apps.businesses',
    'apps.campaigns',
    'apps.websites',
    'apps.billing',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

# Channels real-time WebSocket channel layer configuration (REQ-INF-02)
import sys
from urllib.parse import urlparse, unquote, parse_qs

_redis_channel_url = os.environ.get('CHANNEL_REDIS_URL') or os.environ.get('REDIS_URL')
_use_redis_channels = bool(_redis_channel_url and os.environ.get('USE_REDIS_CHANNELS', 'True').lower() in ('true', '1', 'yes'))
_is_testing = 'test' in sys.argv

if _use_redis_channels and not _is_testing:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [_redis_channel_url],
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }


# Database (REQ-INF-01)
# Flag-driven selection:
#   - DJANGO_ENV=development (or DB_ENGINE=sqlite): uses local SQLite (db.sqlite3)
#   - DJANGO_ENV=production  (or DB_ENGINE=postgres): enforces PostgreSQL via DATABASE_URL or POSTGRES_*
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases


def _build_sqlite_config():
    """Return SQLite database settings using SQLITE_DB_NAME or default db.sqlite3."""
    sqlite_name = os.environ.get('SQLITE_DB_NAME', 'db.sqlite3').strip() or 'db.sqlite3'
    db_path = Path(sqlite_name)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    return {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': db_path,
    }


def _build_postgres_config():
    """Return PostgreSQL database settings from DATABASE_URL or discrete POSTGRES_* variables."""
    conn_max_age = int(os.environ.get('DB_CONN_MAX_AGE', '600'))
    db_url = os.environ.get('DATABASE_URL', '').strip()

    if db_url:
        parsed = urlparse(db_url)
        if parsed.scheme in ('postgres', 'postgresql', 'pgsql'):
            config = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': unquote(parsed.path.lstrip('/')),
                'USER': unquote(parsed.username or ''),
                'PASSWORD': unquote(parsed.password or ''),
                'HOST': parsed.hostname or 'localhost',
                'PORT': str(parsed.port or 5432),
                'CONN_MAX_AGE': conn_max_age,
            }
            query_params = parse_qs(parsed.query)
            sslmode = query_params.get('sslmode', [None])[0] or os.environ.get('POSTGRES_SSLMODE', '').strip()
            if sslmode:
                config['OPTIONS'] = {'sslmode': sslmode}
            return config
        if parsed.scheme == 'sqlite':
            return _build_sqlite_config()

    pg_db = os.environ.get('POSTGRES_DB', '').strip()
    if pg_db:
        config = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': pg_db,
            'USER': os.environ.get('POSTGRES_USER', 'postgres').strip(),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost').strip(),
            'PORT': os.environ.get('POSTGRES_PORT', '5432').strip(),
            'CONN_MAX_AGE': conn_max_age,
        }
        sslmode = os.environ.get('POSTGRES_SSLMODE', '').strip()
        if sslmode:
            config['OPTIONS'] = {'sslmode': sslmode}
        return config

    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "PostgreSQL credentials (DATABASE_URL or POSTGRES_DB) are mandatory when DB_ENGINE=postgres or DJANGO_ENV=production."
    )


def _select_database_config():
    """Select SQLite for local development and PostgreSQL for production/staging."""
    if DB_ENGINE == 'sqlite':
        return _build_sqlite_config()
    if DB_ENGINE in ('postgres', 'postgresql', 'pgsql'):
        return _build_postgres_config()
    if DJANGO_ENV in ('production', 'staging'):
        return _build_postgres_config()
    return _build_sqlite_config()


DATABASES = {
    'default': _select_database_config()
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

_raw_static_url = os.environ.get('STATIC_URL', '/static/').strip() or '/static/'
if not _raw_static_url.startswith('/') and not _raw_static_url.startswith('http'):
    _raw_static_url = f"/{_raw_static_url}"
if not _raw_static_url.endswith('/'):
    _raw_static_url = f"{_raw_static_url}/"
STATIC_URL = _raw_static_url
# Absolute filesystem path where Django's collectstatic command gathers static files for production deployment
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# -----------------------------------------------------------------------------
# Email Configuration (SMTP / Console)
# -----------------------------------------------------------------------------
# If host password is the default placeholder or empty, use console backend in dev to prevent crashes
_raw_email_backend = os.environ.get('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
_email_user = os.environ.get('EMAIL_HOST_USER', '')
_email_pass = os.environ.get('EMAIL_HOST_PASSWORD', '')

if _raw_email_backend == 'django.core.mail.backends.smtp.EmailBackend' and (not _email_user or _email_pass in ('', 'your-google-app-password', 'your-app-password')):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = _raw_email_backend

EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = _email_user
EMAIL_HOST_PASSWORD = _email_pass
_raw_from = os.environ.get('DEFAULT_FROM_EMAIL', 'Influencers <support@influencers.com>').strip()
if '<' in _raw_from and not _raw_from.startswith('"'):
    _name, _addr = _raw_from.split('<', 1)
    DEFAULT_FROM_EMAIL = f'"{_name.strip()}" <{_addr}' if '.' in _name else f'{_name.strip()} <{_addr}'
else:
    DEFAULT_FROM_EMAIL = _raw_from

# Portal Domain URLs for Email Links & Dynamic Multi-Frontend Resolution
CREATOR_HUB_URL = os.environ.get('CREATOR_HUB_URL', 'http://localhost:8080').strip().rstrip('/')
ADMIN_PORTAL_URL = os.environ.get('ADMIN_PORTAL_URL', 'http://localhost:8081').strip().rstrip('/')
MARKETPLACE_URL = os.environ.get('MARKETPLACE_URL', 'http://localhost:8082').strip().rstrip('/')
BUSINESS_PORTAL_URL = os.environ.get('BUSINESS_PORTAL_URL', 'http://localhost:8083').strip().rstrip('/')
BRAND_SUITE_URL = BUSINESS_PORTAL_URL

# -----------------------------------------------------------------------------
# Celery & Redis Task Broker Configuration
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')
# In production, tasks are dispatched asynchronously to Redis task queues; default to DEBUG unless explicitly overridden
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_ALWAYS_EAGER', str(DEBUG)).lower() in ('true', '1', 'yes')
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Multi-Frontend CORS Configuration: Strict origin whitelist without wildcard bypass
_cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in _cors_env.split(',') if origin.strip() and origin.strip() != '*'
] if _cors_env else [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:8082",
    "http://127.0.0.1:8082",
    "http://localhost:8083",
    "http://127.0.0.1:8083",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

# Dynamic CORS regex whitelist (permits all Vercel production and preview deployments)
_cors_regex_env = os.environ.get('CORS_ALLOWED_ORIGIN_REGEXES', '')
if _cors_regex_env:
    CORS_ALLOWED_ORIGIN_REGEXES = [r.strip() for r in _cors_regex_env.split(',') if r.strip()]
else:
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https:\/\/.*\.vercel\.app$",
    ]

# Whitelisted HTTP headers permitted in cross-origin preflight requests
from corsheaders.defaults import default_headers

CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-target-portal',
]

# CSRF Trusted Origins (required in Django 4+ for admin and API POST requests over HTTPS)
_csrf_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if _csrf_env:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_env.split(',') if origin.strip()]
else:
    # Auto-populate from ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, and Vercel subdomains
    _auto_csrf = {'https://*.vercel.app'}
    for _h in ALLOWED_HOSTS:
        if _h and _h.startswith('.'):
            _auto_csrf.add(f"https://*{_h}")
            _auto_csrf.add(f"http://*{_h}")
        elif _h and _h not in ('localhost', '127.0.0.1'):
            _auto_csrf.add(f"https://{_h}")
            _auto_csrf.add(f"http://{_h}")
        elif _h:
            _auto_csrf.add(f"http://{_h}")
    for _o in CORS_ALLOWED_ORIGINS:
        if _o and not _o.startswith('*'):
            _auto_csrf.add(_o)
    CSRF_TRUSTED_ORIGINS = sorted(list(_auto_csrf))



# Caching & Distributed Throttle Store Configuration
# Outside local development (DEBUG=False), RedisCache is required to share
# throttle counters and cache entries across workers, UNLESS CACHE_BACKEND=locmem
# is explicitly configured for single-host deployments (e.g. PythonAnywhere).
CACHE_BACKEND = os.environ.get('CACHE_BACKEND', '').strip().lower()
REDIS_CACHE_URL = os.environ.get('REDIS_URL') or os.environ.get('CACHE_URL')

if not DEBUG and CACHE_BACKEND != 'locmem':
    if not REDIS_CACHE_URL:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "REDIS_URL or CACHE_URL environment variable is mandatory when DEBUG=False to ensure distributed cache safety."
        )

    redis_options = {}
    if REDIS_CACHE_URL.startswith('rediss://'):
        import ssl
        redis_options['ssl_cert_reqs'] = ssl.CERT_REQUIRED
        redis_options['ssl_check_hostname'] = True

    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_CACHE_URL,
            'KEY_PREFIX': 'creator_saas_cache',
            'TIMEOUT': 300,
            'OPTIONS': redis_options,
        }
    }
else:
    # In local development (DEBUG=True) or CACHE_BACKEND=locmem, use RedisCache if REDIS_URL is provided, else fallback to LocMemCache
    if REDIS_CACHE_URL and CACHE_BACKEND != 'locmem':
        redis_options = {}
        if REDIS_CACHE_URL.startswith('rediss://'):
            import ssl
            redis_options['ssl_cert_reqs'] = ssl.CERT_REQUIRED
            redis_options['ssl_check_hostname'] = True
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': REDIS_CACHE_URL,
                'KEY_PREFIX': 'creator_saas_cache',
                'TIMEOUT': 300,
                'OPTIONS': redis_options,
            }
        }
    else:
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'creator-saas-local-cache',
                'TIMEOUT': 300,
            }
        }

# Number of reverse proxies in front of application (0 = trust REMOTE_ADDR directly, >0 = count of trusted upstream proxies)
_raw_num_proxies = os.environ.get('NUM_PROXIES', '0').strip()
try:
    NUM_PROXIES = int(_raw_num_proxies)
except ValueError:
    NUM_PROXIES = 0

# REST Framework Settings
REST_FRAMEWORK = {
    'NUM_PROXIES': NUM_PROXIES,
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
        'auth': '5/minute',
        'inquiry': '10/minute',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# SimpleJWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),  # Reduced from 1 day to 30 mins to minimize blast radius of compromised tokens
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Media Files (Avatars, Covers, Portfolio)
USE_S3 = os.environ.get('USE_S3', 'False').lower() in ('true', '1', 'yes')

if USE_S3:
    # Amazon S3 / Cloudflare R2 object storage for distributed production environments
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', None)
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN', None)
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/" if AWS_S3_CUSTOM_DOMAIN else f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"
else:
    # Local filesystem media storage for development and non-S3 environments
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

# DRF Spectacular OpenAPI Schema Configuration
SPECTACULAR_SETTINGS = {
    'TITLE': 'Influencers.com SaaS Platform REST API',
    'DESCRIPTION': 'Production multi-portal backend powering Creator Hub, Brand Marketplace, and Staff Control Panel.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# Razorpay Payment Gateway Configuration (REQ-PAY-01)
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_MODE = os.environ.get('RAZORPAY_MODE', 'test')

