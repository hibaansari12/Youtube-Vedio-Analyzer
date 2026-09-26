from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-only-change-me"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "analyzer",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

# Streamlit runs on a different port (8501) than Django (8000), so CORS
# needs to be open between them. Tighten this if you ever deploy.
CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = "analyzer_project.urls"
WSGI_APPLICATION = "analyzer_project.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# No database needed — this project is a stateless analysis API.
DATABASES = {}

USE_TZ = True
