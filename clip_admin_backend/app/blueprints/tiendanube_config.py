"""
Blueprint para configuración de app Tiendanube
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.models.client import Client
from app.models.tiendanube_integration import TiendanubeIntegration
from app.models.user import User
from app import db
from urllib.parse import urlparse
from flask_login import login_user
import logging
import requests
import hashlib
import hmac

logger = logging.getLogger(__name__)

bp = Blueprint('tiendanube_config', __name__, url_prefix='/tiendanube')

# Configuración de Tiendanube
TIENDANUBE_API_BASE = 'https://api.tiendanube.com/v1'
SCRIPT_URL = 'https://clipcomparadorv2-production.up.railway.app/static/tiendanube-floating-button.js'
ALLOWED_REFERER_DOMAINS = ['.mitiendanube.com']  # Solo desde TiendaNube


def validate_tiendanube_referer(referer_header):
    """
    Valida que el Referer sea de un dominio permitido de TiendaNube
    Retorna True si es válido, False si no
    """
    if not referer_header:
        logger.warning("⚠️ SEGURIDAD: Intento de acceso sin Referer")
        return False

    # Parsear el Referer
    try:
        parsed = urlparse(referer_header)
        host = parsed.netloc.lower()

        # Verificar que sea de un dominio permitido
        for allowed_domain in ALLOWED_REFERER_DOMAINS:
            if host.endswith(allowed_domain):
                logger.info(f"✅ Referer válido: {host}")
                return True

        logger.warning(f"⚠️ SEGURIDAD: Referer de dominio no permitido: {host}")
        return False
    except Exception as e:
        logger.error(f"❌ Error validando Referer: {str(e)}")
        return False


def create_tiendanube_session(integration):
    """
    Crea una sesión especial para la tienda de TiendaNube
    Esta sesión permite acceso a funcionalidades admin sin login tradicional
    """
    try:
        # Crear token seguro basado en store_id
        token_data = f"{integration.store_id}:{integration.client_id}:{integration.id}"
        token = hashlib.sha256(token_data.encode()).hexdigest()

        # Guardar en sesión
        session['tiendanube_store_id'] = integration.store_id
        session['tiendanube_client_id'] = str(integration.client_id)
        session['tiendanube_integration_id'] = str(integration.id)
        session['tiendanube_token'] = token
        session['tiendanube_mode'] = True  # Modo TiendaNube activo

        logger.info(f"✅ Sesión TiendaNube creada para store_id={integration.store_id}, client_id={integration.client_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error creando sesión TiendaNube: {str(e)}")
        return False

@bp.route('/widget')
def widget():
    """
    Página del widget que se embebe en Tiendanube
    Muestra el comparador visual completo
    """
    # Permitir pasar la API Key por querystring: ?api_key=...
    api_key = request.args.get('api_key') or request.args.get('key') or request.args.get('apikey')
    # Capturar Referer para permitir "volver a la tienda" en el widget
    referer = request.headers.get('Referer')
    return render_template('tiendanube_widget.html', api_key=api_key, referer=referer)

@bp.route('/config')
def config():
    """
    Endpoint de configuración TiendaNube - Auto-login y redirección

    Flujo:
    1. Valida Referer sea desde .mitiendanube.com
    2. Identifica tienda desde subdomain del Referer
    3. Busca usuario STORE_ADMIN del cliente
    4. Auto-login del usuario con Flask-Login
    5. Redirección a dashboard

    Usuario final: Click en "Configurar" en TiendaNube → Auto-login → Dashboard
    """
    logger.info("=" * 80)
    logger.info("TIENDANUBE CONFIG REQUEST - AUTO-LOGIN")
    logger.info("=" * 80)

    # Extraer información del request
    referer = request.headers.get('Referer', '')
    remote_ip = request.remote_addr

    logger.info(f"URL: {request.url}")
    logger.info(f"Referer: {referer}")
    logger.info(f"Remote IP: {remote_ip}")

    # ✅ PASO 1: VALIDAR REFERER - Solo desde .mitiendanube.com
    if not validate_tiendanube_referer(referer):
        logger.error(f"❌ SEGURIDAD: Intento de acceso desde Referer no autorizado")
        return render_unauthorized_page(), 403

    # ✅ PASO 2: EXTRAER TIENDA DEL REFERER (ej: "testclip" de "https://testclip.mitiendanube.com/...")
    store_subdomain = None
    try:
        parsed = urlparse(referer)
        store_subdomain = parsed.netloc.split('.')[0]  # "testclip"
        logger.info(f"Store subdomain extraído: {store_subdomain}")
    except Exception as e:
        logger.error(f"❌ Error extrayendo subdomain: {str(e)}")
        return render_error_page("Error procesando solicitud"), 400

    # ✅ PASO 3: BUSCAR INTEGRACIÓN EN BD
    integration = None
    client = None

    try:
        integration = TiendanubeIntegration.query.filter(
            TiendanubeIntegration.store_domain.ilike(f'%{store_subdomain}%')
        ).first()

        if integration:
            client = integration.client
            logger.info(f"✅ Integración encontrada: store_id={integration.store_id}, client_id={client.id}")
        else:
            logger.warning(f"⚠️ No se encontró integración para subdomain: {store_subdomain}")
            return render_error_page(f"Tienda no encontrada: {store_subdomain}"), 404
    except Exception as e:
        logger.error(f"❌ Error buscando integración: {str(e)}")
        return render_error_page("Error en base de datos"), 500

    # ✅ PASO 4: CREAR SESIÓN SEGURA
    try:
        create_tiendanube_session(integration)
        logger.info(f"✅ Sesión TiendaNube creada correctamente")
    except Exception as e:
        logger.error(f"❌ Error creando sesión: {str(e)}")
        return render_error_page("Error creando sesión"), 500

    # ✅ PASO 5: ENCONTRAR Y AUTO-LOGIN DEL USUARIO STORE_ADMIN
    try:
        # Buscar usuario STORE_ADMIN del cliente
        store_admin_user = User.query.filter_by(
            client_id=client.id,
            role='STORE_ADMIN',
            active=True
        ).first()

        if not store_admin_user:
            logger.error(f"❌ No se encontró usuario STORE_ADMIN activo para client_id={client.id}")
            return render_error_page("No se encontró usuario administrativo para esta tienda"), 500

        logger.info(f"✅ Usuario STORE_ADMIN encontrado: {store_admin_user.email}")

        # Auto-login sin mostrar formulario de login tradicional
        login_user(store_admin_user, remember=True)
        logger.info(f"✅ Usuario auto-logueado: {store_admin_user.email}")

    except Exception as e:
        logger.error(f"❌ Error en auto-login: {str(e)}")
        return render_error_page(f"Error en autenticación: {str(e)}"), 500

    # ✅ PASO 6: REDIRECCIONAR A DASHBOARD
    logger.info("=" * 80)
    logger.info(f"✅ AUTO-LOGIN EXITOSO - Redirigiendo a dashboard")
    logger.info("=" * 80)

    return redirect(url_for('dashboard.index'))


def install_floating_button(store_id, access_token):
    """
    Instala automáticamente el botón flotante en la tienda Tiendanube
    Returns True si se instaló correctamente, False si falló
    """
    try:
        # Verificar si ya existe el script
        headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIP Comparador V2',
            'Content-Type': 'application/json'
        }

        # Listar scripts existentes
        response = requests.get(
            f'{TIENDANUBE_API_BASE}/{store_id}/scripts',
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            response_data = response.json()
            # Asegurar que obtenemos una lista de scripts
            scripts = response_data if isinstance(response_data, list) else (
                response_data.get('response', []) if isinstance(response_data, dict) else []
            )
            # Verificar si nuestro script ya está instalado
            for script in scripts:
                if isinstance(script, dict) and script.get('src') == SCRIPT_URL:
                    logger.info(f"Script ya instalado en tienda {store_id}")
                    return True

        # Instalar el script
        script_data = {
            'src': SCRIPT_URL,
            'event': 'onload',
            'where': 'footer'
        }

        response = requests.post(
            f'{TIENDANUBE_API_BASE}/{store_id}/scripts',
            headers=headers,
            json=script_data,
            timeout=10
        )

        if response.status_code in [200, 201]:
            logger.info(f"✅ Botón flotante instalado en tienda {store_id}")
            return True
        else:
            logger.error(f"❌ Error instalando script: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Error en install_floating_button: {str(e)}")
        return False


def render_unauthorized_page():
    """Renderiza página de acceso no autorizado (sin Referer válido)"""
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Acceso No Autorizado - CLIP Comparador</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #f87171 0%, #dc2626 100%);
                padding: 40px 20px;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                max-width: 600px;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
            }
            .error-icon { font-size: 64px; margin-bottom: 20px; }
            h1 { color: #1f2937; margin-bottom: 20px; font-size: 28px; }
            p { color: #6b7280; line-height: 1.6; margin: 15px 0; }
            .security-warning {
                background: #fee2e2;
                border-left: 4px solid #ef4444;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                color: #991b1b;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">🔒</div>
            <h1>Acceso No Autorizado</h1>
            <p>Esta página solo es accesible desde el panel de administración de TiendaNube.</p>
            <div class="security-warning">
                <strong>🚨 Razón:</strong> No se detectó una solicitud válida desde TiendaNube
            </div>
            <p style="color: #9ca3af; font-size: 14px; margin-top: 20px;">
                Si creés que esto es un error, verifica que estés accediendo desde tu tienda en TiendaNube.
            </p>
        </div>
    </body>
    </html>
    """
    return html


def render_error_page(error_message):
    """Renderiza página de error genérico"""
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Error - CLIP Comparador</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px 20px;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .container {{
                max-width: 600px;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
            }}
            .error-icon {{ font-size: 64px; margin-bottom: 20px; }}
            h1 {{ color: #1f2937; margin-bottom: 20px; font-size: 28px; }}
            p {{ color: #6b7280; line-height: 1.6; }}
            .error-details {{
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                text-align: left;
                color: #92400e;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">❌</div>
            <h1>Error</h1>
            <div class="error-details">
                {error_message}
            </div>
            <p style="color: #9ca3af; font-size: 14px; margin-top: 20px;">
                Si persiste el problema, contactá a soporte.
            </p>
        </div>
    </body>
    </html>
    """
    return html
