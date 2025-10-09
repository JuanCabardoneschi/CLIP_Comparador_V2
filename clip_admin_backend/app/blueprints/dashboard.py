"""
Blueprint del Dashboard
Panel principal de administración
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import db
from app.models.client import Client
from app.models.user import User
from app.models.image import Image
from app.models.product import Product
# from app.models.search_log import SearchLog  # TODO: Implementar cuando se cree la tabla
from app.utils.permissions import requires_role, filter_by_client_scope

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
@requires_role('SUPER_ADMIN', 'STORE_ADMIN')
def index():
    """Dashboard principal - Diferenciado por rol"""

    if current_user.role == 'SUPER_ADMIN':
        # Dashboard para Super Admin - Estadísticas globales
        total_clients = Client.query.count()
        total_users = User.query.count()
        total_images = Image.query.count()
        total_processed_images = Image.query.filter_by(is_processed=True).count()

        context = {
            'role': 'super_admin',
            'stats': {
                'total_clients': total_clients,
                'total_users': total_users,
                'total_images': total_images,
                'total_processed_images': total_processed_images,
                'processing_percentage': round((total_processed_images / total_images * 100) if total_images > 0 else 0, 1)
            }
        }

    elif current_user.role == 'STORE_ADMIN':
        # Dashboard para Store Admin - Solo sus datos
        images_query = Image.query
        images_query = filter_by_client_scope(images_query)

        products_query = Product.query
        products_query = filter_by_client_scope(products_query)

        my_total_images = images_query.count()
        my_processed_images = images_query.filter_by(is_processed=True).count()
        my_pending_images = images_query.filter_by(is_processed=False, upload_status='pending').count()
        my_failed_images = images_query.filter_by(upload_status='failed').count()

        my_total_products = products_query.count()
        my_active_products = products_query.filter_by(is_active=True).count()

        # TODO: Búsquedas cuando se implemente la tabla search_logs
        my_searches_today = 0  # Placeholder hasta implementar search_logs

        context = {
            'role': 'store_admin',
            'client_name': current_user.client.name if current_user.client else 'Cliente no asignado',
            'stats': {
                'my_total_images': my_total_images,
                'my_processed_images': my_processed_images,
                'my_pending_images': my_pending_images,
                'my_failed_images': my_failed_images,
                'my_total_products': my_total_products,
                'my_active_products': my_active_products,
                'my_searches_today': my_searches_today,
                'processing_percentage': round((my_processed_images / my_total_images * 100) if my_total_images > 0 else 0, 1)
            }
        }

    return render_template("dashboard/index.html", **context)


@bp.route("/api/stats")
@login_required
def api_stats():
    """API endpoint para estadísticas del dashboard"""
    return {"message": "Dashboard stats - TODO"}
