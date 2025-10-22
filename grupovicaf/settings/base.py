"""
Configuración Base de Django para el proyecto GRUPO VICAF (LIMS).
Contiene ajustes comunes para todos los entornos.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- CONFIGURACIÓN DE SEGURIDAD Y ENTORNO ---
# La clave secreta DEBE ser obtenida de .env
SECRET_KEY = os.environ.get('SECRET_KEY')

# Apps por defecto y de terceros
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Terceros (añadir después de instalar)
    # 'tailwind', 
    # 'crispy_forms',
    
    # Tus apps
    'core',
    'clientes',
    'trabajadores',
    'servicios',
    'proyectos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'grupovicaf.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'grupovicaf.wsgi.application'

# Base de Datos
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Internacionalización y Zona Horaria (Perú)
LANGUAGE_CODE = 'es-pe' 
TIME_ZONE = 'America/Lima' 
USE_I18N = True
USE_TZ = True 

# Archivos Estáticos
STATIC_URL = 'static/'
# Carpeta donde Django recolecta estáticos en producción
STATIC_ROOT = BASE_DIR / 'staticfiles' 
# Directorios de estáticos de cada app
STATICFILES_DIRS = [
    BASE_DIR / 'static', 
]

# Configuración de URLs de autenticación
LOGIN_REDIRECT_URL = 'dashboard' 
LOGIN_URL = 'login' 
LOGOUT_REDIRECT_URL = 'login'