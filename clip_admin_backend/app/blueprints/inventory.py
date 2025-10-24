"""
Blueprint de Inventario (Gestión de Stock)
Panel de administración para gestionar stock de productos
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models.product import Product
from app.models.category import Category
from app.models.client import Client
from datetime import datetime

bp = Blueprint('inventory', __name__, url_prefix='/inventory')


@bp.route('/')
@login_required
def index():
    """
    Vista principal de inventario
    Carga vacía - solo trae productos al filtrar
    """
    # Obtener parámetros de filtro
    category_id = request.args.get('category_id')
    search = request.args.get('search', '').strip()
    stock_filter = request.args.get('stock_filter')  # 'low', 'out', 'available'
    
    # Determinar si hay filtros activos
    has_filters = bool(category_id or search or stock_filter)
    
    # Solo cargar productos si hay filtros aplicados
    products = []
    if has_filters:
        # Query base
        query = Product.query.filter_by(client_id=current_user.client_id)

        # Filtrar por categoría
        if category_id:
            query = query.filter_by(category_id=category_id)

        # Búsqueda por nombre o SKU
        if search:
            query = query.filter(
                db.or_(
                    Product.name.ilike(f'%{search}%'),
                    Product.sku.ilike(f'%{search}%')
                )
            )

        # Filtrar por estado de stock
        if stock_filter == 'out':
            query = query.filter(Product.stock == 0)
        elif stock_filter == 'low':
            query = query.filter(Product.stock > 0, Product.stock <= 10)
        elif stock_filter == 'available':
            query = query.filter(Product.stock > 10)

        # Ordenar por stock (productos sin stock primero)
        products = query.order_by(Product.stock.asc(), Product.name.asc()).all()

    # Obtener categorías para el filtro
    categories = Category.query.filter_by(
        client_id=current_user.client_id,
        is_active=True
    ).order_by(Category.name).all()

    # Estadísticas (siempre se muestran)
    total_products = Product.query.filter_by(client_id=current_user.client_id).count()
    out_of_stock = Product.query.filter_by(client_id=current_user.client_id, stock=0).count()
    low_stock = Product.query.filter_by(client_id=current_user.client_id).filter(
        Product.stock > 0, Product.stock <= 10
    ).count()

    stats = {
        'total': total_products,
        'out_of_stock': out_of_stock,
        'low_stock': low_stock,
        'available': total_products - out_of_stock - low_stock
    }

    return render_template(
        'inventory/index.html',
        products=products,
        categories=categories,
        stats=stats,
        has_filters=has_filters,
        current_category=category_id,
        current_search=search,
        current_filter=stock_filter
    )


@bp.route('/api/adjust-stock', methods=['POST'])
@login_required
def adjust_stock():
    """
    API para ajustar stock de un producto manualmente

    Request JSON:
        {
            "product_id": "uuid",
            "adjustment": 10,  # positivo para aumentar, negativo para reducir
            "reason": "Ajuste manual - conteo físico"
        }
    """
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        adjustment = int(data.get('adjustment', 0))
        reason = data.get('reason', 'Ajuste manual')

        if not product_id:
            return jsonify({
                'success': False,
                'error': 'product_id es requerido'
            }), 400

        if adjustment == 0:
            return jsonify({
                'success': False,
                'error': 'El ajuste debe ser diferente de 0'
            }), 400

        # Obtener producto
        product = Product.query.filter_by(
            id=product_id,
            client_id=current_user.client_id
        ).first()

        if not product:
            return jsonify({
                'success': False,
                'error': 'Producto no encontrado'
            }), 404

        # Guardar stock anterior
        old_stock = product.stock
        new_stock = max(0, old_stock + adjustment)  # No permitir stock negativo

        # Actualizar stock
        product.stock = new_stock
        product.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Stock actualizado correctamente',
            'product_id': product.id,
            'old_stock': old_stock,
            'new_stock': new_stock,
            'adjustment': adjustment,
            'reason': reason
        })

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'El ajuste debe ser un número entero'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Error ajustando stock: {str(e)}'
        }), 500


@bp.route('/api/set-stock', methods=['POST'])
@login_required
def set_stock():
    """
    API para establecer un stock específico (sin ajuste relativo)

    Request JSON:
        {
            "product_id": "uuid",
            "stock": 50,
            "reason": "Inventario inicial"
        }
    """
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        new_stock = int(data.get('stock', 0))
        reason = data.get('reason', 'Ajuste manual')

        if not product_id:
            return jsonify({
                'success': False,
                'error': 'product_id es requerido'
            }), 400

        if new_stock < 0:
            return jsonify({
                'success': False,
                'error': 'El stock no puede ser negativo'
            }), 400

        # Obtener producto
        product = Product.query.filter_by(
            id=product_id,
            client_id=current_user.client_id
        ).first()

        if not product:
            return jsonify({
                'success': False,
                'error': 'Producto no encontrado'
            }), 404

        old_stock = product.stock
        product.stock = new_stock
        product.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Stock establecido correctamente',
            'product_id': product.id,
            'old_stock': old_stock,
            'new_stock': new_stock,
            'adjustment': new_stock - old_stock,
            'reason': reason
        })

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'El stock debe ser un número entero'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Error estableciendo stock: {str(e)}'
        }), 500
