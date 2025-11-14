"""
Blueprint de API
Endpoints internos para el admin panel y búsqueda visual
"""

import sys
import time
from app.blueprints.embeddings import _get_idle_timeout_seconds
import hashlib
import numpy as np
import torch
import os
from flask import Blueprint, request, jsonify, send_file, current_app, session
from flask_login import login_required, current_user
from flask_cors import CORS
from app import db
from app.models.client import Client
from app.models.category import Category
from app.models.product import Product
from app.models.image import Image
# from app.models.search_log import SearchLog  # Deshabilitado - no se usa logging de búsquedas
from app.models.store_search_config import StoreSearchConfig
from app.services.image_manager import image_manager
from app.core.search_optimizer import SearchOptimizer
from app.utils.system_config import system_config
from app.core.modifier_expander import expand_color_modifiers
from app.utils.colors import normalize_color
from app.utils.llm_query_normalizer import normalize_query
from sqlalchemy import func, or_, text
# from googletrans import Translator  # DESHABILITADO - googletrans 4.0.0rc1 roto con httpcore

# 🚀 IMPORTAR CLIP AL INICIO PARA CACHE GLOBAL
from app.blueprints.embeddings import get_clip_model

bp = Blueprint("api", __name__)

# Habilitar CORS para este blueprint
CORS(bp, origins=["*"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "X-API-Key", "Authorization"])


# 🔍 Helper para logs que funcionen en Railway (Gunicorn)
def railway_log(message):
    """Log que se ve en Railway - usa stderr con flush inmediato"""
    print(f"[RAILWAY] {message}", file=sys.stderr, flush=True)


# 🔤 Helper: construir prompt en inglés para CLIP desde nombres de categoría
def _clip_label_from_spanish(name: str) -> str:
    """
    Mapear nombres de categorías en español (posibles typos) a descriptores
    en inglés que CLIP entienda mejor. Mantenerlo simple y determinista.

    Ejemplos:
      - "shores/short/shorts tiro bajo" → "low-rise jean shorts"
      - "pantalones de jeans rectos" → "straight-leg jeans"
      - "chupin" → "skinny jeans"
      - "boca ancha/oxford" → "wide-leg jeans"
    """
    if not name:
        return "clothing"

    n = name.lower()

    base = None
    qualifiers: list[str] = []

    # Rise
    if "tiro bajo" in n or "bajo" in n and "tiro" in n:
        qualifiers.append("low-rise")
    elif "tiro alto" in n or ("alto" in n and "tiro" in n):
        qualifiers.append("high-rise")

    # Jeans family and cut
    if any(k in n for k in ["short", "shorts", "shore", "shores"]):
        # Shorts de jean si menciona jean/denim
        if "jean" in n or "denim" in n:
            base = "jean shorts"
        else:
            base = "shorts"
    elif "pantalon" in n or "pantalones" in n:
        if "jean" in n or "denim" in n:
            base = "jeans"
        else:
            base = "pants"

    # Cortes
    if any(k in n for k in ["recto", "rectos", "recta"]):
        qualifiers.append("straight-leg")
    if "chupin" in n or "skinny" in n:
        qualifiers.append("skinny")
    if any(k in n for k in ["boca ancha", "pierna ancha", "oxford", "wide"]):
        qualifiers.append("wide-leg")

    # Fallback si no se detectó base
    if base is None:
        if "jean" in n or "denim" in n:
            base = "jeans"
        else:
            base = n.strip() or "clothing"

    phrase = " ".join(qualifiers + [base]).strip()
    return phrase


def _clip_prompt_for_category(category) -> str:
    """Construye el prompt final "a photo of ..." usando clip_prompt/name_en o mapping."""
    try:
        if getattr(category, "clip_prompt", None):
            label = str(category.clip_prompt).lower()
        elif getattr(category, "name_en", None):
            label = str(category.name_en).lower()
        else:
            label = _clip_label_from_spanish(getattr(category, "name", ""))
        return f"a photo of {label}"
    except Exception:
        return "a photo of clothing"


@bp.route("/image/<path:filename>")
def serve_image(filename):
    """Servir imÃ¡genes directamente usando ImageManager"""
    try:
        # âœ… USAR IMAGEMANAGER - Buscar imagen por filename
        from app.models.image import Image
        image = Image.query.filter_by(filename=filename).first()

        if not image:
            return "Image not found", 404

        # Obtener cliente dinÃ¡micamente
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
    """BÃºsqueda global en todos los modelos"""
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

    # Buscar categorÃ­as
    categories = Category.query.filter(
        or_(Category.name.contains(query), Category.description.contains(query))
    ).limit(5).all()

    results["categories"] = [{
        "id": category.id,
        "name": category.name,
        "client": category.client.name,
        "type": "category"
    } for category in categories]

    # Buscar imÃ¡genes
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
        "url": image.display_url,  # Usar propiedad del modelo (patrÃ³n unificado)
        "type": "image"
    } for image in images]

    return jsonify(results)


@bp.route("/stats/dashboard")
@login_required
def dashboard_stats():
    """EstadÃ­sticas para el dashboard principal"""
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
            # "searches_today": SearchLog.query.filter(
            #     func.date(SearchLog.created_at) == func.current_date()
            # ).count()
            "searches_today": 0  # Deshabilitado - no se registran búsquedas
        },

        # Top categorÃ­as por productos
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
    """Validar que un SKU sea Ãºnico"""
    sku = request.args.get("sku")
    product_id = request.args.get("product_id")  # Para ediciÃ³n

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
    """Validar que un slug sea Ãºnico dentro del cliente"""
    slug = request.args.get("slug")
    client_id = request.args.get("client_id")
    model_type = request.args.get("type")  # "category" o "product"
    item_id = request.args.get("item_id")  # Para ediciÃ³n

    if not slug or not client_id or not model_type:
        return jsonify({"valid": False, "message": "ParÃ¡metros requeridos"})

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
        return jsonify({"valid": False, "message": "Tipo invÃ¡lido"})

    existing = query.first()

    return jsonify({
        "valid": existing is None,
        "message": "Slug disponible" if existing is None else "Slug ya existe"
    })


@bp.route("/bulk/delete", methods=["POST"])
@login_required
def bulk_delete():
    """EliminaciÃ³n en lote"""
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
                    # Eliminar imÃ¡genes asociadas
                    Image.query.filter_by(product_id=product_id).delete()
                    db.session.delete(product)
                    deleted_count += 1

        elif model_type == "categories":
            # Eliminar categorÃ­as (solo si no tienen productos)
            for category_id in ids:
                category = Category.query.get(category_id)
                if category:
                    product_count = Product.query.filter_by(category_id=category_id).count()
                    if product_count == 0:
                        db.session.delete(category)
                        deleted_count += 1

        elif model_type == "images":
            # Eliminar imÃ¡genes
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
                "error": "No se proporcionÃ³ texto para traducir"
            })

        # Crear instancia del traductor
        # translator = Translator()  # DESHABILITADO - googletrans roto

        # TODO: Migrar a deep-translator (ver BACKLOG_MEJORAS.md)
        # Por ahora retornar texto sin traducir
        translated_text = text.lower()

        # Obtener el contexto de la industria del cliente
        industry_context = ""
        if current_user.client and current_user.client.industry:
            industry_context = current_user.client.industry.lower()

        # # Traducir el texto
        # translation = translator.translate(text, dest=target_language)
        # translated_text = translation.text.lower()

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
        print(f"Error en traducciÃ³n: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error en la traducciÃ³n: {str(e)}"
        })


@bp.errorhandler(404)
def api_not_found(error):
    return jsonify({"error": "Endpoint no encontrado"}), 404


# ==============================================================================
# ENDPOINT DE BÃšSQUEDA VISUAL PARA WIDGET
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
    """Verificar API Key del header"""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return None, "API Key requerida en header X-API-Key"

    client = Client.query.filter_by(api_key=api_key, is_active=True).first()
    if not client:
        return None, "API Key inválida"

    return client, None



def process_image_for_search(image_data):
    """Procesar imagen y generar embedding para bÃºsqueda"""
    try:
        import logging
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.getLogger("clip_model").info(f"[REQUEST] ComparaciÃ³n recibida")

        print("ðŸ”§ DEBUG: Iniciando procesamiento de imagen")

        # Importar PIL con alias para evitar conflictos
        from PIL import Image as PILImage
        import io
        print("ðŸ”§ DEBUG: Importaciones exitosas")

        # Convertir bytes a imagen PIL
        pil_image = PILImage.open(io.BytesIO(image_data))
        print(f"ðŸ”§ DEBUG: Imagen PIL creada: {pil_image.size}")

        # Obtener modelo CLIP directamente
        start_clip_time = time.time()
        model, processor = get_clip_model()
        clip_load_time = time.time() - start_clip_time
        print(f"ï¿½ CLIP MODEL: Obtenido en {clip_load_time:.3f}s")

        # Generar embedding usando solo argumentos necesarios
        print("ðŸ”§ DEBUG: Llamando al procesador CLIP...")
        start_process_time = time.time()

        # Llamada simplificada al procesador
        with torch.no_grad():
            inputs = processor(
                images=pil_image,
                return_tensors="pt"
            )
            print("ðŸ”§ DEBUG: Inputs del procesador creados exitosamente")

            # Generar features de imagen
            image_features = model.get_image_features(**inputs)
            print(f"ðŸ”§ DEBUG: Image features generadas: {image_features.shape}")

            # Normalizar embedding
            embedding = image_features / image_features.norm(dim=-1, keepdim=True)

            # Convertir a lista de Python
            embedding_list = embedding.squeeze().cpu().numpy().tolist()

            process_time = time.time() - start_process_time
            print(f"âš¡ CLIP PROCESSING: Completado en {process_time:.3f}s")

        print(f"ðŸ”§ DEBUG: Embedding generado exitosamente: {len(embedding_list)} dimensiones")
        return embedding_list, None

    except Exception as e:
        print(f"âŒ DEBUG: Error en process_image_for_search: {str(e)}")
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
    """Valida los parÃ¡metros de la bÃºsqueda visual

    Retorna SIEMPRE una tupla de 4 elementos:
    (client, image_file, error_response, status_code)
    - Ã‰xito: (client, image_file, None, None)
    - Error:  (None, None, jsonify({...}), <status>)
    """
    # Verificar API Key
    client, error = verify_api_key()
    if error:
        return None, None, jsonify({
            "error": "unauthorized",
            "message": error
        }), 401

    # Verificar imagen
    if 'image' not in request.files:
        return None, None, jsonify({
            "error": "bad_request",
            "message": "Imagen requerida en form-data 'image'"
        }), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return None, None, jsonify({
            "error": "bad_request",
            "message": "No se seleccionÃ³ archivo"
        }), 400

    return client, image_file, None, None


def _process_image_data(image_file):
    """Procesa y valida los datos de la imagen"""
    # Obtener configuraciÃ³n del sistema
    default_max_results = system_config.get('search', 'max_results', 10)

    # ParÃ¡metros (usar configuraciÃ³n como default y mÃ¡ximo)
    limit = min(int(request.form.get('limit', default_max_results)), default_max_results)
    threshold = float(request.form.get('threshold', 0.1))

    # Leer imagen
    image_data = image_file.read()

    # Validar tamaÃ±o (15MB mÃ¡ximo)
    if len(image_data) > 15 * 1024 * 1024:
        return None, None, None, jsonify({
            "error": "file_too_large",
            "message": "Imagen muy grande. MÃ¡ximo 15MB"
        }), 400

    return image_data, limit, threshold, None, None


def _generate_query_embedding(image_data, detected_category=None):
    """
    Genera el embedding de la imagen de consulta con enriquecimiento opcional por tags

    Args:
        image_data: Bytes de la imagen
        detected_category: CategorÃ­a detectada (opcional, para contexto)

    Returns:
        Tuple: (embedding_enriquecido, error_response, status_code)
    """
    print(f"ðŸ“· DEBUG: Procesando imagen de {len(image_data)} bytes")
    query_embedding, error = process_image_for_search(image_data)
    if error:
        print(f"âŒ DEBUG: Error en procesamiento: {error}")
        return None, jsonify({
            "error": "processing_failed",
            "message": error
        }), 500

    if query_embedding is None:
        print("âŒ DEBUG: query_embedding es None")
        return None, jsonify({
            "error": "processing_failed",
            "message": "No se pudo generar embedding de la imagen"
        }), 500

    print(f"ðŸ§  DEBUG: Embedding generado - dimensiones: {len(query_embedding)}")
    print(f"ðŸ§  DEBUG: Primeros 5 valores: {query_embedding[:5]}")

    # âœ¨ ENRIQUECIMIENTO CON TAGS INFERIDOS (para bÃºsqueda visual)
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
                # Tomar top 5 tags mÃ¡s relevantes
                top_tags = inferred_tags[:5]
                tag_names = [tag for tag, _ in top_tags]

                print(f"ðŸ”® VISUAL FUSION: Tags inferidos de imagen: {', '.join([f'{t}({c:.2f})' for t, c in top_tags])}")

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

                    print(f"âœ¨ VISUAL FUSION: Embedding enriquecido (Î±={alpha} visual + Î²={beta} tags)")

        except Exception as e:
            print(f"âš ï¸ VISUAL FUSION skip: {e}")
            # Si falla, continuar con embedding original
            pass

    return query_embedding, None, None


