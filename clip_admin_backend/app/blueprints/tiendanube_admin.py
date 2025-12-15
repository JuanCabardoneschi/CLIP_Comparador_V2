"""
Blueprint para gestión de integraciones Tiendanube desde admin
"""
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
import logging

from app.models.client import Client
from app.models.tiendanube_integration import TiendanubeIntegration
from app.services.tiendanube_sync_service import start_full_sync
from app import db

logger = logging.getLogger(__name__)

bp = Blueprint('tiendanube_admin', __name__, url_prefix='/admin/tiendanube')

logger.info("🔧 [tiendanube_admin] Blueprint inicializado con url_prefix='/admin/tiendanube'")


@bp.route('/integrations', methods=['GET'])
@login_required
def list_integrations():
    """Lista todas las integraciones de Tiendanube"""
    logger.info(f"📋 [tiendanube_admin] GET /integrations - User: {current_user.email if current_user.is_authenticated else 'anonymous'}, Role: {current_user.role if current_user.is_authenticated else 'N/A'}")

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


@bp.route('/ui/integrations', methods=['GET'])
@login_required
def ui_list_integrations():
    """Vista simple para gestionar integraciones Tiendanube con acciones."""
    try:
        if current_user.role == 'SUPER_ADMIN':
            integrations = TiendanubeIntegration.query.order_by(TiendanubeIntegration.created_at.desc()).all()
        else:
            integrations = TiendanubeIntegration.query.filter_by(client_id=current_user.client_id).order_by(TiendanubeIntegration.created_at.desc()).all()

        return render_template('tiendanube/integrations.html', integrations=integrations)
    except Exception as e:
        logger.error(f"Error renderizando UI de integraciones: {str(e)}")
        flash(f"Error: {str(e)}", 'danger')
        return redirect(url_for('tiendanube_admin.list_integrations'))



@bp.route('/integrations/<integration_id>', methods=['GET', 'POST'])
@login_required
def get_integration(integration_id):
    """Detalle de integración Tiendanube y formulario de sync manual."""
    logger.info(f"🔍 [tiendanube_admin] GET /integrations/{integration_id} - User: {current_user.email if current_user.is_authenticated else 'anonymous'}")

    integration = TiendanubeIntegration.query.get(integration_id)
    if not integration:
        logger.warning(f"❌ [tiendanube_admin] Integración {integration_id} no encontrada en BD")
        return render_template("errors/404.html", message="Integración no encontrada"), 404

    logger.info(f"✅ [tiendanube_admin] Integración encontrada: Store {integration.store_id}, Client: {integration.client_id}")

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
        result = start_full_sync(str(integration.client_id), sync_options)
        # Recarga el objeto desde la BD para obtener estado actualizado
        db.session.expire(integration)
        integration = TiendanubeIntegration.query.get(integration_id)
        logger.info(f"POST sync completado - Estado actual en BD: {integration.sync_status}")
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

        result = start_full_sync(str(integration.client_id))

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


