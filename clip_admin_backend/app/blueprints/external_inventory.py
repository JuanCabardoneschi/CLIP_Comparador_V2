"""
Blueprint de API Externa de Inventario
Endpoints públicos para integración externa (ecommerce, POS, etc.)
Requiere autenticación con API Key
"""
from flask import Blueprint, request, jsonify
from app import db
from app.models.product import Product
from app.utils.api_auth import require_api_key
from datetime import datetime

bp = Blueprint('external_inventory', __name__, url_prefix='/api/external/inventory')


@bp.route('/reduce-stock', methods=['POST'])
@require_api_key
def reduce_stock():
    """
    Reducir stock de un producto (para ventas externas)
    
    Headers:
        X-API-Key: clip_xxxxxxxxxxxxxxxxxxxx
    
    Request JSON:
        {
            "product_id": "uuid",
            "quantity": 1,
            "reason": "Venta online #12345" (opcional)
        }
        
    O usando SKU:
        {
            "sku": "PROD-001",
            "quantity": 2,
            "reason": "Venta POS #67890" (opcional)
        }
    
    Response JSON:
        {
            "success": true,
            "message": "Stock reducido correctamente",
            "product_id": "uuid",
            "product_name": "Nombre del Producto",
            "old_stock": 10,
            "new_stock": 9,
            "quantity_reduced": 1
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Body JSON requerido'
            }), 400
        
        # Obtener parámetros
        product_id = data.get('product_id')
        sku = data.get('sku')
        quantity = data.get('quantity')
        reason = data.get('reason', 'Reducción de stock externa')
        
        # Validar parámetros
        if not product_id and not sku:
            return jsonify({
                'success': False,
                'error': 'Debe proporcionar product_id o sku'
            }), 400
        
        if not quantity or quantity <= 0:
            return jsonify({
                'success': False,
                'error': 'quantity debe ser un número positivo'
            }), 400
        
        # Buscar producto
        query = Product.query.filter_by(client_id=request.client.id)
        
        if product_id:
            product = query.filter_by(id=product_id).first()
        else:
            product = query.filter_by(sku=sku).first()
        
        if not product:
            return jsonify({
                'success': False,
                'error': 'Producto no encontrado',
                'product_id': product_id,
                'sku': sku
            }), 404
        
        # Validar stock disponible
        if product.stock < quantity:
            return jsonify({
                'success': False,
                'error': 'Stock insuficiente',
                'product_id': product.id,
                'product_name': product.name,
                'requested_quantity': quantity,
                'available_stock': product.stock
            }), 400
        
        # Reducir stock
        old_stock = product.stock
        product.stock -= quantity
        product.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Stock reducido correctamente',
            'product_id': product.id,
            'product_name': product.name,
            'sku': product.sku,
            'old_stock': old_stock,
            'new_stock': product.stock,
            'quantity_reduced': quantity,
            'reason': reason
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Error de validación: {str(e)}'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@bp.route('/check-stock', methods=['GET'])
@require_api_key
def check_stock():
    """
    Consultar stock de un producto
    
    Headers:
        X-API-Key: clip_xxxxxxxxxxxxxxxxxxxx
    
    Query Params:
        product_id=uuid  O  sku=PROD-001
    
    Response JSON:
        {
            "success": true,
            "product_id": "uuid",
            "product_name": "Nombre del Producto",
            "sku": "PROD-001",
            "stock": 10,
            "is_available": true
        }
    """
    try:
        product_id = request.args.get('product_id')
        sku = request.args.get('sku')
        
        if not product_id and not sku:
            return jsonify({
                'success': False,
                'error': 'Debe proporcionar product_id o sku'
            }), 400
        
        # Buscar producto
        query = Product.query.filter_by(client_id=request.client.id)
        
        if product_id:
            product = query.filter_by(id=product_id).first()
        else:
            product = query.filter_by(sku=sku).first()
        
        if not product:
            return jsonify({
                'success': False,
                'error': 'Producto no encontrado'
            }), 404
        
        return jsonify({
            'success': True,
            'product_id': product.id,
            'product_name': product.name,
            'sku': product.sku,
            'stock': product.stock,
            'is_available': product.stock > 0,
            'price': float(product.price) if product.price else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error consultando stock: {str(e)}'
        }), 500


@bp.route('/bulk-check-stock', methods=['POST'])
@require_api_key
def bulk_check_stock():
    """
    Consultar stock de múltiples productos
    
    Headers:
        X-API-Key: clip_xxxxxxxxxxxxxxxxxxxx
    
    Request JSON:
        {
            "products": [
                {"product_id": "uuid1"},
                {"sku": "PROD-001"},
                {"product_id": "uuid2"}
            ]
        }
    
    Response JSON:
        {
            "success": true,
            "results": [
                {
                    "product_id": "uuid1",
                    "product_name": "Producto 1",
                    "stock": 10,
                    "is_available": true
                },
                ...
            ]
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'products' not in data:
            return jsonify({
                'success': False,
                'error': 'Array "products" requerido'
            }), 400
        
        products_data = data['products']
        results = []
        
        for item in products_data:
            product_id = item.get('product_id')
            sku = item.get('sku')
            
            if not product_id and not sku:
                results.append({
                    'error': 'product_id o sku requerido',
                    'item': item
                })
                continue
            
            # Buscar producto
            query = Product.query.filter_by(client_id=request.client.id)
            
            if product_id:
                product = query.filter_by(id=product_id).first()
            else:
                product = query.filter_by(sku=sku).first()
            
            if not product:
                results.append({
                    'product_id': product_id,
                    'sku': sku,
                    'error': 'Producto no encontrado'
                })
                continue
            
            results.append({
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku,
                'stock': product.stock,
                'is_available': product.stock > 0,
                'price': float(product.price) if product.price else None
            })
        
        return jsonify({
            'success': True,
            'total_requested': len(products_data),
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error consultando stocks: {str(e)}'
        }), 500