def _find_similar_products(client, query_embedding, threshold):
    """Encuentra productos similares y agrupa por mejor coincidencia"""
    # Buscar imÃ¡genes similares en la base de datos
    images = Image.query.filter_by(
        client_id=client.id,
        is_processed=True
    ).filter(Image.clip_embedding.isnot(None)).all()

    print(f"ðŸ” DEBUG: Encontradas {len(images)} imÃ¡genes para comparar")

    # Calcular similitudes y agrupar por producto
    product_best_match = {}  # Dict para almacenar la mejor imagen de cada producto
    category_similarities = {}  # Para determinar categorÃ­a mÃ¡s probable

    for img in images:
        try:
            similarity = calculate_similarity(query_embedding, img.clip_embedding)
            category_name = img.product.category.name if img.product.category else "Sin categorÃ­a"

            print(f"ðŸ” DEBUG: Similitud con {img.product.name[:30]} ({category_name}): {similarity:.4f}")

            # Recopilar estadÃ­sticas por categorÃ­a
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
                    print(f"âœ… DEBUG: Mejor imagen para {img.product.name}: {similarity:.4f}")

        except Exception as e:
            print(f"âŒ Error calculando similitud para imagen {img.id}: {e}")
            continue

    # Determinar categorÃ­a mÃ¡s probable basada en mayor similitud promedio
    print(f"\nðŸ“Š DEBUG: AnÃ¡lisis por categorÃ­as:")
    best_category = None
    best_avg_similarity = 0

    for category, similarities in category_similarities.items():
        avg_sim = sum(similarities) / len(similarities)
        max_sim = max(similarities)
        count = len(similarities)
        print(f"   ðŸ“‚ {category}: {count} productos, promedio: {avg_sim:.4f}, mÃ¡ximo: {max_sim:.4f}")

        if max_sim > best_avg_similarity:  # Usar mÃ¡ximo en lugar de promedio para detectar categorÃ­a objetivo
            best_avg_similarity = max_sim
            best_category = category

    print(f"ðŸŽ¯ DEBUG: CategorÃ­a mÃ¡s probable: '{best_category}' (similitud mÃ¡xima: {best_avg_similarity:.4f})")

    # Aplicar boost de categorÃ­a: aumentar similitud para productos de la categorÃ­a mÃ¡s probable
    if best_category and best_category != "Sin categorÃ­a":
        for product_id in product_best_match:
            match_data = product_best_match[product_id]
            if match_data['category'] == best_category:
                # Boost del 15% para productos de la misma categorÃ­a
                original_similarity = match_data['similarity']
                boosted_similarity = min(1.0, original_similarity * 1.15)
                match_data['similarity'] = boosted_similarity
                match_data['category_boost'] = True
                print(f"ðŸš€ DEBUG: Boost aplicado a {match_data['product'].name}: {original_similarity:.4f} â†’ {boosted_similarity:.4f}")
            else:
                match_data['category_boost'] = False

    print(f"ðŸŽ¯ DEBUG: Productos Ãºnicos encontrados: {len(product_best_match)}")
    return product_best_match


def _find_similar_products_in_category(client, query_embedding, threshold, category_id):
    """
    Encuentra productos similares SOLO dentro de una categorÃ­a especÃ­fica

    Args:
        client: Cliente autenticado
        query_embedding: Embedding de la imagen query
        threshold: Umbral mÃ­nimo de similitud
        category_id: ID de la categorÃ­a en la que buscar

    Returns:
        dict: Diccionario con los mejores matches por producto
    """
    # Buscar imÃ¡genes SOLO de la categorÃ­a especÃ­fica
    images = (Image.query
              .join(Product)
              .filter(
                  Image.client_id == client.id,
                  Image.is_processed == True,
                  Image.clip_embedding.isnot(None),
                  Product.category_id == category_id
              ).all())

    print(f"ðŸ” DEBUG: Encontradas {len(images)} imÃ¡genes en la categorÃ­a especÃ­fica")

    # Calcular similitudes y agrupar por producto
    product_best_match = {}  # Dict para almacenar la mejor imagen de cada producto

    for img in images:
        try:
            similarity = calculate_similarity(query_embedding, img.clip_embedding)
            category_name = img.product.category.name if img.product.category else "Sin categorÃ­a"

            print(f"ðŸ” DEBUG: Similitud con {img.product.name[:30]} ({category_name}): {similarity:.4f}")

            if similarity >= threshold:
                product_id = img.product.id

                # Si es la primera imagen de este producto, o si tiene mayor similitud que la anterior
                if product_id not in product_best_match or similarity > product_best_match[product_id]['similarity']:
                    product_best_match[product_id] = {
                        'image': img,
                        'similarity': similarity,
                        'product': img.product,
                        'category': category_name,
                        'category_filtered': True  # Indicador de que se filtrÃ³ por categorÃ­a
                    }
                    print(f"âœ… DEBUG: Mejor imagen para {img.product.name}: {similarity:.4f}")

        except Exception as e:
            print(f"âŒ Error calculando similitud para imagen {img.id}: {e}")
            continue

    print(f"ðŸŽ¯ DEBUG: Total productos Ãºnicos encontrados en categorÃ­a: {len(product_best_match)}")
    return product_best_match


def _apply_category_filter(product_best_match, limit):
    """Aplica filtrado inteligente por categorÃ­a si es necesario"""
    # Filtrado inteligente por categorÃ­a (solo si hay suficientes productos)
    if len(product_best_match) <= limit * 2:  # Solo filtrar si hay muchos productos
        print(f"ðŸŽ¯ DEBUG: Pocos productos encontrados ({len(product_best_match)}), no se aplica filtro de categorÃ­a")
        return product_best_match

    # Obtener las categorÃ­as de los productos con mayor similitud
    sorted_products = sorted(product_best_match.items(), key=lambda x: x[1]['similarity'], reverse=True)

    # Tomar las top similitudes para determinar la categorÃ­a dominante
    top_count = min(3, len(sorted_products))
    top_categories = {}

    for product_id, match_data in sorted_products[:top_count]:
        category_name = match_data['product'].category.name
        if category_name not in top_categories:
            top_categories[category_name] = []
        top_categories[category_name].append(match_data['similarity'])

    # Determinar la categorÃ­a mÃ¡s relevante basada en similitud promedio
    best_category = None
    best_avg_similarity = 0

    for category, similarities in top_categories.items():
        avg_similarity = sum(similarities) / len(similarities)
        print(f"ðŸ“‚ DEBUG: CategorÃ­a '{category}': {len(similarities)} productos, similitud promedio: {avg_similarity:.4f}")

        if avg_similarity > best_avg_similarity:
            best_avg_similarity = avg_similarity
            best_category = category

    # Solo aplicar filtro si la categorÃ­a dominante es muy clara (>60% similitud promedio)
    if not (best_category and best_avg_similarity > 0.6):
        print(f"ðŸŽ¯ DEBUG: No se aplicÃ³ filtro de categorÃ­a (similitud promedio: {best_avg_similarity:.4f})")
        return product_best_match

    print(f"ðŸŽ¯ DEBUG: CategorÃ­a dominante detectada: '{best_category}' (similitud promedio: {best_avg_similarity:.4f})")

    # Filtrar solo productos de la categorÃ­a dominante
    filtered_matches = {}
    for product_id, match_data in product_best_match.items():
        product_category = match_data['product'].category.name

        # Incluir productos de la categorÃ­a dominante
        if product_category == best_category:
            filtered_matches[product_id] = match_data
            print(f"âœ… DEBUG: Incluido por categorÃ­a exacta: {match_data['product'].name} ({product_category})")
        else:
            print(f"âŒ DEBUG: Excluido por categorÃ­a: {match_data['product'].name} ({product_category} != {best_category})")

    # Solo usar el filtro si queda al menos el mÃ­nimo de productos
    if len(filtered_matches) >= limit:
        print(f"ðŸŽ¯ DEBUG: Productos despuÃ©s del filtro de categorÃ­a: {len(filtered_matches)}")
        return filtered_matches
    else:
        print("âš ï¸ DEBUG: El filtro de categorÃ­a eliminÃ³ demasiados productos, manteniendo los originales")
        return product_best_match


def _build_search_results(product_best_match, limit):
    """Construye la lista final de resultados"""
    results = []

    # ðŸ” DEBUG: Verificar contenido del dict recibido
    print(f"ðŸ” DEBUG _build_search_results: Recibido dict con {len(product_best_match)} productos")
    if product_best_match:
        sample_id = list(product_best_match.keys())[0]
        sample_match = product_best_match[sample_id]
        print(f"ðŸ” DEBUG _build_search_results: Claves en sample_match: {list(sample_match.keys())}")
        print(f"ðŸ” DEBUG _build_search_results: Tiene optimizer_scores: {'optimizer_scores' in sample_match}")

    # Intentar obtener configuraciÃ³n de atributos a exponer (si existe la tabla)
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
                    # Primero verificar si hay ALGUNA configuraciÃ³n para este cliente
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

                    # Si no hay ninguna configuraciÃ³n, tratar como "sin config" (None)
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
                        # Crear conjunto (vacÃ­o si todas estÃ¡n ocultas, con elementos si hay visibles)
                        exposed_keys_cache = {r[0] for r in rows}
            except Exception as e:
                # Si no existe la tabla o falla, seguimos sin filtrar (compatible hacia atrÃ¡s)
                print(f"âš ï¸ Error consultando product_attribute_config: {e}")
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

            # Retornar SIEMPRE la URL de Cloudinary (patrÃ³n unificado)
            image_url = primary_image.display_url if primary_image else None
        except Exception as e:
            print(f"âŒ Error obteniendo imagen primaria: {e}")
            # CRITICAL: Hacer rollback para que queries posteriores funcionen
            db.session.rollback()
            # Si falla, usar la imagen que hizo match
            image_url = img.display_url if img else None

        # Preparar atributos dinÃ¡micos del producto (JSONB)
        product_attrs = {}
        product_url_value = None  # Siempre intentar extraer el link, aunque no estÃ© expuesto
        try:
            if hasattr(product, 'attributes') and product.attributes:
                # 1) Siempre intentar obtener url_producto del JSON bruto (ignorar filtros de exposiciÃ³n)
                try:
                    raw_url = product.attributes.get('url_producto')
                    if isinstance(raw_url, dict):
                        # Algunos stores guardan { value: 'https://...' }
                        product_url_value = raw_url.get('value') or raw_url.get('url') or None
                    else:
                        product_url_value = raw_url
                except Exception as ie:
                    print(f"âš ï¸ Error extrayendo url_producto para {product.id}: {ie}")
                    product_url_value = None

                # 2) Aplicar filtros de exposiciÃ³n solo para el bloque de attributes
                if exposed_keys_cache is not None:
                    # Filtrar solo los atributos configurados para exponerse
                    product_attrs = {
                        k: v for k, v in product.attributes.items() if k in exposed_keys_cache
                    }
                else:
                    # Sin configuraciÃ³n, exponer todos los atributos (compatibilidad existente)
                    product_attrs = dict(product.attributes)
        except Exception as e:
            print(f"âš ï¸ Error leyendo atributos de producto {product.id}: {e}")
            product_attrs = {}

        # ðŸš€ FASE 3: Incluir optimizer_scores si estÃ¡n disponibles
        optimizer_scores = best_match.get('optimizer_scores')

        result = {
            "product_id": product.id,
            "name": product.name,
            "description": product.description or "Sin descripciÃ³n",
            "image_url": image_url,
            "similarity": round(similarity, 4),
            "price": float(product.price) if product.price else None,
            "sku": product.sku,
            "stock": product.stock if hasattr(product, 'stock') and product.stock is not None else 0,
            "category": product.category.name if product.category else "Sin categorÃ­a",
            "category_boost": category_boost,
            "color_boost": color_boost,
            # Atributos dinÃ¡micos (filtrados si hay configuraciÃ³n)
            "attributes": product_attrs,
            # URL del producto si estÃ¡ configurada
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

        boost_indicator = "ðŸš€" if category_boost else ""
        color_indicator = "ðŸŽ¨" if color_boost else ""
        optimizer_indicator = "ðŸŽ¯" if optimizer_scores else ""
        print(f"ðŸ“¦ DEBUG: Producto final aÃ±adido: {product.name} (similitud: {similarity:.4f}) {boost_indicator}{color_indicator}{optimizer_indicator}")

    print(f"ðŸŽ¯ DEBUG: Total productos Ãºnicos procesados: {len(results)}")

    # Ordenar por similitud y limitar resultados
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:limit]


