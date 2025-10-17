"""
Blueprint de API
Endpoints internos para el admin panel y búsqueda visual
"""

import time
import hashlib
import numpy as np
import torch
import os
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from flask_cors import CORS
from app import db
from app.models.client import Client
from app.models.category import Category
from app.models.product import Product
from app.models.image import Image
from app.models.search_log import SearchLog
from app.services.image_manager import image_manager
from sqlalchemy import func, or_
from googletrans import Translator

# 🚀 IMPORTAR CLIP AL INICIO PARA CACHE GLOBAL
from app.blueprints.embeddings import get_clip_model

bp = Blueprint("api", __name__)

# Habilitar CORS para este blueprint
CORS(bp, origins=["*"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "X-API-Key", "Authorization"])


@bp.route("/image/<path:filename>")
def serve_image(filename):
    """Servir imágenes directamente usando ImageManager"""
    try:
        # ✅ USAR IMAGEMANAGER - Buscar imagen por filename
        from app.models.image import Image
        image = Image.query.filter_by(filename=filename).first()

        if not image:
            return "Image not found", 404

        # Obtener cliente dinámicamente
        client = image.client if hasattr(image, 'client') else None
        client_slug = client.slug if client else None

        # Usar ImageManager para obtener la ruta (auto-detecta si client_slug es None)
        image_path = image_manager.get_image_path(image, client_slug)

        if image_manager.image_exists(image, client_slug):
            return send_file(image_path)
        else:
            return "Image file not found", 404

    except Exception as e:
        return f"Error: {str(e)}", 500


@bp.route("/search/global")
@login_required
def global_search():
    """Búsqueda global en todos los modelos"""
    query = request.args.get("q", "")
    if not query:
        return jsonify({"results": []})

    results = {
        "clients": [],
        "products": [],
        "categories": [],
        "images": []
    }

    # Buscar clientes
    clients = Client.query.filter(
        or_(Client.name.contains(query), Client.email.contains(query))
    ).limit(5).all()

    results["clients"] = [{
        "id": client.id,
        "name": client.name,
        "email": client.email,
        "type": "client"
    } for client in clients]

    # Buscar productos
    products = Product.query.filter(
        or_(
            Product.name.contains(query),
            Product.description.contains(query),
            Product.sku.contains(query)
        )
    ).limit(5).all()

    results["products"] = [{
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "category": product.category.name,
        "type": "product"
    } for product in products]

    # Buscar categorías
    categories = Category.query.filter(
        or_(Category.name.contains(query), Category.description.contains(query))
    ).limit(5).all()

    results["categories"] = [{
        "id": category.id,
        "name": category.name,
        "client": category.client.name,
        "type": "category"
    } for category in categories]

    # Buscar imágenes
    images = Image.query.join(Product).filter(
        or_(
            Product.name.contains(query),
            Image.alt_text.contains(query),
            Image.original_filename.contains(query)
        )
    ).limit(5).all()

    results["images"] = [{
        "id": image.id,
        "product_name": image.product.name,
        "alt_text": image.alt_text,
        "url": image_manager.get_image_url(image),  # Auto-detecta client_slug
        "type": "image"
    } for image in images]

    return jsonify(results)


@bp.route("/stats/dashboard")
@login_required
def dashboard_stats():
    """Estadísticas para el dashboard principal"""
    stats = {
        # Contadores principales
        "totals": {
            "clients": Client.query.count(),
            "categories": Category.query.count(),
            "products": Product.query.count(),
            "images": Image.query.count(),
            # "api_keys": APIKey.query.filter_by(is_active=True).count()  # Comentado - modelo no existe
        },

        # Actividad reciente
        "recent": {
            "new_clients_this_month": Client.query.filter(
                func.extract("month", Client.created_at) == func.extract("month", func.now())
            ).count(),
            "new_products_this_month": Product.query.filter(
                func.extract("month", Product.created_at) == func.extract("month", func.now())
            ).count(),
            "searches_today": SearchLog.query.filter(
                func.date(SearchLog.created_at) == func.current_date()
            ).count()
        },

        # Top categorías por productos
        "top_categories": db.session.query(
            Category.name,
            Category.id,
            func.count(Product.id).label("product_count")
        ).outerjoin(Product).group_by(
            Category.id, Category.name
        ).order_by(func.count(Product.id).desc()).limit(5).all()
    }

    # Convertir resultados de SQLAlchemy a dict
    stats["top_categories"] = [{
        "name": cat.name,
        "id": cat.id,
        "product_count": cat.product_count
    } for cat in stats["top_categories"]]

    return jsonify(stats)


@bp.route("/validate/sku")
@login_required
def validate_sku():
    """Validar que un SKU sea único"""
    sku = request.args.get("sku")
    product_id = request.args.get("product_id")  # Para edición

    if not sku:
        return jsonify({"valid": False, "message": "SKU requerido"})

    query = Product.query.filter_by(sku=sku)
    if product_id:
        query = query.filter(Product.id != product_id)

    existing = query.first()

    return jsonify({
        "valid": existing is None,
        "message": "SKU disponible" if existing is None else "SKU ya existe"
    })


