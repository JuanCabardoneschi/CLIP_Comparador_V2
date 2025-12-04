"""
Blueprint para configuración de app Tiendanube
"""
from flask import Blueprint, render_template, request, jsonify
from app.models.client import Client
from app.models.tiendanube_integration import TiendanubeIntegration
from urllib.parse import urlparse
import logging
import requests

logger = logging.getLogger(__name__)

bp = Blueprint('tiendanube_config', __name__, url_prefix='/tiendanube')

# Configuración de Tiendanube
TIENDANUBE_API_BASE = 'https://api.tiendanube.com/v1'
SCRIPT_URL = 'https://clipcomparadorv2-production.up.railway.app/static/tiendanube-floating-button.js'

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
    Identifica la tienda desde el Referer y carga sus datos de BD
    """
    # LOG DETALLADO: Ver qué información manda TiendaNube
    logger.info("=" * 80)
    logger.info("TIENDANUBE CONFIG REQUEST RECEIVED")
    logger.info("=" * 80)
    logger.info(f"URL: {request.url}")
    logger.info(f"Query Parameters: {request.args.to_dict()}")
    
    # Extraer información
    referer = request.headers.get('Referer', '')
    logger.info(f"Referer: {referer}")
    
    # Intentar extraer store_subdomain del Referer
    store_subdomain = None
    store_id = None
    integration = None
    client = None
    
    if referer:
        try:
            parsed = urlparse(referer)
            # Ej: "testclip.mitiendanube.com" -> "testclip"
            store_subdomain = parsed.netloc.split('.')[0]
            logger.info(f"Store subdomain extraído del Referer: {store_subdomain}")
            
            # Buscar integración en BD por store_domain
            integration = TiendanubeIntegration.query.filter(
                TiendanubeIntegration.store_domain.ilike(f'%{store_subdomain}%')
            ).first()
            
            if integration:
                store_id = integration.store_id
                client = integration.client
                logger.info(f"✅ Integración encontrada: store_id={store_id}, client_id={client.id}")
            else:
                logger.warning(f"⚠️ No se encontró integración para store_domain '%{store_subdomain}%'")
        except Exception as e:
            logger.error(f"Error extrayendo info del Referer: {str(e)}")
    else:
        logger.warning("⚠️ No se recibió Referer en la solicitud")
    
    logger.info("=" * 80)
    
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