def _normalize_color_gender(color_str: str) -> str:
    """Normaliza gÃ©nero en nombres de colores para matching consistente."""
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
    Usa los colores reales de los productos del cliente (dinÃ¡mico)

    Args:
        image_data: Datos binarios de la imagen
        client_id: ID del cliente para obtener sus colores de productos

    Returns:
        tuple: (color_detectado, confidence_score)
    """
    try:
        # Obtener colores Ãºnicos desde JSONB attributes->>'color' (preferido)
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
            print("âš ï¸ No hay colores definidos en productos del cliente")
            return "unknown", 0.0

        print(f"ðŸŽ¨ Colores disponibles del cliente (JSONB): {unique_colors}")

        # Crear prompts dinÃ¡micos basados en los colores del cliente
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

            print(f"ðŸŽ¨ DETECCIÃ“N COLOR: {detected_color} (confianza: {best_score:.3f})")

            return detected_color, best_score

    except Exception as e:
        print(f"âŒ Error en detecciÃ³n de color: {e}")
        import traceback
        traceback.print_exc()
        return "unknown", 0.0


def detect_dominant_color_from_palette(image_data, colors_list):
    """
    Detecta el color dominante restringiendo la comparaciÃ³n a una paleta dada.

    Args:
        image_data: bytes de la imagen
        colors_list: lista de strings con colores disponibles para comparar

    Returns:
        tuple: (color_detectado, confidence_score)
    """
    try:
        unique_colors = [c.strip() for c in colors_list if c and str(c).strip()]

        if not unique_colors:
            print("âš ï¸ Paleta de colores vacÃ­a para la categorÃ­a")
            return "unknown", 0.0

        print(f"ðŸŽ¨ Paleta de colores (categorÃ­a): {unique_colors}")

        # Crear prompts dinÃ¡micos basados en los colores de la categorÃ­a
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

            print(f"ðŸŽ¨ DETECCIÃ“N COLOR (categorÃ­a): {detected_color} (confianza: {best_score:.3f})")

            return detected_color, best_score

    except Exception as e:
        print(f"âŒ Error en detecciÃ³n de color (paleta): {e}")
        import traceback
        traceback.print_exc()
        return "unknown", 0.0


def detect_general_object(image_data, client_id=None):
    """
    Detecta QUÃ‰ es el objeto en la imagen usando CLIP
    Si se proporciona client_id, usa las categorÃ­as del cliente
    Si no, usa categorÃ­as generales ampliadas

    Args:
        image_data: Datos binarios de la imagen
        client_id: ID del cliente (opcional, para usar sus categorÃ­as)

    Returns:
        tuple: (objeto_detectado, confidence_score)
    """
    try:
        # Si hay client_id, usar las categorÃ­as del cliente
        if client_id:
            categories = Category.query.filter_by(
                client_id=client_id,
                is_active=True
            ).all()

            if categories:
                # Usar name_en de las categorÃ­as como tÃ©rminos de detecciÃ³n
                general_categories = []
                for cat in categories:
                    if cat.name_en:
                        general_categories.append(f"a photo of {cat.name_en.lower()}")
                    else:
                        general_categories.append(f"a photo of {cat.name.lower()}")

                print(f"ðŸ” Usando categorÃ­as del cliente para detecciÃ³n: {[c.split('of ')[1] for c in general_categories]}")
            else:
                print("âš ï¸ No hay categorÃ­as activas, usando detecciÃ³n genÃ©rica")
                general_categories = ["product", "item", "object"]
        else:
            # DetecciÃ³n genÃ©rica amplia para cualquier tipo de producto
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

            # Generar embeddings de texto para categorÃ­as
            text_inputs = processor(text=general_categories, return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = torch.cosine_similarity(image_embedding, text_embeddings, dim=1)

            # Encontrar la mejor coincidencia
            best_idx = similarities.argmax().item()
            best_score = similarities[best_idx].item()
            detected_object = general_categories[best_idx]

            # Extraer solo el tÃ©rmino del objeto (sin "a photo of")
            if "a photo of" in detected_object:
                detected_object = detected_object.replace("a photo of ", "").strip()

            print(f"ðŸ” DETECCIÃ“N GENERAL: {detected_object} (confianza: {best_score:.3f})")

            return detected_object, best_score

    except Exception as e:
        print(f"âŒ Error en detecciÃ³n general: {e}")
        import traceback
        traceback.print_exc()
        return "unknown", 0.0


def detect_image_category_with_centroids(image_data, client_id, confidence_threshold=0.2):
    """
    Detecta la categorÃ­a de una imagen usando centroides de embeddings reales

    En lugar de prompts de texto, usa el promedio de embeddings de productos
    existentes en cada categorÃ­a como "representante" de esa categorÃ­a.

    Args:
        image_data: Datos binarios de la imagen
        client_id: ID del cliente para obtener sus categorÃ­as
        confidence_threshold: Umbral mÃ­nimo de confianza para detecciÃ³n

    Returns:
        tuple: (categoria_detectada, confidence_score) o (None, 0) si no detecta
    """
    try:
        railway_log(f" LOG: Iniciando detecciÃ³n centroides para cliente {client_id}")

        # 1. Obtener categorÃ­as activas del cliente
        categories = Category.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        if not categories:
            railway_log(f" LOG: No categorÃ­as para cliente {client_id}")
            return None, 0

        railway_log(f" LOG: {len(categories)} categorÃ­as encontradas")

        # 2. Generar embedding de la imagen nueva
        from PIL import Image as PILImage
        import io
        pil_image = PILImage.open(io.BytesIO(image_data))
        print(f"ðŸ–¼ï¸ DEBUG: Imagen preparada: {pil_image.size}")

        # 3. Obtener modelo CLIP
        model, processor = get_clip_model()
        print("ðŸ¤– DEBUG: Modelo CLIP obtenido")

        # 4. Generar embedding de imagen nueva
        with torch.no_grad():
            image_inputs = processor(
                images=pil_image,
                return_tensors="pt"
            )
            image_features = model.get_image_features(**image_inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            new_embedding = image_features.squeeze(0).numpy()

        print(f"ðŸ” DEBUG: Embedding generado: shape {new_embedding.shape}")

        # 5. Calcular similitudes contra centroides de cada categorÃ­a
        category_similarities = []

        for category in categories:
            # ðŸš€ USAR CENTROIDE DE BD DIRECTAMENTE
            centroid = category.get_centroid_embedding(auto_calculate=False)
            railway_log(f" LOG: {category.name} - centroide {'OK' if centroid is not None else 'NULL'}")

            if centroid is not None:
                # Calcular similitud coseno
                similarity = np.dot(new_embedding, centroid) / (np.linalg.norm(new_embedding) * np.linalg.norm(centroid))
                category_similarities.append({
                    'category': category,
                    'similarity': float(similarity)
                })
                railway_log(f" LOG: {category.name}: similitud {similarity:.4f}")
            else:
                railway_log(f" LOG: {category.name} SIN CENTROIDE en BD")

        if not category_similarities:
            railway_log(f" LOG: NO HAY SIMILITUDES - sin centroides vÃ¡lidos")
            return None, 0

        # 6. Encontrar la mejor coincidencia con margen de victoria y desempate
        # Ordenar por similitud descendente
        category_similarities.sort(key=lambda x: x['similarity'], reverse=True)
        best_match = category_similarities[0]
        best_category = best_match['category']
        best_score = best_match['similarity']
        second_score = category_similarities[1]['similarity'] if len(category_similarities) > 1 else -1.0

        railway_log(f" LOG: MEJOR: {best_category.name} = {best_score:.4f} | SEGUNDO = {second_score:.4f}")

        # Margen de victoria mÃ­nimo para aceptar directamente la categorÃ­a ganadora
        MARGIN_DELTA = 0.03  # 3 puntos de similitud coseno

        # Si el margen es muy chico, usamos un desempate con la detecciÃ³n general
        if second_score >= 0 and (best_score - second_score) < MARGIN_DELTA:
            railway_log(f" LOG: MARGEN PEQUEÃ‘O ({best_score - second_score:.4f} < {MARGIN_DELTA}), aplicando desempate por objeto general")
            try:
                detected_object, object_confidence = detect_general_object(image_data, client_id)
                railway_log(f" LOG: OBJETO GENERAL = {detected_object} (conf {object_confidence:.3f})")

                if object_confidence >= 0.20:  # usar con umbral bajo, solo como desempate
                    # Comparar el objeto detectado con los nombres de las categorÃ­as (name y name_en)
                    top2 = category_similarities[:2]

                    def cat_matches_object(cat, obj):
                        """Verifica si el objeto detectado estÃ¡ relacionado con la categorÃ­a"""
                        cat_name = (cat.name or '').lower()
                        cat_name_en = (cat.name_en or '').lower()
                        obj_lower = obj.lower()

                        # Match directo o por inclusiÃ³n
                        return obj_lower in cat_name or obj_lower in cat_name_en or \
                               cat_name in obj_lower or cat_name_en in obj_lower

                    best_matches = cat_matches_object(best_category, detected_object)
                    second_cat = top2[1]['category'] if len(top2) > 1 else None
                    second_matches = cat_matches_object(second_cat, detected_object) if second_cat else False

                    if not best_matches and second_matches:
                        # Elegir la segunda si estÃ¡ en el grupo preferido
                        railway_log(f" LOG: DESEMPATE â†’ Preferimos '{second_cat.name}' por concordar con objeto '{detected_object}'")
                        best_category = second_cat
                        best_score = top2[1]['similarity']
                    else:
                        railway_log(f" LOG: Desempate mantiene categorÃ­a original (best={best_matches}, second={second_matches})")
                else:
                    railway_log(" LOG: Desempate no aplicado (baja confianza del objeto)")
            except Exception as e:
                railway_log(f" LOG: Error en desempate por objeto general: {e}")

        # 7. Verificar umbral de confianza
        if best_score >= confidence_threshold:
            railway_log(f" LOG: DETECTADO - {best_category.name} (conf: {best_score:.4f})")
            return best_category, best_score
        else:
            railway_log(f" LOG: RECHAZADO - {best_score:.4f} < {confidence_threshold}")
            return None, best_score

    except Exception as e:
        print(f"âŒ ERROR en detecciÃ³n por centroides: {e}")
        import traceback
        traceback.print_exc()
        return None, 0


def detect_image_category(image_data, client_id, confidence_threshold=0.2):
    """
    FunciÃ³n de detecciÃ³n por prompts (obsoleta, usa centroides como fallback)
    """
    try:
        print(f"ðŸŽ¯ DEBUG: Usando mÃ©todo de centroides en lugar de prompts")
        return detect_image_category_with_centroids(image_data, client_id, confidence_threshold)

    except Exception as e:
        print(f"âŒ ERROR en detecciÃ³n de categorÃ­a: {e}")
        import traceback
        traceback.print_exc()
        return None, 0


def detect_image_category(image_data, client_id, confidence_threshold=0.2):
    """
    Detecta la categorÃ­a de una imagen usando CLIP y los prompts de categorÃ­as del cliente

    Args:
        image_data: Datos binarios de la imagen
        client_id: ID del cliente para obtener sus categorÃ­as
        confidence_threshold: Umbral mÃ­nimo de confianza para detecciÃ³n

    Returns:
        tuple: (categoria_detectada, confidence_score) o (None, 0) si no detecta
    """
    try:
        print(f"ðŸŽ¯ DEBUG: Iniciando detecciÃ³n de categorÃ­a para cliente {client_id}")

        # 1. Obtener categorÃ­as activas del cliente
        categories = Category.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        if not categories:
            print(f"âŒ DEBUG: No se encontraron categorÃ­as para cliente {client_id}")
            return None, 0

        print(f"ðŸ“‹ DEBUG: Encontradas {len(categories)} categorÃ­as activas")

        # 2. Preparar imagen para CLIP
        from PIL import Image as PILImage
        import io
        pil_image = PILImage.open(io.BytesIO(image_data))
        print(f"ðŸ–¼ï¸ DEBUG: Imagen preparada: {pil_image.size}")

        # 3. Obtener modelo CLIP
        model, processor = get_clip_model()
        print("ðŸ¤– DEBUG: Modelo CLIP obtenido")

        # 4. Preparar prompts de categorías (usar prompts en inglés cuando sea posible)
        category_prompts = []
        category_objects = []

        for category in categories:
            prompt = _clip_prompt_for_category(category)

            category_prompts.append(prompt)
            category_objects.append(category)
            railway_log(f"DEBUG: Prompt para {getattr(category,'name','?')}: {prompt}")

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

            print(f"ðŸ” DEBUG: Similitudes calculadas: {similarities.tolist()}")

        # 6. Encontrar la mejor coincidencia
        best_idx = similarities.argmax().item()
        best_score = similarities[best_idx].item()
        best_category = category_objects[best_idx]

        print(f"ðŸŽ¯ DEBUG: Mejor coincidencia: {best_category.name} ({best_score:.4f})")

        # 7. Verificar umbral de confianza
        if best_score >= confidence_threshold:
            print(f"âœ… DEBUG: CategorÃ­a detectada con confianza suficiente")
            return best_category, best_score
        else:
            print(f"âŒ DEBUG: Confianza insuficiente ({best_score:.4f} < {confidence_threshold})")
            return None, best_score

    except Exception as e:
        print(f"âŒ ERROR en detecciÃ³n de categorÃ­a: {e}")
        import traceback
        traceback.print_exc()
        return None, 0


def _filter_diverse_categories(categories_with_scores, diversity_threshold=0.75):
    """
    Filtra categorÃ­as similares usando embeddings CLIP de sus nombres.
    Agrupa categorÃ­as semÃ¡nticamente similares y selecciona la mejor de cada grupo.

    Args:
        categories_with_scores: Lista de dicts con 'category' (objeto Category) y 'confidence'
        diversity_threshold: Umbral de similitud coseno para considerar categorÃ­as como similares (default 0.75)

    Returns:
        Lista filtrada de categorÃ­as diversas (mismo formato que input)
    """
    if len(categories_with_scores) <= 1:
        return categories_with_scores

    try:
        # Obtener modelo CLIP
        clip_model, clip_processor = get_clip_model()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Generar embeddings de nombres de categorías (usando nombre tal cual para no hardcodear)
        category_names = [cat['category'].name for cat in categories_with_scores]
        texts = [f"a photo of {name}" for name in category_names]

        with torch.no_grad():
            text_inputs = clip_processor(text=texts, return_tensors="pt", padding=True, truncation=True).to(device)
            text_embeddings = clip_model.get_text_features(**text_inputs)
            text_embeddings = text_embeddings / text_embeddings.norm(dim=-1, keepdim=True)

        # Matriz de similitud coseno
        similarity_matrix = torch.mm(text_embeddings, text_embeddings.t()).cpu().numpy()

        # Log de similitudes para debugging
        print(f"\nDIVERSITY FILTER: Matriz de similitud entre {len(category_names)} categorías:")
        for i in range(len(category_names)):
            for j in range(i+1, len(category_names)):
                sim = similarity_matrix[i][j]
                if sim > diversity_threshold:
                    print(f"   - {category_names[i]} <-> {category_names[j]}: {sim:.3f} (SIMILAR)")

        # Preparar guardas NUMÉRICAS (agnósticas al dominio) para no colapsar categorías fuertes
        # Evita hardcodear palabras. Si dos categorías están FUERTES o muy cercanas en confianza,
        # no se agrupan aunque el texto sea muy similar (multi-label real).
        confidences = [cat['confidence'] for cat in categories_with_scores]
        strong_conf_threshold = 0.75  # categorías muy seguras (independiente del rubro)
        epsilon_conf = 0.06           # si difieren menos del 6% y son razonables, mantener ambas

        def is_strong_pair(i: int, j: int) -> bool:
            ci = confidences[i]
            cj = confidences[j]
            # Ambos muy fuertes
            if ci >= strong_conf_threshold and cj >= strong_conf_threshold:
                return True
            # Muy cercanas entre sí y al menos razonables (>=0.70)
            if abs(ci - cj) <= epsilon_conf and max(ci, cj) >= 0.70:
                return True
            return False

        # Clustering greedy: agrupar categorías similares SOLO si no violan las guardas numéricas
        groups = []
        used = set()

        for i in range(len(categories_with_scores)):
            if i in used:
                continue

            group = [i]
            used.add(i)

            for j in range(i+1, len(categories_with_scores)):
                if j in used:
                    continue

                # NO agrupar si es un par fuerte o muy cercano en confianza (multi-label válido)
                if is_strong_pair(i, j):
                    continue

                if similarity_matrix[i][j] > diversity_threshold:
                    group.append(j)
                    used.add(j)

            groups.append(group)

        # Seleccionar mejor de cada grupo (por confianza)
        filtered = []
        for group in groups:
            best_idx = max(group, key=lambda idx: categories_with_scores[idx]['confidence'])
            filtered.append(categories_with_scores[best_idx])

            if len(group) > 1:
                group_names = [category_names[idx] for idx in group]
                print(f"DIVERSITY: Agrupadas {group_names} -> seleccionada '{category_names[best_idx]}'")

        print(f"DIVERSITY FILTER: {len(categories_with_scores)} -> {len(filtered)} categorías")
        return filtered

    except Exception as e:
        print(f"âš ï¸ DIVERSITY FILTER: Error, retornando sin filtrar: {e}")
        return categories_with_scores


def detect_multiple_categories(image_data, client_id, min_prob_threshold=0.03, min_conf_threshold=0.18, prelimit_topk=8):
    """
    Detecta MÃšLTIPLES categorÃ­as en una imagen usando CLIP zero-shot classification.
    Sistema adaptativo: modo estricto si hay categorÃ­a dominante, laxo si no.

    Args:
        image_data: Bytes de la imagen
        client_id: ID del cliente
        min_prob_threshold: Umbral mÃ­nimo de probabilidad softmax (default 0.03 = 3%)
        min_conf_threshold: Umbral mÃ­nimo de confianza coseno (default 0.18)
        prelimit_topk: Top K candidatos antes de aplicar filtro de diversidad (default 8)

    Returns:
        Lista de dicts: [{'category': Category, 'confidence': float, 'probability': float}, ...]
        Ordenada por confianza descendente, filtrada por diversidad semÃ¡ntica
    """
    try:
        # Limpiar cualquier transacciÃ³n fallida previa
        try:
            db.session.rollback()
        except:
            pass

        # Obtener categorÃ­as activas del cliente
        categories = Category.query.filter_by(client_id=client_id, is_active=True).all()
        if not categories:
            print(f"âŒ MULTI-CATEGORY: No hay categorÃ­as activas para cliente {client_id}")
            return []

        # Obtener modelo CLIP y embedding de la imagen (una sola vez)
        clip_model, clip_processor = get_clip_model()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        from PIL import Image as PILImage
        import io
        image = PILImage.open(io.BytesIO(image_data))
        image_inputs = clip_processor(images=image, return_tensors="pt").to(device)

        with torch.no_grad():
            image_features = clip_model.get_image_features(**image_inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            image_vec = image_features.squeeze(0).cpu().numpy()

        # Similaridad contra centroides de cada categoría (mismo método que SINGLE)
        confidences = []
        for cat in categories:
            centroid = cat.get_centroid_embedding(auto_calculate=False)
            if centroid is None:
                confidences.append(-1.0)
                continue
            sim = float(np.dot(image_vec, centroid) / (np.linalg.norm(image_vec) * np.linalg.norm(centroid)))
            confidences.append(sim)

        # Probabilidades normalizadas vía softmax de similitudes escaladas
        sims_tensor = torch.tensor(confidences, dtype=torch.float32)
        logits = sims_tensor * 100
        probabilities = torch.nn.functional.softmax(logits, dim=0).cpu().numpy()

        # Crear lista de candidatos con ambas mÃ©tricas
        candidates = []
        for i, category in enumerate(categories):
            candidates.append({
                'category': category,
                'confidence': float(confidences[i]),
                'probability': float(probabilities[i])
            })

        # DEBUG: Mostrar TODOS los candidatos antes de ordenar
        print(f"\n🔍 DEBUG: Candidatos ANTES de ordenar (total: {len(candidates)}):")
        for c in sorted(candidates, key=lambda x: x['confidence'], reverse=True)[:5]:
            print(f"   - {c['category'].name}: prob={c['probability']:.4f}, conf={c['confidence']:.4f}")

        # Ordenar por confidence (similitud real) en lugar de probability (softmax distorsionado)
        candidates.sort(key=lambda x: x['confidence'], reverse=True)

        # FIX: Obtener max_conf de todos los candidatos (máxima confidence global)
        max_conf = max(c['confidence'] for c in candidates)
        dominant_threshold = 0.80  # Threshold más alto para considerar "dominante"
        is_dominant = max_conf > dominant_threshold

        if is_dominant:
            # Modo ESTRICTO: evitar falsos positivos en imágenes de un solo objeto
            print(f"🎯 MULTI-CATEGORY: Modo ESTRICTO (max confidence={max_conf:.3f})")
            strict_conf = 0.75  # 75% de similitud mínima (muy alta)

            selected = [c for c in candidates if c['confidence'] >= strict_conf]
        else:
            lax_conf = 0.70
            # Modo LAXO: permitir mÃºltiples categorÃ­as
            print(f"ðŸ” MULTI-CATEGORY: Modo LAXO (max conf={max_conf:.3f}, sin categorÃ­a dominante)")

            selected = [c for c in candidates if c['confidence'] >= lax_conf]

        # Limitar a top-K ANTES de filtro de diversidad
        selected = selected[:prelimit_topk]

        print(f"PRELIMIT: {len(selected)} categorías seleccionadas (de {len(categories)} totales)")
        for c in selected:
            print(f"   - {c['category'].name}: prob={c['probability']:.4f}, conf={c['confidence']:.4f}")

        # Filtro de diversidad: más conservador y con salvaguarda
        # - Si hay 2 o menos categorías, no colapsar: permiten casos claros de 2 prendas (p. ej., top + short)
        # - Umbral muy alto (0.95) para evitar colapsar categorías con diferencias sutiles pero importantes (p. ej., "tiro alto" vs "tiro bajo")
        if len(selected) <= 2:
            railway_log(" DEBUG: Saltando filtro de diversidad (<=2 categorías prelimit)")
        else:
            railway_log(f" DEBUG: Aplicando filtro de diversidad (threshold=0.95)...")
            # Filtrar por diversidad semántica (evita duplicados muy cercanos)
            selected = _filter_diverse_categories(selected, diversity_threshold=0.95)

        railway_log(f" DEBUG: Despues de diversidad: {len(selected)} categorias finales")

        # Log final
        print(f"âœ… MULTI-CATEGORY: {len(selected)} categorÃ­as finales detectadas")
        for c in selected:
            print(f"   â†’ {c['category'].name}: {c['confidence']:.3f}")

        return selected

    except Exception as e:
        print(f"âŒ ERROR en detect_multiple_categories: {e}")
        import traceback
        traceback.print_exc()
        # Rollback en caso de error
        try:
            db.session.rollback()
        except:
            pass
        return []


@bp.route("/search", methods=["POST", "OPTIONS"])
def visual_search():
    """
    Endpoint de bÃºsqueda visual para el widget con detecciÃ³n automÃ¡tica de categorÃ­a

    Headers:
        X-API-Key: API Key del cliente

    Form Data:
        image: Archivo de imagen
        limit: NÃºmero de resultados (default: 3, max: 10)
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
        # Limpiar cualquier transacciÃ³n fallida previa
        try:
            db.session.rollback()
        except:
            pass

        # Soportar tambiÃ©n bÃºsqueda textual vÃ­a JSON en el mismo endpoint
        # Si el Content-Type es application/json y no hay archivo de imagen, delegar a text_search()
        if request.method == 'POST' and (request.is_json or (request.content_type and 'application/json' in request.content_type)) and not request.files:
            # Delegar al handler de bÃºsqueda textual existente
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
        client, image_file, error_response, status_code = _validate_visual_search_request()
        if error_response:
            return error_response, status_code

        # Procesar datos de imagen
        image_data, limit, _, error_response, status_code = _process_image_data(image_file)
        # Obtener configuraciÃ³n real del panel
        max_results = system_config.get('search', 'max_results')
        # Si el parÃ¡metro limit no estÃ¡ en el request, usar el del panel
        if not limit:
            limit = max_results
        if error_response:
            return error_response, status_code

        # Sensibilidad personalizada por cliente
        category_confidence_threshold = (getattr(client, 'category_confidence_threshold', 70) or 70) / 100.0
        product_similarity_threshold = (getattr(client, 'product_similarity_threshold', 30) or 30) / 100.0

        # ðŸš€ FASE 3: Cargar configuraciÃ³n de SearchOptimizer (si existe)
        use_optimizer = request.form.get('use_optimizer', 'true').lower() == 'true'  # Feature flag
        store_config = None
        search_optimizer = None

        if use_optimizer:
            try:
                store_config = StoreSearchConfig.query.get(client.id)
                if store_config:
                    search_optimizer = SearchOptimizer(store_config)
                    print(f"ðŸŽ¯ OPTIMIZER: Activado para {client.name} (v={store_config.visual_weight}, m={store_config.metadata_weight}, b={store_config.business_weight})")
                else:
                    print(f"âš ï¸ OPTIMIZER: No config found for client {client.id}, usando bÃºsqueda tradicional")
            except Exception as e:
                print(f"âŒ OPTIMIZER: Error cargando config: {e}")
                # Si falla, continuar sin optimizer
                search_optimizer = None

        # ===== PASO 1: DETECCIÃ“N DE CATEGORÃA ESPECÃFICA =====
        # Soporta modo SINGLE (1 categorÃ­a) o MULTI (varias categorÃ­as)
        multi_category_enabled = request.form.get('multi_category', 'false').lower() == 'true'

        if multi_category_enabled:
            print(f"ðŸ” MULTI-CATEGORY MODE: ENABLED")

            # 🚀 USAR SISTEMA UNIFICADO V2: detect_categories_centroid_based
            from app.blueprints.embeddings import detect_categories_centroid_based

            detected_results = detect_categories_centroid_based(
                image_data,
                client.id,
                threshold=category_confidence_threshold,
                top_k=8,
                apply_pair_exclusion=False
            )

            # Convertir formato de Sistema Unificado V2 al formato legacy esperado
            detected_categories = []
            for result in detected_results:
                from app.models.category import Category
                category = Category.query.get(result['category_id'])
                if category:
                    detected_categories.append({
                        'category': category,
                        'confidence': result['score'],
                        'probability': 0.0,
                        'best_crop': result.get('best_crop', 'unknown'),
                        'crop_scores': result.get('crop_scores', {})
                    })

            print(f"✅ Sistema Unificado V2: {len(detected_categories)} categorías detectadas")

            railway_log(f" DEBUG: detected_categories = {len(detected_categories)} categorÃ­as")
            for idx, cat_info in enumerate(detected_categories):
                current_app.logger.info(f"   {idx+1}. {cat_info['category'].name} (conf={cat_info['confidence']:.3f}, prob={cat_info.get('probability', 0):.3f})")

            if not detected_categories:
                print(f"âŒ MULTI-CATEGORY: No se detectÃ³ ninguna categorÃ­a")
                return jsonify({
                    "success": False,
                    "error": "category_not_detected",
                    "message": f"Esta imagen no corresponde a productos que comercializa {client.name}",
                    "details": "No pudimos identificar categorÃ­as comercializadas en la imagen.",
                    "available_categories": [cat.name for cat in Category.query.filter_by(client_id=client.id, is_active=True).all()],
                    "processing_time": round(time.time() - start_time, 3)
                }), 400

            print(f"âœ… MULTI-CATEGORY: {len(detected_categories)} categorÃ­as detectadas")

            # Para backwards compatibility, usar la primera como "detected_category"
            detected_category = detected_categories[0]['category']
            category_confidence = detected_categories[0]['confidence']

            # GENERAR EMBEDDING UNA SOLA VEZ (reutilizar para todas las categorÃ­as)
            query_embedding, error_response, status_code = _generate_query_embedding(
                image_data,
                detected_category=detected_category
            )
            if error_response:
                return error_response, status_code

            # BUSCAR PRODUCTOS EN CADA CATEGORÃA DETECTADA
            results_by_category = []

            for cat_info in detected_categories:
                category = cat_info['category']
                conf = cat_info['confidence']

                railway_log(f" DEBUG: Buscando en {category.name} (conf={conf:.3f})")

                # Buscar productos en esta categorÃ­a
                product_best_match = _find_similar_products_in_category(
                    client,
                    query_embedding,
                    product_similarity_threshold,
                    category.id
                )

                railway_log(f" DEBUG: Encontrados {len(product_best_match)} productos en {category.name}")

                # Aplicar optimizer si estÃ¡ disponible
                if search_optimizer and len(product_best_match) > 0:
                    # Preparar formato para optimizer
                    raw_results = [
                        {
                            'product': match_data['product'],
                            'similarity': match_data['similarity']
                        }
                        for product_id, match_data in product_best_match.items()
                    ]

                    # Aplicar ranking
                    ranked_results = search_optimizer.rank_results(raw_results, {})

                    # Actualizar scores
                    for ranked in ranked_results:
                        for dict_product_id, match_data in product_best_match.items():
                            if str(dict_product_id) == ranked.product_id:
                                product_best_match[dict_product_id]['optimizer_scores'] = {
                                    'visual_score': ranked.visual_score,
                                    'metadata_score': ranked.metadata_score,
                                    'business_score': ranked.business_score,
                                    'final_score': ranked.final_score
                                }
                                product_best_match[dict_product_id]['similarity'] = ranked.final_score
                                break

                # Convertir dict a lista ordenada por similitud
                products_list = sorted(
                    product_best_match.values(),
                    key=lambda x: x['similarity'],
                    reverse=True
                )

                # Limitar resultados por categorÃ­a
                products_list = products_list[:limit]

                # Formatear productos con logs detallados
                formatted_products = []
                for idx, match_data in enumerate(products_list):
                    try:
                        product = match_data['product']
                        score = match_data['similarity']
                        optimizer_scores = match_data.get('optimizer_scores', {
                            "visual_score": float(score),
                            "metadata_score": 0.0,
                            "business_score": 0.0,
                            "final_score": float(score)
                        })

                        # Obtener imagen primaria del producto
                        primary_image = None
                        try:
                            primary_image = Image.query.filter_by(
                                product_id=product.id,
                                is_primary=True
                            ).first()
                            if not primary_image and product.images:
                                primary_image = product.images[0]
                        except Exception as img_err:
                            print(f"âš ï¸ Error obteniendo imagen primaria: {img_err}")
                            db.session.rollback()
                            primary_image = product.images[0] if product.images else None

                        # Usar base64 guardado en BD
                        image_base64 = primary_image.base64_data if primary_image and primary_image.base64_data else None

                        prod_dict = {
                            "id": str(product.id),
                            "name": product.name,
                            "sku": product.sku,
                            "price": float(product.price) if product.price else None,
                            "stock": product.stock,
                            "category": category.name,
                            "image_url": image_base64,  # âœ… BASE64 desde BD
                            "similarity": float(score),
                            "attributes": product.attributes or {},
                            "product_url": product.attributes.get('url_producto') if product.attributes else None,
                            "optimizer_scores": optimizer_scores
                        }
                        print(f"[DEBUG] Producto {idx} serializado OK: id={prod_dict['id']}, name={prod_dict['name']}")
                        formatted_products.append(prod_dict)
                    except Exception as prod_err:
                        print(f"[ERROR] Fallo al serializar producto {idx}: {prod_err}")
                        import traceback
                        traceback.print_exc()
                        prod_dict = {"error": str(prod_err)}
                        formatted_products.append(prod_dict)

                results_by_category.append({
                    "category_name": category.name,
                    "category_id": str(category.id),
                    "confidence": float(conf),
                    "product_count": len(formatted_products),
                    "products": formatted_products
                })

            # Respuesta en modo multi-categorÃ­a
            return jsonify({
                "success": True,
                "mode": "multi_category",
                "results_by_category": results_by_category,
                "total_categories": len(results_by_category),
                "processing_time": round(time.time() - start_time, 3)
            })        # MODO SINGLE (original)
        # 🔧 MODIFICADO: Usar Sistema Unificado V2 con DETECCIÓN MULTI-CATEGORÍA
        # Igual que multicrop: detecta N categorías y busca productos en TODAS ellas
        railway_log(f" LOG: INICIANDO DETECCIÓN MULTI-CATEGORÍA (Sistema Unificado V2)")

        # 🚀 USAR SISTEMA UNIFICADO V2 CON TOP-K DINÁMICO (como multicrop)
        from app.blueprints.embeddings import detect_categories_centroid_based

        detected_results = detect_categories_centroid_based(
            image_data,
            client.id,
            threshold=category_confidence_threshold,
            top_k=8,  # Detectar hasta 8 categorías (como multicrop)
            apply_pair_exclusion=False
        )

        # Log de categorías detectadas
        if detected_results:
            railway_log(f" LOG: {len(detected_results)} categorías detectadas:")
            for idx, res in enumerate(detected_results[:5], 1):
                from app.models.category import Category
                cat = Category.query.get(res['category_id'])
                railway_log(f"    {idx}. {cat.name if cat else 'Unknown'}: score={res['score']:.3f}")
        else:
            railway_log(" LOG: Ninguna categoría detectada")

        if not detected_results:
            detected_category = None
            category_confidence = 0.0
        else:
            from app.models.category import Category
            detected_category = Category.query.get(detected_results[0]['category_id'])
            category_confidence = detected_results[0]['score']

        railway_log(f" LOG: Categoría principal = {detected_category.name if detected_category else 'NULL'} (conf: {category_confidence:.3f})")

        if detected_category is None:
            # No se pudo detectar una categorÃ­a vÃ¡lida
            railway_log(f" LOG: CATEGORÃA NO DETECTADA - devolviendo error")
            return jsonify({
                "success": False,
                "error": "category_not_detected",
                "message": f"Esta imagen no corresponde a productos que comercializa {client.name}",
                "details": f"La imagen no pudo identificarse dentro de nuestras categorÃ­as disponibles (confianza mÃ¡xima: {category_confidence:.1%}). Por favor, intenta con una imagen de un producto de nuestro catÃ¡logo.",
                "available_categories": [cat.name for cat in Category.query.filter_by(client_id=client.id, is_active=True).all()],
                "processing_time": round(time.time() - start_time, 3)
            }), 400

        railway_log(f" LOG: CATEGORÃA OK: {detected_category.name} - procediendo a bÃºsqueda")

        # ===== PASO 2: DETECCIÃ“N DE COLOR RESTRINGIDO A LA CATEGORÃA =====
        railway_log(f" LOG: IDENTIFICANDO COLOR DOMINANTE (por categorÃ­a)...")

        # Construir paleta de colores solo con los productos de la categorÃ­a
        # Preferir colores desde JSONB attributes->>'color' para la categorÃ­a
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
            railway_log(f" LOG: COLOR DETECTADO (cat) = {detected_color} (confianza: {color_confidence:.3f})")
        else:
            detected_color, color_confidence = ("unknown", 0.0)
            railway_log(" LOG: CategorÃ­a sin colores definidos; se omite boost/metadata por color")

        # ===== GENERAR EMBEDDING DE LA IMAGEN (con enriquecimiento por tags) =====
        query_embedding, error_response, status_code = _generate_query_embedding(
            image_data,
            detected_category=detected_category  # Pasar categorÃ­a para contexto
        )
        if error_response:
            railway_log(f" LOG: Error generando embedding")
            return error_response, status_code


        # ===== BUSCAR EN TODAS LAS CATEGORÍAS DETECTADAS (como multicrop) =====
        railway_log(f" LOG: Buscando productos en {len(detected_results)} categorías detectadas")

        # Acumular productos de todas las categorías detectadas
        product_best_match_global = {}

        for cat_result in detected_results:
            from app.models.category import Category
            cat = Category.query.get(cat_result['category_id'])
            if not cat:
                continue

            railway_log(f" LOG: → Buscando en {cat.name} (score={cat_result['score']:.3f})")

            # Buscar productos en esta categoría
            product_best_match_cat = _find_similar_products_in_category(
                client,
                query_embedding,
                product_similarity_threshold,
                cat.id
            )

            # Agregar al global (sin duplicados, conservando el mejor score)
            for prod_id, match_data in product_best_match_cat.items():
                if prod_id not in product_best_match_global:
                    product_best_match_global[prod_id] = match_data
                elif match_data['similarity'] > product_best_match_global[prod_id]['similarity']:
                    product_best_match_global[prod_id] = match_data

        product_best_match = product_best_match_global
        print(f"🎯 DEBUG: Total productos encontrados en TODAS las categorías: {len(product_best_match)}")

        # ===== NO APLICAR BOOST NI METADATA POR COLOR EN BÃšSQUEDA VISUAL =====
        # La detecciÃ³n de color solo se usa para logging/debug
        # El ranking visual debe ser 100% basado en similitud CLIP pura
        # Mantener paridad con producciÃ³n (Railway)

        # ðŸš€ FASE 3: APLICAR SEARCH OPTIMIZER (si estÃ¡ activado)
        if search_optimizer and len(product_best_match) > 0:
            print(f"ðŸŽ¯ OPTIMIZER: Aplicando ranking avanzado a {len(product_best_match)} productos")

            # Preparar atributos detectados para metadata scoring
            detected_attributes = {}
            # NO usar color detectado en bÃºsqueda visual para mantener paridad con producciÃ³n
            # El color solo se considera en bÃºsqueda textual

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

                print(f"âœ… OPTIMIZER: Ranking completado. Top 3 scores: " +
                      ", ".join([f"{r.final_score:.3f}" for r in ranked_results[:3]]))

                # Debug: verificar que optimizer_scores se guardÃ³
                sample_id = list(product_best_match.keys())[0] if product_best_match else None
                if sample_id:
                    has_optimizer = 'optimizer_scores' in product_best_match[sample_id]
                    print(f"ðŸ” DEBUG: Primer producto tiene optimizer_scores: {has_optimizer}")

            except Exception as e:
                print(f"âŒ OPTIMIZER: Error durante ranking: {e}")
                # Si falla, continuar con scores originales
                import traceback
                traceback.print_exc()

        # Construir resultados finales (sin filtro adicional de categorÃ­a)
        results = _build_search_results(product_best_match, limit)

        processing_time = time.time() - start_time

        # Respuesta con informaciÃ³n de categorÃ­a detectada y config real
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
    Endpoint de bÃºsqueda textual hÃ­brida (CLIP + Atributos + Tags)

    Headers:
        X-API-Key: API Key del cliente

    JSON Body:
        query: Texto de bÃºsqueda (ej: "camisa blanca", "delantal marrÃ³n")
        limit: NÃºmero de resultados (default: 10, max: 50)
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
            f"ðŸ‘‰ TEXT SEARCH HIT: path={request.path} from={request.remote_addr} has_key={'X-API-Key' in request.headers}",
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
                "message": "API Key invÃ¡lido"
            }), 401

        # Obtener parÃ¡metros del request
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
                "message": "La query no puede estar vacÃ­a"
            }), 400

        # Obtener configuraciÃ³n real del panel
        max_results = system_config.get('search', 'max_results')
        # Permitir tanto 'limit' como 'max_results' del request, pero respetar el lÃ­mite del sistema
        limit_value = data.get('limit', data.get('max_results', max_results))
        try:
            # Respetar el lÃ­mite configurado en el sistema
            limit = min(int(limit_value), max_results)
        except Exception:
            limit = max_results

        print(f"ðŸ“ TEXT SEARCH: Query='{query_text}' Client={client.name} Limit={limit}", flush=True)

        # --- LLM Normalization (con vocabulario dinÃ¡mico del cliente) ---
        llm_norm = normalize_query(query_text, client_id=client.id)
        print(f"🔍 DEBUG: normalize_query completado", flush=True)
        # TODO: Mover a nivel de logs DEBUG
        # print(f"ðŸ§  LLM Normalizer: {llm_norm}")
        print(f"ðŸ§  LLM Normalizer: tipo={llm_norm.get('tipo')}, color={llm_norm.get('color')}, contexto={llm_norm.get('contexto')}")

        # Extraer campos del normalizador para usar en boosts
        detected_color = llm_norm.get('color', '').lower() if llm_norm.get('color') else None
        detected_tipo = llm_norm.get('tipo', '').lower() if llm_norm.get('tipo') else None
        # Contexto puede ser lista o string
        contexto_raw = llm_norm.get('contexto')
        if isinstance(contexto_raw, list):
            detected_context = contexto_raw  # Ya es lista
        elif isinstance(contexto_raw, str):
            detected_context = [contexto_raw.lower()]
        else:
            detected_context = None

        # Expandir modificadores de color con colores del cliente
        expanded_query = expand_color_modifiers(query_text, client_id=str(client.id))
        if expanded_query != query_text:
            print(f"ðŸ”„ Query expandido: '{query_text}' -> '{expanded_query}'")

        # Generar embedding CLIP del texto de búsqueda (usar query expandido)
        import time as _t
        _t0 = _t.time()
        print("🔍 DEBUG: entrando a get_clip_model()", flush=True)
        model, processor = get_clip_model()
        print(f"🔍 DEBUG: get_clip_model listo en {(_t.time()-_t0):.2f}s", flush=True)
        device = "cuda" if torch.cuda.is_available() else "cpu"

        _t1 = _t.time()
        with torch.no_grad():
            text_inputs = processor(text=[expanded_query], return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            query_embedding = text_features.cpu().numpy()[0]
        print(f"🔍 DEBUG: embedding texto generado en {(_t.time()-_t1):.2f}s", flush=True)

        # Usar query expandido para matching de atributos tambiÃ©n
        query_lower = expanded_query.lower()

        # Intentar detectar categorÃ­a en el query mediante tokens normalizados
        detected_category = None
        categories = Category.query.filter_by(client_id=client.id, is_active=True).all()

        import re, unicodedata

        def _norm_token(t: str) -> str:
            t = ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn')
            t = re.sub(r"[^a-z0-9]+", "", t)
            # singularizaciÃ³n naive: quitar 's' final si queda algo
            if len(t) > 3 and t.endswith('s'):
                t = t[:-1]
            return t

        STOPWORDS = {
            'hombre','hombres','dama','damas','mujer','mujeres','unisex',
            'y','de','para','con','sin','del','la','el','los','las'
        }

        def tokenize(texto: str):
            toks = re.split(r"[\s,./;:()\-â€“]+", texto or "")
            return { _norm_token(t) for t in toks if _norm_token(t) and _norm_token(t) not in STOPWORDS }

        query_tokens = tokenize(expanded_query)
        print(f"ðŸ” Query tokens: {query_tokens}")

        # Construir tokens por categorÃ­a (nombre, name_en y alternative_terms si existe)
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

        # DetecciÃ³n mejorada: evaluar TODAS las categorÃ­as y elegir la mejor coincidencia
        # Buscar primero coincidencia exacta de frase completa (ej: "tiro bajo" completo)
        best_category = None
        best_score = 0

        # 1. Prioridad: Buscar coincidencia de frase completa en alternative_terms o nombre
        query_normalized = expanded_query.lower().strip()
        for category in categories:
            # Verificar en nombre (PRIORIDAD ALTA: nombre exacto de categorÃ­a)
            if query_normalized in category.name.lower() or category.name.lower() in query_normalized:
                detected_category = category
                print(f"ðŸ“ CategorÃ­a detectada por nombre exacto: {category.name}")
                break
            # Verificar en name_en tambiÃ©n con alta prioridad
            if category.name_en and (query_normalized in category.name_en.lower() or category.name_en.lower() in query_normalized):
                detected_category = category
                print(f"ðŸ“ CategorÃ­a detectada por name_en exacto: {category.name}")
                break

        # Segundo pase: alternative_terms si no hubo match en nombre
        if not detected_category:
            for category in categories:
                alt = getattr(category, 'alternative_terms', None)
                if alt:
                    alt_terms = [t.strip().lower() for t in str(alt).split(',')]
                    if query_normalized in alt_terms:
                        detected_category = category
                        print(f"ðŸ“ CategorÃ­a detectada por alternative_term exacto: {category.name}")
                        break

        # 2. Si no hay coincidencia exacta, usar scoring de tokens (mÃ¡xima superposiciÃ³n)
        if not detected_category:
            candidates = []  # Para debugging
            for category, name_toks, alt_toks in cat_tokens_list:
                # Calcular intersecciÃ³n con tokens del nombre (PESO 1.0)
                name_intersection = query_tokens & name_toks
                # Calcular intersecciÃ³n con tokens de alternative_terms (PESO 0.5)
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
                print(f"ðŸŽ¯ Candidatos de categorÃ­a: {[(c[0], f'{c[1]:.2f}', c[2], c[3]) for c in sorted(candidates, key=lambda x: x[1], reverse=True)[:5]]}")

            if best_category and best_score > 0:
                detected_category = best_category
                print(f"ðŸ“ CategorÃ­a detectada por tokens (score={best_score:.2f}): {detected_category.name}")


        # Si NO detectamos categorÃ­a: decidir si es fuera de catÃ¡logo o si permitimos bÃºsqueda global
        if not detected_category:
            all_cat_tokens = set()
            for _, name_toks, alt_toks in cat_tokens_list:
                all_cat_tokens |= name_toks
                all_cat_tokens |= alt_toks

            if query_tokens and query_tokens.isdisjoint(all_cat_tokens):
                # Antes devolvÃ­amos 400. Ahora permitimos BÃšSQUEDA GLOBAL para casos como nombres de modelo (ej: "monaco").
                print("â„¹ï¸ TEXT SEARCH: tokens sin cruce con categorÃ­as â†’ continuamos en bÃºsqueda GLOBAL por nombre/SKU/tags")
            else:
                # Si hay alguna coincidencia dÃ©bil (e.g., tokens genÃ©ricos), continuar sin filtrar por categorÃ­a
                print("â„¹ï¸ TEXT SEARCH: Sin categorÃ­a inequÃ­voca, continuando sin filtro por categorÃ­a")

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
                    print(f"ðŸ§ª FUSION: alpha={alpha} beta_tag={beta_tag} phrases={len(tag_phrases)} tags={len(inferred_tags)}")
        except Exception as _e:
            # Fallback silencioso: si algo falla seguimos con embedding original
            print(f"âš ï¸ FUSION skip: {_e}")
            import traceback
            traceback.print_exc()


        # Consultar productos con embeddings (de imágenes principales), atributos y tags
        _t2 = _t.time()
        print(f"🔍 DEBUG: iniciando query SQL de productos...", flush=True)
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

        # FILTRAR por categorÃ­a si fue detectada
        if detected_category:
            products_query = products_query.filter(Product.category_id == detected_category.id)
            print(f"ðŸ”Ž Filtrando productos por categorÃ­a: {detected_category.name}")
        else:
            print(f"ðŸ”Ž BÃºsqueda SIN filtro de categorÃ­a (global)")

        products = products_query.all()
        print(f"🔍 DEBUG: query SQL ejecutada en {(_t.time()-_t2):.2f}s → {len(products)} productos", flush=True)

        # Fallback 1: Si no hay productos en la categorÃ­a detectada, rehacer bÃºsqueda global
        if detected_category and len(products) == 0:
            print("âš ï¸ TEXT SEARCH: 0 productos en categorÃ­a detectada â†’ Fallback a bÃºsqueda global")
            detected_category = None
            # reconstruir query sin filtro de categorÃ­a
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
        print(f"🔍 DEBUG: query SQL ejecutada en {(_t.time()-_t2):.2f}s → {len(products)} productos", flush=True)

        print(f"ðŸ” TEXT SEARCH: Analizando {len(products)} productos...")

        # Calcular scores hÃ­bridos

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

            # Score CLIP (similitud visual/semÃ¡ntica)
            emb = np.array(embedding, dtype=np.float32)
            clip_similarity = float(np.dot(query_embedding, emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(emb)))

            # Boost por atributos (incluye match de categorÃ­a y color del LLM)
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
                    print(f"  ðŸ”Ž ATTR DEBUG: {prod.name} | attr.color={prod_color_dbg} | detected_color={detected_color} | attr_boost={attr_boost:.3f}")
            except Exception:
                pass

            # Boost por nombre de producto y SKU (nuevo) + tags
            name_boost = _calculate_name_match(query_lower, prod.name, getattr(prod, 'sku', None))
            tag_boost = _calculate_tag_match(query_lower, prod.tags)
            tag_name_boost = min(1.0, tag_boost + name_boost)

            # Score final hÃ­brido
            # AÃ±adimos similitud de color como componente de ranking/desempate
            color_sim = _best_color_similarity(detected_color, prod.attributes) if detected_color else 0.0
            # Clasificar productos por calidad de match de color (solo si la query tiene color)
            # 0 = fuerte (>=0.75), 1 = medio (>=0.45), 2 = bajo (<0.45)
            if detected_color:
                if color_sim >= 0.75:
                    color_group = 0
                elif color_sim >= 0.45:
                    color_group = 1
                else:
                    color_group = 2
                # Prioridad de color para ordenar (mÃ¡s alto es mejor)
                color_priority = 2 - color_group  # fuerte=2, medio=1, bajo=0
            else:
                color_group = 2
                color_priority = 0

            # Ponderaciones: CLIP 50%, Atributos 35%, Color 5%, Tags+Nombre 10%
            # (Total 1.0). Color actÃºa como factor de desempate continuo.
            final_score = (
                clip_similarity * 0.5 +
                attr_boost * 0.35 +
                color_sim * 0.05 +
                tag_name_boost * 0.1
            )

            print(f"Producto: {prod.name} | CLIP: {clip_similarity:.3f} | Attr: {attr_boost:.3f} | ColorSim: {color_sim:.3f} | Tag: {tag_boost:.3f} | Name: {name_boost:.3f} | Score: {final_score:.3f}")

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
                'color_similarity': round(color_sim, 4),
                'color_group': color_group,
                'color_priority': color_priority,
                'name_boost': round(name_boost, 4),
                'final_score': round(final_score, 4)
            })

        # Si la query incluye color, priorizar match/color mÃ¡s cercano antes que score puro.
        if detected_color:
            results.sort(key=lambda x: (x.get('color_priority', 0), x.get('color_similarity', 0.0), x['final_score']), reverse=True)
        else:
            results.sort(key=lambda x: x['final_score'], reverse=True)


        # Limitar resultados
        results = results[:limit]

        elapsed_time = time.time() - start_time


        # 🎯 Análisis de calidad de match en lugar de fallback global
        # En vez de reintentar globalmente, analizamos QUÉ encontramos y damos contexto al usuario

        if len(results) == 0:
            # No hay resultados - analizar por qué y dar feedback útil
            match_quality = "none"

            # Verificar si la categoría existe pero está vacía
            if detected_category:
                category_product_count = len([p for p in products if p.category_id == detected_category.id])
                if category_product_count == 0:
                    partial_match_info = {
                        "message": f"No tenemos productos en la categoría '{detected_category.name}' actualmente.",
                        "suggestion": "Intenta buscar en otras categorías o consulta nuestro catálogo completo.",
                        "reason": "empty_category"
                    }
                else:
                    # Categoría tiene productos pero ninguno matcheó - problema de atributos/color
                    partial_match_info = {
                        "message": f"No encontramos '{query_text}' exactamente en nuestra categoría '{detected_category.name}'.",
                        "suggestion": "Prueba buscar sin especificar color o características tan específicas.",
                        "reason": "no_attribute_match"
                    }
            else:
                # No se detectó categoría o búsqueda global falló
                partial_match_info = {
                    "message": f"No encontramos productos que coincidan con '{query_text}'.",
                    "suggestion": "Intenta usar términos más generales o explora nuestro catálogo.",
                    "reason": "no_match_global"
                }

            detected_attributes = {
                "color": detected_color,
                "tipo": detected_tipo,
                "context": detected_context
            }
        else:
            # Hay resultados - analizar calidad del match
            COLOR_EXACT_THRESHOLD = 0.75
            COLOR_PARTIAL_THRESHOLD = 0.60
            ATTR_EXACT_THRESHOLD = 0.4

            best_result = results[0]
            best_color_sim = best_result.get('color_similarity', 0.0)
            best_attr_score = best_result.get('attribute_match_score', 0.0)

            # Determinar calidad del match
            print(f"🎨 QUALITY CHECK: best_color_sim={best_color_sim:.3f} (thresholds: exact≥0.75, partial≥0.60)")
            if detected_color:
                if best_color_sim >= COLOR_EXACT_THRESHOLD:
                    match_quality = "exact"
                elif best_color_sim >= COLOR_PARTIAL_THRESHOLD:
                    match_quality = "partial"
                else:
                    match_quality = "poor"
            else:
                # Sin color especificado, basar en atributos
                if best_attr_score >= ATTR_EXACT_THRESHOLD:
                    match_quality = "exact"
                else:
                    match_quality = "partial"

            detected_attributes = {
                "color": detected_color,
                "tipo": detected_tipo,
                "context": detected_context
            }

            # Si match es parcial o pobre, dar contexto adicional
            partial_match_info = None
            if match_quality in ["partial", "poor"] and detected_color:
                # Consultar colores reales disponibles en la categoría detectada
                available_colors = set()

                print(f"\n🔍 DEBUG: Iniciando consulta de colores disponibles")
                print(f"   - match_quality: {match_quality}")
                print(f"   - detected_color: {detected_color}")
                print(f"   - detected_category: {detected_category.name if detected_category else None}")
                print(f"   - client_id: {client.id}")

                try:
                    # Query directa a BD para obtener colores únicos de productos en esta categoría
                    color_query = db.session.query(
                        func.jsonb_extract_path_text(Product.attributes, 'color').label('color')
                    ).filter(
                        Product.client_id == client.id,
                        Product.category_id == detected_category.id if detected_category else True,
                        func.jsonb_extract_path_text(Product.attributes, 'color').isnot(None),
                        func.jsonb_extract_path_text(Product.attributes, 'color') != ''
                    ).distinct()

                    print(f"   - Ejecutando query SQL...")
                    color_results = color_query.all()
                    print(f"   - Resultados obtenidos: {len(color_results)} rows")

                    for row in color_results:
                        print(f"   - Row color: '{row.color}'")
                        if row.color and row.color.strip():
                            available_colors.add(row.color.strip().upper())

                    print(f"🎨 Colores disponibles en categoría: {available_colors}")

                except Exception as e:
                    print(f"⚠️ Error consultando colores: {e}")
                    import traceback
                    traceback.print_exc()

                    # Fallback: extraer de los resultados actuales
                    print(f"   - Usando fallback: extraer de resultados actuales")
                    for r in results[:10]:
                        prod_id = r['product_id']
                        product = next((p for p in products if str(p.id) == prod_id), None)
                        if product and product.attributes:
                            prod_color = product.attributes.get('color')
                            print(f"   - Producto {product.name}: color={prod_color}")
                            if prod_color:
                                available_colors.add(prod_color)

                if available_colors:
                    colors_list = sorted(list(available_colors))
                    category_text = detected_tipo or (detected_category.name.lower() if detected_category else 'productos')

                    # Detectar el color de los productos que estamos mostrando (el "más cercano")
                    shown_colors = set()
                    for r in results[:3]:  # Top 3 resultados
                        prod_id = r['product_id']
                        product = next((p for p in products if str(p.id) == prod_id), None)
                        if product and product.attributes:
                            prod_color = product.attributes.get('color')
                            if prod_color:
                                shown_colors.add(prod_color.upper())

                    closest_color_text = ""
                    other_colors = []

                    if shown_colors:
                        # Excluir colores mostrados de la lista de "también disponibles"
                        other_colors = [c for c in colors_list if c not in shown_colors]

                        if len(shown_colors) == 1:
                            closest_color_text = f" Nuestro sistema encontró que {list(shown_colors)[0]} es el color más similar disponible."
                        else:
                            closest_color_text = f" Nuestro sistema encontró estos colores como los más similares: {', '.join(sorted(shown_colors))}."
                    else:
                        other_colors = colors_list

                    if match_quality == "poor":
                        message = f"No tenemos {category_text} en '{detected_color.upper()}' que solicitaste."
                        message += closest_color_text
                        if other_colors:
                            message += f" También disponibles: {', '.join(other_colors)}."
                        partial_match_info = {
                            "message": message,
                            "requested_color": detected_color.upper(),
                            "reason": "color_not_available"
                        }
                    else:  # partial
                        message = f"Coincidencia aproximada para '{detected_color.upper()}' en {category_text}."
                        message += closest_color_text
                        if other_colors:
                            message += f" Otros colores disponibles: {', '.join(other_colors)}."
                        partial_match_info = {
                            "message": message,
                            "available_colors": colors_list,
                            "requested_color": detected_color,
                            "reason": "partial_color_match"
                        }

        print(f"âœ… TEXT SEARCH: {len(results)} resultados en {elapsed_time:.3f}s")
        print(f"ðŸŽ¯ MATCH QUALITY: {match_quality}")
        print(f"ðŸŽ¨ DETECTED COLOR: {detected_color}")
        print(f"ðŸ'¬ PARTIAL MATCH INFO: {partial_match_info}")

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
            "search_time_seconds": round(elapsed_time, 3),
            "match_quality": match_quality,
            "detected_attributes": detected_attributes
        }

        # Agregar información de match parcial si existe
        if partial_match_info:
            response['partial_match_info'] = partial_match_info

        # Agregar sugerencias si la query es ambigua
        if llm_norm.get('needs_refinement'):
            response['needs_refinement'] = True
            response['ambiguous_terms'] = llm_norm.get('ambiguous_terms', [])
            response['suggestions'] = llm_norm.get('suggestions', {})
            response['refinement_message'] = "Tu bÃºsqueda es muy general. Â¿PodrÃ­as ser mÃ¡s especÃ­fico?"

        # AÃ±adir CORS para consistencia cuando este handler es invocado desde /api/search
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
        print(f"âŒ TEXT SEARCH ERROR: {e}")
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": "internal_error",
            "message": str(e)
        }), 500


