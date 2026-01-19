"""
CLIP Comparador V2 - Backend Admin
Aplicación Flask para gestión de clientes y catálogos
"""

import os
import sys
import logging

# Configurar logging ANTES de cualquier otra cosa
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s in %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Añadir el directorio padre al path para las importaciones
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy

# Cargar variables de entorno
# Intentar cargar .env.local primero (desarrollo), luego .env (producción/fallback)
# Buscar en el directorio raíz del proyecto (un nivel arriba)
env_local_path = os.path.join(parent_dir, '.env.local')
env_path = os.path.join(parent_dir, '.env')

if os.path.exists(env_local_path):
    load_dotenv(env_local_path)
    print(f"📄 Cargando configuración desde {env_local_path} (desarrollo)")
elif os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"📄 Cargando configuración desde {env_path}")
else:
    load_dotenv()
    print("📄 Cargando configuración desde variables de entorno")

# Sin Redis: la caché es solo en memoria (ver services)

# Importar extensiones y modelos del paquete app
from app import db, login_manager, jwt
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

    # Importar configuración de entorno
    from app.config import Config, print_environment_info

    # Mostrar información del entorno
    print_environment_info()

    # Cargar configuración
    config = Config()
    app.config.from_object(config)

    # Inyectar credenciales Tiendanube en app.config desde variables de entorno
    # para que los blueprints las lean de forma consistente
    app.config['TIENDANUBE_CLIENT_ID'] = os.getenv('TIENDANUBE_CLIENT_ID', app.config.get('TIENDANUBE_CLIENT_ID'))
    app.config['TIENDANUBE_CLIENT_SECRET'] = os.getenv('TIENDANUBE_CLIENT_SECRET', app.config.get('TIENDANUBE_CLIENT_SECRET'))

    # PostgreSQL es obligatorio - no se permiten otras bases de datos
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

    # Sin Redis: las caches están en memoria dentro de los servicios

    # User loader para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        # print(f"👤 USER_LOADER: ¡INICIO! Cargando usuario con ID: {user_id} (tipo: {type(user_id)})")

        try:
            from app.models.user import User

            # print("👤 USER_LOADER: Importaciones exitosas")

            # UUID almacenado como String(36) en la base de datos
            # print(f"👤 USER_LOADER: Buscando con string ID: {user_id}")

            # Query con string UUID directamente
            user = User.query.filter_by(id=user_id).first()
            # print("👤 USER_LOADER: Query ejecutado")

            if user:
                # print(f"👤 USER_LOADER: ✅ Usuario encontrado - Email: {user.email}, Active: {user.active}")
                return user
            else:
                # print("👤 USER_LOADER: ❌ Usuario no encontrado en BD")
                return None

        except Exception as e:
            print(f"👤 USER_LOADER: ERROR GENERAL: {type(e).__name__}: {e}")
            import traceback
            print(f"👤 USER_LOADER: Traceback: {traceback.format_exc()}")
            return None
            return None

    # Registrar blueprints
    register_blueprints(app)

    # Headers anti-caché para desarrollo
    @app.before_request
    def before_request():
        """Log de requests para debug"""
        # print(f"🌐 REQUEST: {request.method} {request.path}")
        # print(f"🍪 COOKIES: {dict(request.cookies)}")
        # if hasattr(current_user, 'is_authenticated'):
        #     print(f"🌐 REQUEST: Usuario autenticado: {current_user.is_authenticated}")
        #     if current_user.is_authenticated:
        #         print(f"🌐 REQUEST: Usuario actual: {current_user.email}")
        # # Verificar session
        # from flask import session
        # print(f"🎫 SESSION: {dict(session)}")
        pass

    @app.after_request
    def after_request(response):
        """Agregar headers anti-caché en desarrollo y log response"""
        # print(f"🌐 RESPONSE: {response.status_code} para {request.path}")
        # print(f"🍪 SET-COOKIES: {response.headers.getlist('Set-Cookie')}")
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

    @app.template_filter("attribute_label")
    def attribute_label(key, client_id=None):
        """Obtiene el label de un atributo desde ProductAttributeConfig

        Args:
            key: El key del atributo (ej: 'color', 'talla')
            client_id: ID del cliente (opcional, si no se pasa usa current_user.client_id)

        Returns:
            El label configurado o el key capitalizado si no existe config
        """
        from app.models.product_attribute_config import ProductAttributeConfig
        from flask_login import current_user

        if not client_id and current_user and current_user.is_authenticated:
            client_id = current_user.client_id

        if client_id:
            config = ProductAttributeConfig.query.filter_by(
                client_id=client_id,
                key=key
            ).first()

            if config:
                return config.label

        # Fallback: capitalizar el key
        return key.replace('_', ' ').title()

    # Catch-all temporal para webhooks viejos de Tiendanube
    @app.route('/webhooks/tiendanube/<path:subpath>', methods=['POST', 'GET'])
    def catch_old_webhooks(subpath):
        """Intercepta webhooks viejos para debug"""
        import logging
        logger = logging.getLogger(__name__)

        store_id = request.headers.get('X-Linked-Nube-Info-Id', 'UNKNOWN')
        logger.warning(f"⚠️ WEBHOOK VIEJO detectado: /webhooks/tiendanube/{subpath}")
        logger.warning(f"   Store ID: {store_id}")
        logger.warning(f"   Headers: {dict(request.headers)}")

        try:
            payload = request.get_json()
            logger.warning(f"   Payload: {payload}")
        except:
            logger.warning(f"   Body: {request.data[:200]}")

        # Responder 204 para cortar reintentos del emisor y evitar saturación.
        # Mantener logs para diagnóstico.
        return ('', 204)
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

    # Blueprint de usuarios
    try:
        from app.blueprints.users import bp as users_bp
        app.register_blueprint(users_bp, url_prefix="/users")
        print("✓ Blueprint users registrado")
    except ImportError as e:
        print(f"✗ Error importando users blueprint: {e}")

    # Blueprint de categorías
    try:
        from app.blueprints.categories import bp as categories_bp
        app.register_blueprint(categories_bp, url_prefix="/categories")
        print("✓ Blueprint categories registrado")
    except ImportError as e:
        print(f"✗ Error importando categories blueprint: {e}")

    # Blueprint de exclusiones de pares de categorías eliminado (category_exclusions)

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

    # Blueprint de monitoreo del sistema (desactivado; métricas se ven en Railway)
    # try:
    #     from app.blueprints.system_monitor import bp as system_monitor_bp
    #     app.register_blueprint(system_monitor_bp)
    #     print("✓ Blueprint system_monitor registrado")
    # except ImportError as e:
    #     print(f"✗ Error importando system_monitor blueprint: {e}")

    # Blueprint de atributos de productos
    try:
        from app.blueprints.attributes import bp as attributes_bp
        app.register_blueprint(attributes_bp, url_prefix="/attributes")
        print("✓ Blueprint attributes registrado")
    except ImportError as e:
        print(f"✗ Error importando attributes blueprint: {e}")

    # Blueprint de configuración de búsqueda
    try:
        from app.blueprints.search_config import bp as search_config_bp
        app.register_blueprint(search_config_bp, url_prefix="/search-config")
        print("✓ Blueprint search_config registrado")
    except ImportError as e:
        print(f"✗ Error importando search_config blueprint: {e}")

    # Blueprint de inventario (gestión de stock)
    try:
        from app.blueprints.inventory import bp as inventory_bp
        app.register_blueprint(inventory_bp, url_prefix="/inventory")
        print("✓ Blueprint inventory registrado")
    except ImportError as e:
        print(f"✗ Error importando inventory blueprint: {e}")

    # Blueprint de API externa de inventario
    try:
        from app.blueprints.external_inventory import bp as external_inventory_bp
        app.register_blueprint(external_inventory_bp)
        print("✓ Blueprint external_inventory registrado")
    except ImportError as e:
        print(f"✗ Error importando external_inventory blueprint: {e}")

    # Blueprint de configuración del sistema (SuperAdmin)
    try:
        from app.blueprints.system_config_admin import bp as system_config_bp
        app.register_blueprint(system_config_bp, url_prefix="/admin/system-config")
        print("✓ Blueprint system_config_admin registrado")
    except ImportError as e:
        print(f"✗ Error importando system_config_admin blueprint: {e}")

    # Blueprint de búsqueda del widget (público)
    try:
        from app.blueprints.widget_search import widget_search_bp
        app.register_blueprint(widget_search_bp)
        print("✓ Blueprint widget_search registrado")
    except ImportError as e:
        print(f"✗ Error importando widget_search blueprint: {e}")
    except Exception as e:
        print(f"✗ Error registrando system_config_admin blueprint: {e}")

    # Blueprint de webhooks (WooCommerce)
    try:
        from app.blueprints.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp)
        print("✓ Blueprint webhooks registrado")
    except ImportError as e:
        print(f"✗ Error importando webhooks blueprint: {e}")

    # Blueprint GPT-4 Vision (detección de categorías)
    try:
        from app.blueprints.gpt4v_detection import gpt4v_bp
        app.register_blueprint(gpt4v_bp)
        print("✓ Blueprint gpt4v_detection registrado")
    except ImportError as e:
        print(f"✗ Error importando gpt4v_detection blueprint: {e}")
    except Exception as e:
        print(f"✗ Error registrando gpt4v_detection blueprint: {e}")

    # 🆕 Blueprint de búsqueda textual V2 (nuevo sistema con GPT-4 + CLIP)
    try:
        from app.blueprints.search_text import bp as search_text_bp
        app.register_blueprint(search_text_bp, url_prefix="/api")
        print("✓ Blueprint search_text V2 registrado (🆕 NUEVO)")
    except ImportError as e:
        print(f"✗ Error importando search_text blueprint: {e}")

    # 🆕 Blueprint de administración de perfiles de búsqueda
    try:
        from app.blueprints.search_profiles_admin import bp as search_profiles_admin_bp
        app.register_blueprint(search_profiles_admin_bp)
        print("✓ Blueprint search_profiles_admin registrado (🆕 NUEVO)")
    except ImportError as e:
        print(f"✗ Error importando search_profiles_admin blueprint: {e}")
    except Exception as e:
        print(f"✗ Error registrando search_text blueprint: {e}")

    # Blueprint de OAuth Tiendanube
    try:
        from app.blueprints.tiendanube_oauth import bp as tiendanube_oauth_bp
        app.register_blueprint(tiendanube_oauth_bp)
        print("✓ Blueprint tiendanube_oauth registrado")
    except ImportError as e:
        print(f"✗ Error importando tiendanube_oauth blueprint: {e}")
    except Exception as e:
        print(f"✗ Error registrando tiendanube_oauth blueprint: {e}")

    # Blueprint de configuración Tiendanube
    try:
        from app.blueprints.tiendanube_config import bp as tiendanube_config_bp
        app.register_blueprint(tiendanube_config_bp)
        print("✓ Blueprint tiendanube_config registrado")
    except ImportError as e:
        print(f"✗ Error importando tiendanube_config blueprint: {e}")
    except Exception as e:
        print(f"✗ Error registrando tiendanube_config blueprint: {e}")

    # Blueprint de administración Tiendanube
    try:
        from app.blueprints.tiendanube_admin import bp as tiendanube_admin_bp
        app.register_blueprint(tiendanube_admin_bp)
        print("✓ Blueprint tiendanube_admin registrado")
    except ImportError as e:
        print(f"✗ Error importando tiendanube_admin blueprint: {e}")
    except Exception as e:
        print(f"✗ Error registrando tiendanube_admin blueprint: {e}")

    # Blueprint de webhooks Tiendanube
    try:
        from app.blueprints.tiendanube_webhooks import tiendanube_webhooks_bp
        app.register_blueprint(tiendanube_webhooks_bp)
        print("✓ Blueprint tiendanube_webhooks registrado")
    except ImportError as e:
        print(f"✗ Error importando tiendanube_webhooks blueprint: {e}")
    except Exception as e:
        print(f"✗ Error registrando tiendanube_webhooks blueprint: {e}")

    # 🆕 Registrar módulos personalizados de búsqueda por cliente
    try:
        from app.search_modules import register_client_module

        # Eve's Store
        import app.search_modules.search_client_eve_s_store as eve_module
        register_client_module("eve-s-store", eve_module)

        print("✓ Módulos de búsqueda personalizados registrados")
    except ImportError as e:
        print(f"⚠️ Advertencia: No se pudieron cargar módulos personalizados: {e}")
    except Exception as e:
        print(f"⚠️ Error registrando módulos personalizados: {e}")

