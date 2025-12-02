"""
Blueprint para configuración de app Tiendanube
"""
from flask import Blueprint, render_template, request, jsonify
from app.models.client import Client
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
    return render_template('tiendanube_widget.html', api_key=api_key)

@bp.route('/config')
def config():
    """
    Página de configuración de la app (para el panel de Tiendanube)
    Instala automáticamente el botón flotante en la tienda
    """
    store_id = request.args.get('store_id', '')
    access_token = request.args.get('access_token', '')

    # Si tenemos store_id y access_token, intentar instalar el script automáticamente
    script_installed = False
    if store_id and access_token:
        script_installed = install_floating_button(store_id, access_token)

    # Sugerir URL con placeholder de API Key para que cada tienda use su clave
    # URL con api_key (única forma soportada)
    widget_url_api = 'https://clipcomparadorv2-production.up.railway.app/tiendanube/widget?api_key=TU_API_KEY'

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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>¡App instalada correctamente!</h1>
            <p class="subtitle">Tu tienda ahora tiene búsqueda visual con inteligencia artificial</p>

            {f'<div class="section" style="background: #d1fae5; border-left-color: #10b981;"><h2>🎉 ¡Botón flotante activado!</h2><p>El botón de búsqueda con IA ya está visible en tu tienda. Tus clientes lo verán en la esquina inferior derecha.</p></div>' if script_installed else ''}

            <div class="store-info">
                <strong>Store ID:</strong> {store_id or 'No detectado'}
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
                        <div class="code-block" style="word-break: break-all;">{widget_url}</div>
                        <p style="margin-top: 10px;">El enlace abrirá el buscador visual en una nueva pestaña</p>
                    </div>

                    <div class="step">
                        <h3>Alternativa: Botón flotante</h3>
                        <p>Si tenés un plan pago de Tiendanube, podés editar el código del tema y agregar:</p>
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
                <p>Copiá esta URL y reemplazá <strong>TU_API_KEY</strong> por tu clave.</p>
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
