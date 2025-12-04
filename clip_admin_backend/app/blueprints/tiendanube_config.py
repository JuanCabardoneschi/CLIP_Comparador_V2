"""
Blueprint para configuración de app Tiendanube
"""
from flask import Blueprint, render_template, request, jsonify, session
from app.models.client import Client
from app.models.tiendanube_integration import TiendanubeIntegration
from app.models.user import User
from app import db
from urllib.parse import urlparse
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
    Página de configuración de la app (para el panel de Tiendanube)
    Identifica la tienda desde el Referer, valida seguridad y crea sesión
    """
    logger.info("=" * 80)
    logger.info("TIENDANUBE CONFIG REQUEST RECEIVED")
    logger.info("=" * 80)

    # Extraer información del request
    referer = request.headers.get('Referer', '')
    remote_ip = request.remote_addr

    logger.info(f"URL: {request.url}")
    logger.info(f"Referer: {referer}")
    logger.info(f"Remote IP: {remote_ip}")

    # ✅ PASO 1: VALIDAR REFERER
    if not validate_tiendanube_referer(referer):
        logger.error(f"❌ SEGURIDAD: Intento de acceso desde Referer no autorizado")
        return render_unauthorized_page(), 403

    # ✅ PASO 2: EXTRAER TIENDA DEL REFERER
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

    logger.info("=" * 80)

    # ✅ PASO 5: RENDERIZAR PÁGINA DE CONFIGURACIÓN CON DATOS
    api_key = client.api_key
    widget_url_api = f'https://clipcomparadorv2-production.up.railway.app/tiendanube/widget?api_key={api_key}'

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CLIP Comparador - Configuración</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{
                color: #1f2937;
                margin-bottom: 10px;
                font-size: 32px;
            }}
            .subtitle {{
                color: #6b7280;
                margin-bottom: 30px;
                font-size: 18px;
            }}
            .success-icon {{
                font-size: 64px;
                text-align: center;
                margin-bottom: 20px;
            }}
            .section {{
                margin: 30px 0;
                padding: 20px;
                background: #f9fafb;
                border-radius: 10px;
                border-left: 4px solid #667eea;
            }}
            .section h2 {{
                color: #374151;
                margin-bottom: 15px;
                font-size: 20px;
            }}
            .section p {{
                color: #6b7280;
                line-height: 1.6;
                margin-bottom: 10px;
            }}
            .code-block {{
                background: #1f2937;
                color: #10b981;
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 14px;
                overflow-x: auto;
                margin: 15px 0;
                word-break: break-all;
            }}
            .button {{
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 12px 30px;
                border-radius: 8px;
                text-decoration: none;
                margin-top: 20px;
                transition: background 0.3s;
                text-align: center;
            }}
            .button:hover {{
                background: #5568d3;
            }}
            .store-info {{
                background: #dbeafe;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                border: 2px solid #3b82f6;
            }}
            .store-info strong {{
                color: #1e40af;
            }}
            .security-badge {{
                display: inline-block;
                background: #d1fae5;
                color: #065f46;
                padding: 8px 12px;
                border-radius: 20px;
                font-size: 12px;
                margin-top: 10px;
                font-weight: bold;
            }}
            .steps {{
                counter-reset: step;
            }}
            .step {{
                position: relative;
                padding-left: 50px;
                margin: 25px 0;
            }}
            .step:before {{
                counter-increment: step;
                content: counter(step);
                position: absolute;
                left: 0;
                top: 0;
                width: 35px;
                height: 35px;
                background: #667eea;
                color: white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
            }}
            .step h3 {{
                color: #1f2937;
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>¡App configurada correctamente!</h1>
            <p class="subtitle">Tu tienda ya tiene búsqueda visual con inteligencia artificial</p>

            <div class="store-info">
                <strong>🏪 Tienda:</strong> {client.name}<br>
                <strong>🔑 Store ID:</strong> {integration.store_id}<br>
                <strong>🌐 Dominio:</strong> {integration.store_domain}<br>
                <span class="security-badge">🔒 Conectada de forma segura</span>
            </div>

            <div class="section">
                <h2>🎯 ¿Cómo funciona?</h2>
                <p>CLIP Comparador permite a tus clientes buscar productos usando imágenes o texto.
                La inteligencia artificial encuentra productos similares en tu catálogo automáticamente.</p>
            </div>

            <div class="section">
                <h2>📋 Próximos Pasos</h2>
                <div class="steps">
                    <div class="step">
                        <h3>Agregar enlace en tu menú</h3>
                        <p>Ve a <strong>Tienda online → Navegación → Menú principal</strong></p>
                        <p>Agregá un nuevo enlace con la URL de abajo</p>
                    </div>

                    <div class="step">
                        <h3>URL del Buscador</h3>
                        <div class="code-block">{widget_url_api}</div>
                        <p style="margin-top: 10px;">Usá esta URL para enlazar el buscador visual en tu menú</p>
                    </div>

                    <div class="step">
                        <h3>Botón Flotante (Opcional)</h3>
                        <p>Si tenés un plan pago, podés agregar un botón flotante en tu tema:</p>
                        <div class="code-block">&lt;script src="https://clipcomparadorv2-production.up.railway.app/static/tiendanube-floating-button.js"&gt;&lt;/script&gt;</div>
                    </div>

                    <div class="step">
                        <h3>¡Listo! 🎉</h3>
                        <p>Tus clientes ya pueden buscar por imágenes desde el menú de tu tienda</p>
                    </div>
                </div>
            </div>

            <a href="{widget_url_api}" target="_blank" class="button">Probar Buscador</a>
        </div>
    </body>
    </html>
    """

    return html

    # Si no encontramos integración, mostrar página de error
    if not integration or not client:
        error_html = """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Error - CLIP Comparador</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
                h1 { color: #1f2937; margin-bottom: 20px; }
                p { color: #6b7280; line-height: 1.6; }
                .code {
                    background: #f3f4f6;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 20px 0;
                    word-break: break-all;
                    font-family: monospace;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error-icon">❌</div>
                <h1>No se pudo identificar tu tienda</h1>
                <p>Parece que accediste desde una URL no registrada en nuestro sistema.</p>
                <p>Por favor, asegúrate de estar accediendo desde el panel de administración de tu tienda en TiendaNube.</p>
                <div class="code">Subdomain detectado: """ + (store_subdomain or "No disponible") + """</div>
                <p style="color: #9ca3af; font-size: 14px; margin-top: 20px;">
                    Si creés que esto es un error, contactá a soporte.
                </p>
            </div>
        </body>
        </html>
        """
        return error_html, 400

    # Obtener API Key del cliente
    api_key = client.api_key
    widget_url_api = f'https://clipcomparadorv2-production.up.railway.app/tiendanube/widget?api_key={api_key}'

    # HTML de configuración (con datos de la tienda identificada)
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CLIP Comparador - Configuración</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{
                color: #1f2937;
                margin-bottom: 10px;
                font-size: 32px;
            }}
            .subtitle {{
                color: #6b7280;
                margin-bottom: 30px;
                font-size: 18px;
            }}
            .success-icon {{
                font-size: 64px;
                text-align: center;
                margin-bottom: 20px;
            }}
            .section {{
                margin: 30px 0;
                padding: 20px;
                background: #f9fafb;
                border-radius: 10px;
                border-left: 4px solid #667eea;
            }}
            .section h2 {{
                color: #374151;
                margin-bottom: 15px;
                font-size: 20px;
            }}
            .section p {{
                color: #6b7280;
                line-height: 1.6;
                margin-bottom: 10px;
            }}
            .code-block {{
                background: #1f2937;
                color: #10b981;
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 14px;
                overflow-x: auto;
                margin: 15px 0;
                word-break: break-all;
            }}
            .button {{
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 12px 30px;
                border-radius: 8px;
                text-decoration: none;
                margin-top: 20px;
                transition: background 0.3s;
                text-align: center;
            }}
            .button:hover {{
                background: #5568d3;
            }}
            .store-info {{
                background: #dbeafe;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .store-info strong {{
                color: #1e40af;
            }}
            .steps {{
                counter-reset: step;
            }}
            .step {{
                position: relative;
                padding-left: 50px;
                margin: 25px 0;
            }}
            .step:before {{
                counter-increment: step;
                content: counter(step);
                position: absolute;
                left: 0;
                top: 0;
                width: 35px;
                height: 35px;
                background: #667eea;
                color: white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
            }}
            .step h3 {{
                color: #1f2937;
                margin-bottom: 10px;
            }}
            .status-badge {{
                display: inline-block;
                background: #d1fae5;
                color: #065f46;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                margin: 10px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>¡App instalada correctamente!</h1>
            <p class="subtitle">Tu tienda ahora tiene búsqueda visual con inteligencia artificial</p>

            <div class="store-info">
                <strong>Tienda:</strong> {client.name}<br>
                <strong>Store ID:</strong> {store_id}<br>
                <strong>Dominio:</strong> {integration.store_domain}<br>
                <span class="status-badge">✅ Conectada</span>
            </div>

            <div class="section">
                <h2>🎯 ¿Cómo funciona?</h2>
                <p>CLIP Comparador permite a tus clientes buscar productos usando imágenes o texto.
                La inteligencia artificial encuentra productos similares en tu catálogo.</p>
            </div>

            <div class="section">
                <h2>📋 Cómo agregar la búsqueda a tu tienda</h2>
                <div class="steps">
                    <div class="step">
                        <h3>Agregar enlace en el menú</h3>
                        <p>Ve a <strong>Tienda online → Navegación → Menú principal</strong></p>
                        <p>Agregá un nuevo enlace:</p>
                        <ul style="margin-top: 10px; padding-left: 20px;">
                            <li><strong>Texto:</strong> Búsqueda con IA</li>
                            <li><strong>URL:</strong> Copiá la URL de abajo</li>
                        </ul>
                    </div>

                    <div class="step">
                        <h3>URL del comparador</h3>
                        <div class="code-block">{widget_url_api}</div>
                        <p style="margin-top: 10px;">El enlace abrirá el buscador visual en una nueva pestaña</p>
                    </div>

                    <div class="step">
                        <h3>Alternativa: Botón flotante</h3>
                        <p>Si tenés un plan pago de TiendaNube, podés editar el código del tema y agregar:</p>
                        <div class="code-block">&lt;script src="https://clipcomparadorv2-production.up.railway.app/static/tiendanube-floating-button.js"&gt;&lt;/script&gt;</div>
                        <p style="margin-top: 10px;">Esto agregará un botón morado flotante en todas las páginas</p>
                    </div>

                    <div class="step">
                        <h3>¡Listo!</h3>
                        <p>Tus clientes ya pueden buscar productos con imágenes desde el menú de tu tienda</p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>🔗 URL del Widget</h2>
                <div class="code-block">{widget_url_api}</div>
                <p>Esta es tu URL única de acceso al widget de búsqueda.</p>
            </div>

            <a href="{widget_url_api}" target="_blank" class="button">Ver Demo del Widget</a>
        </div>
    </body>
    </html>
    """

    return html
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
            scripts = response.json()
            # Verificar si nuestro script ya está instalado
            for script in scripts:
                if script.get('src') == SCRIPT_URL:
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
