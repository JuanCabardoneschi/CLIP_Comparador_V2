"""
Blueprint de Autenticación
Login, logout y gestión de sesiones
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Login del usuario"""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        remember = request.form.get("remember") == "on"

        if not email or not password:
            flash("Email y contraseña son requeridos", "error")
            return render_template("auth/login.html")

        # Buscar usuario
        user = User.query.filter_by(email=email).first()

        if user:
            if user.check_password(password):
                login_result = login_user(user, remember=remember)

                # Force session save
                session.permanent = False
                session.modified = True

                flash(f"Bienvenido {user.full_name or user.email}!", "success")

                # Redirigir a la página solicitada o al dashboard
                next_page = request.args.get("next")
                redirect_url = next_page if next_page else url_for("dashboard.index")
                return redirect(redirect_url)
            else:
                flash("Credenciales inválidas", "error")
        else:
            flash("Credenciales inválidas", "error")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    """Logout del usuario"""
    logout_user()
    flash("Has cerrado sesión exitosamente", "info")
    return redirect(url_for("auth.login"))
