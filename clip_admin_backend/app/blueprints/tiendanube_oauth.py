"""
Blueprint para manejar OAuth con Tiendanube
Flujo completo: OAuth → Crear Cliente → Registrar Integración → Webhooks → Widget
"""
from flask import Blueprint, request, jsonify, render_template_string
import requests
import logging
import urllib3
from app.models.client import Client
from app.models.tiendanube_integration import TiendanubeIntegration
from app.models.user import User
from app import db

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
    Callback OAuth completo:
    1. Intercambia code por access_token
    2. Crea nuevo Cliente en el sistema
    3. Guarda integración con token encriptado
    4. Registra webhooks
    5. Intenta inyectar widget (con fallback)
    6. Redirige a página de éxito
    """
    try:
        code = request.args.get('code')
        if not code:
            error = request.args.get('error', 'No se recibió código de autorización')
            logger.error(f"OAuth error: {error}")
            return render_template_string(render_error_page(error)), 400

        # 1. Intercambio de código por token
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
            return render_template_string(render_error_page(error_msg)), 400

        token_response = response.json()
        access_token = token_response.get('access_token')
        scope = token_response.get('scope', '')
        user_id = token_response.get('user_id')  # store_id

        if not access_token or not user_id:
            return render_template_string(render_error_page('No se recibió access_token o user_id')), 400

        # 2. Obtener información de la tienda
        store_info = get_store_info(user_id, access_token)
        if not store_info:
            return render_template_string(render_error_page('No se pudo obtener información de la tienda')), 400

        store_name = store_info.get('name', {}).get('es', f'Tienda {user_id}')
        store_email = store_info.get('email', '')
        store_domain = store_info.get('original_domain', store_info.get('main_domain', ''))

        # 3. Verificar si ya existe integración (reinstalación)
        existing_integration = db.session.query(TiendanubeIntegration).filter(
            TiendanubeIntegration.store_id == str(user_id)
        ).first()

        if existing_integration:
            # Reinstalación: actualizar token y reactivar
            logger.info(f"Reinstalación detectada para store_id={user_id}")
            existing_integration.set_access_token(access_token)
            existing_integration.scopes = scope.split() if scope else []
            existing_integration.is_active = True
            existing_integration.uninstalled_at = None
            existing_integration.sync_status = 'pending'
            db.session.commit()

            client = existing_integration.client
            logger.info(f"Cliente reactivado: {client.id}")
        else:
            # 4. Crear nuevo Cliente
            client = Client(
                name=store_name,
                email=store_email or f'{user_id}@tiendanube.com',
                industry='ecommerce',
                integration_type='tiendanube',
                is_read_only=True,
                integration_config={
                    'store_id': str(user_id),
                    'store_domain': store_domain,
                    'installed_at': str(db.func.now())
                }
            )
            db.session.add(client)
            db.session.flush()  # Obtener client.id

            logger.info(f"Cliente creado: {client.id} para tienda {store_name}")

            # 5a. Crear usuario STORE_ADMIN automáticamente
            admin_full_name = f"Admin {store_name}"
            # Usar SIEMPRE el email real del usuario de la tienda (store_email)
            admin_email = store_email

            # Verificar si ya existe un usuario con ese email
            existing_user = None
            if admin_email:
                existing_user = User.query.filter_by(email=admin_email, client_id=client.id).first()

            # Crear usuario admin:
            # - Si tenemos email: crear con email
            # - Si NO hay email: crear sin email, usando full_name como identificador
            if (admin_email and not existing_user) or (not admin_email):
                from werkzeug.security import generate_password_hash
                import secrets

                # Generar contraseña temporal
                temp_password = secrets.token_urlsafe(12)

                # Si no hay email, usar un placeholder para cumplir NOT NULL
                if not admin_email:
                    admin_email = f"{user_id}@no-email.local"

                admin_user = User(
                    email=admin_email,
                    password_hash=generate_password_hash(temp_password),
                    full_name=admin_full_name,
                    role='STORE_ADMIN',
                    client_id=client.id,
                    is_active=True
                )
                db.session.add(admin_user)
                db.session.flush()

                logger.info(f"Usuario STORE_ADMIN creado: {admin_email} (contraseña temporal: {temp_password})")

                # Guardar credenciales en config del cliente para mostrarlas
                if not client.integration_config:
                    client.integration_config = {}
                client.integration_config['admin_email'] = admin_email
                client.integration_config['admin_name'] = admin_full_name
                client.integration_config['admin_temp_password'] = temp_password
            elif existing_user:
                logger.info(f"Usuario existente encontrado: {existing_user.email}")
            else:
                # No tenemos email del dueño de la tienda; no crear usuario automático
                logger.warning("No se recibió store_email desde Tiendanube; no se crea usuario STORE_ADMIN automáticamente")
                if not client.integration_config:
                    client.integration_config = {}
                client.integration_config['admin_email'] = None
                client.integration_config['admin_name'] = None
                client.integration_config['admin_temp_password'] = None

            # 5b. Crear integración con token encriptado
            integration = TiendanubeIntegration(
                client_id=client.id,
                store_id=str(user_id),
                store_name=store_name,
                store_email=store_email,
                store_domain=store_domain,
                scopes=scope.split() if scope else [],
                sync_status='pending'
            )
            integration.set_access_token(access_token)
            db.session.add(integration)
            db.session.commit()

            logger.info(f"Integración creada: {integration.id}")

        # 6. Registrar webhooks (asíncrono recomendado, pero por ahora inline)
        webhook_ids = register_webhooks(user_id, access_token)
        if webhook_ids:
            if existing_integration:
                existing_integration.webhook_ids = webhook_ids
            else:
                integration.webhook_ids = webhook_ids
            db.session.commit()
            logger.info(f"Webhooks registrados: {webhook_ids}")

        # 7. Intentar inyectar widget script
        script_id = inject_widget_script(user_id, access_token, client.api_key)
        if script_id:
            if existing_integration:
                existing_integration.script_id = script_id
            else:
                integration.script_id = script_id
            db.session.commit()
            logger.info(f"Widget script inyectado: {script_id}")
        else:
            logger.warning(f"No se pudo inyectar script; usar fallback de enlace")

        # 8. Disparar sincronización inicial en background (no bloqueante)
        try:
            import threading
            from app.services.tiendanube_sync_service import start_full_sync

            def _run_sync(cid: str):
                try:
                    logger.info(f"[SYNC] Iniciando sincronización inicial para cliente {cid}...")
                    result = start_full_sync(cid)
                    if result.get('success'):
                        logger.info(f"[SYNC] Sincronización completada: {result.get('stats')}")
                    else:
                        logger.error(f"[SYNC] Error en sincronización: {result.get('error')}")
                except Exception as ex:
                    logger.error(f"[SYNC] Excepción en hilo de sincronización: {str(ex)}")

            threading.Thread(target=_run_sync, args=(str(client.id),), daemon=True).start()
        except Exception as e:
            logger.error(f"No se pudo iniciar sincronización en background: {str(e)}")

        # 9. Renderizar página de éxito
        return render_template_string(
            render_success_page(
                store_name=store_name,
                store_id=user_id,
                scope=scope,
                api_key=client.api_key,
                has_script=(script_id is not None),
                admin_email=client.integration_config.get('admin_email'),
                admin_name=client.integration_config.get('admin_name'),
                admin_password=client.integration_config.get('admin_temp_password')
            )
        )

    except Exception as e:
        logger.error(f"Error en OAuth callback: {str(e)}", exc_info=True)
        db.session.rollback()
        return render_template_string(render_error_page(str(e))), 500


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
            f'{TIENDANUBE_API_BASE}/{store_id}/store',
            headers=headers,
            timeout=10,
            verify=False
        )
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"No se pudo obtener info de tienda: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error al obtener info de tienda: {str(e)}")
        return None


def register_webhooks(store_id, access_token):
    """
    Registra webhooks para productos, categorías y app lifecycle.
    Retorna dict con IDs de webhooks creados.
    """
    webhook_ids = {}
    headers = {
        'Authentication': f'bearer {access_token}',
        'User-Agent': 'CLIP Comparador V2 (info@clipcomparador.com)',
        'Content-Type': 'application/json'
    }

    webhook_url_base = 'https://clipcomparadorv2-production.up.railway.app/webhooks/tiendanube'

    webhooks_to_create = [
        {'event': 'product/created', 'url': f'{webhook_url_base}/product/created'},
        {'event': 'product/updated', 'url': f'{webhook_url_base}/product/updated'},
        {'event': 'product/deleted', 'url': f'{webhook_url_base}/product/deleted'},
        {'event': 'category/created', 'url': f'{webhook_url_base}/category/created'},
        {'event': 'category/updated', 'url': f'{webhook_url_base}/category/updated'},
        {'event': 'category/deleted', 'url': f'{webhook_url_base}/category/deleted'},
        {'event': 'app/uninstalled', 'url': f'{webhook_url_base}/app/uninstalled'},
        {'event': 'store/redact', 'url': f'{webhook_url_base}/store/redact'},
    ]

    for webhook in webhooks_to_create:
        try:
            response = requests.post(
                f'{TIENDANUBE_API_BASE}/{store_id}/webhooks',
                json=webhook,
                headers=headers,
                timeout=10,
                verify=False
            )
            if response.status_code in [200, 201]:
                data = response.json()
                webhook_ids[webhook['event']] = data.get('id')
                logger.info(f"Webhook {webhook['event']} registrado: {data.get('id')}")
            else:
                logger.warning(f"No se pudo crear webhook {webhook['event']}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error creando webhook {webhook['event']}: {str(e)}")

    return webhook_ids if webhook_ids else None


def inject_widget_script(store_id, access_token, api_key):
    """
    Intenta inyectar el script del widget en la tienda.
    Retorna script_id si tiene éxito, None si falla (plan no soporta scripts).
    """
    try:
        headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIP Comparador V2 (info@clipcomparador.com)',
            'Content-Type': 'application/json'
        }

        script_src = f'https://clipcomparadorv2-production.up.railway.app/static/widget/clip-widget-embed-unified.js?api_key={api_key}'

        script_data = {
            'src': script_src,
            'event': 'onload',  # Script se ejecuta al cargar la página
            'where': 'footer'   # Cargar en footer
        }

        response = requests.post(
            f'{TIENDANUBE_API_BASE}/{store_id}/scripts',
            json=script_data,
            headers=headers,
            timeout=10,
            verify=False
        )

        if response.status_code in [200, 201]:
            data = response.json()
            script_id = data.get('id')
            logger.info(f"Script inyectado exitosamente: {script_id}")
            return script_id
        else:
            logger.warning(f"No se pudo inyectar script (plan puede no soportarlo): {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error inyectando script: {str(e)}")
        return None


def render_success_page(store_name, store_id, scope, api_key, has_script=False, admin_email=None, admin_name=None, admin_password=None):
    """Renderiza página de éxito con instrucciones según disponibilidad de script"""

        # Sección de credenciales de admin
        admin_section = ""
        if admin_email and admin_password:
            admin_section = f"""
            <div class=\"alert alert-info\">
                <strong>🔐 Credenciales de Acceso al Panel Admin</strong><br><br>
                <strong>URL:</strong> <a href=\"https://clipcomparadorv2-production.up.railway.app/auth/login\" target=\"_blank\">
                    https://clipcomparadorv2-production.up.railway.app/auth/login
                </a><br>
                <strong>Email:</strong> <code>{admin_email}</code><br>
                <strong>Nombre:</strong> <code>{admin_name}</code><br>
                <strong>Contraseña temporal:</strong> <code>{admin_password}</code><br>
                <br>
                <small>⚠️ Guardá estas credenciales en un lugar seguro. Podrás cambiar la contraseña una vez que inicies sesión.</small>
            </div>
            """

    script_status = """
        <div class="info-item">
            <span class="info-label">Widget:</span> ✅ Instalado automáticamente
        </div>
    """ if has_script else f"""
        <div class="info-item">
            <span class="info-label">Widget:</span> ⚠️ Configuración manual requerida
        </div>
        <div class="alert alert-warning">
            <strong>Tu plan no permite scripts automáticos.</strong><br>
            Podés agregar el widget manualmente desde tu panel de administración:<br>
            <code>Menú → Agregar enlace → https://clipcomparadorv2-production.up.railway.app/tiendanube/widget?api_key={api_key}</code>
        </div>
    """

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
                max-width: 600px;
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
            .alert-warning {{
                background: #fef3c7;
                border: 2px solid #f59e0b;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                text-align: left;
                color: #92400e;
            }}
            .alert-info {{
                background: #dbeafe;
                border: 2px solid #3b82f6;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                text-align: left;
                color: #1e40af;
            }}
            .alert-info a {{
                color: #1d4ed8;
                text-decoration: none;
                font-weight: bold;
            }}
            .alert-info a:hover {{
                text-decoration: underline;
            }}
            .alert-warning code {{
                background: white;
                padding: 2px 6px;
                border-radius: 4px;
                display: block;
                margin-top: 10px;
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
            }}
            .button:hover {{
                background: #5568d3;
            }}
            .next-steps {{
                background: #e0e7ff;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: left;
            }}
            .next-steps h3 {{
                color: #3730a3;
                margin-top: 0;
            }}
            .next-steps ul {{
                color: #4c1d95;
                text-align: left;
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
                    <span class="info-label">API Key:</span> <code>{api_key[:20]}...</code>
                </div>
                <div class="info-item">
                    <span class="info-label">Permisos:</span> {scope}
                </div>
                {script_status}
            </div>

            {admin_section}

            <div class="next-steps">
                <h3>📋 Próximos Pasos</h3>
                <ul>
                    <li>La sincronización inicial de tus productos comenzará automáticamente</li>
                    <li>Recibirás un email cuando esté completa (puede tomar algunos minutos)</li>
                    <li>Podés gestionar tu integración desde el panel de administración</li>
                    <li>El widget de búsqueda visual ya está {"activo en tu tienda" if has_script else "listo para configurar"}</li>
                </ul>
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
