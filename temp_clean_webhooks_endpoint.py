"""
Endpoint temporal para limpiar webhooks duplicados de Tiendanube
Agregar esto a tiendanube_admin.py temporalmente
"""

@bp.route('/integrations/<integration_id>/clean-webhooks', methods=['POST'])
@login_required
def clean_duplicate_webhooks(integration_id):
    """Elimina webhooks con URLs incorrectas (sin /api/)"""
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
        response = requests.get(
            f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks',
            headers=headers,
            timeout=10,
            verify=False
        )

        if response.status_code != 200:
            return jsonify({'success': False, 'error': f'Error listando webhooks: {response.status_code}'}), 500

        all_webhooks = response.json()

        webhooks_deleted = []
        webhooks_kept = []

        for wh in all_webhooks:
            wh_id = wh.get('id')
            url = wh.get('url', '')
            event = wh.get('event')

            # Si NO tiene /api/ en la URL, es viejo y debe eliminarse
            if '/api/webhooks/tiendanube/' not in url:
                # Eliminar
                del_response = requests.delete(
                    f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks/{wh_id}',
                    headers=headers,
                    timeout=10,
                    verify=False
                )

                if del_response.status_code == 200:
                    webhooks_deleted.append({'id': wh_id, 'event': event, 'url': url})
                    logger.info(f"🗑️ Webhook eliminado: {event} (ID: {wh_id}) - URL incorrecta")
            else:
                webhooks_kept.append({'id': wh_id, 'event': event})

        return jsonify({
            'success': True,
            'deleted': len(webhooks_deleted),
            'kept': len(webhooks_kept),
            'deleted_webhooks': webhooks_deleted,
            'kept_webhooks': webhooks_kept
        })

    except Exception as e:
        logger.error(f"Error limpiando webhooks: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
