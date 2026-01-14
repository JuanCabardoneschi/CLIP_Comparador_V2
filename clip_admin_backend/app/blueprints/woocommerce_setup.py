"""
Blueprint para conectar una tienda WooCommerce
Proceso: Formulario → Validación → Crear Cliente → Guardar integración
"""
from flask import Blueprint, request, jsonify, render_template
import logging
import uuid
from app import db
from app.models.client import Client
from app.models.woocommerce_integration import WooCommerceIntegration
from app.services.woocommerce_api_client import WooCommerceAPIClient, WooCommerceAPIError

logger = logging.getLogger(__name__)

bp = Blueprint('woocommerce_setup', __name__, url_prefix='/woocommerce')

@bp.route('/connect', methods=['GET'])
def connect_form():
    """
    Muestra formulario de conexión WooCommerce.
    """
    return render_template('woocommerce/connect_form.html')

@bp.route('/test-connection', methods=['POST'])
def test_connection():
    """
    API para testear conexión con WooCommerce antes de guardar.

    Request JSON:
    {
        "store_url": "https://mitienda.com",
        "consumer_key": "ck_xxxxxxxxxxxxx",
        "consumer_secret": "cs_xxxxxxxxxxxxx"
    }

    Response:
    {
        "success": true,
        "store_info": {
            "name": "Mi Tienda",
            "wc_version": "8.5.0",
            "wp_version": "6.4.2",
            ...
        }
    }
    """
    try:
        data = request.get_json()

        # Validar campos requeridos
        required_fields = ['store_url', 'consumer_key', 'consumer_secret']
        if not all(field in data for field in required_fields):
            return jsonify({
                'success': False,
                'error': 'Faltan campos requeridos'
            }), 400

        store_url = data['store_url'].strip()
        consumer_key = data['consumer_key'].strip()
        consumer_secret = data['consumer_secret'].strip()

        # Crear cliente temporal para probar conexión
        client = WooCommerceAPIClient(
            store_url=store_url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret
        )

        # Probar conexión obteniendo system_status
        logger.info(f"Probando conexión con {store_url}...")
        system_status = client.get_system_status()

        # Extraer información relevante
        environment = system_status.get('environment', {})
        settings = system_status.get('settings', {})

        store_info = {
            'name': environment.get('site_name', 'Sin nombre'),
            'url': environment.get('home_url', store_url),
            'wc_version': environment.get('version', 'Desconocida'),
            'wp_version': environment.get('wp_version', 'Desconocida'),
            'timezone': settings.get('timezone', 'UTC'),
            'currency': settings.get('currency', 'USD'),
            'products_count': None  # Se podría obtener luego
        }

        logger.info(f"✅ Conexión exitosa con {store_info['name']}")

        return jsonify({
            'success': True,
            'store_info': store_info
        })

    except WooCommerceAPIError as e:
        logger.error(f"Error de API WooCommerce: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error inesperado: {str(e)}'
        }), 500