def _translate_query_to_english(query: str) -> str:
    """
    Traduce el query a inglÃ©s usando deep-translator (gratuito, sin API key).
    Fallback: retorna query original si falla.
    """
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='en')
        translated = translator.translate(query)
        if translated and translated != query:
            print(f"ðŸŒ TraducciÃ³n: '{query}' â†’ '{translated}'")
            return translated
    except ImportError:
        print("âš ï¸ deep-translator no instalado. Instalar con: pip install deep-translator")
    except Exception as e:
        print(f"âš ï¸ Error en traducciÃ³n: {e}")

    return query


## expand_color_modifiers fue extraÃ­do a app.core.modifier_expander.expand_color_modifiers


## normalize_color fue extraÃ­do a app.utils.colors.normalize_color


def _calculate_attribute_match(query_lower: str, attributes: dict, category: str = None, detected_color: str = None, detected_tipo: str = None) -> float:
    """
    Calcula boost por matching de atributos JSONB + categorÃ­a.

    Estrategia de scoring:
    - CategorÃ­a match: +0.30 (identifica el tipo de producto)
    - Color exacto (del LLM normalizer): +0.50 (crÃ­tico para bÃºsquedas visuales)
    - Otros atributos exactos: +0.20 cada uno
    - Match parcial: +0.10

    Args:
        query_lower: Query en minÃºsculas
        attributes: Atributos JSONB del producto
        category: Nombre de categorÃ­a del producto
        detected_color: Color detectado por LLM normalizer
        detected_tipo: Tipo detectado por LLM normalizer
    """
    score = 0.0
    other_attr_score = 0.0  # Limitar contribuciÃ³n de atributos NO color
    query_words = set(query_lower.split())

    # 1. Match de categorÃ­a (importante para tipo de producto)
    if category:
        category_lower = category.lower()
        for word in query_words:
            if len(word) > 3 and word in category_lower:
                score += 0.30  # Boost fuerte por match de categorÃ­a
                break  # Solo una vez

    # 2. Match de atributos JSONB con ponderaciÃ³n por tipo
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
                    # PRIORIDAD 1: Usar color del LLM normalizer si estÃ¡ disponible
                    if detected_color:
                        # Usar colors_are_similar() para comparaciÃ³n semÃ¡ntica (embeddings)
                        from app.utils.colors import colors_are_similar

                        if colors_are_similar(detected_color, v, threshold=0.75):
                            score += 0.50  # Boost fuerte por color del LLM
                            print(f"  ðŸŽ¨ COLOR MATCH (LLM Semantic): '{detected_color}' â‰ˆ '{v}' (+0.50)")
                            break

                        # SOFT-BOOST: aunque no supere el umbral, favorecer el color mÃ¡s cercano
                        try:
                            from app.utils.llm_query_normalizer import normalize_query
                            import numpy as np
                            ra = normalize_query(detected_color)
                            rb = normalize_query(v)
                            ea, eb = ra.get('embedding'), rb.get('embedding')
                            if ea and eb:
                                ea = np.array(ea, dtype=np.float32)
                                eb = np.array(eb, dtype=np.float32)
                                sim = float(np.dot(ea, eb) / (np.linalg.norm(ea) * np.linalg.norm(eb)))
                                # Escalar hasta +0.20 cuando se acerca al umbral 0.75
                                soft_boost = min(0.20, max(0.0, (sim / 0.75) * 0.20))
                                if soft_boost > 0:
                                    score += soft_boost
                                    print(f"  ðŸŽ¨ COLOR NEAREST (LLM Semantic): '{detected_color}' ~ '{v}' sim={sim:.3f} (+{soft_boost:.3f})")
                                    break
                        except Exception:
                            pass

                    # FALLBACK: Match tradicional por query con similitud semÃ¡ntica
                    matched_color = False
                    for word in query_words:
                        if len(word) >= 3:  # Solo palabras significativas
                            from app.utils.colors import colors_are_similar
                            if colors_are_similar(word, v, threshold=0.75):
                                score += 0.40  # Match de color por palabra
                                print(f"  ðŸŽ¨ COLOR MATCH (Query Semantic): '{word}' â‰ˆ '{v}' (+0.40)")
                                matched_color = True
                                break

                    if matched_color:
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


