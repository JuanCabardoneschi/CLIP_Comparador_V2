"""
Blueprint de Usuarios
Gestión de usuarios del sistema (CRUD, contraseñas, permisos)
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.client import Client
from app.utils.permissions import requires_super_admin
import secrets
import string

bp = Blueprint("users", __name__)


@bp.route("/")
@login_required
def index():
    """Lista de todos los usuarios"""
    if current_user.is_super_admin:
        # Super Admin ve todos los usuarios
        users = User.query.order_by(User.created_at.desc()).all()
    else:
        # Admin de tienda solo ve usuarios de su cliente
        users = User.query.filter_by(client_id=current_user.client_id).order_by(User.created_at.desc()).all()

    return render_template("users/index.html", users=users)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Crear nuevo usuario"""
    # Obtener lista de clientes para el formulario
    if current_user.is_super_admin:
        clients = Client.query.filter_by(is_active=True).all()
    else:
        # Admin de tienda solo puede crear usuarios de su propio cliente
        clients = Client.query.filter_by(id=current_user.client_id).all()

    if request.method == "POST":
        email = request.form.get("email")
        full_name = request.form.get("full_name")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        client_id = request.form.get("client_id")
        role = request.form.get("role", "STORE_ADMIN")
        send_credentials = request.form.get("send_credentials") == "on"

        # Validaciones
        if not email or not full_name or not password or not client_id:
            flash("Email, nombre completo, contraseña y cliente son requeridos", "error")
            return render_template("users/create.html", clients=clients)

        if password != confirm_password:
            flash("Las contraseñas no coinciden", "error")
            return render_template("users/create.html", clients=clients)

        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres", "error")
            return render_template("users/create.html", clients=clients)

        # Verificar permisos
        if not current_user.is_super_admin:
            if str(client_id) != str(current_user.client_id):
                flash("No tienes permisos para crear usuarios de otros clientes", "error")
                return redirect(url_for("users.index"))
            if role == "SUPER_ADMIN":
                flash("No tienes permisos para crear Super Administradores", "error")
                return render_template("users/create.html", clients=clients)

        # Verificar que no exista un usuario con el mismo email
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Ya existe un usuario con ese email", "error")
            return render_template("users/create.html", clients=clients)

        # Crear usuario
        user = User(
            email=email,
            full_name=full_name,
            client_id=client_id,
            role=role,
            active=True
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        # Mostrar las credenciales en pantalla
        flash(f"Usuario '{full_name}' creado exitosamente", "success")
        flash(f"📧 Email: {email}", "info")
        flash(f"🔑 Contraseña: {password}", "info")
        flash("⚠️ IMPORTANTE: Guarda estas credenciales, la contraseña no se mostrará nuevamente", "warning")

        # TODO: Enviar credenciales por email si send_credentials está activado

        return redirect(url_for("users.view", user_id=user.id))

    return render_template("users/create.html", clients=clients)


@bp.route("/<user_id>")
@login_required
def view(user_id):
    """Ver detalles de un usuario"""
    user = User.query.get_or_404(user_id)

    # Verificar permisos
    if not current_user.can_access_client(user.client_id) and current_user.id != user.id:
        flash("No tienes permisos para ver este usuario", "error")
        return redirect(url_for("users.index"))

    return render_template("users/view.html", user=user)


@bp.route("/<user_id>/edit", methods=["GET", "POST"])
@login_required
def edit(user_id):
    """Editar usuario"""
    user = User.query.get_or_404(user_id)

    # Verificar permisos
    if not current_user.can_access_client(user.client_id) and current_user.id != user.id:
        flash("No tienes permisos para editar este usuario", "error")
        return redirect(url_for("users.index"))

    if request.method == "POST":
        user.full_name = request.form.get("full_name", user.full_name)
        user.email = request.form.get("email", user.email)

        # Solo Super Admin puede cambiar el rol
        if current_user.is_super_admin:
            user.role = request.form.get("role", user.role)
            user.active = request.form.get("active") == "on"

        db.session.commit()
        flash("Usuario actualizado exitosamente", "success")
        return redirect(url_for("users.view", user_id=user.id))

    # Obtener clientes para el select
    if current_user.is_super_admin:
        clients = Client.query.filter_by(is_active=True).all()
    else:
        clients = Client.query.filter_by(id=current_user.client_id).all()

    return render_template("users/edit.html", user=user, clients=clients)


@bp.route("/<user_id>/reset-password", methods=["POST"])
@login_required
def reset_password(user_id):
    """Resetear contraseña de un usuario"""
    user = User.query.get_or_404(user_id)

    # Verificar permisos
    if not current_user.can_access_client(user.client_id) and current_user.id != user.id:
        flash("No tienes permisos para resetear la contraseña de este usuario", "error")
        return redirect(url_for("users.index"))

    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not new_password or not confirm_password:
        flash("Debes ingresar y confirmar la nueva contraseña", "error")
        return redirect(url_for("users.view", user_id=user.id))

    if new_password != confirm_password:
        flash("Las contraseñas no coinciden", "error")
        return redirect(url_for("users.view", user_id=user.id))

    if len(new_password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres", "error")
        return redirect(url_for("users.view", user_id=user.id))

    user.set_password(new_password)
    db.session.commit()

    flash("Contraseña actualizada exitosamente", "success")
    flash(f"🔑 Nueva contraseña: {new_password}", "info")
    flash("⚠️ IMPORTANTE: Guarda esta contraseña, no se mostrará nuevamente", "warning")

    return redirect(url_for("users.view", user_id=user.id))


@bp.route("/<user_id>/delete", methods=["POST"])
@login_required
@requires_super_admin
def delete(user_id):
    """Eliminar usuario (solo Super Admin)"""
    user = User.query.get_or_404(user_id)

    # No permitir eliminar el propio usuario
    if user.id == current_user.id:
        flash("No puedes eliminar tu propio usuario", "error")
        return redirect(url_for("users.view", user_id=user.id))

    if request.form.get("confirm") == "DELETE":
        db.session.delete(user)
        db.session.commit()
        flash(f"Usuario '{user.full_name}' eliminado exitosamente", "success")
        return redirect(url_for("users.index"))

    flash("Confirmación requerida para eliminar usuario", "error")
    return redirect(url_for("users.view", user_id=user.id))


@bp.route("/<user_id>/toggle-active", methods=["POST"])
@login_required
@requires_super_admin
def toggle_active(user_id):
    """Activar/desactivar usuario"""
    user = User.query.get_or_404(user_id)

    # No permitir desactivar el propio usuario
    if user.id == current_user.id:
        flash("No puedes desactivar tu propio usuario", "error")
        return redirect(url_for("users.view", user_id=user.id))

    user.active = not user.active
    db.session.commit()

    status = "activado" if user.active else "desactivado"
    flash(f"Usuario {status} exitosamente", "success")

    return redirect(url_for("users.view", user_id=user.id))