@bp.route("/validate/slug")
@login_required
def validate_slug():
    """Validar que un slug sea único dentro del cliente"""
    slug = request.args.get("slug")
    client_id = request.args.get("client_id")
    model_type = request.args.get("type")  # "category" o "product"
    item_id = request.args.get("item_id")  # Para edición

    if not slug or not client_id or not model_type:
        return jsonify({"valid": False, "message": "Parámetros requeridos"})

    if model_type == "category":
        query = Category.query.filter_by(slug=slug, client_id=client_id)
        if item_id:
            query = query.filter(Category.id != item_id)
    elif model_type == "product":
        query = Product.query.join(Category).filter(
            Product.slug == slug,
            Category.client_id == client_id
        )
        if item_id:
            query = query.filter(Product.id != item_id)
    else:
        return jsonify({"valid": False, "message": "Tipo inválido"})

    existing = query.first()

    return jsonify({
        "valid": existing is None,
        "message": "Slug disponible" if existing is None else "Slug ya existe"
    })


@bp.route("/bulk/delete", methods=["POST"])
@login_required
def bulk_delete():
    """Eliminación en lote"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Datos requeridos"})

    model_type = data.get("type")
    ids = data.get("ids", [])

    if not model_type or not ids:
        return jsonify({"success": False, "message": "Tipo e IDs requeridos"})

    try:
        deleted_count = 0

        if model_type == "products":
            # Eliminar productos
            for product_id in ids:
                product = Product.query.get(product_id)
                if product:
                    # Eliminar imágenes asociadas
                    Image.query.filter_by(product_id=product_id).delete()
                    db.session.delete(product)
                    deleted_count += 1

        elif model_type == "categories":
            # Eliminar categorías (solo si no tienen productos)
            for category_id in ids:
                category = Category.query.get(category_id)
                if category:
                    product_count = Product.query.filter_by(category_id=category_id).count()
                    if product_count == 0:
                        db.session.delete(category)
                        deleted_count += 1

        elif model_type == "images":
            # Eliminar imágenes
            for image_id in ids:
                image = Image.query.get(image_id)
                if image:
                    # Usar ImageManager para eliminar la imagen (auto-detecta client_slug)
                    image_manager.delete_image(image)
                    deleted_count += 1

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{deleted_count} elemento(s) eliminado(s)",
            "deleted_count": deleted_count
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        })


@bp.route("/export/data")
@login_required
def export_data():
    """Exportar datos en formato JSON"""
    client_id = request.args.get("client_id")
    data_type = request.args.get("type", "all")

    export_data = {}

    if data_type in ["all", "clients"]:
        query = Client.query
        if client_id:
            query = query.filter_by(id=client_id)

        export_data["clients"] = [{
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "description": client.description,
            "created_at": client.created_at.isoformat()
        } for client in query.all()]

    if data_type in ["all", "categories"]:
        query = Category.query
        if client_id:
            query = query.filter_by(client_id=client_id)

        export_data["categories"] = [{
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "client_id": category.client_id,
            "created_at": category.created_at.isoformat()
        } for category in query.all()]

    if data_type in ["all", "products"]:
        query = Product.query
        if client_id:
            query = query.join(Category).filter(Category.client_id == client_id)

        export_data["products"] = [{
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "description": product.description,
            "price": product.price,
            "sku": product.sku,
            "category_id": product.category_id,
            "created_at": product.created_at.isoformat()
        } for product in query.all()]

    return jsonify(export_data)


@bp.route("/translate", methods=["POST"])
@login_required
def translate_text():
    """Traducir texto usando Google Translate"""
    try:
        data = request.get_json()
        text = data.get("text", "").strip()
        target_language = data.get("target_language", "en")

        if not text:
            return jsonify({
                "success": False,
                "error": "No se proporcionó texto para traducir"
            })

        # Crear instancia del traductor
        translator = Translator()

        # Obtener el contexto de la industria del cliente
        industry_context = ""
        if current_user.client and current_user.client.industry:
            industry_context = current_user.client.industry.lower()

        # Traducir el texto
        translation = translator.translate(text, dest=target_language)
        translated_text = translation.text.lower()

        # Post-procesar basado en la industria (como en el modelo Category)
        if industry_context == "textil":
            textil_corrections = {
                'tablier': 'apron',
                'tabliers': 'aprons',
                'tabler': 'apron',
                'delantal': 'apron',
                'delantales': 'aprons',
                'uniforms': 'uniform',
                'uniformes': 'uniform',
                'gorras': 'hat',
                'gorros': 'hat',
                'gorra': 'hat',
                'gorro': 'hat',
                'caps': 'hat',
                'cap': 'hat',
                'shirts': 'shirt',
                'camisas': 'shirt',
                'camisa': 'shirt',
                'pants': 'pants',
                'pantalones': 'pants',
                'pantalon': 'pants',
                'trousers': 'pants'
            }

            for wrong, correct in textil_corrections.items():
                translated_text = translated_text.replace(wrong.lower(), correct.lower())

        return jsonify({
            "success": True,
            "translated_text": translated_text,
            "original_text": text,
            "target_language": target_language
        })

    except Exception as e:
        print(f"Error en traducción: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error en la traducción: {str(e)}"
        })


@bp.errorhandler(404)
def api_not_found(error):
    return jsonify({"error": "Endpoint no encontrado"}), 404


# ==============================================================================
# ENDPOINT DE BÚSQUEDA VISUAL PARA WIDGET
# ==============================================================================

@bp.route("/test", methods=["GET", "OPTIONS"])
def test_endpoint():
    """Endpoint de prueba para verificar conectividad"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    response = jsonify({
        "success": True,
        "message": "Endpoint funcionando correctamente",
        "timestamp": time.time()
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

