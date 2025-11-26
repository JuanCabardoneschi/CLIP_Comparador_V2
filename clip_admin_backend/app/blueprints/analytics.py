"""
Blueprint de Analytics
Estadísticas y métricas del sistema
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.client import Client
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
        "active_api_keys": Client.query.filter(Client.api_key.isnot(None), Client.is_active == True).count()
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
    ).join(SearchLog).group_by(
        Client.id, Client.name
    ).order_by(desc("search_count")).limit(10).all()

    return render_template("analytics/clients.html",
                           top_clients=top_clients,
                           client_searches=client_searches)


@bp.route("/searches")
@login_required
def searches():
    """Analytics de búsquedas"""
    # Periodo de análisis (por defecto 30 días)
    days = request.args.get('days', 30, type=int)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Búsquedas por día
    daily_searches = db.session.query(
        func.date(SearchLog.created_at).label("date"),
        func.count(SearchLog.id).label("count")
    ).filter(
        SearchLog.created_at >= start_date
    ).group_by(
        func.date(SearchLog.created_at)
    ).order_by("date").all()

    # Top queries de texto
    top_queries = db.session.query(
        SearchLog.query_text,
        func.count(SearchLog.id).label("count")
    ).filter(
        SearchLog.query_text.isnot(None),
        SearchLog.created_at >= start_date
    ).group_by(
        SearchLog.query_text
    ).order_by(desc("count")).limit(20).all()

    # Búsquedas por tipo
    search_types = db.session.query(
        SearchLog.search_type,
        func.count(SearchLog.id).label("count")
    ).filter(
        SearchLog.created_at >= start_date
    ).group_by(
        SearchLog.search_type
    ).all()

    # 🆕 Tasa de éxito (búsquedas con resultados vs sin resultados)
    success_rate = db.session.query(
        func.sum(func.cast(SearchLog.had_results, db.Integer)).label('with_results'),
        func.count(SearchLog.id).label('total')
    ).filter(
        SearchLog.created_at >= start_date
    ).first()

    success_percentage = 0
    if success_rate and success_rate.total > 0:
        success_percentage = round((success_rate.with_results / success_rate.total) * 100, 1)

    return render_template("analytics/searches.html",
                           daily_searches=daily_searches,
                           top_queries=top_queries,
                           search_types=search_types,
                           success_percentage=success_percentage,
                           days=days)


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
        "total_embeddings": Image.query.filter(Image.clip_embedding.isnot(None)).count(),
        "images_without_embeddings": Image.query.filter(Image.clip_embedding.is_(None)).count(),
        "avg_confidence": 1.0  # Placeholder ya que no tenemos campo confidence_score
    }

    return render_template("analytics/performance.html",
                           avg_response_time=avg_response_time,
                           response_times=response_times,
                           embedding_stats=embedding_stats)


@bp.route("/gaps")
@login_required
def gaps():
    """🆕 Analytics de Gap Detection - Oportunidades de catálogo"""
    # Periodo de análisis (por defecto 60 días)
    days = request.args.get('days', 60, type=int)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # 1. Categorías más buscadas que NO están en el catálogo
    from sqlalchemy import func, text
    missing_categories = db.session.execute(
        text("""
            SELECT
                unnest(categories_missing) as category_name,
                COUNT(*) as search_count
            FROM search_logs
            WHERE created_at >= :start_date
              AND categories_missing IS NOT NULL
              AND array_length(categories_missing, 1) > 0
            GROUP BY category_name
            ORDER BY search_count DESC
            LIMIT 20
        """),
        {"start_date": start_date}
    ).fetchall()

    # 2. Términos/atributos más buscados que NO matchean
    unmatched_terms = db.session.execute(
        text("""
            SELECT
                unnest(terms_unmatched) as term,
                COUNT(*) as search_count
            FROM search_logs
            WHERE created_at >= :start_date
              AND terms_unmatched IS NOT NULL
              AND array_length(terms_unmatched, 1) > 0
            GROUP BY term
            ORDER BY search_count DESC
            LIMIT 30
        """),
        {"start_date": start_date}
    ).fetchall()

    # 3. Búsquedas sin resultados (0 products found)
    zero_results = db.session.query(
        SearchLog.query_text,
        SearchLog.categories_detected,
        func.count(SearchLog.id).label("count")
    ).filter(
        SearchLog.created_at >= start_date,
        SearchLog.results_count == 0,
        SearchLog.query_text.isnot(None)
    ).group_by(
        SearchLog.query_text,
        SearchLog.categories_detected
    ).order_by(desc("count")).limit(20).all()

    # 4. Categorías detectadas vs matcheadas (eficiencia)
    category_efficiency = db.session.execute(
        text("""
            SELECT
                unnest(categories_detected) as category_name,
                COUNT(*) as detected_count,
                SUM(CASE WHEN unnest(categories_detected) = ANY(categories_matched) THEN 1 ELSE 0 END) as matched_count
            FROM search_logs
            WHERE created_at >= :start_date
              AND categories_detected IS NOT NULL
              AND array_length(categories_detected, 1) > 0
            GROUP BY category_name
            ORDER BY detected_count DESC
            LIMIT 15
        """),
        {"start_date": start_date}
    ).fetchall()

    return render_template("analytics/gaps.html",
                           missing_categories=missing_categories,
                           unmatched_terms=unmatched_terms,
                           zero_results=zero_results,
                           category_efficiency=category_efficiency,
                           days=days)


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
        "images": db.session.query(Image).join(Product).join(Category).filter(
            Category.client_id == client_id
        ).count(),
        "api_keys": 1 if client.api_key else 0,  # En este sistema cada cliente tiene máximo 1 API key
        "active_keys": 1 if client.api_key and client.is_active else 0
    }

    # Búsquedas del cliente (últimos 30 días)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    client_searches = db.session.query(
        func.date(SearchLog.created_at).label("date"),
        func.count(SearchLog.id).label("count")
    ).filter(
        SearchLog.client_id == client_id,
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
        "images": Image.query.count(),
        "searches_today": SearchLog.query.filter(
            func.date(SearchLog.created_at) == datetime.now().date()
        ).count(),
        "active_api_keys": Client.query.filter(Client.api_key.isnot(None), Client.is_active == True).count()
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
        "images": db.session.query(Image).join(Product).join(Category).filter(
            Category.client_id == client_id
        ).count(),
        "searches_last_30_days": db.session.query(SearchLog).filter(
            SearchLog.client_id == client_id,
            SearchLog.created_at >= datetime.now() - timedelta(days=30)
        ).count()
    })


@bp.route("/api/stats/gaps")
@login_required
def api_gaps():
    """🆕 API endpoint para gap detection data"""
    days = request.args.get('days', 60, type=int)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    from sqlalchemy import text

    # Categorías faltantes
    missing_cats = db.session.execute(
        text("""
            SELECT
                unnest(categories_missing) as category,
                COUNT(*) as count
            FROM search_logs
            WHERE created_at >= :start_date
              AND categories_missing IS NOT NULL
              AND array_length(categories_missing, 1) > 0
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10
        """),
        {"start_date": start_date}
    ).fetchall()

    # Términos no matcheados
    unmatched = db.session.execute(
        text("""
            SELECT
                unnest(terms_unmatched) as term,
                COUNT(*) as count
            FROM search_logs
            WHERE created_at >= :start_date
              AND terms_unmatched IS NOT NULL
              AND array_length(terms_unmatched, 1) > 0
            GROUP BY term
            ORDER BY count DESC
            LIMIT 15
        """),
        {"start_date": start_date}
    ).fetchall()

    return jsonify({
        "missing_categories": [{"name": row[0], "count": row[1]} for row in missing_cats],
        "unmatched_terms": [{"term": row[0], "count": row[1]} for row in unmatched],
        "period_days": days
    })

