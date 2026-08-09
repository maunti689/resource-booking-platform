import os

import dj_database_url

from config.settings import *

DATABASES = {"default": dj_database_url.parse(os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:"))}
if test_cache_url := os.getenv("TEST_CACHE_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": test_cache_url,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "resource-booking-tests",
        }
    }
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
SECRET_KEY = "test-secret-key-with-at-least-thirty-two-characters"
