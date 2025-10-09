"""
Blueprint Principal
Página de inicio y rutas básicas
"""

import os
from flask import Blueprint, redirect, url_for, send_from_directory, current_app, abort
from flask_login import current_user

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    """Página de inicio - redirige según estado de autenticación"""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    else:
        return redirect(url_for("auth.login"))


@bp.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "clip-admin-backend", "version": "2.0.0"}


@bp.route("/favicon.ico")
def favicon():
    """Servir favicon"""
    return send_from_directory(
        os.path.join(current_app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )


@bp.route("/debug/routes")
def debug_routes():
    """Debug endpoint para listar todas las rutas"""
    routes = []
    for rule in current_app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods": list(rule.methods),
            "url": str(rule)
        })

    return {"routes": routes, "total": len(routes)}


@bp.route("/uploads/clients/<client_folder>/<filename>")
def uploaded_file(client_folder, filename):
    """Servir archivos de clientes"""
    # Intentar primero en clip_admin_backend/static/uploads/clients/
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'clients', client_folder)
    file_path = os.path.join(upload_folder, filename)

    if os.path.exists(file_path):
        return send_from_directory(upload_folder, filename)

    # Ruta alternativa fuera de app/
    alt_upload_folder = os.path.join(os.path.dirname(current_app.root_path), 'static', 'uploads', 'clients', client_folder)
    alt_file_path = os.path.join(alt_upload_folder, filename)

    if os.path.exists(alt_file_path):
        return send_from_directory(alt_upload_folder, filename)

    abort(404)
