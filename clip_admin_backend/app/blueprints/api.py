"""
Blueprint de API
Endpoints internos para el admin panel y búsqueda visual
"""

import time
from app.blueprints.embeddings import _get_idle_timeout_seconds
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
from app.models.store_search_config import StoreSearchConfig
from app.services.image_manager import image_manager
from app.core.search_optimizer import SearchOptimizer
from app.utils.system_config import system_config
from app.core.modifier_expander import expand_color_modifiers
from app.utils.colors import normalize_color
from app.utils.llm_query_normalizer import normalize_query
from sqlalchemy import func, or_, text
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
        "url": image.display_url,  # Usar propiedad del modelo (patrón unificado)
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
        import logging
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.getLogger("clip_model").info(f"[REQUEST] Comparación recibida")

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
    # Obtener configuración del sistema
    default_max_results = system_config.get('search', 'max_results', 10)

    # Parámetros (usar configuración como default y máximo)
    limit = min(int(request.form.get('limit', default_max_results)), default_max_results)
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


def _generate_query_embedding(image_data, detected_category=None):
    """
    Genera el embedding de la imagen de consulta con enriquecimiento opcional por tags

    Args:
        image_data: Bytes de la imagen
        detected_category: Categoría detectada (opcional, para contexto)

    Returns:
        Tuple: (embedding_enriquecido, error_response, status_code)
    """
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

    # ✨ ENRIQUECIMIENTO CON TAGS INFERIDOS (para búsqueda visual)
    fusion_enabled = system_config.get('search', 'enable_inferred_tags', False)
    if fusion_enabled:
        try:
            from PIL import Image
            from io import BytesIO
            from app.services.attribute_autofill_service import AttributeAutofillService
            import torch

            # Convertir bytes a PIL Image
            pil_image = Image.open(BytesIO(image_data)).convert('RGB')
            category_context = detected_category.name.lower() if detected_category else "producto"

            # Inferir tags visuales de la imagen subida
            from app.services.attribute_autofill_service import TAG_OPTIONS
            inferred_tags = AttributeAutofillService._classify_tags(
                pil_image,
                TAG_OPTIONS,
                threshold=0.15,
                category_context=category_context
            )

            if inferred_tags and len(inferred_tags) > 0:
                # Tomar top 5 tags más relevantes
                top_tags = inferred_tags[:5]
                tag_names = [tag for tag, _ in top_tags]

                print(f"🔮 VISUAL FUSION: Tags inferidos de imagen: {', '.join([f'{t}({c:.2f})' for t, c in top_tags])}")

                # Generar embeddings de los tags
                model, processor = get_clip_model()
                tag_phrases = [f"a {tag} style {category_context}" for tag in tag_names]

                with torch.no_grad():
                    tag_inputs = processor(text=tag_phrases, return_tensors="pt", padding=True)
                    tag_embeddings = model.get_text_features(**tag_inputs)
                    tag_embeddings = tag_embeddings / tag_embeddings.norm(dim=-1, keepdim=True)
                    tag_mean = tag_embeddings.mean(dim=0)
                    tag_mean = tag_mean / tag_mean.norm()

                    # Fusionar: 80% visual + 20% tags inferidos
                    q = torch.tensor(query_embedding).unsqueeze(0)
                    q = q / q.norm()

                    alpha = 0.8  # Peso del embedding visual original
                    beta = 0.2   # Peso de los tags inferidos

                    fused = alpha * q + beta * tag_mean
                    fused = fused / fused.norm()
                    query_embedding = fused.squeeze().cpu().numpy().tolist()

                    print(f"✨ VISUAL FUSION: Embedding enriquecido (α={alpha} visual + β={beta} tags)")

        except Exception as e:
            print(f"⚠️ VISUAL FUSION skip: {e}")
            # Si falla, continuar con embedding original
            pass

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

    # 🔍 DEBUG: Verificar contenido del dict recibido
    print(f"🔍 DEBUG _build_search_results: Recibido dict con {len(product_best_match)} productos")
    if product_best_match:
        sample_id = list(product_best_match.keys())[0]
        sample_match = product_best_match[sample_id]
        print(f"🔍 DEBUG _build_search_results: Claves en sample_match: {list(sample_match.keys())}")
        print(f"🔍 DEBUG _build_search_results: Tiene optimizer_scores: {'optimizer_scores' in sample_match}")

    # Intentar obtener configuración de atributos a exponer (si existe la tabla)
    exposed_keys_cache = None  # cache por request
    checked_config = False
    for product_id, best_match in product_best_match.items():
        img = best_match['image']
        product = best_match['product']
        similarity = best_match['similarity']
        category_boost = best_match.get('category_boost', False)
        color_boost = best_match.get('color_boost', False)

        # La primera vez, intentamos cargar la config de atributos visibles por cliente
        if not checked_config:
            try:
                client_id = getattr(product, 'client_id', None)
                if client_id:
                    # Primero verificar si hay ALGUNA configuración para este cliente
                    total_configs = db.session.execute(
                        text(
                            """
                            SELECT COUNT(*) as total
                            FROM product_attribute_config
                            WHERE client_id = :client_id
                            """
                        ),
                        {"client_id": client_id},
                    ).fetchone()

                    # Si no hay ninguna configuración, tratar como "sin config" (None)
                    if total_configs and total_configs[0] == 0:
                        exposed_keys_cache = None
                    else:
                        # Hay configuraciones, obtener las visibles
                        rows = db.session.execute(
                            text(
                                """
                                SELECT key
                                FROM product_attribute_config
                                WHERE client_id = :client_id AND expose_in_search = true
                                """
                            ),
                            {"client_id": client_id},
                        ).fetchall()
                        # Crear conjunto (vacío si todas están ocultas, con elementos si hay visibles)
                        exposed_keys_cache = {r[0] for r in rows}
            except Exception as e:
                # Si no existe la tabla o falla, seguimos sin filtrar (compatible hacia atrás)
                print(f"⚠️ Error consultando product_attribute_config: {e}")
                # CRITICAL: Hacer rollback para que queries posteriores funcionen
                db.session.rollback()
                exposed_keys_cache = None
            finally:
                checked_config = True

        # Obtener la imagen primaria del producto en lugar de la que hizo match
        primary_image = None
        try:
            # Buscar la imagen primaria del producto
            primary_image = Image.query.filter_by(
                product_id=product.id,
                is_primary=True
            ).first()

            # Si no hay primaria, usar la que hizo match
            if not primary_image:
                primary_image = img

            # Retornar SIEMPRE la URL de Cloudinary (patrón unificado)
            image_url = primary_image.display_url if primary_image else None
        except Exception as e:
            print(f"❌ Error obteniendo imagen primaria: {e}")
            # CRITICAL: Hacer rollback para que queries posteriores funcionen
            db.session.rollback()
            # Si falla, usar la imagen que hizo match
            image_url = img.display_url if img else None

        # Preparar atributos dinámicos del producto (JSONB)
        product_attrs = {}
        product_url_value = None  # Siempre intentar extraer el link, aunque no esté expuesto
        try:
            if hasattr(product, 'attributes') and product.attributes:
                # 1) Siempre intentar obtener url_producto del JSON bruto (ignorar filtros de exposición)
                try:
                    raw_url = product.attributes.get('url_producto')
                    if isinstance(raw_url, dict):
                        # Algunos stores guardan { value: 'https://...' }
                        product_url_value = raw_url.get('value') or raw_url.get('url') or None
                    else:
                        product_url_value = raw_url
                except Exception as ie:
                    print(f"⚠️ Error extrayendo url_producto para {product.id}: {ie}")
                    product_url_value = None

                # 2) Aplicar filtros de exposición solo para el bloque de attributes
                if exposed_keys_cache is not None:
                    # Filtrar solo los atributos configurados para exponerse
                    product_attrs = {
                        k: v for k, v in product.attributes.items() if k in exposed_keys_cache
                    }
                else:
                    # Sin configuración, exponer todos los atributos (compatibilidad existente)
                    product_attrs = dict(product.attributes)
        except Exception as e:
            print(f"⚠️ Error leyendo atributos de producto {product.id}: {e}")
            product_attrs = {}

        # 🚀 FASE 3: Incluir optimizer_scores si están disponibles
        optimizer_scores = best_match.get('optimizer_scores')

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
            "category_boost": category_boost,
            "color_boost": color_boost,
            # Atributos dinámicos (filtrados si hay configuración)
            "attributes": product_attrs,
            # URL del producto si está configurada
            "product_url": product_url_value
        }

        # Agregar scores del optimizer si existen
        if optimizer_scores:
            result['optimizer'] = {
                'visual_score': round(optimizer_scores['visual_score'], 4),
                'metadata_score': round(optimizer_scores['metadata_score'], 4),
                'business_score': round(optimizer_scores['business_score'], 4),
                'final_score': round(optimizer_scores['final_score'], 4),
                'enabled': True
            }

        results.append(result)

        boost_indicator = "🚀" if category_boost else ""
        color_indicator = "🎨" if color_boost else ""
        optimizer_indicator = "🎯" if optimizer_scores else ""
        print(f"📦 DEBUG: Producto final añadido: {product.name} (similitud: {similarity:.4f}) {boost_indicator}{color_indicator}{optimizer_indicator}")

    print(f"🎯 DEBUG: Total productos únicos procesados: {len(results)}")

    # Ordenar por similitud y limitar resultados
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:limit]


