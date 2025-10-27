"""
Blueprint de Configuración del Sistema
Panel de administración para SuperAdmin
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.utils.permissions import requires_role
from app.utils.system_config import system_config

bp = Blueprint('system_config_bp', __name__)


@bp.route('/')
@login_required
@requires_role('SUPER_ADMIN')
def index():
    """Panel de configuración del sistema"""
    config = system_config.get_all()
    return render_template('system_config/index.html', config=config)


@bp.route('/api/get', methods=['GET'])
@login_required
@requires_role('SUPER_ADMIN')
def get_config():
    """Obtener configuración actual (API)"""
    return jsonify({
        'success': True,
        'config': system_config.get_all()
    })


@bp.route('/api/update', methods=['POST'])
@login_required
@requires_role('SUPER_ADMIN')
def update_config():
    """Actualizar configuración del sistema"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        section = data.get('section')
        values = data.get('values')

        if not section or not values:
            return jsonify({
                'success': False,
                'message': 'Sección y valores son requeridos'
            }), 400

        # Validaciones específicas
        if section == 'clip':
            if 'idle_timeout' in values:
                timeout = values['idle_timeout']
                if not isinstance(timeout, int) or timeout < 60:
                    return jsonify({
                        'success': False,
                        'message': 'idle_timeout debe ser un entero >= 60 segundos'
                    }), 400

            if 'preload' in values:
                if not isinstance(values['preload'], bool):
                    return jsonify({
                        'success': False,
                        'message': 'preload debe ser true o false'
                    }), 400

        # Actualizar configuración
        success = system_config.update_section(section, values)

        if success:
            return jsonify({
                'success': True,
                'message': f'Configuración de {section} actualizada correctamente',
                'config': system_config.get_all()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error guardando configuración'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@bp.route('/api/reload', methods=['POST'])
@login_required
@requires_role('SUPER_ADMIN')
def reload_config():
    """Recargar configuración desde disco"""
    try:
        config = system_config.reload()
        return jsonify({
            'success': True,
            'message': 'Configuración recargada desde disco',
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@bp.route('/api/reset', methods=['POST'])
@login_required
@requires_role('SUPER_ADMIN')
def reset_config():
    """Restaurar configuración por defecto"""
    try:
        system_config._config = system_config._get_default_config()
        success = system_config.save_config()

        if success:
            return jsonify({
                'success': True,
                'message': 'Configuración restaurada a valores por defecto',
                'config': system_config.get_all()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error guardando configuración'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