def _best_color_similarity(detected_color: str, attributes: dict) -> float:
    """
    Calcula la mejor similitud semÃ¡ntica (coseno) entre el color detectado por LLM
    y los valores de atributos de color del producto. Devuelve un valor en [0,1].

    Se usa como desempate/ranking cuando no hay match por encima del umbral.
    """
    if not detected_color or not attributes:
        return 0.0

    try:
        from app.utils.llm_query_normalizer import normalize_query
        import numpy as np

        q = normalize_query(detected_color)
        ea = q.get('embedding')
        if not ea:
            return 0.0
        ea = np.array(ea, dtype=np.float32)

        def _to_str_list(val):
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

        best_sim = 0.0
        for attr_key, attr_value in attributes.items():
            if attr_key and attr_key.lower() in ['color', 'colour', 'color_principal', 'color_secundario']:
                for v in _to_str_list(attr_value):
                    rb = normalize_query(str(v))
                    eb = rb.get('embedding')
                    if eb:
                        eb = np.array(eb, dtype=np.float32)
                        sim = float(np.dot(ea, eb) / (np.linalg.norm(ea) * np.linalg.norm(eb)))
                        if sim > best_sim:
                            best_sim = sim
        return max(0.0, min(1.0, best_sim))
    except Exception:
        return 0.0


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