def verify_api_key():
    """Verificar API Key del header (simplificado para testing)"""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return None, "API Key requerida en header X-API-Key"

    # Para testing, usar la API Key del cliente demo
    client = Client.query.filter_by(api_key=api_key, is_active=True).first()
    if not client:
        return None, "API Key inválida"

    return client, None



def process_image_for_search(image_data):
    """Procesar imagen y generar embedding para búsqueda"""
    try:
        print("🔧 DEBUG: Iniciando procesamiento de imagen")

        # Importar PIL con alias para evitar conflictos
        from PIL import Image as PILImage
        import io
        print("🔧 DEBUG: Importaciones exitosas")

        # Convertir bytes a imagen PIL
        pil_image = PILImage.open(io.BytesIO(image_data))
        print(f"🔧 DEBUG: Imagen PIL creada: {pil_image.size}")

        # Obtener modelo CLIP directamente
        start_clip_time = time.time()
        model, processor = get_clip_model()
        clip_load_time = time.time() - start_clip_time
        print(f"� CLIP MODEL: Obtenido en {clip_load_time:.3f}s")

        # Generar embedding usando solo argumentos necesarios
        print("🔧 DEBUG: Llamando al procesador CLIP...")
        start_process_time = time.time()

        # Llamada simplificada al procesador
        with torch.no_grad():
            inputs = processor(
                images=pil_image,
                return_tensors="pt"
            )
            print("🔧 DEBUG: Inputs del procesador creados exitosamente")

            # Generar features de imagen
            image_features = model.get_image_features(**inputs)
            print(f"🔧 DEBUG: Image features generadas: {image_features.shape}")

            # Normalizar embedding
            embedding = image_features / image_features.norm(dim=-1, keepdim=True)

            # Convertir a lista de Python
            embedding_list = embedding.squeeze().cpu().numpy().tolist()
            
            process_time = time.time() - start_process_time
            print(f"⚡ CLIP PROCESSING: Completado en {process_time:.3f}s")

        print(f"🔧 DEBUG: Embedding generado exitosamente: {len(embedding_list)} dimensiones")
        return embedding_list, None

    except Exception as e:
        print(f"❌ DEBUG: Error en process_image_for_search: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"Error procesando imagen: {str(e)}"


def calculate_similarity(embedding1, embedding2):
    """Calcular similitud coseno entre embeddings"""
    if isinstance(embedding1, str):
        embedding1 = eval(embedding1)  # Convertir string a lista
    if isinstance(embedding2, str):
        embedding2 = eval(embedding2)

    embedding1 = np.array(embedding1)
    embedding2 = np.array(embedding2)

    # Normalizar
    embedding1 = embedding1 / np.linalg.norm(embedding1)
    embedding2 = embedding2 / np.linalg.norm(embedding2)

    # Similitud coseno
    similarity = np.dot(embedding1, embedding2)
    return float(similarity)


def _validate_visual_search_request():
    """Valida los parámetros de la búsqueda visual"""
    # Verificar API Key
    client, error = verify_api_key()
    if error:
        return None, jsonify({
            "error": "unauthorized",
            "message": error
        }), 401

    # Verificar imagen
    if 'image' not in request.files:
        return None, jsonify({
            "error": "bad_request",
            "message": "Imagen requerida en form-data 'image'"
        }), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return None, jsonify({
            "error": "bad_request",
            "message": "No se seleccionó archivo"
        }), 400

    return client, image_file, None


def _process_image_data(image_file):
    """Procesa y valida los datos de la imagen"""
    # Parámetros
    limit = min(int(request.form.get('limit', 3)), 10)
    threshold = float(request.form.get('threshold', 0.1))

    # Leer imagen
    image_data = image_file.read()

    # Validar tamaño (15MB máximo)
    if len(image_data) > 15 * 1024 * 1024:
        return None, None, None, jsonify({
            "error": "file_too_large",
            "message": "Imagen muy grande. Máximo 15MB"
        }), 400

    return image_data, limit, threshold, None, None


def _generate_query_embedding(image_data):
    """Genera el embedding de la imagen de consulta"""
    print(f"📷 DEBUG: Procesando imagen de {len(image_data)} bytes")
    query_embedding, error = process_image_for_search(image_data)
    if error:
        print(f"❌ DEBUG: Error en procesamiento: {error}")
        return None, jsonify({
            "error": "processing_failed",
            "message": error
        }), 500

    if query_embedding is None:
        print("❌ DEBUG: query_embedding es None")
        return None, jsonify({
            "error": "processing_failed",
            "message": "No se pudo generar embedding de la imagen"
        }), 500

    print(f"🧠 DEBUG: Embedding generado - dimensiones: {len(query_embedding)}")
    print(f"🧠 DEBUG: Primeros 5 valores: {query_embedding[:5]}")

    return query_embedding, None, None


def _find_similar_products(client, query_embedding, threshold):
    """Encuentra productos similares y agrupa por mejor coincidencia"""
    # Buscar imágenes similares en la base de datos
    images = Image.query.filter_by(
        client_id=client.id,
        is_processed=True
    ).filter(Image.clip_embedding.isnot(None)).all()

    print(f"🔍 DEBUG: Encontradas {len(images)} imágenes para comparar")

    # Calcular similitudes y agrupar por producto
    product_best_match = {}  # Dict para almacenar la mejor imagen de cada producto
    category_similarities = {}  # Para determinar categoría más probable

    for img in images:
        try:
            similarity = calculate_similarity(query_embedding, img.clip_embedding)
            category_name = img.product.category.name if img.product.category else "Sin categoría"

            print(f"🔍 DEBUG: Similitud con {img.product.name[:30]} ({category_name}): {similarity:.4f}")

            # Recopilar estadísticas por categoría
            if category_name not in category_similarities:
                category_similarities[category_name] = []
            category_similarities[category_name].append(similarity)

            if similarity >= threshold:
                product_id = img.product.id

                # Si es la primera imagen de este producto, o si tiene mayor similitud que la anterior
                if product_id not in product_best_match or similarity > product_best_match[product_id]['similarity']:
                    product_best_match[product_id] = {
                        'image': img,
                        'similarity': similarity,
                        'product': img.product,
                        'category': category_name
                    }
                    print(f"✅ DEBUG: Mejor imagen para {img.product.name}: {similarity:.4f}")

        except Exception as e:
            print(f"❌ Error calculando similitud para imagen {img.id}: {e}")
            continue

    # Determinar categoría más probable basada en mayor similitud promedio
    print(f"\n📊 DEBUG: Análisis por categorías:")
    best_category = None
    best_avg_similarity = 0

    for category, similarities in category_similarities.items():
        avg_sim = sum(similarities) / len(similarities)
        max_sim = max(similarities)
        count = len(similarities)
        print(f"   📂 {category}: {count} productos, promedio: {avg_sim:.4f}, máximo: {max_sim:.4f}")

        if max_sim > best_avg_similarity:  # Usar máximo en lugar de promedio para detectar categoría objetivo
            best_avg_similarity = max_sim
            best_category = category

    print(f"🎯 DEBUG: Categoría más probable: '{best_category}' (similitud máxima: {best_avg_similarity:.4f})")

    # Aplicar boost de categoría: aumentar similitud para productos de la categoría más probable
    if best_category and best_category != "Sin categoría":
        for product_id in product_best_match:
            match_data = product_best_match[product_id]
            if match_data['category'] == best_category:
                # Boost del 15% para productos de la misma categoría
                original_similarity = match_data['similarity']
                boosted_similarity = min(1.0, original_similarity * 1.15)
                match_data['similarity'] = boosted_similarity
                match_data['category_boost'] = True
                print(f"🚀 DEBUG: Boost aplicado a {match_data['product'].name}: {original_similarity:.4f} → {boosted_similarity:.4f}")
            else:
                match_data['category_boost'] = False

    print(f"🎯 DEBUG: Productos únicos encontrados: {len(product_best_match)}")
    return product_best_match


def _find_similar_products_in_category(client, query_embedding, threshold, category_id):
    """
    Encuentra productos similares SOLO dentro de una categoría específica

    Args:
        client: Cliente autenticado
        query_embedding: Embedding de la imagen query
        threshold: Umbral mínimo de similitud
        category_id: ID de la categoría en la que buscar

    Returns:
        dict: Diccionario con los mejores matches por producto
    """
    # Buscar imágenes SOLO de la categoría específica
    images = (Image.query
              .join(Product)
              .filter(
                  Image.client_id == client.id,
                  Image.is_processed == True,
                  Image.clip_embedding.isnot(None),
                  Product.category_id == category_id
              ).all())

    print(f"🔍 DEBUG: Encontradas {len(images)} imágenes en la categoría específica")

    # Calcular similitudes y agrupar por producto
    product_best_match = {}  # Dict para almacenar la mejor imagen de cada producto

    for img in images:
        try:
            similarity = calculate_similarity(query_embedding, img.clip_embedding)
            category_name = img.product.category.name if img.product.category else "Sin categoría"

            print(f"🔍 DEBUG: Similitud con {img.product.name[:30]} ({category_name}): {similarity:.4f}")

            if similarity >= threshold:
                product_id = img.product.id

                # Si es la primera imagen de este producto, o si tiene mayor similitud que la anterior
                if product_id not in product_best_match or similarity > product_best_match[product_id]['similarity']:
                    product_best_match[product_id] = {
                        'image': img,
                        'similarity': similarity,
                        'product': img.product,
                        'category': category_name,
                        'category_filtered': True  # Indicador de que se filtró por categoría
                    }
                    print(f"✅ DEBUG: Mejor imagen para {img.product.name}: {similarity:.4f}")

        except Exception as e:
            print(f"❌ Error calculando similitud para imagen {img.id}: {e}")
            continue

    print(f"🎯 DEBUG: Total productos únicos encontrados en categoría: {len(product_best_match)}")
    return product_best_match


def _apply_category_filter(product_best_match, limit):
    """Aplica filtrado inteligente por categoría si es necesario"""
    # Filtrado inteligente por categoría (solo si hay suficientes productos)
    if len(product_best_match) <= limit * 2:  # Solo filtrar si hay muchos productos
        print(f"🎯 DEBUG: Pocos productos encontrados ({len(product_best_match)}), no se aplica filtro de categoría")
        return product_best_match

    # Obtener las categorías de los productos con mayor similitud
    sorted_products = sorted(product_best_match.items(), key=lambda x: x[1]['similarity'], reverse=True)

    # Tomar las top similitudes para determinar la categoría dominante
    top_count = min(3, len(sorted_products))
    top_categories = {}

    for product_id, match_data in sorted_products[:top_count]:
        category_name = match_data['product'].category.name
        if category_name not in top_categories:
            top_categories[category_name] = []
        top_categories[category_name].append(match_data['similarity'])

    # Determinar la categoría más relevante basada en similitud promedio
    best_category = None
    best_avg_similarity = 0

    for category, similarities in top_categories.items():
        avg_similarity = sum(similarities) / len(similarities)
        print(f"📂 DEBUG: Categoría '{category}': {len(similarities)} productos, similitud promedio: {avg_similarity:.4f}")

        if avg_similarity > best_avg_similarity:
            best_avg_similarity = avg_similarity
            best_category = category

    # Solo aplicar filtro si la categoría dominante es muy clara (>60% similitud promedio)
    if not (best_category and best_avg_similarity > 0.6):
        print(f"🎯 DEBUG: No se aplicó filtro de categoría (similitud promedio: {best_avg_similarity:.4f})")
        return product_best_match

    print(f"🎯 DEBUG: Categoría dominante detectada: '{best_category}' (similitud promedio: {best_avg_similarity:.4f})")

    # Filtrar solo productos de la categoría dominante
    filtered_matches = {}
    for product_id, match_data in product_best_match.items():
        product_category = match_data['product'].category.name

        # Incluir productos de la categoría dominante
        if product_category == best_category:
            filtered_matches[product_id] = match_data
            print(f"✅ DEBUG: Incluido por categoría exacta: {match_data['product'].name} ({product_category})")
        else:
            print(f"❌ DEBUG: Excluido por categoría: {match_data['product'].name} ({product_category} != {best_category})")

    # Solo usar el filtro si queda al menos el mínimo de productos
    if len(filtered_matches) >= limit:
        print(f"🎯 DEBUG: Productos después del filtro de categoría: {len(filtered_matches)}")
        return filtered_matches
    else:
        print("⚠️ DEBUG: El filtro de categoría eliminó demasiados productos, manteniendo los originales")
        return product_best_match


def _build_search_results(product_best_match, limit):
    """Construye la lista final de resultados"""
    results = []
    for product_id, best_match in product_best_match.items():
        img = best_match['image']
        product = best_match['product']
        similarity = best_match['similarity']
        category_boost = best_match.get('category_boost', False)

        # Usar base64_data directamente del modelo Image
        try:
            if img.base64_data:
                image_url = img.base64_data
            elif img.cloudinary_url:
                # Fallback: usar URL de Cloudinary si no hay base64
                image_url = img.cloudinary_url
            else:
                image_url = None
        except Exception as e:
            print(f"❌ Error obteniendo imagen {img.filename}: {e}")
            image_url = None

        result = {
            "product_id": product.id,
            "name": product.name,
            "description": product.description or "Sin descripción",
            "image_url": image_url,
            "similarity": round(similarity, 4),
            "price": float(product.price) if product.price else None,
            "sku": product.sku,
            "stock": product.stock if hasattr(product, 'stock') and product.stock is not None else 0,
            "category": product.category.name if product.category else "Sin categoría",
            "category_boost": category_boost
        }
        results.append(result)

        boost_indicator = "🚀" if category_boost else ""
        print(f"📦 DEBUG: Producto final añadido: {product.name} (similitud: {similarity:.4f}) {boost_indicator}")

    print(f"🎯 DEBUG: Total productos únicos procesados: {len(results)}")

    # Ordenar por similitud y limitar resultados
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:limit]


