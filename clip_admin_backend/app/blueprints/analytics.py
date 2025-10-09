"""
Blueprint de Analytics
Estadísticas y métricas del sistema
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.client import Client
# APIKey temporalmente deshabilitado
from app.models.product import Product
from app.models.image import Image
from app.models.search_log import SearchLog
from app.models.category import Category
from sqlalchemy import func, desc
from datetime import datetime, timedelta

bp = Blueprint("analytics", __name__)


@bp.route("/")
@login_required
def index():
    """Dashboard de analytics principal"""
    # Estadísticas generales
    stats = {
        "total_clients": Client.query.count(),
        "total_products": Product.query.count(),
        "total_images": Image.query.count(),
        "total_searches": SearchLog.query.count(),
        "active_api_keys": APIKey.query.filter_by(is_active=True).count()
    }

    return render_template("analytics/index.html", stats=stats)


@bp.route("/clients")
@login_required
def clients():
    """Analytics por cliente"""
    # Top clientes por productos
    top_clients = db.session.query(
        Client.name,
        Client.id,
        func.count(Product.id).label("product_count")
    ).join(Category).join(Product).group_by(
        Client.id, Client.name
    ).order_by(desc("product_count")).limit(10).all()

    # Clientes por búsquedas
    client_searches = db.session.query(
        Client.name,
        Client.id,
        func.count(SearchLog.id).label("search_count")
    ).join(APIKey).join(SearchLog).group_by(
        Client.id, Client.name
    ).order_by(desc("search_count")).limit(10).all()

    return render_template("analytics/clients.html",
                         top_clients=top_clients,
                         client_searches=client_searches)


@bp.route("/searches")
@login_required
def searches():
    """Analytics de búsquedas"""
    # Búsquedas por día (últimos 30 días)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    daily_searches = db.session.query(
        func.date(SearchLog.created_at).label("date"),
        func.count(SearchLog.id).label("count")
    ).filter(
        SearchLog.created_at >= start_date
    ).group_by(
        func.date(SearchLog.created_at)
    ).order_by("date").all()

    # Top términos de búsqueda
    top_queries = db.session.query(
        SearchLog.query_text,
        func.count(SearchLog.id).label("count")
    ).filter(
        SearchLog.query_text.isnot(None)
    ).group_by(
        SearchLog.query_text
    ).order_by(desc("count")).limit(20).all()

    # Búsquedas por tipo
    search_types = db.session.query(
        SearchLog.search_type,
        func.count(SearchLog.id).label("count")
    ).group_by(
        SearchLog.search_type
    ).all()

    return render_template("analytics/searches.html",
                         daily_searches=daily_searches,
                         top_queries=top_queries,
                         search_types=search_types)


@bp.route("/performance")
@login_required
def performance():
    """Analytics de rendimiento"""
    # Tiempo promedio de respuesta
    avg_response_time = db.session.query(
        func.avg(SearchLog.response_time_ms)
    ).scalar() or 0

    # Distribución de tiempos de respuesta
    response_times = db.session.query(
        SearchLog.response_time_ms,
        SearchLog.results_count,
        SearchLog.created_at
    ).filter(
        SearchLog.response_time_ms.isnot(None)
    ).order_by(desc(SearchLog.created_at)).limit(100).all()

    # Estadísticas de embeddings
    embedding_stats = {
        "total_embeddings": ImageEmbedding.query.count(),
        "images_without_embeddings": db.session.query(ProductImage).outerjoin(
            ImageEmbedding
        ).filter(ImageEmbedding.id.is_(None)).count(),
        "avg_confidence": db.session.query(
            func.avg(ImageEmbedding.confidence_score)
        ).scalar() or 0
    }

    return render_template("analytics/performance.html",
                         avg_response_time=avg_response_time,
                         response_times=response_times,
                         embedding_stats=embedding_stats)


@bp.route("/client/<client_id>")
@login_required
def client_detail(client_id):
    """Analytics detallado de un cliente"""
    client = Client.query.get_or_404(client_id)

    # Estadísticas del cliente
    client_stats = {
        "categories": Category.query.filter_by(client_id=client_id).count(),
        "products": db.session.query(Product).join(Category).filter(
            Category.client_id == client_id
        ).count(),
        "images": db.session.query(ProductImage).join(Product).join(Category).filter(
            Category.client_id == client_id
        ).count(),
        "api_keys": APIKey.query.filter_by(client_id=client_id).count(),
        "active_keys": APIKey.query.filter_by(
            client_id=client_id, is_active=True
        ).count()
    }

    # Búsquedas del cliente (últimos 30 días)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    client_searches = db.session.query(
        func.date(SearchLog.created_at).label("date"),
        func.count(SearchLog.id).label("count")
    ).join(APIKey).filter(
        APIKey.client_id == client_id,
        SearchLog.created_at >= start_date
    ).group_by(
        func.date(SearchLog.created_at)
    ).order_by("date").all()

    # Categorías más populares
    popular_categories = db.session.query(
        Category.name,
        func.count(Product.id).label("product_count")
    ).outerjoin(Product).filter(
        Category.client_id == client_id
    ).group_by(
        Category.id, Category.name
    ).order_by(desc("product_count")).all()

    return render_template("analytics/client_detail.html",
                         client=client,
                         client_stats=client_stats,
                         client_searches=client_searches,
                         popular_categories=popular_categories)


@bp.route("/api/stats/overview")
@login_required
def api_stats_overview():
    """API endpoint para estadísticas generales"""
    return jsonify({
        "clients": Client.query.count(),
        "products": Product.query.count(),
        "images": ProductImage.query.count(),
        "searches_today": SearchLog.query.filter(
            func.date(SearchLog.created_at) == datetime.now().date()
        ).count(),
        "active_api_keys": APIKey.query.filter_by(is_active=True).count()
    })


@bp.route("/api/stats/searches-by-day")
@login_required
def api_searches_by_day():
    """API endpoint para búsquedas por día"""
    days = request.args.get("days", 30, type=int)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    results = db.session.query(
        func.date(SearchLog.created_at).label("date"),
        func.count(SearchLog.id).label("count")
    ).filter(
        SearchLog.created_at >= start_date
    ).group_by(
        func.date(SearchLog.created_at)
    ).order_by("date").all()

    return jsonify([{
        "date": result.date.isoformat(),
        "count": result.count
    } for result in results])


@bp.route("/api/stats/client/<client_id>")
@login_required
def api_client_stats(client_id):
    """API endpoint para estadísticas de cliente específico"""
    client = Client.query.get_or_404(client_id)

    return jsonify({
        "client_name": client.name,
        "categories": Category.query.filter_by(client_id=client_id).count(),
        "products": db.session.query(Product).join(Category).filter(
            Category.client_id == client_id
        ).count(),
        "images": db.session.query(ProductImage).join(Product).join(Category).filter(
            Category.client_id == client_id
        ).count(),
        "searches_last_30_days": db.session.query(SearchLog).join(APIKey).filter(
            APIKey.client_id == client_id,
            SearchLog.created_at >= datetime.now() - timedelta(days=30)
        ).count()
    })
