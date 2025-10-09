"""
CLIP Comparador V2 - Backend Admin
Aplicación Flask para gestión de clientes y catálogos
"""

import os
import sys

# Añadir el directorio padre al path para las importaciones
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

import redis
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Cargar variables de entorno
load_dotenv()

# Cliente Redis global
redis_client = None

# Importar extensiones y modelos del paquete app
from app import db, migrate, login_manager, jwt
def create_app(config_name=None):
    """Factory pattern para crear la aplicación Flask"""

    # Configurar paths absolutos para templates y static
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'app', 'templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'app', 'static'))  # Usar app/static para CSS/JS

    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)

    # Debug: Verificar rutas de templates
    print(f"📁 Template folder: {template_dir}")
    print(f"📁 Static folder: {static_dir}")
    print(f"📁 Template folder exists: {os.path.exists(template_dir)}")

    # Configuración
    secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    app.config["SECRET_KEY"] = secret_key
    print(f"🔑 SECRET_KEY configurado: {secret_key[:10]}... (longitud: {len(secret_key)})")

    # Configurar ruta absoluta para la base de datos
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("sqlite:///") and not os.path.isabs(database_url[10:]):
        # Convertir ruta relativa a absoluta desde la raíz del proyecto
        db_path = os.path.join(parent_dir, database_url[10:])
        database_url = f"sqlite:///{db_path}"

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = os.getenv(
        "JWT_SECRET_KEY", "jwt-secret-key"
    )
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # No expiran por defecto

    # Configuración para archivos grandes (imágenes hasta 50MB)
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max
    app.config["UPLOAD_FOLDER"] = os.path.join(current_dir, 'static', 'uploads')  # Usar static/ en lugar de app/static
    app.config["MAX_FILE_SIZE"] = 50 * 1024 * 1024  # 50MB por archivo
    app.config["ALLOWED_EXTENSIONS"] = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}

    # Configuración de sesiones para Flask-Login (muy permisiva para debugging)
    app.config["SESSION_COOKIE_SECURE"] = False  # Para HTTP en desarrollo
    app.config["SESSION_COOKIE_HTTPONLY"] = False  # Permitir acceso JS para debugging
    app.config["SESSION_COOKIE_SAMESITE"] = None  # Más permisivo
    app.config["SESSION_PERMANENT"] = True  # Hacer sesiones permanentes
    app.config["PERMANENT_SESSION_LIFETIME"] = 7200  # 2 horas (más tiempo)
    app.config["SESSION_COOKIE_NAME"] = "clip_session"  # Nombre específico
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True  # Renovar sesión en cada request

    print("⚙️ Configuración de sesiones:")
    print(f"   SESSION_COOKIE_SECURE: {app.config.get('SESSION_COOKIE_SECURE')}")
    print(f"   SESSION_COOKIE_HTTPONLY: {app.config.get('SESSION_COOKIE_HTTPONLY')}")
    print(f"   SESSION_COOKIE_SAMESITE: {app.config.get('SESSION_COOKIE_SAMESITE')}")
    print(f"   SESSION_COOKIE_NAME: {app.config.get('SESSION_COOKIE_NAME')}")
    print(f"   SESSION_PERMANENT: {app.config.get('SESSION_PERMANENT')}")
    print(f"   PERMANENT_SESSION_LIFETIME: {app.config.get('PERMANENT_SESSION_LIFETIME')}")

    # Configuración anti-caché para desarrollo
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Desactivar caché de templates en desarrollo
    if os.getenv("FLASK_DEBUG", "False").lower() == "true":
        app.jinja_env.auto_reload = True
        app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Inicializar extensiones con la app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    jwt.init_app(app)

    # Configurar CORS para permitir requests desde el widget
    CORS(app, origins=["*"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "X-API-Key", "Authorization"],
         supports_credentials=False)
    print("🌐 CORS configurado para permitir requests externos")

    # Configurar Flask-Login
    login_manager.login_view = "auth.login"
    login_manager.login_message = (
        "Por favor inicia sesión para acceder a " "esta página."
    )
    login_manager.login_message_category = "info"

    # Configurar Redis
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(redis_url, decode_responses=True)

    # User loader para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        print(f"👤 USER_LOADER: ¡INICIO! Cargando usuario con ID: {user_id} (tipo: {type(user_id)})")

        try:
            from app.models.user import User

            print("👤 USER_LOADER: Importaciones exitosas")

            # Usar directamente el string, no convertir a UUID object
            # SQLite almacena UUIDs como strings
            print(f"👤 USER_LOADER: Buscando con string ID: {user_id}")

            # Usar query.filter_by con el string directamente
            user = User.query.filter_by(id=user_id).first()
            print("👤 USER_LOADER: Query ejecutado con string")

            if user:
                print(f"👤 USER_LOADER: ✅ Usuario encontrado - Email: {user.email}, Active: {user.active}")
                return user
            else:
                print("👤 USER_LOADER: ❌ Usuario no encontrado en BD")
                return None

        except Exception as e:
            print(f"👤 USER_LOADER: ERROR GENERAL: {type(e).__name__}: {e}")
            import traceback
            print(f"👤 USER_LOADER: Traceback: {traceback.format_exc()}")
            return None

    # Registrar blueprints
    register_blueprints(app)

    # Headers anti-caché para desarrollo
    @app.before_request
    def before_request():
        """Log de requests para debug"""
        print(f"🌐 REQUEST: {request.method} {request.path}")
        print(f"🍪 COOKIES: {dict(request.cookies)}")
        if hasattr(current_user, 'is_authenticated'):
            print(f"🌐 REQUEST: Usuario autenticado: {current_user.is_authenticated}")
            if current_user.is_authenticated:
                print(f"🌐 REQUEST: Usuario actual: {current_user.email}")

        # Verificar session
        from flask import session
        print(f"🎫 SESSION: {dict(session)}")

    @app.after_request
    def after_request(response):
        """Agregar headers anti-caché en desarrollo y log response"""
        print(f"🌐 RESPONSE: {response.status_code} para {request.path}")
        print(f"🍪 SET-COOKIES: {response.headers.getlist('Set-Cookie')}")
        if os.getenv("FLASK_DEBUG", "False").lower() == "true":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # Context processors
    @app.context_processor
    def inject_user():
        """Inyectar usuario actual en todos los templates"""
        from flask_login import current_user

        return dict(current_user=current_user)

    # Filtros de template personalizados
    @app.template_filter("datetime_format")
    def datetime_format(value, format="%d/%m/%Y %H:%M"):
        if value is None:
            return ""
        return value.strftime(format)

    @app.template_filter("currency")
    def currency_format(value):
        if value is None:
            return "N/A"
        return f"${value:,.2f}"

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Manejar archivos demasiado grandes"""
        flash("Los archivos subidos son demasiado grandes. El tamaño máximo permitido es 50MB por archivo.", "error")
        return render_template("errors/413.html"), 413

    # Ruta adicional para servir archivos de uploads
    @app.route('/static/uploads/<path:filename>')
    def uploaded_file(filename):
        """Servir archivos desde el directorio de uploads"""
        from flask import send_from_directory
        uploads_dir = os.path.join(current_dir, 'static', 'uploads')
        return send_from_directory(uploads_dir, filename)

    return app


def register_blueprints(app):
    """Registrar todos los blueprints"""

    # Blueprint principal
    try:
        from app.blueprints.main import bp as main_bp
        app.register_blueprint(main_bp)
        print("✓ Blueprint main registrado")
    except ImportError as e:
        print(f"✗ Error importando main blueprint: {e}")

    # Blueprint de autenticación
    try:
        from app.blueprints.auth import bp as auth_bp
        app.register_blueprint(auth_bp, url_prefix="/auth")
        print("✓ Blueprint auth registrado")
    except ImportError as e:
        print(f"✗ Error importando auth blueprint: {e}")

    # Blueprint de dashboard
    try:
        from app.blueprints.dashboard import bp as dashboard_bp
        app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
        print("✓ Blueprint dashboard registrado")
    except ImportError as e:
        print(f"✗ Error importando dashboard blueprint: {e}")

    # Blueprint de clientes
    try:
        from app.blueprints.clients import bp as clients_bp
        app.register_blueprint(clients_bp, url_prefix="/clients")
        print("✓ Blueprint clients registrado")
    except ImportError as e:
        print(f"✗ Error importando clients blueprint: {e}")

    # Blueprint de categorías
    try:
        from app.blueprints.categories import bp as categories_bp
        app.register_blueprint(categories_bp, url_prefix="/categories")
        print("✓ Blueprint categories registrado")
    except ImportError as e:
        print(f"✗ Error importando categories blueprint: {e}")

    # Blueprint de productos
    try:
        from app.blueprints.products import bp as products_bp
        app.register_blueprint(products_bp, url_prefix="/products")
        print("✓ Blueprint products registrado")
    except ImportError as e:
        print(f"✗ Error importando products blueprint: {e}")

    # Blueprint de imágenes
    try:
        from app.blueprints.images import bp as images_bp
        app.register_blueprint(images_bp, url_prefix="/images")
        print("✓ Blueprint images registrado")
    except ImportError as e:
        print(f"✗ Error importando images blueprint: {e}")

    # Blueprint de analytics
    try:
        from app.blueprints.analytics import bp as analytics_bp
        app.register_blueprint(analytics_bp, url_prefix="/analytics")
        print("✓ Blueprint analytics registrado")
    except ImportError as e:
        print(f"✗ Error importando analytics blueprint: {e}")

    # Blueprint de API interna
    try:
        from app.blueprints.api import bp as api_bp
        app.register_blueprint(api_bp, url_prefix="/api")
        print("✓ Blueprint api registrado")
    except ImportError as e:
        print(f"✗ Error importando api blueprint: {e}")

    # Blueprint de embeddings CLIP
    try:
        from app.blueprints.embeddings import bp as embeddings_bp
        app.register_blueprint(embeddings_bp, url_prefix="/embeddings")
        print("✓ Blueprint embeddings registrado")
    except ImportError as e:
        print(f"✗ Error importando embeddings blueprint: {e}")


# Crear instancia de la aplicación
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    print("🚀 Iniciando CLIP Comparador V2 - Backend Admin")
    print(f"📍 Puerto: {port}")
    print(f"🔧 Debug: {debug}")
    print(f"🗄️ Base de datos: {os.getenv('DATABASE_URL', 'No configurada')}")

    app.run(host="0.0.0.0", port=port, debug=debug)
