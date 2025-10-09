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
    """Crear nuevo cliente - Solo Super Admin"""
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        description = request.form.get("description", "")
        industry = request.form.get("industry", "general")

        if not name or not email:
            flash("Nombre y email son requeridos", "error")
            return render_template("clients/create.html")

        # Verificar que no exista un cliente con el mismo email
        existing = Client.query.filter_by(email=email).first()
        if existing:
            flash("Ya existe un cliente con ese email", "error")
            return render_template("clients/create.html")

        # Crear cliente
        client = Client(name=name, email=email, description=description, industry=industry)
        db.session.add(client)
        db.session.commit()

        flash(f"Cliente '{name}' creado exitosamente", "success")
        return redirect(url_for("clients.view", client_id=client.id))

    return render_template("clients/create.html")


@bp.route("/<client_id>")
@login_required
def view(client_id):
    """Ver detalles de un cliente"""
    client = Client.query.get_or_404(client_id)
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