def detect_general_object(image_data):
    """
    Detecta QUÉ es el objeto en la imagen usando CLIP con categorías generales
    
    Args:
        image_data: Datos binarios de la imagen
        
    Returns:
        tuple: (objeto_detectado, confidence_score)
    """
    try:
        # Categorías generales para identificar objetos
        general_categories = [
            "car", "automobile", "vehicle",
            "hat", "cap", "beanie", "gorra", 
            "shoe", "boot", "sneaker", "zapato",
            "shirt", "t-shirt", "clothing", "camisa",
            "jacket", "coat", "chaqueta",
            "food", "comida", "meal",
            "animal", "pet", "dog", "cat",
            "electronics", "phone", "computer",
            "furniture", "chair", "table",
            "building", "house", "architecture",
            "person", "human", "people",
            "nature", "tree", "flower", "landscape"
        ]
        
        # Convertir a imagen PIL
        from PIL import Image as PILImage
        import io
        pil_image = PILImage.open(io.BytesIO(image_data))
        
        # Obtener modelo CLIP
        model, processor = get_clip_model()
        
        # Generar embedding de imagen
        with torch.no_grad():
            image_inputs = processor(images=pil_image, return_tensors="pt")
            image_features = model.get_image_features(**image_inputs)
            image_embedding = image_features / image_features.norm(dim=-1, keepdim=True)
            
            # Generar embeddings de texto para categorías generales
            text_inputs = processor(text=general_categories, return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)
            
            # Calcular similitudes
            similarities = torch.cosine_similarity(image_embedding, text_embeddings, dim=1)
            
            # Encontrar la mejor coincidencia
            best_idx = similarities.argmax().item()
            best_score = similarities[best_idx].item()
            detected_object = general_categories[best_idx]
            
            print(f"🔍 DETECCIÓN GENERAL: {detected_object} (confianza: {best_score:.3f})")
            
            return detected_object, best_score
            
    except Exception as e:
        print(f"❌ Error en detección general: {e}")
        return "unknown", 0.0


