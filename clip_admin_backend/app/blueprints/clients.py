"""
Blueprint de Clientes
Gestión de clientes y API keys
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.client import Client
from app.models.user import User
from app.utils.permissions import requires_super_admin
import secrets
import string

bp = Blueprint("clients", __name__)


@bp.route("/")
@login_required
@requires_super_admin
def index():
    """Lista de todos los clientes - Solo Super Admin"""
    clients = Client.query.all()
    return render_template("clients/index.html", clients=clients)


@bp.route("/create", methods=["GET", "POST"])
@login_required
@requires_super_admin
def create():
    """Crear nuevo cliente con usuario administrador - Solo Super Admin"""
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        industry = request.form.get("industry", "general")
        integration_type = request.form.get("integration_type", "standalone")

        # Datos del usuario administrador
        admin_name = request.form.get("admin_name")
        admin_email = request.form.get("admin_email")
        admin_password = request.form.get("admin_password")
        admin_password_confirm = request.form.get("admin_password_confirm")

        # Validaciones básicas
        if not name or not email:
            flash("Nombre y email del cliente son requeridos", "error")
            return render_template("clients/create.html")

        if not admin_name or not admin_email or not admin_password:
            flash("Todos los campos del usuario administrador son requeridos", "error")
            return render_template("clients/create.html")

        if admin_password != admin_password_confirm:
            flash("Las contraseñas no coinciden", "error")
            return render_template("clients/create.html")

        if len(admin_password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres", "error")
            return render_template("clients/create.html")

        # Verificar que no exista un cliente con el mismo email
        existing_client = Client.query.filter_by(email=email).first()
        if existing_client:
            flash("Ya existe un cliente con ese email", "error")
            return render_template("clients/create.html")

        # Verificar que no exista un usuario con el mismo email
        existing_user = User.query.filter_by(email=admin_email).first()
        if existing_user:
            flash("Ya existe un usuario con ese email de login", "error")
            return render_template("clients/create.html")

        # Validar credenciales según el tipo de integración
        integration_config = {}

        if integration_type == "woocommerce":
            wc_store_url = request.form.get("wc_store_url", "").strip()
            wc_consumer_key = request.form.get("wc_consumer_key", "").strip()
            wc_consumer_secret = request.form.get("wc_consumer_secret", "").strip()

            if not wc_store_url or not wc_consumer_key or not wc_consumer_secret:
                flash("URL de la tienda, Consumer Key y Consumer Secret de WooCommerce son requeridos", "error")
                return render_template("clients/create.html")

            # Validar formato de URL
            if not wc_store_url.startswith(("http://", "https://")):
                flash("La URL de WooCommerce debe comenzar con http:// o https://", "error")
                return render_template("clients/create.html")

            integration_config = {
                "store_url": wc_store_url,
                "consumer_key": wc_consumer_key,
                "consumer_secret": wc_consumer_secret
            }

        try:
            # Crear cliente (la API Key se genera automáticamente)
            client = Client(
                name=name,
                email=email,
                industry=industry,
                integration_type=integration_type,
                integration_config=integration_config if integration_config else {}
            )
            db.session.add(client)
            db.session.flush()  # Para obtener el client.id

            # Crear usuario administrador para este cliente
            admin_user = User(
                email=admin_email,
                full_name=admin_name,
                client_id=client.id,
                role="STORE_ADMIN",
                active=True
            )
            admin_user.set_password(admin_password)
            db.session.add(admin_user)

            db.session.commit()

            # Mostrar credenciales completas
            flash(f"✅ Cliente '{name}' creado exitosamente", "success")
            flash(f"🔑 API Key: {client.api_key}", "info")
            flash(f"👤 Usuario Administrador creado:", "success")
            flash(f"📧 Email: {admin_email}", "info")
            flash(f"🔐 Contraseña: {admin_password}", "info")
            flash("⚠️ IMPORTANTE: Guarda estas credenciales, la contraseña no se mostrará nuevamente", "warning")

            # Mensaje según tipo de integración
            if integration_type == "woocommerce":
                flash(f"🔗 Integración WooCommerce: {integration_config['store_url']}", "info")

            return redirect(url_for("clients.view", client_id=client.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear cliente: {str(e)}", "error")
            return render_template("clients/create.html")

    return render_template("clients/create.html")


@bp.route("/api/validate-integration", methods=["POST"])
@login_required
@requires_super_admin
def validate_integration():
    """Validar credenciales de integración (AJAX)"""
    data = request.get_json()
    integration_type = data.get("integration_type", "standalone")

    if integration_type == "standalone":
        return jsonify({"success": True, "message": "✅ Integración Standalone (sin credenciales necesarias)"})

    elif integration_type == "woocommerce":
        store_url = data.get("store_url", "").strip()
        consumer_key = data.get("consumer_key", "").strip()
        consumer_secret = data.get("consumer_secret", "").strip()

        if not store_url or not consumer_key or not consumer_secret:
            return jsonify({"success": False, "message": "❌ URL, Consumer Key y Consumer Secret son requeridos"}), 400

        # Validar formato de URL
        if not store_url.startswith(("http://", "https://")):
            return jsonify({"success": False, "message": "❌ La URL debe comenzar con http:// o https://"}), 400

        try:
            # Importar el cliente de WooCommerce
            from app.services.woocommerce_api_client import WooCommerceAPIClient
            client = WooCommerceAPIClient(store_url, consumer_key, consumer_secret)

            # Intentar obtener información del sistema
            result = client.test_connection()
            if result.get("success"):
                return jsonify({
                    "success": True,
                    "message": f"✅ Conexión exitosa con WooCommerce: {result.get('store_name', store_url)}"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": f"❌ Error en WooCommerce: {result.get('error', 'Error desconocido')}"
                }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"❌ Error al validar WooCommerce: {str(e)}"
            }), 400

    else:
        return jsonify({"success": False, "message": "❌ Tipo de integración desconocido"}), 400


@bp.route("/<client_id>")
@login_required
def view(client_id):
    """Ver detalles de un cliente - Super Admin o usuario del cliente"""
    client = Client.query.get_or_404(client_id)

    # Verificar permisos: Super Admin o usuario del mismo cliente
    if not current_user.is_super_admin and str(current_user.client_id) != str(client_id):
        flash("No tienes permisos para ver este cliente", "error")
        return redirect(url_for("dashboard.index"))

    # api_keys = APIKey.query.filter_by(client_id=client_id).all()  # COMENTADO: No existe APIKey
    api_keys = []  # Lista vacía temporal
    users = User.query.filter_by(client_id=client_id).all()

    return render_template("clients/view.html",
                           client=client,
                           api_keys=api_keys,
                           users=users)


@bp.route("/<client_id>/edit", methods=["GET", "POST"])
@login_required
@requires_super_admin
def edit(client_id):
    """Editar cliente"""
    client = Client.query.get_or_404(client_id)

    if request.method == "POST":
        client.name = request.form.get("name", client.name)
        client.email = request.form.get("email", client.email)
        client.description = request.form.get("description", client.description)
        client.industry = request.form.get("industry", client.industry)

        db.session.commit()
        flash("Cliente actualizado exitosamente", "success")
        return redirect(url_for("clients.view", client_id=client.id))

    return render_template("clients/edit.html", client=client)


# COMENTADO: Funciones de API Keys deshabilitadas temporalmente
# @bp.route("/<client_id>/api-keys/create", methods=["POST"])
# @login_required
# def create_api_key(client_id):
#     """Crear nueva API key para el cliente"""
#     client = Client.query.get_or_404(client_id)
#
#     name = request.form.get("name", "API Key")
#
#     # Generar API key segura
#     key = "".join(secrets.choice(string.ascii_letters + string.digits + "-_") for _ in range(43))
#
#     api_key = APIKey(
#         client_id=client_id,
#         name=name,
#         key_hash=key  # En producción, hashear la clave
#     )
#
#     db.session.add(api_key)
#     db.session.commit()
#
#     flash(f"API Key '{name}' creada exitosamente", "success")
#     return redirect(url_for("clients.view", client_id=client_id))


# @bp.route("/<client_id>/api-keys/<key_id>/toggle", methods=["POST"])
# @login_required
# def toggle_api_key(client_id, key_id):
#     """Activar/desactivar API key"""
#     api_key = APIKey.query.filter_by(id=key_id, client_id=client_id).first_or_404()
#
#     api_key.is_active = not api_key.is_active
#     db.session.commit()
#
#     status = "activada" if api_key.is_active else "desactivada"
#     flash(f"API Key {status} exitosamente", "success")
#
#     return redirect(url_for("clients.view", client_id=client_id))


@bp.route("/<client_id>/delete", methods=["POST"])
@login_required
@requires_super_admin
def delete(client_id):
    """Eliminar cliente (con confirmación)"""
    client = Client.query.get_or_404(client_id)

    if request.form.get("confirm") == "DELETE":
        db.session.delete(client)
        db.session.commit()
        flash(f"Cliente '{client.name}' eliminado exitosamente", "success")
        return redirect(url_for("clients.index"))

    flash("Confirmación requerida para eliminar cliente", "error")
    return redirect(url_for("clients.view", client_id=client_id))


@bp.route("/api/search")
@login_required
def api_search():
    """API endpoint para buscar clientes"""
    query = request.args.get("q", "")

    if not query:
        return jsonify([])

    clients = Client.query.filter(
        Client.name.contains(query) | Client.email.contains(query)
    ).limit(10).all()

    return jsonify([{
        "id": client.id,
        "name": client.name,
        "email": client.email,
        "created_at": client.created_at.isoformat()
    } for client in clients])


@bp.route("/<client_id>/regenerate-api-key", methods=["POST"])
@login_required
def regenerate_api_key(client_id):
    """Regenerar API Key de un cliente - Super Admin o usuario del cliente"""
    client = Client.query.get_or_404(client_id)

    # Verificar permisos: Super Admin o usuario del mismo cliente
    if not current_user.is_super_admin and str(current_user.client_id) != str(client_id):
        flash("No tienes permisos para regenerar la API Key de este cliente", "error")
        return redirect(url_for("dashboard.index"))

    try:
        old_key, new_key = client.regenerate_api_key()
        db.session.commit()

        flash(f"API Key regenerada exitosamente. Nueva API Key: {new_key}", "success")
        return redirect(url_for("clients.view", client_id=client.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Error al regenerar API Key: {str(e)}", "error")
        return redirect(url_for("clients.view", client_id=client.id))


# Endpoint AJAX para actualizar sensibilidad
@bp.route("/<client_id>/update-sensitivity", methods=["POST"])
@login_required
def update_sensitivity(client_id):
    client = Client.query.get_or_404(client_id)
    data = request.get_json()
    try:
        cat = int(data.get("category_confidence_threshold", client.category_confidence_threshold or 70))
        prod = int(data.get("product_similarity_threshold", client.product_similarity_threshold or 30))
        client.category_confidence_threshold = cat
        client.product_similarity_threshold = prod
        db.session.commit()
        return jsonify({"success": True, "category_confidence_threshold": cat, "product_similarity_threshold": prod})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})
