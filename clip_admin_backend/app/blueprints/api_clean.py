"""
Blueprint de API
Endpoints internos para el admin panel y búsqueda visual
"""

import sys
import time
import re
from app.blueprints.embeddings import _get_idle_timeout_seconds
import hashlib
import numpy as np
import torch
import os
from flask import Blueprint, request, jsonify, send_file, current_app, session, redirect, url_for
from flask_login import login_required, current_user
from flask_cors import CORS
from app.utils.logging_config import (
    log_error, log_request, log_search, log_category_detection,
    log_nlp, log_database, LogCategory, should_log
)
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
from app.utils.colors import normalize_color
from app.utils.llm_query_normalizer import normalize_query, get_model
from sqlalchemy import func, or_, text
# from googletrans import Translator  # DESHABILITADO - googletrans 4.0.0rc1 roto con httpcore

# ?? IMPORTAR CLIP AL INICIO PARA CACHE GLOBAL
from app.blueprints.embeddings import get_clip_model
from app.models.embedding import Embedding
from app.blueprints.search_visual import (
    process_image_for_search,
    calculate_similarity,
    _generate_query_embedding,
    _find_similar_products,
    _find_similar_products_in_category,
    _apply_category_filter,
    _build_search_results,
    detect_dominant_color,
    detect_dominant_color_from_palette,
    detect_general_object,
    detect_image_category_with_centroids,
    detect_image_category,
)
import json

bp = Blueprint("api", __name__)

# Habilitar CORS para este blueprint
CORS(bp, origins=["*"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "X-API-Key", "Authorization"])

# ?? CACHÉ GLOBAL DE EMBEDDINGS (evita recalcular en cada request)
_CATEGORY_EMBEDDINGS_CACHE = {}
_COLOR_EMBEDDINGS_CACHE = {}

# spaCy es OBLIGATORIO para tokenización (no opcional)
_USE_SPACY_NORMALIZER = True  # Siempre activo
_SPACY_NLP = None

def _get_spacy_nlp():
    """Carga perezosa del modelo spaCy español (OBLIGATORIO)."""
    global _SPACY_NLP
    # Si ya falló antes, no reintentar
    if _SPACY_NLP is False:
        return None
    if _SPACY_NLP is None:
        try:
            import spacy  # type: ignore
            model_name = os.getenv("SPACY_MODEL", "es_core_news_md")
            # Deshabilitar componentes no necesarios para reducir overhead
            _SPACY_NLP = spacy.load(model_name, disable=["parser", "ner", "textcat"])
            log_nlp(f"spaCy cargado: {model_name}")
        except Exception as e:
            log_error(f"CRITICAL: spaCy no disponible: {e}")
            _SPACY_NLP = False
    return _SPACY_NLP if _SPACY_NLP not in (None, False) else None

def _get_category_embedding(category_name: str, client_id: str):
    """
    Obtiene embedding de categoría desde BD persistida o lo calcula si no existe.
    Key: "category:<client_id>:<category_name>"
    """
    cache_key = f"{client_id}:{category_name.lower()}"
    db_key = f"category:{client_id}:{category_name.lower()}"
    if cache_key in _CATEGORY_EMBEDDINGS_CACHE:
        return _CATEGORY_EMBEDDINGS_CACHE[cache_key]
    emb_row = Embedding.query.filter_by(key=db_key, type="category").first()
    if emb_row:
        emb = json.loads(emb_row.embedding)
        _CATEGORY_EMBEDDINGS_CACHE[cache_key] = emb
        return emb
    # Si no existe, fallback a None (no calcular en request)
    return None

def _get_color_embedding(color_text: str):
    """
    Obtiene embedding de color desde BD persistida o lo calcula si no existe.
    Key: "color:<color_text>"
    """
    cache_key = color_text.lower()
    db_key = f"color:{color_text.lower()}"
    if cache_key in _COLOR_EMBEDDINGS_CACHE:
        return _COLOR_EMBEDDINGS_CACHE[cache_key]
    emb_row = Embedding.query.filter_by(key=db_key, type="color").first()
    if emb_row:
        emb = json.loads(emb_row.embedding)
        _COLOR_EMBEDDINGS_CACHE[cache_key] = np.array(emb, dtype=np.float32)
        return _COLOR_EMBEDDINGS_CACHE[cache_key]
    # Si no existe, fallback a None (no calcular en request)
    return None


# ?? Helper para logs que funcionen en Railway (Gunicorn)
def railway_log(message):
    """Log que se ve en Railway - usa stderr con flush inmediato"""
    # Redirigir a sistema de logging centralizado
    from app.utils.logging_config import railway_log as new_railway_log
    new_railway_log(message)


def _clip_prompt_for_category(category) -> str:
    """
    Construye el prompt final "a photo of ..." usando SOLO propiedades del modelo Category.
    NO usa hardcodeo ni fallbacks - depende 100% de datos configurados en BD.

    Prioridad:
    1. category.clip_prompt (prompt personalizado completo)
    2. category.name_en (nombre en inglés)
    3. category.name (nombre en español sin traducción)

    Returns:
        str: Prompt en formato "a photo of <label>"
    """
    try:
        # Prioridad 1: clip_prompt (puede incluir modificadores, contexto, etc.)
        if getattr(category, "clip_prompt", None) and str(category.clip_prompt).strip():
            label = str(category.clip_prompt).strip().lower()
            return f"a photo of {label}"

        # Prioridad 2: name_en (nombre en inglés)
        if getattr(category, "name_en", None) and str(category.name_en).strip():
            label = str(category.name_en).strip().lower()
            return f"a photo of {label}"

        # Prioridad 3: name (español como último recurso, sin traducción)
        if getattr(category, "name", None) and str(category.name).strip():
            label = str(category.name).strip().lower()
            return f"a photo of {label}"

        # Sin datos: usar genérico
        return "a photo of clothing"

    except Exception as e:
        print(f"?? Error construyendo CLIP prompt para categoría: {e}")
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
        "url": image.optimized_url,  # Usar base64 cacheado (evita descargas de Cloudinary)
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


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


# Función movida a app.blueprints.search_visual


## Función detect_image_category movida a app.blueprints.search_visual


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
        categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
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
        print(f"\n?? DEBUG: Candidatos ANTES de ordenar (total: {len(candidates)}):")
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
            print(f"?? MULTI-CATEGORY: Modo ESTRICTO (max confidence={max_conf:.3f})")
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
    DEPRECATED: Endpoint legacy. Usar /api/search/gpt4v-unified o /api/search/text.
    Se mantiene con 410 para detectar usos residuales sin romper clientes.
    """
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    deprec = jsonify({
        "success": False,
        "error": "DEPRECATED_ENDPOINT",
        "message": "Este endpoint /api/search (visual) está deprecado. Usa /api/search/gpt4v-unified o /api/search/text."
    })
    try:
        deprec.headers['Access-Control-Allow-Origin'] = '*'
        deprec.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        deprec.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        deprec.headers['X-Deprecated-Endpoint'] = 'true'
    except Exception:
        pass
    return deprec, 410
