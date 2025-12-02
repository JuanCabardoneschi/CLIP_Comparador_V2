"""
Blueprint para gestión de integraciones Tiendanube desde admin
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging

from app.models.client import Client
from app.models.tiendanube_integration import TiendanubeIntegration
from app.services.tiendanube_sync_service import start_full_sync
from app import db

logger = logging.getLogger(__name__)

bp = Blueprint('tiendanube_admin', __name__, url_prefix='/admin/tiendanube')


@bp.route('/integrations', methods=['GET'])
@login_required
def list_integrations():
    """Lista todas las integraciones de Tiendanube"""
    try:
        # Si es SUPER_ADMIN, ver todas; si no, solo su cliente
        if current_user.role == 'SUPER_ADMIN':
            integrations = TiendanubeIntegration.query.all()
        else:
            integrations = TiendanubeIntegration.query.filter_by(
                client_id=current_user.client_id
            ).all()

        return jsonify({
            'success': True,
            'integrations': [i.to_dict() for i in integrations]
        })
    except Exception as e:
        logger.error(f"Error listando integraciones: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500



@bp.route('/integrations/<integration_id>', methods=['GET', 'POST'])
@login_required
def get_integration(integration_id):
    """Detalle de integración Tiendanube y formulario de sync manual."""
    integration = TiendanubeIntegration.query.get(integration_id)
    if not integration:
        return render_template("errors/404.html", message="Integración no encontrada"), 404

    # Verificar permisos
    if current_user.role != 'SUPER_ADMIN' and integration.client_id != current_user.client_id:
        return render_template("errors/403.html", message="Acceso denegado"), 403

    if request.method == 'POST':
        if integration.sync_status == 'in_progress':
            return render_template("tiendanube_admin/integration_detail.html", integration=integration, error="Ya hay una sincronización en progreso")

        # Leer opciones del formulario
        sync_options = {
            'products': bool(request.form.get('sync_products')),
            'categories': bool(request.form.get('sync_categories')),
            'images': bool(request.form.get('sync_images')),
            'stock': bool(request.form.get('sync_stock')),
            'attributes': bool(request.form.get('sync_attributes')),
            'embeddings': bool(request.form.get('sync_embeddings')),
        }
        # Llama al servicio de sync con las opciones
        from app.services.tiendanube_sync_service import start_full_sync
        result = start_full_sync(integration.client_id, sync_options)
        # Recarga el objeto por si cambió el estado
        db.session.refresh(integration)
        return render_template("tiendanube_admin/integration_detail.html", integration=integration, result=result)

    return render_template("tiendanube_admin/integration_detail.html", integration=integration)


@bp.route('/integrations/<integration_id>/sync', methods=['POST'])
@login_required
def trigger_sync(integration_id):
    """
    Fuerza sincronización completa para una integración.
    Body (opcional): { "sync_type": "full" | "incremental" }
    """
    try:
        integration = TiendanubeIntegration.query.get(integration_id)
        if not integration:
            return jsonify({'success': False, 'error': 'Integración no encontrada'}), 404

        # Verificar permisos
        if current_user.role != 'SUPER_ADMIN' and integration.client_id != current_user.client_id:
            return jsonify({'success': False, 'error': 'Acceso denegado'}), 403

        # Verificar que no haya sync en progreso
        if integration.sync_status == 'in_progress':
            return jsonify({
                'success': False,
                'error': 'Ya hay una sincronización en progreso'
            }), 409

        # TODO: En producción, ejecutar en background task
        logger.info(f"Iniciando sincronización manual para integración {integration_id}")

        result = start_full_sync(integration.client_id)

        return jsonify({
            'success': result.get('success'),
            'result': result
        })

    except Exception as e:
        logger.error(f"Error forzando sincronización: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/integrations/<integration_id>/status', methods=['GET'])
@login_required
def get_sync_status(integration_id):
    """Obtiene el estado actual de sincronización"""
    try:
        integration = TiendanubeIntegration.query.get(integration_id)
        if not integration:
            return jsonify({'success': False, 'error': 'Integración no encontrada'}), 404

        # Verificar permisos
        if current_user.role != 'SUPER_ADMIN' and integration.client_id != current_user.client_id:
            return jsonify({'success': False, 'error': 'Acceso denegado'}), 403

        return jsonify({
            'success': True,
            'sync_status': integration.sync_status,
            'last_sync_at': integration.last_sync_at.isoformat() if integration.last_sync_at else None,
            'sync_error': integration.sync_error
        })
    except Exception as e:
        logger.error(f"Error obteniendo estado de sync: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/integrations/<integration_id>/deactivate', methods=['POST'])
@login_required
def deactivate_integration(integration_id):
    """Desactiva una integración (sin eliminarla)"""
    try:
        integration = TiendanubeIntegration.query.get(integration_id)
        if not integration:
            return jsonify({'success': False, 'error': 'Integración no encontrada'}), 404

        # Verificar permisos (solo SUPER_ADMIN puede desactivar)
        if current_user.role != 'SUPER_ADMIN':
            return jsonify({'success': False, 'error': 'Acceso denegado'}), 403

        integration.is_active = False
        db.session.commit()

        logger.info(f"Integración {integration_id} desactivada por {current_user.username}")

        return jsonify({
            'success': True,
            'message': 'Integración desactivada exitosamente'
        })
    except Exception as e:
        logger.error(f"Error desactivando integración: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/stats', methods=['GET'])
@login_required
def get_tiendanube_stats():
    """Obtiene estadísticas generales de integraciones Tiendanube"""
    try:
        if current_user.role != 'SUPER_ADMIN':
            return jsonify({'success': False, 'error': 'Acceso denegado'}), 403

        total_integrations = TiendanubeIntegration.query.count()
        active_integrations = TiendanubeIntegration.query.filter_by(is_active=True).count()

        # Integraciones por estado de sync
        pending = TiendanubeIntegration.query.filter_by(sync_status='pending').count()
        in_progress = TiendanubeIntegration.query.filter_by(sync_status='in_progress').count()
        completed = TiendanubeIntegration.query.filter_by(sync_status='completed').count()
        error = TiendanubeIntegration.query.filter_by(sync_status='error').count()

        # Clientes Tiendanube
        tn_clients = Client.query.filter_by(integration_type='tiendanube').count()

        return jsonify({
            'success': True,
            'stats': {
                'total_integrations': total_integrations,
                'active_integrations': active_integrations,
                'tiendanube_clients': tn_clients,
                'sync_status': {
                    'pending': pending,
                    'in_progress': in_progress,
                    'completed': completed,
                    'error': error
                }
            }
        })
    except Exception as e:
        logger.error(f"Error obteniendo stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