# Crear instancia de la aplicación
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    print("🚀 Iniciando CLIP Comparador V2 - Backend Admin v2.1.0")
    print(f"📍 Puerto: {port}")
    print(f"🔧 Debug: {debug}")
    print(f"🗄️ Base de datos: {os.getenv('DATABASE_URL', 'No configurada')}")

    # Precarga condicional de modelos (CLIP y LM) controlada por system_config
    try:
        # Leer configuración desde system_config.json
        from app.utils.system_config import system_config
        preload_clip = system_config.get('clip', 'preload', False)
        preload_text = system_config.get('text', 'preload', False)

        if preload_clip:
            from app.blueprints.embeddings import get_clip_model
            print("⚡ Precargando CLIP al iniciar (configuración del sistema)")
            get_clip_model()
            print("✅ CLIP precargado correctamente")
        else:
            print("⚡ CLIP se cargará al primer uso (lazy loading configurado)")

        if preload_text:
            from app.utils.llm_query_normalizer import get_model as get_minilm_model
            print("⚡ Precargando MiniLM al iniciar (configuración del sistema)")
            # Validar spaCy solo si se solicitó precarga de texto
            try:
                import spacy
                model_name = os.getenv("SPACY_MODEL", "es_core_news_md")
                _ = spacy.load(model_name, disable=["parser", "ner", "textcat"])
                print(f"✅ spaCy validado correctamente ({model_name})")
            except Exception as spacy_err:
                print(f"⚠️ spaCy no disponible al inicio: {spacy_err} (se cargará on-demand)")
            get_minilm_model()
            print("✅ MiniLM precargado correctamente")
        else:
            print("⚡ MiniLM se cargará al primer uso (lazy loading configurado)")
    except Exception as e:
        # En caso de fallo de lectura de configuración, continuar en lazy
        print(f"⚠️  Error en configuración de precarga, usando lazy loading: {e}")

    app.run(host="0.0.0.0", port=port, debug=debug)