def _normalize_color_gender(color_str: str) -> str:
    """Normaliza género en nombres de colores para matching consistente."""
    if not color_str:
        return color_str
    mapping = {
        'NEGRA': 'NEGRO', 'BLANCA': 'BLANCO', 'ROJA': 'ROJO', 'AMARILLA': 'AMARILLO',
        'MORADA': 'MORADO', 'DORADA': 'DORADO', 'PLATEADA': 'PLATEADO', 'BRONCEADA': 'BRONCEADO'
    }
    u = str(color_str).strip().upper()
    return mapping.get(u, u)


def detect_dominant_color(image_data, client_id):
    """
    Detecta el color dominante en la imagen usando CLIP
    Usa los colores reales de los productos del cliente (dinámico)

    Args:
        image_data: Datos binarios de la imagen
        client_id: ID del cliente para obtener sus colores de productos

    Returns:
        tuple: (color_detectado, confidence_score)
    """
    try:
        # Obtener colores únicos desde JSONB attributes->>'color' (preferido)
        rows = db.session.execute(
            text(
                """
                SELECT DISTINCT UPPER(TRIM(attributes->>'color')) AS color
                FROM products
                WHERE client_id = :client_id
                  AND attributes ? 'color'
                  AND NULLIF(TRIM(attributes->>'color'), '') IS NOT NULL
                """
            ),
            {"client_id": client_id},
        ).fetchall()

        unique_colors = [r[0] for r in rows if r[0]]

        if not unique_colors:
            print("⚠️ No hay colores definidos en productos del cliente")
            return "unknown", 0.0

        print(f"🎨 Colores disponibles del cliente (JSONB): {unique_colors}")

        # Crear prompts dinámicos basados en los colores del cliente
        color_prompts = [f"a photo of {color.lower()} product" for color in unique_colors]

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

            # Generar embeddings de texto para colores
            text_inputs = processor(text=color_prompts, return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = torch.cosine_similarity(image_embedding, text_embeddings, dim=1)

            # Encontrar la mejor coincidencia
            best_idx = similarities.argmax().item()
            best_score = similarities[best_idx].item()
            detected_color = unique_colors[best_idx]

            print(f"🎨 DETECCIÓN COLOR: {detected_color} (confianza: {best_score:.3f})")

            return detected_color, best_score

    except Exception as e:
        print(f"❌ Error en detección de color: {e}")
        import traceback
        traceback.print_exc()
        return "unknown", 0.0


def detect_dominant_color_from_palette(image_data, colors_list):
    """
    Detecta el color dominante restringiendo la comparación a una paleta dada.

    Args:
        image_data: bytes de la imagen
        colors_list: lista de strings con colores disponibles para comparar

    Returns:
        tuple: (color_detectado, confidence_score)
    """
    try:
        unique_colors = [c.strip() for c in colors_list if c and str(c).strip()]

        if not unique_colors:
            print("⚠️ Paleta de colores vacía para la categoría")
            return "unknown", 0.0

        print(f"🎨 Paleta de colores (categoría): {unique_colors}")

        # Crear prompts dinámicos basados en los colores de la categoría
        color_prompts = [f"a photo of {color.lower()} product" for color in unique_colors]

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

            # Generar embeddings de texto para colores
            text_inputs = processor(text=color_prompts, return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = torch.cosine_similarity(image_embedding, text_embeddings, dim=1)

            # Encontrar la mejor coincidencia
            best_idx = similarities.argmax().item()
            best_score = similarities[best_idx].item()
            detected_color = unique_colors[best_idx]

            print(f"🎨 DETECCIÓN COLOR (categoría): {detected_color} (confianza: {best_score:.3f})")

            return detected_color, best_score

    except Exception as e:
        print(f"❌ Error en detección de color (paleta): {e}")
        import traceback
        traceback.print_exc()
        return "unknown", 0.0


def detect_general_object(image_data, client_id=None):
    """
    Detecta QUÉ es el objeto en la imagen usando CLIP
    Si se proporciona client_id, usa las categorías del cliente
    Si no, usa categorías generales ampliadas

    Args:
        image_data: Datos binarios de la imagen
        client_id: ID del cliente (opcional, para usar sus categorías)

    Returns:
        tuple: (objeto_detectado, confidence_score)
    """
    try:
        # Si hay client_id, usar las categorías del cliente
        if client_id:
            categories = Category.query.filter_by(
                client_id=client_id,
                is_active=True
            ).all()

            if categories:
                # Usar name_en de las categorías como términos de detección
                general_categories = []
                for cat in categories:
                    if cat.name_en:
                        general_categories.append(f"a photo of {cat.name_en.lower()}")
                    else:
                        general_categories.append(f"a photo of {cat.name.lower()}")

                print(f"🔍 Usando categorías del cliente para detección: {[c.split('of ')[1] for c in general_categories]}")
            else:
                print("⚠️ No hay categorías activas, usando detección genérica")
                general_categories = ["product", "item", "object"]
        else:
            # Detección genérica amplia para cualquier tipo de producto
            general_categories = [
                "product", "item", "object", "merchandise",
                "clothing", "apparel", "garment",
                "accessory", "tool", "equipment",
                "furniture", "decoration", "appliance"
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

            # Generar embeddings de texto para categorías
            text_inputs = processor(text=general_categories, return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = torch.cosine_similarity(image_embedding, text_embeddings, dim=1)

            # Encontrar la mejor coincidencia
            best_idx = similarities.argmax().item()
            best_score = similarities[best_idx].item()
            detected_object = general_categories[best_idx]

            # Extraer solo el término del objeto (sin "a photo of")
            if "a photo of" in detected_object:
                detected_object = detected_object.replace("a photo of ", "").strip()

            print(f"🔍 DETECCIÓN GENERAL: {detected_object} (confianza: {best_score:.3f})")

            return detected_object, best_score

    except Exception as e:
        print(f"❌ Error en detección general: {e}")
        import traceback
        traceback.print_exc()
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

        # 6. Encontrar la mejor coincidencia con margen de victoria y desempate
        # Ordenar por similitud descendente
        category_similarities.sort(key=lambda x: x['similarity'], reverse=True)
        best_match = category_similarities[0]
        best_category = best_match['category']
        best_score = best_match['similarity']
        second_score = category_similarities[1]['similarity'] if len(category_similarities) > 1 else -1.0

        print(f"🎯 RAILWAY LOG: MEJOR: {best_category.name} = {best_score:.4f} | SEGUNDO = {second_score:.4f}")

        # Margen de victoria mínimo para aceptar directamente la categoría ganadora
        MARGIN_DELTA = 0.03  # 3 puntos de similitud coseno

        # Si el margen es muy chico, usamos un desempate con la detección general
        if second_score >= 0 and (best_score - second_score) < MARGIN_DELTA:
            print(f"⚖️  RAILWAY LOG: MARGEN PEQUEÑO ({best_score - second_score:.4f} < {MARGIN_DELTA}), aplicando desempate por objeto general")
            try:
                detected_object, object_confidence = detect_general_object(image_data, client_id)
                print(f"🔍 RAILWAY LOG: OBJETO GENERAL = {detected_object} (conf {object_confidence:.3f})")

                if object_confidence >= 0.20:  # usar con umbral bajo, solo como desempate
                    # Comparar el objeto detectado con los nombres de las categorías (name y name_en)
                    top2 = category_similarities[:2]

                    def cat_matches_object(cat, obj):
                        """Verifica si el objeto detectado está relacionado con la categoría"""
                        cat_name = (cat.name or '').lower()
                        cat_name_en = (cat.name_en or '').lower()
                        obj_lower = obj.lower()

                        # Match directo o por inclusión
                        return obj_lower in cat_name or obj_lower in cat_name_en or \
                               cat_name in obj_lower or cat_name_en in obj_lower

                    best_matches = cat_matches_object(best_category, detected_object)
                    second_cat = top2[1]['category'] if len(top2) > 1 else None
                    second_matches = cat_matches_object(second_cat, detected_object) if second_cat else False

                    if not best_matches and second_matches:
                        # Elegir la segunda si está en el grupo preferido
                        print(f"✅ RAILWAY LOG: DESEMPATE → Preferimos '{second_cat.name}' por concordar con objeto '{detected_object}'")
                        best_category = second_cat
                        best_score = top2[1]['similarity']
                    else:
                        print(f"ℹ️  RAILWAY LOG: Desempate mantiene categoría original (best={best_matches}, second={second_matches})")
                else:
                    print("ℹ️  RAILWAY LOG: Desempate no aplicado (baja confianza del objeto)")
            except Exception as e:
                print(f"⚠️ RAILWAY LOG: Error en desempate por objeto general: {e}")

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
        # Soportar también búsqueda textual vía JSON en el mismo endpoint
        # Si el Content-Type es application/json y no hay archivo de imagen, delegar a text_search()
        if request.method == 'POST' and (request.is_json or (request.content_type and 'application/json' in request.content_type)) and not request.files:
            # Delegar al handler de búsqueda textual existente
            resp = text_search()

            # Asegurar headers CORS consistentes con el endpoint unificado
            if isinstance(resp, tuple):
                resp_obj, status_code = resp
                try:
                    resp_obj.headers['Access-Control-Allow-Origin'] = '*'
                    resp_obj.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
                    resp_obj.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
                except Exception:
                    pass
                return resp_obj, status_code
            else:
                try:
                    resp.headers['Access-Control-Allow-Origin'] = '*'
                    resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
                    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
                except Exception:
                    pass
                return resp

        # Validar request
        client, image_file, error_response = _validate_visual_search_request()
        if error_response:
            return error_response

        # Procesar datos de imagen
        image_data, limit, _, error_response, status_code = _process_image_data(image_file)
        # Obtener configuración real del panel
        max_results = system_config.get('search', 'max_results')
        # Si el parámetro limit no está en el request, usar el del panel
        if not limit:
            limit = max_results
        if error_response:
            return error_response, status_code

        # Sensibilidad personalizada por cliente
        category_confidence_threshold = (getattr(client, 'category_confidence_threshold', 70) or 70) / 100.0
        product_similarity_threshold = (getattr(client, 'product_similarity_threshold', 30) or 30) / 100.0

        # 🚀 FASE 3: Cargar configuración de SearchOptimizer (si existe)
        use_optimizer = request.form.get('use_optimizer', 'true').lower() == 'true'  # Feature flag
        store_config = None
        search_optimizer = None

        if use_optimizer:
            try:
                store_config = StoreSearchConfig.query.get(client.id)
                if store_config:
                    search_optimizer = SearchOptimizer(store_config)
                    print(f"🎯 OPTIMIZER: Activado para {client.name} (v={store_config.visual_weight}, m={store_config.metadata_weight}, b={store_config.business_weight})")
                else:
                    print(f"⚠️ OPTIMIZER: No config found for client {client.id}, usando búsqueda tradicional")
            except Exception as e:
                print(f"❌ OPTIMIZER: Error cargando config: {e}")
                # Si falla, continuar sin optimizer
                search_optimizer = None

        # ===== PASO 1: DETECCIÓN DE CATEGORÍA ESPECÍFICA =====
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

        # ===== PASO 2: DETECCIÓN DE COLOR RESTRINGIDO A LA CATEGORÍA =====
        print(f"🎨 RAILWAY LOG: IDENTIFICANDO COLOR DOMINANTE (por categoría)...")

        # Construir paleta de colores solo con los productos de la categoría
        # Preferir colores desde JSONB attributes->>'color' para la categoría
        rows = db.session.execute(
            text(
                """
                SELECT DISTINCT UPPER(TRIM(p.attributes->>'color')) AS color
                FROM products p
                WHERE p.client_id = :client_id
                  AND p.category_id = :category_id
                  AND p.attributes ? 'color'
                  AND NULLIF(TRIM(p.attributes->>'color'), '') IS NOT NULL
                """
            ),
            {"client_id": client.id, "category_id": detected_category.id},
        ).fetchall()

        category_colors = [r[0] for r in rows if r[0]]

        if category_colors:
            detected_color, color_confidence = detect_dominant_color_from_palette(image_data, category_colors)
            print(f"🎨 RAILWAY LOG: COLOR DETECTADO (cat) = {detected_color} (confianza: {color_confidence:.3f})")
        else:
            detected_color, color_confidence = ("unknown", 0.0)
            print("⚠️ RAILWAY LOG: Categoría sin colores definidos; se omite boost/metadata por color")

        # ===== GENERAR EMBEDDING DE LA IMAGEN (con enriquecimiento por tags) =====
        query_embedding, error_response, status_code = _generate_query_embedding(
            image_data,
            detected_category=detected_category  # Pasar categoría para contexto
        )
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

        # ===== NO APLICAR BOOST NI METADATA POR COLOR EN BÚSQUEDA VISUAL =====
        # La detección de color solo se usa para logging/debug
        # El ranking visual debe ser 100% basado en similitud CLIP pura
        # Mantener paridad con producción (Railway)

        # 🚀 FASE 3: APLICAR SEARCH OPTIMIZER (si está activado)
        if search_optimizer and len(product_best_match) > 0:
            print(f"🎯 OPTIMIZER: Aplicando ranking avanzado a {len(product_best_match)} productos")

            # Preparar atributos detectados para metadata scoring
            detected_attributes = {}
            # NO usar color detectado en búsqueda visual para mantener paridad con producción
            # El color solo se considera en búsqueda textual

            # Convertir product_best_match a formato esperado por optimizer
            raw_results = [
                {
                    'product': match_data['product'],
                    'similarity': match_data['similarity']
                }
                for product_id, match_data in product_best_match.items()
            ]

            # Aplicar ranking con SearchOptimizer
            try:
                ranked_results = search_optimizer.rank_results(raw_results, detected_attributes)

                # Actualizar product_best_match con scores enriquecidos
                for ranked in ranked_results:
                    # ranked.product_id es string, pero las claves del dict son UUID objects
                    # Buscar por el objeto Product directamente
                    product_obj = ranked.product

                    # Buscar la clave UUID en el diccionario que corresponde a este producto
                    for dict_product_id, match_data in product_best_match.items():
                        if str(dict_product_id) == ranked.product_id:
                            product_best_match[dict_product_id]['optimizer_scores'] = {
                                'visual_score': ranked.visual_score,
                                'metadata_score': ranked.metadata_score,
                                'business_score': ranked.business_score,
                                'final_score': ranked.final_score,
                                'debug_info': ranked.debug_info
                            }
                            # Actualizar similarity con final_score para que _build_search_results ordene correctamente
                            product_best_match[dict_product_id]['similarity'] = ranked.final_score
                            break

                print(f"✅ OPTIMIZER: Ranking completado. Top 3 scores: " +
                      ", ".join([f"{r.final_score:.3f}" for r in ranked_results[:3]]))

                # Debug: verificar que optimizer_scores se guardó
                sample_id = list(product_best_match.keys())[0] if product_best_match else None
                if sample_id:
                    has_optimizer = 'optimizer_scores' in product_best_match[sample_id]
                    print(f"🔍 DEBUG: Primer producto tiene optimizer_scores: {has_optimizer}")

            except Exception as e:
                print(f"❌ OPTIMIZER: Error durante ranking: {e}")
                # Si falla, continuar con scores originales
                import traceback
                traceback.print_exc()

        # Construir resultados finales (sin filtro adicional de categoría)
        results = _build_search_results(product_best_match, limit)

        processing_time = time.time() - start_time

        # Respuesta con información de categoría detectada y config real
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
                "category_filter": True
            },
            "results": results,
            "total_results": len(results),
            "processing_time": round(processing_time, 3),
            "client_id": client.id,
            "client_name": client.name,
            "search_method": "category_filtered",
            "timestamp": time.time(),
            "timeout_minutes": round(_get_idle_timeout_seconds() / 60, 2),
            "max_results_config": max_results
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


@bp.route("/search/text", methods=["POST", "OPTIONS"])
def text_search():
    """
    Endpoint de búsqueda textual híbrida (CLIP + Atributos + Tags)

    Headers:
        X-API-Key: API Key del cliente

    JSON Body:
        query: Texto de búsqueda (ej: "camisa blanca", "delantal marrón")
        limit: Número de resultados (default: 10, max: 50)
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
        # Log temprano para verificar llegada de requests incluso si falla la API Key
        print(
            f"👉 TEXT SEARCH HIT: path={request.path} from={request.remote_addr} has_key={'X-API-Key' in request.headers}",
            flush=True
        )
        # Validar API Key
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({
                "success": False,
                "error": "missing_api_key",
                "message": "X-API-Key header requerido"
            }), 401

        # Buscar cliente por API Key
        client = Client.query.filter_by(api_key=api_key).first()
        if not client:
            return jsonify({
                "success": False,
                "error": "invalid_api_key",
                "message": "API Key inválido"
            }), 401

        # Obtener parámetros del request
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "missing_query",
                "message": "Campo 'query' requerido en el body JSON"
            }), 400

        query_text = data.get('query', '').strip()
        if not query_text:
            return jsonify({
                "success": False,
                "error": "empty_query",
                "message": "La query no puede estar vacía"
            }), 400

        # Obtener configuración real del panel
        max_results = system_config.get('search', 'max_results')
        # Permitir tanto 'limit' como 'max_results' del request, pero respetar el límite del sistema
        limit_value = data.get('limit', data.get('max_results', max_results))
        try:
            # Respetar el límite configurado en el sistema
            limit = min(int(limit_value), max_results)
        except Exception:
            limit = max_results

        print(f"📝 TEXT SEARCH: Query='{query_text}' Client={client.name} Limit={limit}", flush=True)

        # --- LLM Normalization (con vocabulario dinámico del cliente) ---
        llm_norm = normalize_query(query_text, client_id=client.id)
        # TODO: Mover a nivel de logs DEBUG
        # print(f"🧠 LLM Normalizer: {llm_norm}")
        print(f"🧠 LLM Normalizer: tipo={llm_norm.get('tipo')}, color={llm_norm.get('color')}, contexto={llm_norm.get('contexto')}")

        # Extraer campos del normalizador para usar en boosts
        detected_color = llm_norm.get('color', '').lower() if llm_norm.get('color') else None
        detected_tipo = llm_norm.get('tipo', '').lower() if llm_norm.get('tipo') else None

        # Expandir modificadores de color con colores del cliente
        expanded_query = expand_color_modifiers(query_text, client_id=str(client.id))
        if expanded_query != query_text:
            print(f"🔄 Query expandido: '{query_text}' -> '{expanded_query}'")

        # Generar embedding CLIP del texto de búsqueda (usar query expandido)
        model, processor = get_clip_model()
        device = "cuda" if torch.cuda.is_available() else "cpu"

        with torch.no_grad():
            text_inputs = processor(text=[expanded_query], return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            query_embedding = text_features.cpu().numpy()[0]

        # Usar query expandido para matching de atributos también
        query_lower = expanded_query.lower()

        # Intentar detectar categoría en el query mediante tokens normalizados
        detected_category = None
        categories = Category.query.filter_by(client_id=client.id, is_active=True).all()

        import re, unicodedata

        def _norm_token(t: str) -> str:
            t = ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn')
            t = re.sub(r"[^a-z0-9]+", "", t)
            # singularización naive: quitar 's' final si queda algo
            if len(t) > 3 and t.endswith('s'):
                t = t[:-1]
            return t

        STOPWORDS = {
            'hombre','hombres','dama','damas','mujer','mujeres','unisex',
            'y','de','para','con','sin','del','la','el','los','las'
        }

        def tokenize(texto: str):
            toks = re.split(r"[\s,./;:()\-–]+", texto or "")
            return { _norm_token(t) for t in toks if _norm_token(t) and _norm_token(t) not in STOPWORDS }

        query_tokens = tokenize(expanded_query)
        print(f"🔍 Query tokens: {query_tokens}")

        # Construir tokens por categoría (nombre, name_en y alternative_terms si existe)
        cat_tokens_list = []
        for category in categories:
            # Separar tokens del nombre (PESO ALTO) vs alternative_terms (PESO BAJO)
            name_toks = set()
            name_toks |= tokenize(category.name)
            if category.name_en:
                name_toks |= tokenize(category.name_en)

            alt_toks = set()
            alt = getattr(category, 'alternative_terms', None)
            if alt:
                for term in str(alt).split(','):
                    alt_toks |= tokenize(term.strip())

            cat_tokens_list.append((category, name_toks, alt_toks))

        # Detección mejorada: evaluar TODAS las categorías y elegir la mejor coincidencia
        # Buscar primero coincidencia exacta de frase completa (ej: "tiro bajo" completo)
        best_category = None
        best_score = 0

        # 1. Prioridad: Buscar coincidencia de frase completa en alternative_terms o nombre
        query_normalized = expanded_query.lower().strip()
        for category in categories:
            # Verificar en nombre (PRIORIDAD ALTA: nombre exacto de categoría)
            if query_normalized in category.name.lower() or category.name.lower() in query_normalized:
                detected_category = category
                print(f"📁 Categoría detectada por nombre exacto: {category.name}")
                break
            # Verificar en name_en también con alta prioridad
            if category.name_en and (query_normalized in category.name_en.lower() or category.name_en.lower() in query_normalized):
                detected_category = category
                print(f"📁 Categoría detectada por name_en exacto: {category.name}")
                break

        # Segundo pase: alternative_terms si no hubo match en nombre
        if not detected_category:
            for category in categories:
                alt = getattr(category, 'alternative_terms', None)
                if alt:
                    alt_terms = [t.strip().lower() for t in str(alt).split(',')]
                    if query_normalized in alt_terms:
                        detected_category = category
                        print(f"📁 Categoría detectada por alternative_term exacto: {category.name}")
                        break

        # 2. Si no hay coincidencia exacta, usar scoring de tokens (máxima superposición)
        if not detected_category:
            candidates = []  # Para debugging
            for category, name_toks, alt_toks in cat_tokens_list:
                # Calcular intersección con tokens del nombre (PESO 1.0)
                name_intersection = query_tokens & name_toks
                # Calcular intersección con tokens de alternative_terms (PESO 0.5)
                alt_intersection = query_tokens & alt_toks

                if name_intersection or alt_intersection:
                    # Score ponderado: tokens del nombre valen el doble
                    score = (len(name_intersection) * 1.0 + len(alt_intersection) * 0.5) / max(len(query_tokens), 1)
                    all_intersection = name_intersection | alt_intersection
                    candidates.append((category.name, score, all_intersection, 'name' if name_intersection else 'alt'))
                    if score > best_score:
                        best_score = score
                        best_category = category

            if candidates:
                print(f"🎯 Candidatos de categoría: {[(c[0], f'{c[1]:.2f}', c[2], c[3]) for c in sorted(candidates, key=lambda x: x[1], reverse=True)[:5]]}")

            if best_category and best_score > 0:
                detected_category = best_category
                print(f"📁 Categoría detectada por tokens (score={best_score:.2f}): {detected_category.name}")


        # Si NO detectamos categoría: decidir si es fuera de catálogo o si permitimos búsqueda global
        if not detected_category:
            all_cat_tokens = set()
            for _, name_toks, alt_toks in cat_tokens_list:
                all_cat_tokens |= name_toks
                all_cat_tokens |= alt_toks

            if query_tokens and query_tokens.isdisjoint(all_cat_tokens):
                # Ningún token del query coincide con tokens de categorías → fuera de catálogo
                available_names = [cat.name for cat in categories]
                return jsonify({
                    "success": False,
                    "error": "category_not_detected",
                    "query": query_text,
                    "detected_category": None,
                    "results": [],
                    "total_products_analyzed": 0,
                    "message": "No pudimos reconocer una categoría comercializada en tu consulta.",
                    "details": "Probá con una de estas categorías disponibles.",
                    "available_categories": available_names
                }), 400
            # Si hay alguna coincidencia débil (e.g., tokens genéricos), continuar sin filtrar por categoría
            print("ℹ️ TEXT SEARCH: Sin categoría inequívoca, continuando sin filtro por categoría")

        # --- Enriquecimiento opcional de query con tags inferidos (feature flag) ---
        try:
            fusion_enabled = system_config.get('search', 'enable_inferred_tags', False)
            if fusion_enabled:
                from app.services.query_enrichment_service import QueryEnrichmentService

                fusion_cfg = system_config.get('search', 'clip_fusion', {}) or {}
                alpha = float(fusion_cfg.get('alpha', 1.0))
                beta_tag = float(fusion_cfg.get('beta_tag', 0.5))

                # Usar servicio de enriquecimiento
                enrichment = QueryEnrichmentService.enrich_query(
                    query_text=expanded_query,
                    detected_category=detected_category.name if detected_category else None,
                    detected_color=detected_color,
                    detected_contexts=llm_norm.get('contexto') or [],
                    image_url=None,  # TODO: agregar soporte para imagen del usuario
                    client_id=str(client.id),
                    use_cache=True
                )

                tag_phrases = enrichment.get('tag_phrases', [])

                if tag_phrases:
                    with torch.no_grad():
                        tag_inputs = processor(text=tag_phrases, return_tensors="pt", padding=True)
                        tag_feats = model.get_text_features(**tag_inputs)
                        tag_feats = tag_feats / tag_feats.norm(dim=-1, keepdim=True)
                        tag_mean = tag_feats.mean(dim=0)

                        q = torch.tensor(query_embedding, dtype=torch.float32)
                        q = q / q.norm()
                        fused = alpha * q + beta_tag * tag_mean
                        fused = fused / fused.norm()
                        query_embedding = fused.cpu().numpy()

                    inferred_tags = enrichment.get('inferred_tags', [])
                    print(f"🧪 FUSION: alpha={alpha} beta_tag={beta_tag} phrases={len(tag_phrases)} tags={len(inferred_tags)}")
        except Exception as _e:
            # Fallback silencioso: si algo falla seguimos con embedding original
            print(f"⚠️ FUSION skip: {_e}")
            import traceback
            traceback.print_exc()


        # Consultar productos con embeddings (de imágenes principales), atributos y tags
        products_query = db.session.query(
            Product.id,
            Product.name,
            Product.sku,
            Product.price,
            Product.attributes,
            Product.tags,
            Category.name.label('category_name'),
            Image.clip_embedding,
            Image.cloudinary_url
        ).join(
            Category, Product.category_id == Category.id
        ).join(
            Image, db.and_(
                Product.id == Image.product_id,
                Image.is_primary == True
            )
        ).filter(
            Product.client_id == client.id,
            Image.clip_embedding.isnot(None)
        )

        # FILTRAR por categoría si fue detectada
        if detected_category:
            products_query = products_query.filter(Product.category_id == detected_category.id)
            print(f"🔎 Filtrando productos por categoría: {detected_category.name}")
        else:
            print(f"🔎 Búsqueda SIN filtro de categoría (global)")

        products = products_query.all()

        # Fallback 1: Si no hay productos en la categoría detectada, rehacer búsqueda global
        if detected_category and len(products) == 0:
            print("⚠️ TEXT SEARCH: 0 productos en categoría detectada → Fallback a búsqueda global")
            detected_category = None
            # reconstruir query sin filtro de categoría
            products_query = db.session.query(
                Product.id,
                Product.name,
                Product.sku,
                Product.price,
                Product.attributes,
                Product.tags,
                Category.name.label('category_name'),
                Image.clip_embedding,
                Image.cloudinary_url
            ).join(
                Category, Product.category_id == Category.id
            ).join(
                Image, db.and_(
                    Product.id == Image.product_id,
                    Image.is_primary == True
                )
            ).filter(
                Product.client_id == client.id,
                Image.clip_embedding.isnot(None)
            )
            products = products_query.all()

        print(f"🔍 TEXT SEARCH: Analizando {len(products)} productos...")

        # Calcular scores híbridos

        results = []
        for prod in products:
            # Parse embedding (puede estar como string JSON)
            embedding = prod.clip_embedding
            if isinstance(embedding, str):
                import json
                try:
                    embedding = json.loads(embedding)
                except:
                    continue  # Skip si no se puede parsear

            # Score CLIP (similitud visual/semántica)
            emb = np.array(embedding, dtype=np.float32)
            clip_similarity = float(np.dot(query_embedding, emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(emb)))

            # Boost por atributos (incluye match de categoría y color del LLM)
            attr_boost = _calculate_attribute_match(query_lower, prod.attributes, prod.category_name, detected_color, detected_tipo)
            # Debug de atributos clave: color declarado vs color detectado
            try:
                prod_color_dbg = None
                if isinstance(prod.attributes, dict):
                    for k in ['color', 'colour', 'color_principal', 'color_secundario']:
                        if k in prod.attributes and prod.attributes[k]:
                            prod_color_dbg = prod.attributes[k]
                            break
                if detected_color:
                    print(f"  🔎 ATTR DEBUG: {prod.name} | attr.color={prod_color_dbg} | detected_color={detected_color} | attr_boost={attr_boost:.3f}")
            except Exception:
                pass

            # Boost por nombre de producto y SKU (nuevo) + tags
            name_boost = _calculate_name_match(query_lower, prod.name, getattr(prod, 'sku', None))
            tag_boost = _calculate_tag_match(query_lower, prod.tags)
            tag_name_boost = min(1.0, tag_boost + name_boost)

            # Score final híbrido
            # Ponderaciones: CLIP 50%, Atributos 40%, Tags+Nombre 10%
            final_score = (
                clip_similarity * 0.5 +
                attr_boost * 0.4 +
                tag_name_boost * 0.1
            )

            print(f"Producto: {prod.name} | CLIP: {clip_similarity:.3f} | Attr: {attr_boost:.3f} | Tag: {tag_boost:.3f} | Name: {name_boost:.3f} | Score: {final_score:.3f}")

            results.append({
                'product_id': str(prod.id),
                'name': prod.name,
                'sku': prod.sku,
                'price': float(prod.price) if prod.price else None,
                'category': prod.category_name,
                'attributes': prod.attributes,
                'tags': prod.tags or "",
                'image_url': prod.cloudinary_url,
                'clip_similarity': round(clip_similarity, 4),
                'attr_boost': round(attr_boost, 4),
                'tag_boost': round(tag_boost, 4),
                'name_boost': round(name_boost, 4),
                'final_score': round(final_score, 4)
            })

        # Ordenar por score descendente
        results.sort(key=lambda x: x['final_score'], reverse=True)


        # Limitar resultados
        results = results[:limit]

        elapsed_time = time.time() - start_time

        # Fallback 2: Si tras el scoring no hay resultados, intentar una búsqueda global sin categoría
        if len(results) == 0 and detected_category is not None:
            print("⚠️ TEXT SEARCH: 0 resultados tras filtrar por categoría → Reintentando global")
            detected_category = None
            # reconstruir query sin filtro de categoría
            products_query = db.session.query(
                Product.id,
                Product.name,
                Product.sku,
                Product.price,
                Product.attributes,
                Product.tags,
                Category.name.label('category_name'),
                Image.clip_embedding,
                Image.cloudinary_url
            ).join(
                Category, Product.category_id == Category.id
            ).join(
                Image, db.and_(
                    Product.id == Image.product_id,
                    Image.is_primary == True
                )
            ).filter(
                Product.client_id == client.id,
                Image.clip_embedding.isnot(None)
            )
            products = products_query.all()

            print(f"🔍 TEXT SEARCH (fallback): Analizando {len(products)} productos...")

            results = []
            for prod in products:
                embedding = prod.clip_embedding
                if isinstance(embedding, str):
                    import json
                    try:
                        embedding = json.loads(embedding)
                    except:
                        continue
                emb = np.array(embedding, dtype=np.float32)
                clip_similarity = float(np.dot(query_embedding, emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(emb)))
                attr_boost = _calculate_attribute_match(query_lower, prod.attributes, prod.category_name, detected_color, detected_tipo)
                name_boost = _calculate_name_match(query_lower, prod.name, getattr(prod, 'sku', None))
                tag_boost = _calculate_tag_match(query_lower, prod.tags)
                tag_name_boost = min(1.0, tag_boost + name_boost)
                final_score = (
                    clip_similarity * 0.5 +
                    attr_boost * 0.4 +
                    tag_name_boost * 0.1
                )
                results.append({
                    'product_id': str(prod.id),
                    'name': prod.name,
                    'sku': prod.sku,
                    'price': float(prod.price) if prod.price else None,
                    'category': prod.category_name,
                    'attributes': prod.attributes,
                    'tags': prod.tags or "",
                    'image_url': prod.cloudinary_url,
                    'clip_similarity': round(clip_similarity, 4),
                    'attr_boost': round(attr_boost, 4),
                    'tag_boost': round(tag_boost, 4),
                    'name_boost': round(name_boost, 4),
                    'final_score': round(final_score, 4)
                })

            results.sort(key=lambda x: x['final_score'], reverse=True)
            results = results[:limit]
            print(f"🔁 TEXT SEARCH Fallback: {len(results)} resultados")

        print(f"✅ TEXT SEARCH: {len(results)} resultados en {elapsed_time:.3f}s")

        response = {
            "success": True,
            "query": query_text,
            "detected_category": {
                "id": str(detected_category.id),
                "name": detected_category.name,
                "name_en": detected_category.name_en
            } if detected_category else None,
            "results": results,
            "total_products_analyzed": len(products),
            "search_time_seconds": round(elapsed_time, 3)
        }

        # Agregar sugerencias si la query es ambigua
        if llm_norm.get('needs_refinement'):
            response['needs_refinement'] = True
            response['ambiguous_terms'] = llm_norm.get('ambiguous_terms', [])
            response['suggestions'] = llm_norm.get('suggestions', {})
            response['refinement_message'] = "Tu búsqueda es muy general. ¿Podrías ser más específico?"

        # Añadir CORS para consistencia cuando este handler es invocado desde /api/search
        resp = jsonify(response)
        try:
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        except Exception:
            pass
        return resp

    except Exception as e:
        import traceback
        print(f"❌ TEXT SEARCH ERROR: {e}")
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": "internal_error",
            "message": str(e)
        }), 500


def _translate_query_to_english(query: str) -> str:
    """
    Traduce el query a inglés usando deep-translator (gratuito, sin API key).
    Fallback: retorna query original si falla.
    """
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='en')
        translated = translator.translate(query)
        if translated and translated != query:
            print(f"🌐 Traducción: '{query}' → '{translated}'")
            return translated
    except ImportError:
        print("⚠️ deep-translator no instalado. Instalar con: pip install deep-translator")
    except Exception as e:
        print(f"⚠️ Error en traducción: {e}")

    return query


## expand_color_modifiers fue extraído a app.core.modifier_expander.expand_color_modifiers


## normalize_color fue extraído a app.utils.colors.normalize_color


def _calculate_attribute_match(query_lower: str, attributes: dict, category: str = None, detected_color: str = None, detected_tipo: str = None) -> float:
    """
    Calcula boost por matching de atributos JSONB + categoría.

    Estrategia de scoring:
    - Categoría match: +0.30 (identifica el tipo de producto)
    - Color exacto (del LLM normalizer): +0.50 (crítico para búsquedas visuales)
    - Otros atributos exactos: +0.20 cada uno
    - Match parcial: +0.10

    Args:
        query_lower: Query en minúsculas
        attributes: Atributos JSONB del producto
        category: Nombre de categoría del producto
        detected_color: Color detectado por LLM normalizer
        detected_tipo: Tipo detectado por LLM normalizer
    """
    score = 0.0
    other_attr_score = 0.0  # Limitar contribución de atributos NO color
    query_words = set(query_lower.split())

    # 1. Match de categoría (importante para tipo de producto)
    if category:
        category_lower = category.lower()
        for word in query_words:
            if len(word) > 3 and word in category_lower:
                score += 0.30  # Boost fuerte por match de categoría
                break  # Solo una vez

    # 2. Match de atributos JSONB con ponderación por tipo
    if attributes:
        def _to_str_list(val):
            # Aceptar string, lista de strings o dicts con 'value'
            if val is None:
                return []
            if isinstance(val, str):
                return [val]
            if isinstance(val, list):
                return [str(x) for x in val if x is not None]
            if isinstance(val, dict):
                v = val.get('value')
                return [str(v)] if v is not None else []
            return []

        for attr_key, attr_value in attributes.items():
            values = _to_str_list(attr_value)
            if not values:
                continue

            attr_key_lower = attr_key.lower()

            # Identificar si es un atributo de color
            is_color_attr = attr_key_lower in ['color', 'colour', 'color_principal', 'color_secundario']

            for v in values:
                v_lower = v.lower()

                if is_color_attr:
                    # PRIORIDAD 1: Usar color del LLM normalizer si está disponible
                    if detected_color:
                        product_color_norm = normalize_color(v)
                        llm_color_norm = normalize_color(detected_color)

                        if product_color_norm and llm_color_norm and product_color_norm == llm_color_norm:
                            score += 0.50  # Boost fuerte por color del LLM
                            print(f"  🎨 COLOR MATCH (LLM): '{detected_color}' == '{v}' (+0.50)")
                            break

                    # FALLBACK: Match tradicional por query
                    product_color_normalized = normalize_color(v)
                    query_normalized = normalize_color(query_lower)

                    if product_color_normalized and query_normalized and product_color_normalized == query_normalized:
                        score += 0.40  # Match de color normalizado
                        break
                    else:
                        # Match por palabra individual (solo si ambas normalizaciones son válidas)
                        matched_word = False
                        if product_color_normalized:
                            for word in query_words:
                                nw = normalize_color(word)
                                if nw and nw == product_color_normalized:
                                    matched_word = True
                                    break
                        if matched_word:
                            score += 0.40
                            break
                else:
                    # Para otros atributos, permitir aporte HASTA +0.20 en total
                    if other_attr_score < 0.20:
                        if v_lower in query_lower:
                            delta = min(0.20, 0.20 - other_attr_score)
                            other_attr_score += delta
                            score += delta
                            break
                        elif any(word in v_lower for word in query_words if len(word) > 2):
                            delta = min(0.10, 0.20 - other_attr_score)
                            if delta > 0:
                                other_attr_score += delta
                                score += delta
                                break

    return min(score, 1.0)  # Cap a 1.0


def _calculate_name_match(query_lower: str, name: str, sku: str = None) -> float:
    """
    Calcula boost por coincidencia con nombre del producto y/o SKU.

    Reglas simples y baratas:
    - Frase completa contenida en el nombre: +0.6
    - Coincidencia por palabras (>2 letras) en el nombre: +0.15 por match, hasta +0.4
    - SKU: coincidencia exacta +0.6, contiene +0.3
    El resultado se capa a 1.0 y luego se pondera externamente con peso 0.1
    """
    score = 0.0
    if not name and not sku:
        return score

    name_lower = (name or "").lower()
    q = (query_lower or "").strip()
    if q:
        # Frase completa
        if len(q) >= 3 and q in name_lower:
            score += 0.6
        # Por palabras
        words = [w for w in q.split() if len(w) > 2]
        if words:
            matches = sum(1 for w in words if w in name_lower)
            if matches:
                score += min(0.4, matches * 0.15)

    if sku:
        sku_lower = str(sku).lower()
        if q and q == sku_lower:
            score += 0.6
        elif q and q in sku_lower:
            score += 0.3

    return min(score, 1.0)


def _calculate_tag_match(query_lower: str, tags: str) -> float:
    """
    Calcula boost por matching de tags.
    """
    score = 0.0
    if not tags:
        return score

    tags_lower = tags.lower()
    query_words = set(query_lower.split())

    # Match directo de tags
    for word in query_words:
        if word in tags_lower:
            score += 0.2

    return score


@bp.errorhandler(500)
def api_internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500
