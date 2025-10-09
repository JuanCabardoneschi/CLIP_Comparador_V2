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
    print(f"� INICIO LOGIN: Método {request.method}")
    print(f"🔥 INICIO LOGIN: Headers: {dict(request.headers)}")
    print(f"🔥 INICIO LOGIN: Form data: {dict(request.form)}")
    print(f"�🔐 LOGIN: Método {request.method}")

    if current_user.is_authenticated:
        print(f"🔐 LOGIN: Usuario ya autenticado: {current_user.email}")
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        remember = request.form.get("remember") == "on"

        print(f"🔐 LOGIN: Intento de login - Email: {email}, Remember: {remember}")

        if not email or not password:
            print("🔐 LOGIN: Email o contraseña faltantes")
            flash("Email y contraseña son requeridos", "error")
            return render_template("auth/login.html")

        # Buscar usuario
        print(f"🔐 LOGIN: Buscando usuario con email: {email}")
        user = User.query.filter_by(email=email).first()

        if user:
            print(f"🔐 LOGIN: Usuario encontrado - ID: {user.id}, Active: {user.active}")
            print(f"🔐 LOGIN: Verificando contraseña...")

            if user.check_password(password):
                print(f"🔐 LOGIN: Contraseña correcta, intentando login_user...")
                print(f"🔐 LOGIN: user.is_active: {user.is_active}")
                print(f"🔐 LOGIN: user.is_authenticated: {user.is_authenticated}")
                print(f"🔐 LOGIN: user.get_id(): {user.get_id()}")

                login_result = login_user(user, remember=remember)
                print(f"🔐 LOGIN: login_user result: {login_result}")

                # Verificar session después del login
                print(f"🔐 LOGIN: Session después de login_user: {dict(session)}")
                print(f"🔐 LOGIN: current_user después de login_user: {current_user.is_authenticated}")

                # Debug adicional de Flask globals y configuración
                print(f"🔐 LOGIN: flask.g: {vars(g) if hasattr(g, '__dict__') else 'N/A'}")
                print(f"🔐 LOGIN: SESSION_COOKIE_NAME: {current_app.config.get('SESSION_COOKIE_NAME')}")
                print(f"🔐 LOGIN: SECRET_KEY length: {len(current_app.config.get('SECRET_KEY', ''))}")

                # Force session save
                session.permanent = False
                session.modified = True
                print("🔐 LOGIN: Session modified flag establecido")

                flash(f"Bienvenido {user.full_name or user.email}!", "success")

                # Redirigir a la página solicitada o al dashboard
                next_page = request.args.get("next")
                redirect_url = next_page if next_page else url_for("dashboard.index")
                print(f"🔐 LOGIN: Redirigiendo a: {redirect_url}")
                return redirect(redirect_url)
            else:
                print("🔐 LOGIN: Contraseña incorrecta")
                flash("Credenciales inválidas", "error")
        else:
            print(f"🔐 LOGIN: Usuario no encontrado con email: {email}")
            flash("Credenciales inválidas", "error")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    """Logout del usuario"""
    logout_user()
    flash("Has cerrado sesión exitosamente", "info")
    return redirect(url_for("auth.login"))