@bp.route('/integrations/<integration_id>/clean-webhooks', methods=['POST'])
@login_required
def clean_duplicate_webhooks(integration_id):
    """Elimina webhooks con URLs incorrectas (sin /api/)"""
    import requests

    try:
        integration = TiendanubeIntegration.query.get(integration_id)
        if not integration:
            return jsonify({'success': False, 'error': 'Integración no encontrada'}), 404

        # Verificar permisos
        if current_user.role != 'SUPER_ADMIN' and integration.client_id != current_user.client_id:
            return jsonify({'success': False, 'error': 'Sin permisos'}), 403

        access_token = integration.get_access_token()
        headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIP Comparador V2',
            'Content-Type': 'application/json'
        }

        # Listar todos los webhooks
        logger.info(f"🔍 Listando webhooks de Tiendanube para store {integration.store_id}")
        response = requests.get(
            f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks',
            headers=headers,
            timeout=10,
            verify=False
        )

        if response.status_code != 200:
            logger.error(f"❌ Error listando webhooks: {response.status_code} - {response.text}")
            return jsonify({'success': False, 'error': f'Error listando webhooks: {response.status_code}'}), 500

        all_webhooks = response.json()
        logger.info(f"📋 Total de webhooks encontrados: {len(all_webhooks)}")

        webhooks_deleted = []
        webhooks_kept = []
        errors = []

        for wh in all_webhooks:
            wh_id = wh.get('id')
            url = wh.get('url', '')
            event = wh.get('event')

            # Si NO tiene /api/ en la URL, es viejo y debe eliminarse
            if '/api/webhooks/tiendanube/' not in url:
                logger.info(f"🗑️ Eliminando webhook viejo: {event} (ID: {wh_id}) - URL: {url}")

                # Eliminar
                del_response = requests.delete(
                    f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks/{wh_id}',
                    headers=headers,
                    timeout=10,
                    verify=False
                )

                if del_response.status_code == 200:
                    webhooks_deleted.append({'id': wh_id, 'event': event, 'url': url})
                    logger.info(f"✅ Webhook eliminado exitosamente: {event} (ID: {wh_id})")
                else:
                    error_msg = f"Error eliminando webhook {wh_id}: {del_response.status_code}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
            else:
                webhooks_kept.append({'id': wh_id, 'event': event})
                logger.info(f"✅ Webhook correcto mantenido: {event} (ID: {wh_id})")

        logger.info(f"🎉 Limpieza completada: {len(webhooks_deleted)} eliminados, {len(webhooks_kept)} mantenidos")

        return jsonify({
            'success': True,
            'deleted': len(webhooks_deleted),
            'kept': len(webhooks_kept),
            'deleted_webhooks': webhooks_deleted,
            'kept_webhooks': webhooks_kept,
            'errors': errors
        })

    except Exception as e:
        logger.error(f"❌ Error limpiando webhooks: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/integrations/<integration_id>/list-all-webhooks', methods=['GET'])
@login_required
def list_all_webhooks(integration_id):
    """Lista TODOS los webhooks del store sin filtrar"""
    import requests

    try:
        integration = TiendanubeIntegration.query.get(integration_id)
        if not integration:
            return jsonify({'success': False, 'error': 'Integración no encontrada'}), 404

        # Verificar permisos
        if current_user.role != 'SUPER_ADMIN' and integration.client_id != current_user.client_id:
            return jsonify({'success': False, 'error': 'Sin permisos'}), 403

        access_token = integration.get_access_token()
        headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIP Comparador V2',
            'Content-Type': 'application/json'
        }

        # Listar TODOS los webhooks
        logger.info(f"🔍 Listando TODOS los webhooks para store {integration.store_id}")
        response = requests.get(
            f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks',
            headers=headers,
            timeout=10,
            verify=False
        )

        if response.status_code != 200:
            logger.error(f"❌ Error listando webhooks: {response.status_code} - {response.text}")
            return jsonify({'success': False, 'error': f'Error listando webhooks: {response.status_code}'}), 500

        all_webhooks = response.json()

        # Clasificar webhooks
        correct_webhooks = []
        incorrect_webhooks = []

        for wh in all_webhooks:
            wh_info = {
                'id': wh.get('id'),
                'event': wh.get('event'),
                'url': wh.get('url', ''),
                'created_at': wh.get('created_at', ''),
                'updated_at': wh.get('updated_at', '')
            }

            if '/api/webhooks/tiendanube/' in wh_info['url']:
                correct_webhooks.append(wh_info)
            else:
                incorrect_webhooks.append(wh_info)

        logger.info(f"📋 Total: {len(all_webhooks)} webhooks ({len(correct_webhooks)} correctos, {len(incorrect_webhooks)} incorrectos)")

        return jsonify({
            'success': True,
            'total': len(all_webhooks),
            'correct': len(correct_webhooks),
            'incorrect': len(incorrect_webhooks),
            'correct_webhooks': correct_webhooks,
            'incorrect_webhooks': incorrect_webhooks
        })

    except Exception as e:
        logger.error(f"❌ Error listando webhooks: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/integrations/<integration_id>/delete-all-incorrect-webhooks', methods=['POST'])
@login_required
def delete_all_incorrect_webhooks(integration_id):
    """Elimina TODOS los webhooks sin /api/ sin importar cuándo se crearon"""
    import requests

    try:
        integration = TiendanubeIntegration.query.get(integration_id)
        if not integration:
            return jsonify({'success': False, 'error': 'Integración no encontrada'}), 404

        # Solo SUPER_ADMIN
        if current_user.role != 'SUPER_ADMIN':
            return jsonify({'success': False, 'error': 'Solo SUPER_ADMIN'}), 403

        access_token = integration.get_access_token()
        headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIP Comparador V2',
            'Content-Type': 'application/json'
        }

        # Listar TODOS
        response = requests.get(
            f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks',
            headers=headers,
            timeout=10,
            verify=False
        )

        if response.status_code != 200:
            return jsonify({'success': False, 'error': f'Error listando: {response.status_code}'}), 500

        all_webhooks = response.json()
        deleted = []
        errors = []

        for wh in all_webhooks:
            wh_id = wh.get('id')
            url = wh.get('url', '')
            event = wh.get('event')

            # Eliminar si NO tiene /api/
            if '/api/webhooks/tiendanube/' not in url:
                logger.warning(f"🗑️ ELIMINANDO webhook incorrecto: {event} (ID: {wh_id}) - {url}")

                del_resp = requests.delete(
                    f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks/{wh_id}',
                    headers=headers,
                    timeout=10,
                    verify=False
                )

                if del_resp.status_code == 200:
                    deleted.append({'id': wh_id, 'event': event, 'url': url})
                    logger.info(f"✅ Eliminado: {event} (ID: {wh_id})")
                else:
                    error = f"Error eliminando {wh_id}: {del_resp.status_code}"
                    errors.append(error)
                    logger.error(f"❌ {error}")

        logger.warning(f"🎉 LIMPIEZA TOTAL: {len(deleted)} eliminados, {len(errors)} errores")

        return jsonify({
            'success': True,
            'deleted': len(deleted),
            'deleted_webhooks': deleted,
            'errors': errors
        })

    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
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
