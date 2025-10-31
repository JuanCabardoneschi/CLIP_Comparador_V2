"""
Configuración centralizada para entorno de desarrollo vs producción
"""

import os


def is_production():
    """
    Detecta si estamos en producción

    Returns:
        bool: True si estamos en producción (Railway), False si es desarrollo local
    """
    # Método 1: Railway siempre setea RAILWAY_ENVIRONMENT
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        return True

    # Método 2: Variable explícita FLASK_ENV
    flask_env = os.environ.get('FLASK_ENV', 'development')
    if flask_env == 'production':
        return True

    # Método 3: Verificar si DATABASE_URL apunta a Railway
    db_url = os.environ.get('DATABASE_URL', '')
    if 'railway.app' in db_url or 'railway.internal' in db_url:
        return True

    # Por defecto, asumir desarrollo local
    return False


def get_environment_name():
    """
    Obtiene el nombre legible del entorno actual

    Returns:
        str: 'Production (Railway)' o 'Development (Local)'
    """
    return 'Production (Railway)' if is_production() else 'Development (Local)'


def get_database_url():
    """
    Obtiene la URL de base de datos correcta según el entorno

    Returns:
        str: URL de conexión a la base de datos

    Raises:
        ValueError: Si DATABASE_URL no está configurada
    """
    db_url = os.environ.get('DATABASE_URL')

    if not db_url:
        raise ValueError(
            "DATABASE_URL no está configurada.\n"
            "Para desarrollo local:\n"
            "  1. Instala PostgreSQL: https://www.postgresql.org/download/\n"
            "  2. Crea la base de datos: psql -U postgres -c 'CREATE DATABASE clip_comparador_v2;'\n"
            "  3. Configura .env.local con:\n"
            "     DATABASE_URL=postgresql://postgres:tu_password@localhost:5432/clip_comparador_v2\n"
            "  4. Ejecuta: python setup_local_postgres.py\n"
        )

    # Validar que sea PostgreSQL
    if not (db_url.startswith('postgresql://') or db_url.startswith('postgres://')):
        raise ValueError(
            f"DATABASE_URL debe ser PostgreSQL, no {db_url.split('://')[0] if '://' in db_url else 'desconocido'}.\n"
            "SQLite no es soportado en este proyecto.\n"
            "Usa: postgresql://usuario:password@host:5432/database"
        )

    # Railway usa postgres:// pero SQLAlchemy necesita postgresql://
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    return db_url


def get_redis_url():
    """
    Obtiene la URL de Redis correcta según el entorno

    Returns:
        str or None: URL de Redis o None si no está disponible
    """
    redis_url = os.environ.get('REDIS_URL')

    if not redis_url and not is_production():
        # En desarrollo local, Redis es opcional
        return None

    return redis_url


def get_secret_key():
    """
    Obtiene la SECRET_KEY apropiada

    Returns:
        str: Clave secreta para Flask
    """
    secret_key = os.environ.get('SECRET_KEY')

    if not secret_key:
        if is_production():
            raise ValueError('SECRET_KEY debe estar configurada en producción')
        else:
            # Usar clave de desarrollo
            return 'dev-secret-key-insecure-change-in-production'

    return secret_key


def get_debug_mode():
    """
    Determina si Flask debe correr en modo debug

    Returns:
        bool: True para desarrollo local, False para producción
    """
    # Nunca debug en producción
    if is_production():
        return False

    # En local, verificar variable explícita
    return os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')


def get_log_level():
    """
    Obtiene el nivel de logging apropiado

    Returns:
        str: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
    """
    if is_production():
        return os.environ.get('LOG_LEVEL', 'INFO')
    else:
        return os.environ.get('LOG_LEVEL', 'DEBUG')


# Configuración consolidada
class Config:
    """Clase de configuración que se adapta al entorno"""

    def __init__(self):
        self.ENV = 'production' if is_production() else 'development'
        self.DEBUG = get_debug_mode()
        self.TESTING = False

        # Base de datos (PostgreSQL obligatorio)
        self.SQLALCHEMY_DATABASE_URI = get_database_url()
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.SQLALCHEMY_ECHO = False  # Desactivado temporalmente para debug limpio
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,  # Verificar conexiones antes de usarlas
            'pool_recycle': 300,    # Reciclar conexiones cada 5 minutos
        }

        # Seguridad
        self.SECRET_KEY = get_secret_key()

        # Redis
        self.REDIS_URL = get_redis_url()

        # Logging
        self.LOG_LEVEL = get_log_level()

        # Cloudinary (mismo en todos los entornos)
        self.CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
        self.CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
        self.CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

        # CORS
        self.CORS_ORIGINS = '*' if not is_production() else os.environ.get('CORS_ORIGINS', '*')

    def __repr__(self):
        return f'<Config: {get_environment_name()}>'


def print_environment_info():
    """Imprime información del entorno al iniciar la aplicación"""
    print("\n" + "="*60)
    print(f"🚀 CLIP Comparador V2 - {get_environment_name()}")
    print("="*60)
    print(f"📍 Environment: {os.environ.get('FLASK_ENV', 'development')}")

    try:
        db_url = get_database_url()
        # Ocultar password en el log
        if '@' in db_url:
            parts = db_url.split('@')
            user_part = parts[0].split('://')[-1].split(':')[0]
            host_part = '@'.join(parts[1:])
            db_display = f"postgresql://{user_part}:****@{host_part}"
        else:
            db_display = db_url
        print(f"🗄️  Database: {db_display[:60]}...")
    except ValueError as e:
        print(f"❌ Database: ERROR - {str(e).split(chr(10))[0]}")

    print(f"🔐 Redis: {'Configured' if get_redis_url() else 'Not configured (using memory cache)'}")
    print(f"🐛 Debug Mode: {get_debug_mode()}")
    print(f"📝 Log Level: {get_log_level()}")

    if is_production():
        print(f"☁️  Railway Environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'N/A')}")
    else:
        print(f"💻 Local Development: PostgreSQL required")

    print("="*60 + "\n")