@bp.route('/save-integration', methods=['POST'])
def save_integration():
    """
    Guarda la integración WooCommerce después de validación exitosa.

    Request JSON:
    {
        "store_url": "https://mitienda.com",
        "consumer_key": "ck_xxxxxxxxxxxxx",
        "consumer_secret": "cs_xxxxxxxxxxxxx",
        "store_name": "Mi Tienda",
        "store_email": "admin@mitienda.com"
    }

    Response:
    {
        "success": true,
        "client_id": "uuid",
        "api_key": "generated_api_key",
        "integration_id": "uuid"
    }
    """
    try:
        data = request.get_json()

        # Validar campos
        required_fields = ['store_url', 'consumer_key', 'consumer_secret', 'store_name']
        if not all(field in data for field in required_fields):
            return jsonify({
                'success': False,
                'error': 'Faltan campos requeridos'
            }), 400

        store_url = data['store_url'].strip()
        consumer_key = data['consumer_key'].strip()
        consumer_secret = data['consumer_secret'].strip()
        store_name = data['store_name'].strip()
        store_email = data.get('store_email', '').strip()

        # Verificar si ya existe integración con esta URL
        existing = WooCommerceIntegration.query.filter_by(store_url=store_url).first()
        if existing:
            return jsonify({
                'success': False,
                'error': f'Ya existe una integración para {store_url}'
            }), 400

        # 1. Crear Cliente
        client_id = str(uuid.uuid4())
        api_key = Client.generate_api_key()

        # Nombre del cliente basado en store_name
        client_name = f"{store_name} (WooCommerce)"

        client = Client(
            id=client_id,
            name=client_name,
            email=store_email if store_email else f"{client_id}@woocommerce.local",
            domain=store_url,
            api_key=api_key,
            is_active=True,
            integration_type='woocommerce',  # Marcar como WooCommerce
            is_read_only=True,  # Read-only porque sincroniza con tienda externa
            plan='free'  # Ajustar según tu modelo de negocio
        )

        db.session.add(client)
        db.session.flush()  # Para obtener el ID

        # 2. Crear integración WooCommerce
        integration_id = str(uuid.uuid4())
        integration = WooCommerceIntegration(
            id=integration_id,
            client_id=client.id,
            store_url=store_url,
            store_name=store_name,
            store_email=store_email
        )

        # Encriptar y guardar credenciales
        integration.set_consumer_key(consumer_key)
        integration.set_consumer_secret(consumer_secret)

        # Obtener metadata adicional
        try:
            wc_client = WooCommerceAPIClient(store_url, consumer_key, consumer_secret)
            system_status = wc_client.get_system_status()
            environment = system_status.get('environment', {})
            settings = system_status.get('settings', {})

            integration.wc_version = environment.get('version')
            integration.wp_version = environment.get('wp_version')
            integration.timezone = settings.get('timezone')
            integration.currency = settings.get('currency')
        except Exception as e:
            logger.warning(f"No se pudo obtener metadata: {str(e)}")

        integration.sync_status = 'pending'

        db.session.add(integration)
        db.session.commit()

        logger.info(f"✅ Integración WooCommerce creada: {integration_id} para {store_name}")

        return jsonify({
            'success': True,
            'client_id': client.id,
            'api_key': api_key,
            'integration_id': integration.id,
            'message': 'Integración guardada exitosamente'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error guardando integración: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/integrations', methods=['GET'])
def list_integrations():
    """
    Lista todas las integraciones WooCommerce activas.
    """
    try:
        integrations = WooCommerceIntegration.query.filter_by(is_active=True).all()

        result = []
        for integration in integrations:
            result.append({
                'id': integration.id,
                'store_name': integration.store_name,
                'store_url': integration.store_url,
                'client_id': integration.client_id,
                'sync_status': integration.sync_status,
                'last_sync': integration.last_sync_at.isoformat() if integration.last_sync_at else None,
                'installed_at': integration.installed_at.isoformat() if integration.installed_at else None
            })

        return jsonify({
            'success': True,
            'integrations': result,
            'total': len(result)
        })

    except Exception as e:
        logger.error(f"Error listando integraciones: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/integration/<integration_id>', methods=['GET'])
def get_integration(integration_id):
    """
    Obtiene detalles de una integración específica.
    """
    try:
        integration = WooCommerceIntegration.query.get(integration_id)

        if not integration:
            return jsonify({
                'success': False,
                'error': 'Integración no encontrada'
            }), 404

        # No incluir credenciales por seguridad
        return jsonify({
            'success': True,
            'integration': integration.to_dict(include_credentials=False)
        })

    except Exception as e:
        logger.error(f"Error obteniendo integración: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/integration/<integration_id>', methods=['DELETE'])
def delete_integration(integration_id):
    """
    Elimina (desactiva) una integración WooCommerce.
    """
    try:
        integration = WooCommerceIntegration.query.get(integration_id)

        if not integration:
            return jsonify({
                'success': False,
                'error': 'Integración no encontrada'
            }), 404

        # Marcar como inactiva en vez de eliminar
        integration.is_active = False
        integration.uninstalled_at = db.func.now()

        # Desactivar cliente asociado
        client = Client.query.get(integration.client_id)
        if client:
            client.is_active = False

        db.session.commit()

        logger.info(f"Integración {integration_id} desactivada")

        return jsonify({
            'success': True,
            'message': 'Integración eliminada exitosamente'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error eliminando integración: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
