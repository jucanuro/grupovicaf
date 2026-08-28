"""Solo para correr la suite en local sin Redis. No usar en dev/prod."""
from .dev import *  # noqa

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