# ============================================================================
# UNIFIED SEARCH ENDPOINT (V2 - SaaS Ready)
# Endpoint unificado que usa detect_categories_centroid_based
# Retorna datos completos para vista cliente + vista análisis
# ============================================================================

@bp.route("/search/unified", methods=["POST", "OPTIONS"])
def unified_search():
    """
    Endpoint simplificado de búsqueda visual (requiere categoría pre-detectada).

    La detección de categoría se realiza previamente con GPT-4 Vision en /api/gpt4v/detect.
    Este endpoint solo busca productos similares dentro de la categoría especificada.

    Headers:
        X-API-Key: API Key del cliente

    JSON Body:
        image: Base64 de imagen O URL de imagen (requerido)
        category: Nombre de categoría (requerido, debe existir en BD)
        max_results: Productos a retornar (default: 5)

    Response:
        {
            "success": true,
            "client": {...},
            "category_used": "Delantal Completo",
            "products": [
                {
                    "id": "...",
                    "name": "...",
                    "similarity_score": 0.xx,
                    "image_url": "...",
                    ...
                }
            ],
            "metadata": {
                "processing_time_ms": xxx,
                "total_products_in_category": N
            }
        }
    """
    # Manejar preflight OPTIONS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    start_time = time.time()

    try:
        railway_log(f"🔍 UNIFIED SEARCH (GPT-4V): Request from {request.remote_addr}")

        # Validar API Key
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({
                "success": False,
                "error": "missing_api_key",
                "message": "X-API-Key header requerido"
            }), 401

        client = Client.query.filter_by(api_key=api_key).first()
        if not client:
            return jsonify({
                "success": False,
                "error": "invalid_api_key",
                "message": "API Key inválido"
            }), 401

        railway_log(f"✅ Cliente autenticado: {client.name}")

        # Obtener parámetros
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "missing_body",
                "message": "Body JSON requerido"
            }), 400

        # Validar parámetros requeridos
        image_data = data.get('image')
        category_name = data.get('category')

        if not image_data:
            return jsonify({
                "success": False,
                "error": "missing_image",
                "message": "Campo 'image' requerido (base64 o URL)"
            }), 400

        if not category_name:
            return jsonify({
                "success": False,
                "error": "missing_category",
                "message": "Campo 'category' requerido (debe ser detectado previamente con /api/gpt4v/detect)"
            }), 400

        max_results = int(data.get('max_results', 5))

        railway_log(f"📊 Parámetros: category={category_name}, max_results={max_results}")

        # Buscar categoría en BD
        from app.models.category import Category
        category = Category.query.filter_by(
            client_id=client.id,
            name=category_name,
            is_active=True
        ).first()

        if not category:
            return jsonify({
                "success": False,
                "error": "category_not_found",
                "message": f"Categoría '{category_name}' no encontrada para este cliente"
            }), 404

        railway_log(f"✅ Categoría encontrada: {category.name} (ID: {category.id})")

        # Procesar imagen y generar embedding
        from app.blueprints.embeddings import load_image_from_source, get_clip_model

        try:
            image = load_image_from_source(image_data)
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "invalid_image",
                "message": f"Error procesando imagen: {str(e)}"
            }), 400

        # Generar embedding de imagen query
        model, preprocess = get_clip_model()
        import torch
        from PIL import Image as PILImage

        with torch.no_grad():
            image_input = preprocess(image).unsqueeze(0)
            query_embedding = model.encode_image(image_input)
            query_embedding = query_embedding / query_embedding.norm(dim=-1, keepdim=True)
            query_embedding = query_embedding.cpu().numpy().flatten()

        # Buscar productos similares en la categoría
        products_query = Product.query.filter_by(
            client_id=client.id,
            category_id=category.id,
            is_active=True
        ).join(Image).filter(
            Image.is_processed == True,
            Image.embedding != None
        ).distinct()

        total_products = products_query.count()
        products = products_query.all()
        print(f"🔍 DEBUG: query SQL ejecutada en {(_t.time()-_t2):.2f}s → {len(products)} productos", flush=True)

        railway_log(f"🔍 Evaluando {len(products)} productos en categoría '{category.name}'")

        # Calcular similitudes
        from app.utils.similarity import cosine_similarity
        import numpy as np

        product_similarities = []
        for product in products:
            if not product.images.first() or product.images.first().embedding is None:
                continue

            # Obtener embedding del producto
            product_embedding = np.frombuffer(product.images.first().embedding, dtype=np.float32)

            # Calcular similitud
            similarity = cosine_similarity(query_embedding, product_embedding)

            product_similarities.append({
                'product': product,
                'similarity': float(similarity),
                'image': product.images.first()
            })

        # Ordenar por similitud descendente
        product_similarities.sort(key=lambda x: x['similarity'], reverse=True)

        # Tomar top N resultados
        top_results = product_similarities[:max_results]

        # Serializar resultados
        products_data = []
        for result in top_results:
            p = result['product']
            img = result['image']

            products_data.append({
                'id': str(p.id),
                'name': p.name,
                'sku': p.sku,
                'category': category.name,
                'price': float(p.price) if p.price else None,
                'image_url': img.display_url if img else None,
                'similarity_score': result['similarity'],
                'attributes': (p.attributes or {})
            })

        # Metadata de respuesta
        processing_time = (time.time() - start_time) * 1000

        response_data = {
            "success": True,
            "client": {
                "id": str(client.id),
                "name": client.name
            },
            "category_used": category.name,
            "products": products_data,
            "metadata": {
                "total_products_in_category": total_products,
                "products_evaluated": len(products),
                "results_returned": len(products_data),
                "processing_time_ms": round(processing_time, 2)
            }
        }

        railway_log(f"✅ Búsqueda completada: {len(products_data)} productos en {processing_time:.0f}ms")

        return jsonify(response_data), 200

    except Exception as e:
        railway_log(f"❌ Error en unified_search: {str(e)}")
        import traceback
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": "internal_error",
            "message": str(e)
        }), 500


