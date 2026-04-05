"""
Configuración Django mínima para correr los tests del paquete.
"""
SECRET_KEY = "test-secret-key-not-for-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "tests",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "America/Mexico_City"
USE_TZ = True
