"""
Blueprint: Administración de Perfiles de Búsqueda

Endpoints para visualizar, editar y probar perfiles de búsqueda por cliente.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import json
import logging

from app.models.client import Client
from app.models.category import Category
from app.services.search_profiles_service import SearchProfilesService

bp = Blueprint("search_profiles_admin", __name__, url_prefix="/search-profiles-admin")
logger = logging.getLogger(__name__)


def admin_required(f):
    """Verifica que el usuario sea admin."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or "role" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") not in ("SUPER_ADMIN", "STORE_ADMIN"):
            return jsonify({"error": "Acceso denegado"}), 403
        return f(*args, **kwargs)

    return decorated_function


@bp.route("/profiles", methods=["GET"])
@admin_required
def list_profiles():
    """Lista clientes y sus perfiles actuales."""
    try:
        # Obtener clientes (si es STORE_ADMIN, solo el suyo)
        if session.get("role") == "STORE_ADMIN":
            clients = [Client.query.get(session.get("client_id"))]
        else:
            clients = Client.query.filter_by(is_active=True).all()

        profiles_data = []
        for client in clients:
            if not client:
                continue

            profile = SearchProfilesService.get_profile(client.id, client.industry)
            profiles_data.append(
                {
                    "client_id": client.id,
                    "client_name": client.name,
                    "slug": client.slug,
                    "industry": client.industry,
                    "profile_name": profile.get("name", "Desconocido"),
                    "has_overrides": "search_rules" in (client.integration_config or {}),
                }
            )

        return render_template(
            "search_profiles/list.html", profiles=profiles_data, available_profiles=SearchProfilesService.get_all_profiles()
        )
    except Exception as e:
        logger.error(f"Error listando perfiles: {e}")
        return render_template("error.html", error=str(e)), 500


@bp.route("/client/<client_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_client_profile(client_id):
    """Edita perfil y overrides para un cliente específico."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({"error": "Cliente no encontrado"}), 404

        # Verificar permisos
        if session.get("role") == "STORE_ADMIN" and session.get("client_id") != client_id:
            return jsonify({"error": "Acceso denegado"}), 403

        if request.method == "POST":
            data = request.get_json() or {}
            overrides = data.get("search_rules", {})

            # Validar estructura
            valid_keys = {"variants_map", "category_synonyms", "color_tokens", "name_en_ignore_modifiers", "filter_strategy"}
            for key in overrides.keys():
                if key not in valid_keys:
                    return jsonify({"error": f"Clave desconocida: {key}"}), 400

            # Guardar overrides
            if SearchProfilesService.save_client_overrides(client_id, overrides):
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Perfil actualizado correctamente",
                            "client_id": client_id,
                        }
                    ),
                    200,
                )
            else:
                return jsonify({"error": "Error al guardar"}), 500

        # GET: Mostrar formulario de edición
        profile = SearchProfilesService.get_profile(client_id, client.industry)
        categories = Category.query.filter_by(client_id=client_id, is_active=True).all()
        overrides = client.integration_config.get("search_rules", {}) if client.integration_config else {}

        return render_template(
            "search_profiles/edit.html",
            client=client,
            profile=profile,
            categories=[{"id": c.id, "name": c.name, "alternative_terms": c.alternative_terms} for c in categories],
            overrides=overrides,
        )

    except Exception as e:
        logger.error(f"Error editando perfil para {client_id}: {e}")
        return render_template("error.html", error=str(e)), 500


@bp.route("/client/<client_id>/preview", methods=["POST"])
@admin_required
def preview_search(client_id):
    """Preview: simula una búsqueda con las reglas actuales."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({"error": "Cliente no encontrado"}), 404

        data = request.get_json() or {}
        query_text = data.get("query", "").strip()

        if not query_text:
            return jsonify({"error": "Query vacío"}), 400

        # Cargar perfil + overrides
        profile = SearchProfilesService.get_profile(client_id, client.industry, force_reload=True)

        # Normalizar tokens
        normalized_tokens = SearchProfilesService.normalize_tokens(query_text, profile)

        # Obtener categorías
        categories = Category.query.filter_by(client_id=client_id, is_active=True).all()

        # Expandir query
        expanded_terms = SearchProfilesService.expand_query(query_text, categories, profile)

        # Detectar categoría
        category_filter_ids, detection_metadata = SearchProfilesService.detect_category_filter(
            normalized_tokens, categories, profile
        )

        # Enriquecer metadata
        matched_cat_names = []
        if category_filter_ids:
            matched_cat_names = [c.name for c in categories if c.id in category_filter_ids]

        return jsonify(
            {
                "success": True,
                "query": query_text,
                "normalized_tokens": normalized_tokens,
                "expanded_terms": expanded_terms,
                "category_filter": {
                    "applies": bool(category_filter_ids),
                    "category_ids": category_filter_ids or [],
                    "category_names": matched_cat_names,
                    "metadata": detection_metadata,
                },
                "profile_info": {
                    "industry": client.industry,
                    "name": profile.get("name", "Desconocido"),
                    "filter_strategy": profile.get("filter_strategy", "root-unique"),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error en preview para {client_id}: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@bp.route("/profiles/available", methods=["GET"])
@admin_required
def get_available_profiles():
    """Retorna lista de perfiles disponibles."""
    try:
        profiles = SearchProfilesService.get_all_profiles()
        return jsonify({"success": True, "profiles": profiles}), 200
    except Exception as e:
        logger.error(f"Error obteniendo perfiles: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/client/<client_id>/reset-overrides", methods=["POST"])
@admin_required
def reset_client_overrides(client_id):
    """Resetea overrides a valores base del perfil de industria."""
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({"error": "Cliente no encontrado"}), 404

        # Verificar permisos
        if session.get("role") == "STORE_ADMIN" and session.get("client_id") != client_id:
            return jsonify({"error": "Acceso denegado"}), 403

        # Limpiar overrides
        if client.integration_config:
            client.integration_config.pop("search_rules", None)
            client.updated_at = db.func.now()
            db.session.add(client)
            db.session.commit()

        # Invalidar cache (en memory cache se maneja automáticamente)
        return jsonify({"success": True, "message": "Overrides reseteados"}), 200

    except Exception as e:
        logger.error(f"Error reseteando overrides para {client_id}: {e}")
        return jsonify({"error": str(e)}), 500