@bp.route("/clients/list", methods=["GET"])
def list_clients():
    """
    Endpoint para obtener lista de clientes con sus API keys.
    Útil para selector dinámico en interfaces de testing.

    Response:
        {
            "success": true,
            "clients": [
                {
                    "id": "...",
                    "name": "...",
                    "api_key": "...",
                    "is_active": true
                }
            ]
        }
    """
    try:
        clients = Client.query.filter_by(is_active=True).all()

        clients_data = [
            {
                "id": str(c.id),
                "name": c.name,
                "api_key": c.api_key,
                "is_active": c.is_active,
                "category_count": Category.query.filter_by(client_id=c.id, is_active=True).count(),
                "product_count": Product.query.filter_by(client_id=c.id, is_active=True).count()
            }
            for c in clients
        ]

        return jsonify({
            "success": True,
            "clients": clients_data
        }), 200

    except Exception as e:
        railway_log(f"❌ Error listando clientes: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GPT-4V UNIFIED SEARCH (V3 - Vision + CLIP Integration)
# Flujo: Imagen → GPT-4V detecta categorías → Búsqueda CLIP en cada categoría
# ============================================================================

@bp.route("/search/gpt4v-unified", methods=["POST", "OPTIONS"])
def gpt4v_unified_search():
    """
    Endpoint unificado con GPT-4 Vision para detección automática de categorías.

    Flujo:
    1. Recibe imagen del cliente
    2. GPT-4V detecta prendas y categorías automáticamente
    3. Para cada categoría detectada, busca productos similares con CLIP
    4. Retorna resultados agrupados por categoría

    Headers:
        X-API-Key: API Key del cliente

    Body (multipart/form-data o JSON):
        image: Archivo imagen o base64 (requerido)
        max_results_per_category: Productos por categoría (default: 5)
        similarity_threshold: Umbral de similitud 0-1 (default: 0.7)

    Response:
        {
            "success": true,
            "client": {...},
            "detection": {
                "prendas": [{tipo, color, confianza, categoria_sugerida}],
                "categories_detected": ["Delantal Completo", "..."],
                "cost_usd": 0.0025
            },
            "results_by_category": {
                "Delantal Completo": {
                    "products": [{...}],
                    "total_in_category": N
                }
            },
            "metadata": {
                "total_products_found": N,
                "categories_searched": N,
                "processing_time_ms": xxx
            }
        }
    """
    # Manejar preflight OPTIONS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    start_time = time.time()

    try:
        railway_log(f"🔍 GPT4V-UNIFIED SEARCH: Request from {request.remote_addr}")

        # Validar API Key
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({
                "success": False,
                "error": "missing_api_key",
                "message": "X-API-Key header requerido"
            }), 401

        # Validar API Key usando el modelo Client
        client = Client.query.filter_by(api_key=api_key, is_active=True).first()
        if not client:
            return jsonify({
                "success": False,
                "error": "invalid_api_key",
                "message": "API Key inválido o cliente inactivo"
            }), 401

        railway_log(f"✅ Cliente autenticado: {client.name}")

        # Usar product_similarity_threshold del cliente (convertir de % a 0.0-1.0)
        default_threshold = (client.product_similarity_threshold or 30) / 100.0

        # Max results desde system_config
        default_max_results = system_config.get('search', 'max_results', 10)

        # Obtener imagen (multipart o JSON)
        # image_data: se usará luego para generar el embedding (acepta bytes o str)
        # image_for_detection: será bytes o PIL.Image para GPT-4V
        image_data = None
        image_for_detection = None
        if request.content_type and 'multipart/form-data' in request.content_type:
            file = request.files.get('image')
            if file:
                image_bytes = file.read()
                # Mantener bytes para detección y para carga posterior
                image_data = image_bytes
                image_for_detection = image_bytes
            max_results = int(request.form.get('max_results_per_category', default_max_results))
            threshold = float(request.form.get('similarity_threshold', default_threshold))
        else:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "missing_body",
                    "message": "Body JSON o multipart/form-data requerido"
                }), 400
            image_data = data.get('image')
            max_results = int(data.get('max_results_per_category', default_max_results))
            threshold = float(data.get('similarity_threshold', default_threshold))
            # Para JSON, convertir a PIL.Image para detección (admite data URL/base64)
            from app.blueprints.embeddings import load_image_from_source
            image_for_detection = load_image_from_source(image_data)

        if not image_data:
            return jsonify({
                "success": False,
                "error": "missing_image",
                "message": "Campo 'image' requerido (archivo o base64)"
            }), 400

        # Obtener max_results desde configuración del sistema
        max_results_config = system_config.get('search', 'max_results', 10)
        # Respetar el límite del sistema si el usuario pide más
        max_results = min(max_results, max_results_config)

        railway_log(f"📊 Parámetros: max_results={max_results} (límite sistema: {max_results_config}), threshold={threshold} (config: {default_threshold})")

        # ===================================================================
        # PASO 1: Detectar categorías con GPT-4 Vision (opcional)
        # ===================================================================
        from app.blueprints.gpt4v_detection import detect_categories_with_gpt4v
        from app.models.category import Category
        from app.models.product import Product
        from app.models.image import Image

        # Obtener categorías activas que tengan imágenes procesadas con embedding
        # (evita enviar a Vision categorías sin inventario/embeddings)
        try:
            category_id_rows = db.session.query(Product.category_id)\
                .join(Image, Image.product_id == Product.id)\
                .filter(
                    Product.client_id == client.id
                )\
                .distinct()\
                .all()

            category_ids = [row[0] for row in category_id_rows]

            categories = []
            if category_ids:
                # Enviar toda categoría activa que tenga imágenes
                categories = Category.query.filter(
                    Category.id.in_(category_ids),
                    Category.client_id == client.id,
                    Category.is_active == True
                ).all()
            categories_list = [cat.name for cat in categories]
        except Exception as e:
            railway_log(f"⚠️ Error obteniendo categorías con imágenes: {e}")
            # Fallback: categorías activas del cliente
            categories = Category.query.filter_by(
                client_id=client.id,
                is_active=True
            ).all()
            categories_list = [cat.name for cat in categories]

        # Bandera para NO mandar fotos a Vision (por privacidad o pruebas)
        disable_header = request.headers.get('X-Disable-Vision', '').lower() in ('1', 'true', 'yes')
        # Vision habilitado por defecto; obtener de config si existe la sección
        vision_cfg = system_config.get_section('vision') or {}
        vision_enabled = bool(vision_cfg.get('enabled', True)) and not disable_header

        prendas = []
        categories_detected = []
        categories_detected_raw = []

        if vision_enabled:
            railway_log(f"🤖 Detectando categorías con GPT-4V")

            gpt4v_result = detect_categories_with_gpt4v(
                image_for_detection,
                categories_list,
                str(client.id)
            )

            prendas = gpt4v_result.get('prendas', [])
            # Lista RAW tal como la devuelve Vision (mantener orden y posibles duplicados)
            categories_detected_raw = [
                p['categoria_sugerida']
                for p in prendas
                if p.get('categoria_sugerida')
            ]
            # Versión única para fines de búsqueda (sin afectar UI)
            categories_detected = list(dict.fromkeys(categories_detected_raw))

            railway_log(f"✅ GPT-4V detectó {len(categories_detected)} categorías: {categories_detected}")
        else:
            railway_log("🛡️ Vision deshabilitado: no se envía imagen a GPT-4V. Se hará pre-búsqueda CLIP por categorías.")

        # ===================================================================
        # PASO 2: Buscar productos similares en cada categoría detectada
        # ===================================================================
        from app.blueprints.embeddings import load_image_from_source, get_clip_model
        import torch
        import numpy as np

        # Compat: similitud coseno local (evita dependencia a app.utils.similarity)
        def cosine_similarity(a, b):
            a = np.asarray(a, dtype=np.float32)
            b = np.asarray(b, dtype=np.float32)
            na = np.linalg.norm(a)
            nb = np.linalg.norm(b)
            if na == 0 or nb == 0:
                return 0.0
            return float(np.dot(a, b) / (na * nb))

        # Generar embedding de imagen query (usar CLIPProcessor como en el resto del sistema)
        image = load_image_from_source(image_data)
        model, processor = get_clip_model()

        with torch.no_grad():
            inputs = processor(images=image, return_tensors="pt")
            image_features = model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            query_embedding = image_features.cpu().numpy().flatten()

        railway_log(f"🔍 Embedding generado, buscando productos...")

        results_by_category = {}
        total_products_found = 0

        # Si Vision está deshabilitado o no detectó categorías, buscar en todas las categorías disponibles
        categories_to_search = list(set(categories_detected)) if categories_detected else categories_list

        for category_name in categories_to_search:
            # Buscar categoría en BD
            # Resolver categoría con tolerancia mínima (case-insensitive y fallback singular/plural/contiene)
            from sqlalchemy import func

            def _resolve_category(name: str):
                # 1) Igualdad case-insensitive
                cat = Category.query.filter(
                    Category.client_id == client.id,
                    Category.is_active == True,
                    func.lower(Category.name) == name.lower()
                ).first()
                if cat:
                    return cat
                # 2) Singular/plural simple
                alt = name[:-1] if name.lower().endswith('s') else (name + 's')
                cat = Category.query.filter(
                    Category.client_id == client.id,
                    Category.is_active == True,
                    func.lower(Category.name) == alt.lower()
                ).first()
                if cat:
                    return cat
                # 3) Contiene (evita perder por guiones o espacios)
                like_pat = f"%{name.lower()}%"
                cat = Category.query.filter(
                    Category.client_id == client.id,
                    Category.is_active == True,
                    func.lower(Category.name).like(like_pat)
                ).first()
                return cat

            category = _resolve_category(category_name)

            if not category:
                railway_log(f"⚠️ Categoría '{category_name}' no encontrada en BD")
                continue

            # Buscar productos en esta categoría
            products_query = Product.query.filter_by(
                client_id=client.id,
                category_id=category.id,
                is_active=True
            ).join(Image).filter(
                Image.is_processed == True,
                Image.clip_embedding != None
            ).distinct()

            products = products_query.all()
        print(f"🔍 DEBUG: query SQL ejecutada en {(_t.time()-_t2):.2f}s → {len(products)} productos", flush=True)
            total_in_category = products_query.count()

            railway_log(f"   📦 {category_name}: {len(products)} productos")

            # Calcular similitudes
            product_similarities = []
            for product in products:
                # Seleccionar una imagen procesada con embedding válido para este producto
                try:
                    img_obj = product.images.filter_by(is_processed=True).filter(Image.clip_embedding != None).first()
                except Exception:
                    img_obj = product.images.first()
                if not img_obj or not img_obj.embedding_vector:
                    continue

                # embedding_vector es lista de floats (JSON); convertir a np.array
                product_embedding = np.asarray(img_obj.embedding_vector, dtype=np.float32)

                similarity = cosine_similarity(query_embedding, product_embedding)

                # Log temporal para debug de gorras
                if 'gorro' in category_name.lower() or 'gorra' in category_name.lower():
                    railway_log(f"      → {product.name} (SKU: {product.sku}): similarity={similarity:.4f}, threshold={threshold:.4f}, pass={'✅' if similarity >= threshold else '❌'}")

                # Aplicar threshold
                if similarity >= threshold:
                    product_similarities.append({
                        'product': product,
                        'similarity': float(similarity),
                        'image': product.images.first()
                    })

            # Ordenar por similitud descendente
            product_similarities.sort(key=lambda x: x['similarity'], reverse=True)

            # Tomar top N resultados
            top_results = product_similarities[:max_results]

            # Serializar resultados usando lógica enriquecida similar a _build_search_results
            products_data = []

            # Cache de configuración de atributos (una consulta por categoría)
            exposed_keys_cache = None
            checked_config = False

            for result in top_results:
                p = result['product']
                img = result['image']

                # Primera vez: cargar configuración de atributos visibles
                if not checked_config:
                    try:
                        client_id = p.client_id
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

                        if total_configs and total_configs[0] == 0:
                            exposed_keys_cache = None  # Sin configuración, exponer todo
                        else:
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
                            exposed_keys_cache = {r[0] for r in rows}
                    except Exception as e:
                        railway_log(f"⚠️ Error consultando product_attribute_config: {e}")
                        db.session.rollback()
                        exposed_keys_cache = None
                    finally:
                        checked_config = True

                # Obtener imagen primaria en lugar de la que hizo match
                primary_image = None
                try:
                    primary_image = Image.query.filter_by(
                        product_id=p.id,
                        is_primary=True
                    ).first()
                    if not primary_image:
                        primary_image = img
                    image_url = primary_image.display_url if primary_image else None
                except Exception as e:
                    railway_log(f"⚠️ Error obteniendo imagen primaria: {e}")
                    db.session.rollback()
                    image_url = img.display_url if img else None

                # Preparar atributos filtrados y extraer product_url
                product_attrs = {}
                product_url_value = None
                try:
                    if hasattr(p, 'attributes') and p.attributes:
                        # 1) Extraer url_producto del JSONB (siempre, ignorar filtros)
                        raw_url = p.attributes.get('url_producto')
                        if isinstance(raw_url, dict):
                            product_url_value = raw_url.get('value') or raw_url.get('url') or None
                        else:
                            product_url_value = raw_url

                        # 2) Filtrar atributos según configuración
                        if exposed_keys_cache is not None:
                            product_attrs = {
                                k: v for k, v in p.attributes.items() if k in exposed_keys_cache
                            }
                        else:
                            product_attrs = dict(p.attributes)
                except Exception as e:
                    railway_log(f"⚠️ Error procesando atributos de {p.id}: {e}")
                    product_attrs = {}

                products_data.append({
                    'id': str(p.id),
                    'name': p.name,
                    'sku': p.sku,
                    'category': category_name,
                    'price': float(p.price) if p.price else None,
                    'image_url': image_url,  # ✅ Imagen primaria con fallback
                    'similarity_score': result['similarity'],
                    'attributes': product_attrs,  # ✅ Filtrado por config
                    'stock': p.stock if hasattr(p, 'stock') and p.stock is not None else 0,
                    'product_url': product_url_value  # ✅ URL del producto
                })

            total_products_found += len(products_data)

            results_by_category[category_name] = {
                'products': products_data,
                'total_in_category': total_in_category,
                'results_returned': len(products_data)
            }

        # Marcar como detectadas las categorías con resultados si Vision está deshabilitado
        # o como refuerzo cuando Vision no devolvió alguna categoría evidente.
        if not vision_enabled:
            categories_detected = [
                name for name, data in results_by_category.items() if data['results_returned'] > 0
            ]

        # ===================================================================
        # PASO 3: Preparar respuesta final
        # ===================================================================
        processing_time = (time.time() - start_time) * 1000

        response_data = {
            "success": True,
            "client": {
                "id": str(client.id),
                "name": client.name
            },
            "detection": {
                "prendas": prendas,
                "categories_detected": categories_detected,
                "categories_detected_raw": categories_detected_raw,
                "cost_usd": 0.0025,  # Costo GPT-4o
                "mensaje_usuario": gpt4v_result.get('mensaje_usuario', '') if vision_enabled else '',
                "user_intent": gpt4v_result.get('mensaje_usuario', '') if vision_enabled else ''  # Alias para compatibilidad
            },
            "results_by_category": results_by_category,
            "metadata": {
                "total_products_found": total_products_found,
                "categories_searched": len(results_by_category),
                "max_results_per_category": max_results,
                "max_results_config": max_results_config,
                "processing_time_ms": round(processing_time, 2),
                "similarity_threshold": threshold
            }
        }

        railway_log(f"✅ Búsqueda completada: {total_products_found} productos en {processing_time:.0f}ms")

        return jsonify(response_data), 200

    except Exception as e:
        railway_log(f"❌ Error en gpt4v_unified_search: {str(e)}")
        import traceback
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": "internal_error",
            "message": str(e)
        }), 500


