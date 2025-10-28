"""
Blueprint de Configuración del Sistema (SuperAdmin)
Panel de administración para configurar parámetros globales del sistema
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.utils.permissions import requires_role
from app.utils.system_config import system_config

bp = Blueprint('system_config_admin', __name__)


@bp.route('/')
@login_required
@requires_role('SUPER_ADMIN')
def index():
    """Panel principal de configuración del sistema"""
    config = system_config.get_all()
    return render_template('system_config/index.html', config=config)


@bp.route('/update', methods=['POST'])
@login_required
@requires_role('SUPER_ADMIN')
def update():
    """Actualizar configuración del sistema"""
    try:
        # Obtener datos del formulario
        clip_preload = request.form.get('clip_preload') == 'on'
        clip_idle_timeout = int(request.form.get('clip_idle_timeout_minutes', 120))
        clip_model = request.form.get('clip_model_name', 'openai/clip-vit-base-patch16')

        max_results = int(request.form.get('search_max_results', 50))
        enable_category_detection = request.form.get('enable_category_detection') == 'on'
        enable_visual_search = request.form.get('enable_visual_search') == 'on'

        # Validaciones
        if clip_idle_timeout < 1 or clip_idle_timeout > 1440:
            flash('El timeout de CLIP debe estar entre 1 y 1440 minutos', 'danger')
            return redirect(url_for('system_config_admin.index'))

        if max_results < 1 or max_results > 10:
            flash('El máximo de resultados debe estar entre 1 y 10', 'danger')
            return redirect(url_for('system_config_admin.index'))

        # Actualizar configuración
        updates = {
            'clip': {
                'preload': clip_preload,
                'idle_timeout_minutes': clip_idle_timeout,
                'model_name': clip_model
            },
            'search': {
                'max_results': max_results,
                'enable_category_detection': enable_category_detection,
                'enable_visual_search': enable_visual_search
            }
        }

        system_config.update_multiple(updates)

        # 🔄 Invalidar cache de CLIP para que lea la nueva configuración
        try:
            from app.blueprints.embeddings import reload_clip_config
            reload_clip_config()
        except Exception as e:
            print(f"⚠️ No se pudo recargar config de CLIP: {e}")

        flash('✅ Configuración actualizada correctamente', 'success')
        return redirect(url_for('system_config_admin.index'))

    except ValueError as e:
        flash(f'❌ Error en los valores ingresados: {str(e)}', 'danger')
        return redirect(url_for('system_config_admin.index'))
    except Exception as e:
        flash(f'❌ Error actualizando configuración: {str(e)}', 'danger')
        return redirect(url_for('system_config_admin.index'))


@bp.route('/api/config', methods=['GET'])
@login_required
@requires_role('SUPER_ADMIN')
def get_config_api():
    """API para obtener configuración actual (JSON)"""
    try:
        config = system_config.get_all()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/config', methods=['POST'])
@login_required
@requires_role('SUPER_ADMIN')
def update_config_api():
    """API para actualizar configuración (JSON)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos'
            }), 400

        system_config.update_multiple(data)

        # 🔄 Invalidar cache de CLIP
        try:
            from app.blueprints.embeddings import reload_clip_config
            reload_clip_config()
        except Exception as e:
            print(f"⚠️ No se pudo recargar config de CLIP: {e}")

        return jsonify({
            'success': True,
            'message': 'Configuración actualizada correctamente'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/reset', methods=['POST'])
@login_required
@requires_role('SUPER_ADMIN')
def reset():
    """Restablecer configuración a valores por defecto"""
    try:
        default_config = {
            "clip": {
                "preload": False,
                "idle_timeout_minutes": 120,
                "model_name": "openai/clip-vit-base-patch16"
            },
            "search": {
                "max_results": 50,
                "enable_category_detection": True,
                "enable_visual_search": True
            },
            "system": {
                "environment": "production",
                "version": "2.0.0"
            }
        }

        # Escribir configuración por defecto
        from pathlib import Path
        import json
        config_path = Path(system_config.config_path)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)

        # 🔄 Invalidar cache de CLIP
        try:
            from app.blueprints.embeddings import reload_clip_config
            reload_clip_config()
        except Exception as e:
            print(f"⚠️ No se pudo recargar config de CLIP: {e}")

        flash('✅ Configuración restablecida a valores por defecto', 'success')
        return redirect(url_for('system_config_admin.index'))

    except Exception as e:
        flash(f'❌ Error restableciendo configuración: {str(e)}', 'danger')
        return redirect(url_for('system_config_admin.index'))
