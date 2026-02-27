"""
Blueprint de Configuración del Sistema (SuperAdmin)
Panel de administración para configurar parámetros globales del sistema
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.utils.permissions import requires_role
from app.utils.system_config import system_config
import json
from pathlib import Path

bp = Blueprint('system_config_admin', __name__)


def _get_nlp_config_path():
    """Obtiene ruta al archivo de configuración NLP."""
    return Path(__file__).resolve().parents[3] / "shared" / "system_nlp_config.json"

def _get_colors_config_path():
    """Obtiene ruta al archivo de colores semánticos."""
    return Path(__file__).resolve().parents[3] / "shared" / "system_semantic_colors.json"

def _load_json_config(path):
    """Carga configuración desde JSON."""
    if not path.exists():
        print(f"[DEBUG] Archivo no existe: {path}")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[DEBUG] JSON cargado desde {path.name}: {list(data.keys())}")
        return data
    except Exception as e:
        print(f"Error cargando config desde {path}: {e}")
        return {}

def _save_json_config(path, data):
    """Guarda configuración a JSON."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error guardando config: {e}")
        return False


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

        # Nivel de log
        log_level = request.form.get('log_level', 'REQUEST_LIFECYCLE')
        valid_log_levels = ['ERROR_ONLY', 'REQUEST_LIFECYCLE', 'MAIN_PROCESSES', 'VERBOSE']
        if log_level not in valid_log_levels:
            log_level = 'REQUEST_LIFECYCLE'

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
            },
            'system': {
                'log_level': log_level
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


# === NUEVAS RUTAS PARA VOCABULARIO NLP Y COLORES SEMÁNTICOS ===

@bp.route('/nlp-vocabulary')
@login_required
@requires_role('SUPER_ADMIN')
def nlp_vocabulary():
    """Editar vocabulario NLP (fashion categories, terms, color adjectives)."""
    config = _load_json_config(_get_nlp_config_path())
    # Asegurar que existan todas las claves con valores por defecto
    config.setdefault('fashion_categories', [])
    config.setdefault('fashion_terms', [])
    config.setdefault('color_adjectives', [])
    config.setdefault('semantic_color_config', {
        'similarity_threshold': 0.55,
        'fallback_threshold': 0.48,
        'top_k': 3,
        'max_final_colors': 2
    })
    # Debug: imprimir configuración cargada
    print(f"[DEBUG] Config cargada: fashion_categories={len(config['fashion_categories'])}, fashion_terms={len(config['fashion_terms'])}, color_adjectives={len(config['color_adjectives'])}")
    return render_template('system_config/nlp_vocabulary.html', config=config)


@bp.route('/nlp-vocabulary/save', methods=['POST'])
@login_required
@requires_role('SUPER_ADMIN')
def nlp_vocabulary_save():
    """Guardar vocabulario NLP."""
    try:
        data = request.get_json()

        # Validar estructura
        required_keys = ['fashion_categories', 'fashion_terms', 'color_adjectives', 'semantic_color_config']
        for key in required_keys:
            if key not in data:
                return jsonify({'success': False, 'error': f'Falta campo: {key}'}), 400

        # Validar que sean listas
        for key in ['fashion_categories', 'fashion_terms', 'color_adjectives']:
            if not isinstance(data[key], list):
                return jsonify({'success': False, 'error': f'{key} debe ser una lista'}), 400

        # Guardar
        if _save_json_config(_get_nlp_config_path(), data):
            # Invalidar cache de spaCy para recargar en próximo request
            try:
                import app.blueprints.search_text as st_module
                st_module._NLP_ES_WITH_PARSER = None
                st_module._NLP_CONFIG = st_module._load_nlp_config()
            except Exception as e:
                print(f"⚠️ No se pudo invalidar cache NLP: {e}")

            flash('Configuración NLP guardada exitosamente', 'success')
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Error al guardar archivo'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/semantic-colors')
@login_required
@requires_role('SUPER_ADMIN')
def semantic_colors():
    """Editar colores semánticos."""
    config = _load_json_config(_get_colors_config_path())
    # Asegurar que existan todas las claves con valores por defecto
    config.setdefault('colors', [])
    config.setdefault('config', {
        'similarity_threshold': 0.55,
        'fallback_threshold': 0.48,
        'top_k': 3,
        'max_final_colors': 2
    })
    return render_template('system_config/semantic_colors.html', config=config)


@bp.route('/semantic-colors/save', methods=['POST'])
@login_required
@requires_role('SUPER_ADMIN')
def semantic_colors_save():
    """Guardar colores semánticos."""
    try:
        data = request.get_json()

        # Validar estructura
        if 'colors' not in data or not isinstance(data['colors'], list):
            return jsonify({'success': False, 'error': 'Falta campo colors (lista)'}), 400

        if 'config' not in data or not isinstance(data['config'], dict):
            return jsonify({'success': False, 'error': 'Falta campo config (dict)'}), 400

        # Validar cada color
        for color_item in data['colors']:
            if not isinstance(color_item, dict) or 'token' not in color_item:
                return jsonify({'success': False, 'error': 'Cada color debe tener campo token'}), 400

        # Guardar
        if _save_json_config(_get_colors_config_path(), data):
            # Invalidar cache
            try:
                from app.utils import semantic_colors as sc_module
                sc_module._SYSTEM_COLOR_DATA = None
                sc_module._SYSTEM_COLOR_SET = None
            except Exception as e:
                print(f"⚠️ No se pudo invalidar cache colores: {e}")

            try:
                from app.utils import colors as colors_module
                colors_module._llm_color_cache.clear()
            except Exception as e:
                print(f"⚠️ No se pudo invalidar cache normalize_color: {e}")

            flash('Configuración de colores semánticos guardada', 'success')
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Error al guardar archivo'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
