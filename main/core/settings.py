"""
Django settings for NET-1.
All secrets via environment variables — never hardcode.
"""

from pathlib import Path
from decouple import config

# ============================================================
#  PATHS
# ============================================================
BASE_DIR  = Path(__file__).resolve().parent.parent   # net-1/main/
ROOT_DIR  = BASE_DIR.parent                          # net-1/

# ============================================================
#  CORE SECURITY
# ============================================================
SECRET_KEY    = config('SECRET_KEY')
DEBUG         = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])

# ============================================================
#  HTTPS / SECURITY HEADERS
#  Set to True when serving behind Nginx with SSL
# ============================================================
SECURE_BROWSER_XSS_FILTER         = True
SECURE_CONTENT_TYPE_NOSNIFF        = True
X_FRAME_OPTIONS                    = 'DENY'
SECURE_HSTS_SECONDS                = config('SECURE_HSTS_SECONDS',             default=0,     cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS     = config('SECURE_HSTS_INCLUDE_SUBDOMAINS',  default=False, cast=bool)
SECURE_SSL_REDIRECT                = config('SECURE_SSL_REDIRECT',             default=False, cast=bool)
SESSION_COOKIE_SECURE              = config('SESSION_COOKIE_SECURE',           default=False, cast=bool)
CSRF_COOKIE_SECURE                 = config('CSRF_COOKIE_SECURE',              default=False, cast=bool)

# ============================================================
#  SESSION
# ============================================================
SESSION_ENGINE          = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE      = 60 * 60 * 12    # 12 hours

# ============================================================
#  AUTH
# ============================================================
LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/'
LOGOUT_REDIRECT_URL = '/login/'

# ============================================================
#  APPLICATIONS
# ============================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'interface',
    'data_master',
    'system_logger',
    'notes',
]

# ============================================================
#  MIDDLEWARE
# ============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serves static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'system_logger.middleware.ActivityLogMiddleware',
]

ROOT_URLCONF     = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'

# ============================================================
#  TEMPLATES
# ============================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# ============================================================
#  DATABASE
# ============================================================
DATABASES = {
    'default': {
        'ENGINE'      : 'django.db.backends.postgresql',
        'NAME'        : config('DB_NAME'),
        'USER'        : config('DB_USER'),
        'PASSWORD'    : config('DB_PASSWORD'),
        'HOST'        : config('DB_HOST'),
        'PORT'        : config('DB_PORT'),
        'CONN_MAX_AGE': 60,
    }
}

# ============================================================
#  PASSWORD VALIDATION
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================================
#  INTERNATIONALISATION
# ============================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True

# ============================================================
#  STATIC & MEDIA
#  Matches actual net-1/ folder structure
# ============================================================
STATIC_URL  = '/static/'
STATIC_ROOT = ROOT_DIR / 'data' / 'static'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL   = '/media/'
MEDIA_ROOT  = ROOT_DIR / 'data' / 'media'

# PDF files location
PDF_ROOT        = ROOT_DIR / 'data' / 'pdfs'
PDF_THUMBS_ROOT = ROOT_DIR / 'data' / 'pdf_thumbs'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
#  OLLAMA
# ============================================================
OLLAMA_HOST  = config('OLLAMA_HOST',  default='http://localhost:11434')
OLLAMA_MODEL = config('OLLAMA_MODEL', default='qwen3:8b')


# ============================================================
#  VALKEY (cache + chat history)
# ============================================================
CACHES = {
    'default': {
        'BACKEND' : 'django_valkey.cache.ValkeyCache',
        'LOCATION': f"valkey://{config('VALKEY_HOST')}:{config('VALKEY_PORT')}/0",
        'OPTIONS' : {
            'CLIENT_CLASS': 'django_valkey.client.DefaultClient',
        },
        'TIMEOUT'   : 60 * 60 * 24,
        'KEY_PREFIX': 'net1',
    }
}

# ============================================================
#  LOGGING  (warnings+ to file, errors to console)
# ============================================================
LOGGING = {
    'version'                  : 1,
    'disable_existing_loggers' : False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style' : '{',
        },
    },
    'handlers': {
        'file': {
            'level'    : 'WARNING',
            'class'    : 'logging.FileHandler',
            'filename' : BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'class'    : 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level'   : 'WARNING',
    },
}

