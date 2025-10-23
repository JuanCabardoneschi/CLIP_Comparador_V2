"""
Blueprint de Configuración de Búsqueda
Gestión de pesos del SearchOptimizer por cliente
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.store_search_config import StoreSearchConfig
from app.models.client import Client
from app.utils.permissions import requires_super_admin
from sqlalchemy.exc import SQLAlchemyError

bp = Blueprint("search_config", __name__, url_prefix="/search-config")


@bp.route("/")
@login_required
def index():
    """
    Vista principal de configuración de búsqueda

    - Super Admin: Ve todas las configuraciones
    - Cliente Admin: Ve solo su configuración
    """
    if current_user.is_super_admin:
        # Super admin ve todas las configuraciones
        configs = (
            db.session.query(StoreSearchConfig, Client)
            .join(Client, StoreSearchConfig.store_id == Client.id)
            .order_by(Client.name)
            .all()
        )
        configs_data = [
            {
                'config': config,
                'client': client
            }
            for config, client in configs
        ]
    else:
        # Cliente admin ve solo su configuración
        client_id = current_user.client_id
        config = StoreSearchConfig.query.get(client_id)
        client = Client.query.get(client_id)

        if not config:
            # Crear configuración default si no existe
            config = StoreSearchConfig.get_or_create_default(client_id, commit=True)

        configs_data = [{'config': config, 'client': client}]

    return render_template("search_config/index.html", configs=configs_data)


@bp.route("/edit", methods=["GET"])
@login_required
def edit_redirect():
    """
    Ruta sin client_id: redirige al cliente del usuario actual
    """
    if current_user.is_super_admin:
        # Super admin necesita especificar client_id
        flash("Selecciona un cliente desde la lista", "info")
        return redirect(url_for("search_config.index"))
    else:
        # Cliente admin: redirigir a su propia configuración
        return redirect(url_for("search_config.edit", client_id=current_user.client_id))


@bp.route("/edit/<client_id>", methods=["GET", "POST"])
@login_required
def edit(client_id):
    """
    Editar configuración de búsqueda

    Args:
        client_id: UUID del cliente

    Permissions:
        - Super Admin: Puede editar cualquier cliente
        - Cliente Admin: Solo puede editar su propia configuración
    """
    # Verificar permisos
    if not current_user.is_super_admin and str(current_user.client_id) != client_id:
        flash("No tienes permisos para acceder a esta configuración", "error")
        return redirect(url_for("search_config.index"))

    # Obtener cliente
    client = Client.query.get(client_id)
    if not client:
        flash("Cliente no encontrado", "error")
        return redirect(url_for("search_config.index"))

    # Obtener o crear configuración
    config = StoreSearchConfig.query.get(client_id)
    if not config:
        config = StoreSearchConfig.get_or_create_default(client_id, commit=True)

    if request.method == "POST":
        try:
            # Obtener pesos del formulario
            visual_weight = float(request.form.get("visual_weight", 0.6))
            metadata_weight = float(request.form.get("metadata_weight", 0.3))
            business_weight = float(request.form.get("business_weight", 0.1))

            # Actualizar configuración
            success, error = config.update_weights(
                visual=visual_weight,
                metadata=metadata_weight,
                business=business_weight,
                commit=True
            )

            if success:
                flash(f"✅ Configuración actualizada para {client.name}", "success")
                return redirect(url_for("search_config.index"))
            else:
                flash(f"❌ Error: {error}", "error")

        except ValueError as e:
            flash(f"❌ Error en valores: {str(e)}", "error")
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f"❌ Error de base de datos: {str(e)}", "error")

    return render_template(
        "search_config/edit.html",
        config=config,
        client=client
    )


@bp.route("/api/update/<client_id>", methods=["POST"])
@login_required
def api_update(client_id):
    """
    API endpoint para actualizar configuración (AJAX)

    Request JSON:
        {
            "visual_weight": 0.6,
            "metadata_weight": 0.3,
            "business_weight": 0.1
        }

    Response JSON:
        {
            "success": true,
            "message": "Configuración actualizada",
            "config": {
                "visual_weight": 0.6,
                "metadata_weight": 0.3,
                "business_weight": 0.1
            }
        }
    """
    # Verificar permisos
    if not current_user.is_super_admin and str(current_user.client_id) != client_id:
        return jsonify({
            "success": False,
            "error": "No tienes permisos para modificar esta configuración"
        }), 403

    # Obtener cliente
    client = Client.query.get(client_id)
    if not client:
        return jsonify({
            "success": False,
            "error": "Cliente no encontrado"
        }), 404

    # Obtener configuración
    config = StoreSearchConfig.query.get(client_id)
    if not config:
        config = StoreSearchConfig.get_or_create_default(client_id, commit=True)

    try:
        data = request.get_json()

        visual_weight = float(data.get("visual_weight", 0.6))
        metadata_weight = float(data.get("metadata_weight", 0.3))
        business_weight = float(data.get("business_weight", 0.1))
        category_confidence = int(data.get("category_confidence_threshold", client.category_confidence_threshold or 70))
        product_similarity = int(data.get("product_similarity_threshold", client.product_similarity_threshold or 30))

        # Actualizar configuración de pesos
        success, error = config.update_weights(
            visual=visual_weight,
            metadata=metadata_weight,
            business=business_weight,
            commit=False  # No commit aún, vamos a actualizar más campos
        )

        if not success:
            return jsonify({
                "success": False,
                "error": error
            }), 400

        # Actualizar thresholds en el cliente
        client.category_confidence_threshold = category_confidence
        client.product_similarity_threshold = product_similarity

        # Commit de ambos cambios
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Configuración actualizada correctamente",
            "config": {
                "visual_weight": config.visual_weight,
                "metadata_weight": config.metadata_weight,
                "business_weight": config.business_weight,
                "category_confidence_threshold": client.category_confidence_threshold,
                "product_similarity_threshold": client.product_similarity_threshold
            }
        })

    except ValueError as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Error en valores: {str(e)}"
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Error inesperado: {str(e)}"
        }), 500


@bp.route("/api/preset/<client_id>/<preset_name>", methods=["POST"])
@login_required
def api_apply_preset(client_id, preset_name):
    """
    API endpoint para aplicar preset predefinido

    Presets disponibles:
        - visual: Prioriza similitud visual CLIP (0.8, 0.15, 0.05)
        - metadata: Prioriza atributos de producto (0.3, 0.6, 0.1)
        - balanced: Balance equilibrado (0.5, 0.3, 0.2)

    Response JSON:
        {
            "success": true,
            "message": "Preset 'visual' aplicado",
            "config": {...}
        }
    """
    # Verificar permisos
    if not current_user.is_super_admin and str(current_user.client_id) != client_id:
        return jsonify({
            "success": False,
            "error": "No tienes permisos"
        }), 403

    # Obtener configuración
    config = StoreSearchConfig.query.get(client_id)
    if not config:
        config = StoreSearchConfig.get_or_create_default(client_id, commit=True)

    try:
        # Aplicar preset
        success, error = config.apply_preset(preset_name, commit=True)

        if success:
            return jsonify({
                "success": True,
                "message": f"Preset '{preset_name}' aplicado correctamente",
                "config": {
                    "visual_weight": config.visual_weight,
                    "metadata_weight": config.metadata_weight,
                    "business_weight": config.business_weight
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": error
            }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Error aplicando preset: {str(e)}"
        }), 500


@bp.route("/api/validate", methods=["POST"])
@login_required
def api_validate_weights():
    """
    API endpoint para validar pesos antes de guardar

    Request JSON:
        {
            "visual_weight": 0.6,
            "metadata_weight": 0.3,
            "business_weight": 0.1
        }

    Response JSON:
        {
            "valid": true,
            "sum": 1.0,
            "message": "Pesos válidos"
        }
    """
    try:
        data = request.get_json()

        visual = float(data.get("visual_weight", 0))
        metadata = float(data.get("metadata_weight", 0))
        business = float(data.get("business_weight", 0))

        total = visual + metadata + business

        # Validar que sumen 1.0 ± 0.01
        is_valid = abs(total - 1.0) <= 0.01

        # Validar rangos individuales
        all_in_range = all(0 <= w <= 1 for w in [visual, metadata, business])

        if is_valid and all_in_range:
            return jsonify({
                "valid": True,
                "sum": round(total, 2),
                "message": "✅ Pesos válidos"
            })
        elif not all_in_range:
            return jsonify({
                "valid": False,
                "sum": round(total, 2),
                "message": "❌ Cada peso debe estar entre 0 y 1"
            })
        else:
            return jsonify({
                "valid": False,
                "sum": round(total, 2),
                "message": f"❌ La suma debe ser 1.0 (actual: {total:.2f})"
            })

    except ValueError:
        return jsonify({
            "valid": False,
            "message": "❌ Valores inválidos"
        }), 400
