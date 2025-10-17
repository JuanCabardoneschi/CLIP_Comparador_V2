"""
Middleware de permisos para sistema de roles
"""

from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def requires_role(*allowed_roles):
    """
    Decorador para requerir roles específicos

    Usage:
        @requires_role('SUPER_ADMIN')
        @requires_role('SUPER_ADMIN', 'STORE_ADMIN')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Debes iniciar sesión para acceder a esta página', 'error')
                return redirect(url_for('auth.login'))

            if not current_user.is_active:
                flash('Tu cuenta está desactivada', 'error')
                return redirect(url_for('auth.login'))

            if current_user.role not in allowed_roles:
                flash(f'No tienes permisos para acceder a esta sección. Rol requerido: {", ".join(allowed_roles)}', 'error')
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def requires_super_admin(f):
    """Decorador específico para super admin"""
    return requires_role('SUPER_ADMIN')(f)


def requires_client_scope(f):
    """
    Decorador para asegurar que STORE_ADMIN solo vea datos de su cliente
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión', 'error')
            return redirect(url_for('auth.login'))

        # Super admin puede ver todo
        if current_user.role == 'SUPER_ADMIN':
            return f(*args, **kwargs)

        # Store admin debe tener client_id
        if current_user.role == 'STORE_ADMIN':
            if not current_user.client_id:
                flash('Error: Usuario sin cliente asignado', 'error')
                abort(403)
            return f(*args, **kwargs)

        # Otros roles no permitidos
        flash('Rol no autorizado para esta acción', 'error')
        abort(403)

    return decorated_function


def get_client_filter():
    """
    Retorna el filtro de cliente para queries

    Returns:
        - None si es SUPER_ADMIN (ve todo)
        - client_id si es STORE_ADMIN (solo su cliente)
    """
    if not current_user.is_authenticated:
        return None

    if current_user.role == 'SUPER_ADMIN':
        return None  # Ve todo

    if current_user.role == 'STORE_ADMIN':
        return current_user.client_id

    return None


def filter_by_client_scope(query, model=None):
    """
    Aplica filtro de cliente a una query SQLAlchemy

    Args:
        query: Query SQLAlchemy
        model: Modelo que tiene client_id (opcional, se infiere)

    Returns:
        Query filtrada por cliente si es necesario
    """
    client_filter = get_client_filter()

    if client_filter is None:
        return query  # Super admin ve todo

    # Aplicar filtro por client_id
    return query.filter_by(client_id=client_filter)


# Alias para compatibilidad
admin_required = requires_client_scope
