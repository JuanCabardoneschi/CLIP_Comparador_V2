"""
Blueprint para manejar OAuth con Tiendanube (sin base de datos)
"""
from flask import Blueprint, request, jsonify
import requests
import logging
import urllib3

# Deshabilitar warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

bp = Blueprint('tiendanube_oauth', __name__, url_prefix='/oauth')

# Configuración de la app Tiendanube
TIENDANUBE_CLIENT_ID = '22436'
TIENDANUBE_CLIENT_SECRET = 'd2d37cc732c511993531d58e8a3d354b14de11a92a29313d'
TIENDANUBE_REDIRECT_URI = 'https://clipcomparadorv2-production.up.railway.app/oauth/callback'
TIENDANUBE_TOKEN_URL = 'https://www.tiendanube.com/apps/authorize/token'
TIENDANUBE_API_BASE = 'https://api.tiendanube.com/v1'

@bp.route('/callback', methods=['GET'])
def oauth_callback():
    """
    Callback OAuth: intercambia el `code` por `access_token` y
    devuelve JSON con `access_token`, `user_id` y `scope`.
    No persiste nada en base de datos.
    """
    try:
        code = request.args.get('code')
        if not code:
            error = request.args.get('error', 'No se recibió código de autorización')
            logger.error(f"OAuth error: {error}")
            return jsonify({'success': False, 'error': error}), 400

        token_data = {
            'client_id': TIENDANUBE_CLIENT_ID,
            'client_secret': TIENDANUBE_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': TIENDANUBE_REDIRECT_URI
        }

        logger.info(f"Solicitando token con code: {code[:10]}...")
        response = requests.post(
            TIENDANUBE_TOKEN_URL,
            json=token_data,
            headers={'Content-Type': 'application/json'},
            verify=False
        )

        if response.status_code != 200:
            try:
                err = response.json()
                error_msg = err.get('error_description', err.get('error', 'Error desconocido'))
            except Exception:
                error_msg = f"HTTP {response.status_code}"
            logger.error(f"Error al obtener token: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 400

        token_response = response.json()
        access_token = token_response.get('access_token')
        token_type = token_response.get('token_type', 'bearer')
        scope = token_response.get('scope', '')
        user_id = token_response.get('user_id')

        if not access_token:
            return jsonify({'success': False, 'error': 'No se recibió access_token'}), 400

        # Intentar obtener info de tienda (opcional)
        store_info = {}
        if user_id:
            store_info = get_store_info(user_id, access_token) or {}

        return jsonify({
            'success': True,
            'access_token': access_token,
            'token_type': token_type,
            'scope': scope,
            'user_id': user_id,
            'store': store_info
        })
    except Exception as e:
        logger.error(f"Error en OAuth callback: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def get_store_info(store_id, access_token):
    """
    Obtiene información básica de la tienda desde la API de Tiendanube
    """
    try:
        headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIP Comparador V2 (info@clipcomparador.com)'
        }
        response = requests.get(
            f'{TIENDANUBE_API_BASE}/store/',
            headers=headers,
            timeout=10,
            verify=False  # Deshabilitar verificación SSL temporalmente
        )
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"No se pudo obtener info de tienda: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Error al obtener info de tienda: {str(e)}")
        return {}


def render_success_page(store_name, store_id, scope):
    """Renderiza página de éxito"""
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Autorización Exitosa - CLIP Comparador</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 500px;
                text-align: center;
            }}
            .success-icon {{
                font-size: 64px;
                color: #10b981;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #1f2937;
                margin-bottom: 10px;
                font-size: 28px;
            }}
            .store-name {{
                color: #667eea;
                font-weight: bold;
                font-size: 20px;
                margin: 20px 0;
            }}
            .info {{
                background: #f3f4f6;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: left;
            }}
            .info-item {{
                margin: 10px 0;
                color: #4b5563;
            }}
            .info-label {{
                font-weight: bold;
                color: #1f2937;
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
            }}
            .button:hover {{
                background: #5568d3;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>¡Autorización Exitosa!</h1>
            <p>Tu tienda ha sido conectada correctamente con CLIP Comparador</p>

            <div class="store-name">{store_name}</div>

            <div class="info">
                <div class="info-item">
                    <span class="info-label">Store ID:</span> {store_id}
                </div>
                <div class="info-item">
                    <span class="info-label">Permisos:</span> {scope}
                </div>
                <div class="info-item">
                    <span class="info-label">Estado:</span> Activo
                </div>
            </div>

            <p style="color: #6b7280; margin-top: 20px;">
                Ya podés cerrar esta ventana y volver a tu tienda.
            </p>

            <a href="javascript:window.close()" class="button">Cerrar</a>
        </div>
    </body>
    </html>
    """
    return html


def render_error_page(error_message):
    """Renderiza página de error"""
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Error de Autorización - CLIP Comparador</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #f87171 0%, #dc2626 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 500px;
                text-align: center;
            }}
            .error-icon {{
                font-size: 64px;
                color: #ef4444;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #1f2937;
                margin-bottom: 20px;
                font-size: 28px;
            }}
            .error-message {{
                background: #fee2e2;
                color: #991b1b;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                border-left: 4px solid #ef4444;
            }}
            .button {{
                display: inline-block;
                background: #ef4444;
                color: white;
                padding: 12px 30px;
                border-radius: 8px;
                text-decoration: none;
                margin-top: 20px;
                transition: background 0.3s;
            }}
            .button:hover {{
                background: #dc2626;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">❌</div>
            <h1>Error de Autorización</h1>
            <div class="error-message">
                {error_message}
            </div>
            <p style="color: #6b7280;">
                Por favor, intentá nuevamente o contactá a soporte.
            </p>
            <a href="javascript:window.close()" class="button">Cerrar</a>
        </div>
    </body>
    </html>
    """
    return html


@bp.route('/exchange', methods=['POST'])
def oauth_exchange():
    """
    Endpoint simple para pruebas: recibe `code` en JSON y devuelve
    el token como JSON sin usar BD.
    Body: { "code": "..." }
    """
    payload = request.get_json(silent=True) or {}
    code = payload.get('code')
    if not code:
        return jsonify({'success': False, 'error': 'Falta code'}), 400

    token_data = {
        'client_id': TIENDANUBE_CLIENT_ID,
        'client_secret': TIENDANUBE_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': TIENDANUBE_REDIRECT_URI,
    }

    response = requests.post(
        TIENDANUBE_TOKEN_URL,
        json=token_data,
        headers={'Content-Type': 'application/json'},
        verify=False
    )

    try:
        data = response.json()
    except Exception:
        data = {'raw': response.text}

    return jsonify({'status_code': response.status_code, 'data': data}), (200 if response.status_code == 200 else 400)