def detect_image_category_with_centroids(image_data, client_id, confidence_threshold=0.2):
    """
    Detecta la categoría de una imagen usando centroides de embeddings reales

    En lugar de prompts de texto, usa el promedio de embeddings de productos
    existentes en cada categoría como "representante" de esa categoría.

    Args:
        image_data: Datos binarios de la imagen
        client_id: ID del cliente para obtener sus categorías
        confidence_threshold: Umbral mínimo de confianza para detección

    Returns:
        tuple: (categoria_detectada, confidence_score) o (None, 0) si no detecta
    """
    try:
        print(f"🚀 RAILWAY LOG: Iniciando detección centroides para cliente {client_id}")

        # 1. Obtener categorías activas del cliente
        categories = Category.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        if not categories:
            print(f"❌ RAILWAY LOG: No categorías para cliente {client_id}")
            return None, 0

        print(f"📋 RAILWAY LOG: {len(categories)} categorías encontradas")

        # 2. Generar embedding de la imagen nueva
        from PIL import Image as PILImage
        import io
        pil_image = PILImage.open(io.BytesIO(image_data))
        print(f"🖼️ DEBUG: Imagen preparada: {pil_image.size}")

        # 3. Obtener modelo CLIP
        model, processor = get_clip_model()
        print("🤖 DEBUG: Modelo CLIP obtenido")

        # 4. Generar embedding de imagen nueva
        with torch.no_grad():
            image_inputs = processor(
                images=pil_image,
                return_tensors="pt"
            )
            image_features = model.get_image_features(**image_inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            new_embedding = image_features.squeeze(0).numpy()

        print(f"🔍 DEBUG: Embedding generado: shape {new_embedding.shape}")

        # 5. Calcular similitudes contra centroides de cada categoría
        category_similarities = []

        for category in categories:
            # 🚀 USAR CENTROIDE DE BD DIRECTAMENTE
            centroid = category.get_centroid_embedding(auto_calculate=False)
            print(f"🔍 RAILWAY LOG: {category.name} - centroide {'OK' if centroid is not None else 'NULL'}")

            if centroid is not None:
                # Calcular similitud coseno
                similarity = np.dot(new_embedding, centroid) / (np.linalg.norm(new_embedding) * np.linalg.norm(centroid))
                category_similarities.append({
                    'category': category,
                    'similarity': float(similarity)
                })
                print(f"📊 RAILWAY LOG: {category.name}: similitud {similarity:.4f}")
            else:
                print(f"⚠️ RAILWAY LOG: {category.name} SIN CENTROIDE en BD")

        if not category_similarities:
            print(f"❌ RAILWAY LOG: NO HAY SIMILITUDES - sin centroides válidos")
            return None, 0

        # 6. Encontrar la mejor coincidencia
        best_match = max(category_similarities, key=lambda x: x['similarity'])
        best_category = best_match['category']
        best_score = best_match['similarity']

        print(f"🎯 RAILWAY LOG: MEJOR: {best_category.name} = {best_score:.4f}")

        # 7. Verificar umbral de confianza
        if best_score >= confidence_threshold:
            print(f"✅ RAILWAY LOG: DETECTADO - {best_category.name} (conf: {best_score:.4f})")
            return best_category, best_score
        else:
            print(f"❌ RAILWAY LOG: RECHAZADO - {best_score:.4f} < {confidence_threshold}")
            return None, best_score

    except Exception as e:
        print(f"❌ ERROR en detección por centroides: {e}")
        import traceback
        traceback.print_exc()
        return None, 0


def detect_image_category(image_data, client_id, confidence_threshold=0.2):
    """
    Función de detección por prompts (obsoleta, usa centroides como fallback)
    """
    try:
        print(f"🎯 DEBUG: Usando método de centroides en lugar de prompts")
        return detect_image_category_with_centroids(image_data, client_id, confidence_threshold)

    except Exception as e:
        print(f"❌ ERROR en detección de categoría: {e}")
        import traceback
        traceback.print_exc()
        return None, 0


def detect_image_category(image_data, client_id, confidence_threshold=0.2):
    """
    Detecta la categoría de una imagen usando CLIP y los prompts de categorías del cliente

    Args:
        image_data: Datos binarios de la imagen
        client_id: ID del cliente para obtener sus categorías
        confidence_threshold: Umbral mínimo de confianza para detección

    Returns:
        tuple: (categoria_detectada, confidence_score) o (None, 0) si no detecta
    """
    try:
        print(f"🎯 DEBUG: Iniciando detección de categoría para cliente {client_id}")

        # 1. Obtener categorías activas del cliente
        categories = Category.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        if not categories:
            print(f"❌ DEBUG: No se encontraron categorías para cliente {client_id}")
            return None, 0

        print(f"📋 DEBUG: Encontradas {len(categories)} categorías activas")

        # 2. Preparar imagen para CLIP
        from PIL import Image as PILImage
        import io
        pil_image = PILImage.open(io.BytesIO(image_data))
        print(f"🖼️ DEBUG: Imagen preparada: {pil_image.size}")

        # 3. Obtener modelo CLIP
        model, processor = get_clip_model()
        print("🤖 DEBUG: Modelo CLIP obtenido")

        # 4. Preparar prompts de categorías
        category_prompts = []
        category_objects = []

        for category in categories:
            # Usar clip_prompt si existe, sino usar name_en, sino name
            if category.clip_prompt:
                prompt = f"a photo of {category.clip_prompt}"
            elif category.name_en:
                prompt = f"a photo of {category.name_en.lower()}"
            else:
                prompt = f"a photo of {category.name.lower()}"

            category_prompts.append(prompt)
            category_objects.append(category)
            print(f"📝 DEBUG: Prompt para {category.name}: {prompt}")

        # 5. Procesar imagen y textos con CLIP
        with torch.no_grad():
            # Procesar imagen
            image_inputs = processor(
                images=pil_image,
                return_tensors="pt"
            )
            image_features = model.get_image_features(**image_inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Procesar textos
            text_inputs = processor(
                text=category_prompts,
                return_tensors="pt",
                padding=True,
                truncation=True
            )
            text_features = model.get_text_features(**text_inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = (image_features @ text_features.T).squeeze(0)

            print(f"🔍 DEBUG: Similitudes calculadas: {similarities.tolist()}")

        # 6. Encontrar la mejor coincidencia
        best_idx = similarities.argmax().item()
        best_score = similarities[best_idx].item()
        best_category = category_objects[best_idx]

        print(f"🎯 DEBUG: Mejor coincidencia: {best_category.name} ({best_score:.4f})")

        # 7. Verificar umbral de confianza
        if best_score >= confidence_threshold:
            print(f"✅ DEBUG: Categoría detectada con confianza suficiente")
            return best_category, best_score
        else:
            print(f"❌ DEBUG: Confianza insuficiente ({best_score:.4f} < {confidence_threshold})")
            return None, best_score

    except Exception as e:
        print(f"❌ ERROR en detección de categoría: {e}")
        import traceback
        traceback.print_exc()
        return None, 0


@bp.route("/search", methods=["POST", "OPTIONS"])
def visual_search():
    """
    Endpoint de búsqueda visual para el widget con detección automática de categoría

    Headers:
        X-API-Key: API Key del cliente

    Form Data:
        image: Archivo de imagen
        limit: Número de resultados (default: 3, max: 10)
        threshold: Umbral de similitud (default: 0.1)
    """
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    start_time = time.time()

    try:
        # Validar request
        client, image_file, error_response = _validate_visual_search_request()
        if error_response:
            return error_response

        # Procesar datos de imagen
        image_data, limit, _, error_response, status_code = _process_image_data(image_file)
        if error_response:
            return error_response, status_code

        # Sensibilidad personalizada por cliente
        category_confidence_threshold = (getattr(client, 'category_confidence_threshold', 70) or 70) / 100.0
        product_similarity_threshold = (getattr(client, 'product_similarity_threshold', 30) or 30) / 100.0

        # ===== PASO 1: DETECCIÓN GENERAL DEL OBJETO =====
        print(f"🔍 RAILWAY LOG: IDENTIFICANDO QUÉ ES EL OBJETO...")

        detected_object, object_confidence = detect_general_object(image_data)
        print(f"🎯 RAILWAY LOG: OBJETO DETECTADO = {detected_object} (confianza: {object_confidence:.3f})")

        # Mapeo de objetos detectados a si los comercializamos
        commercial_keywords = [
            "hat", "cap", "beanie", "gorra",
            "shoe", "boot", "sneaker", "zapato", 
            "shirt", "t-shirt", "clothing", "camisa",
            "jacket", "coat", "chaqueta"
        ]

        # Verificar si el objeto detectado es comercializable
        is_commercial = detected_object in commercial_keywords
        
        if not is_commercial and object_confidence > 0.6:
            # El objeto está claramente identificado pero no lo comercializamos
            print(f"❌ RAILWAY LOG: OBJETO NO COMERCIAL - {detected_object}")
            return jsonify({
                "success": False,
                "error": "non_commercial_object",
                "message": f"Esta imagen contiene un {detected_object} que no comercializamos",
                "details": f"Detectamos que es un '{detected_object}' con {object_confidence:.1%} de confianza, pero no vendemos este tipo de productos.",
                "available_categories": [cat.name for cat in Category.query.filter_by(client_id=client.id, is_active=True).all()],
                "processing_time": round(time.time() - start_time, 3)
            }), 400

        # ===== PASO 2: DETECCIÓN DE CATEGORÍA ESPECÍFICA =====
        print(f"🚀 RAILWAY LOG: INICIANDO DETECCIÓN DE CATEGORÍA ESPECÍFICA")

        detected_category, category_confidence = detect_image_category_with_centroids(
            image_data,
            client.id,
            confidence_threshold=category_confidence_threshold  # Sensibilidad por cliente
        )

        print(f"🎯 RAILWAY LOG: Resultado detección = {detected_category.name if detected_category else 'NULL'} (conf: {category_confidence:.3f})")

        if detected_category is None:
            # No se pudo detectar una categoría válida
            print(f"❌ RAILWAY LOG: CATEGORÍA NO DETECTADA - devolviendo error")
            return jsonify({
                "success": False,
                "error": "category_not_detected", 
                "message": f"Esta imagen no corresponde a productos que comercializa {client.name}",
                "details": f"La imagen no pudo identificarse dentro de nuestras categorías disponibles (confianza máxima: {category_confidence:.1%}). Por favor, intenta con una imagen de un producto de nuestro catálogo.",
                "available_categories": [cat.name for cat in Category.query.filter_by(client_id=client.id, is_active=True).all()],
                "processing_time": round(time.time() - start_time, 3)
            }), 400

        print(f"✅ RAILWAY LOG: CATEGORÍA OK: {detected_category.name} - procediendo a búsqueda")

        # ===== GENERAR EMBEDDING DE LA IMAGEN =====
        query_embedding, error_response, status_code = _generate_query_embedding(image_data)
        if error_response:
            print(f"❌ RAILWAY LOG: Error generando embedding")
            return error_response, status_code

        # ===== BUSCAR SOLO EN LA CATEGORÍA DETECTADA =====
        print(f"🔍 RAILWAY LOG: Buscando productos en {detected_category.name}")

        # Modificar la búsqueda para filtrar por categoría detectada
        product_best_match = _find_similar_products_in_category(
            client,
            query_embedding,
            product_similarity_threshold,
            detected_category.id
        )

        print(f"🎯 DEBUG: Productos encontrados en categoría {detected_category.name}: {len(product_best_match)}")

        # Construir resultados finales (sin filtro adicional de categoría)
        results = _build_search_results(product_best_match, limit)

        processing_time = time.time() - start_time

        # Respuesta con información de categoría detectada
        response = {
            "success": True,
            "query_type": "image_with_category_detection",
            "detected_category": {
                "id": detected_category.id,
                "name": detected_category.name,
                "name_en": detected_category.name_en,
                "confidence": round(category_confidence, 4)
            },
            "query_info": {
                "method": "category_detection_with_clip",
                "detected_category": detected_category.name,
                "confidence": round(category_confidence, 4),
                "threshold_used": threshold,
                "category_filter": True
            },
            "results": results,
            "total_results": len(results),
            "processing_time": round(processing_time, 3),
            "client_id": client.id,
            "client_name": client.name,
            "search_method": "category_filtered",
            "timestamp": time.time()
        }

        # Headers CORS para widget
        response_obj = jsonify(response)
        response_obj.headers['Access-Control-Allow-Origin'] = '*'
        response_obj.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response_obj.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'

        return response_obj

    except Exception as e:
        processing_time = time.time() - start_time
        return jsonify({
            "error": "internal_error",
            "message": f"Error interno: {str(e)}",
            "processing_time": round(processing_time, 3)
        }), 500


@bp.route("/search", methods=["OPTIONS"])
def visual_search_options():
    """CORS preflight para el endpoint de búsqueda"""
    response = jsonify({"message": "OK"})
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    return response


@bp.errorhandler(500)
def api_internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500
