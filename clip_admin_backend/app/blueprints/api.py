"""
Blueprint de API
Endpoints internos para el admin panel y búsqueda visual
"""

import sys
import time
import re
import threading
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

# 🚀 IMPORTAR CLIP AL INICIO PARA CACHE GLOBAL
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

# 🔥 CACHÉ GLOBAL DE EMBEDDINGS (evita recalcular en cada request)
_CATEGORY_EMBEDDINGS_CACHE = {}
_COLOR_EMBEDDINGS_CACHE = {}
_COLOR_TEXT_MATRIX_GLOBAL = None
_COLOR_KEYS_GLOBAL = None
_COLOR_TEXT_CACHE_LOCK = threading.Lock()


def _build_global_color_text_cache(model=None, processor=None, force_reload: bool = False):
    """Construye (una sola vez por proceso) la matriz de colores para inferencia CLIP."""
    global _COLOR_TEXT_MATRIX_GLOBAL, _COLOR_KEYS_GLOBAL

    if _COLOR_TEXT_MATRIX_GLOBAL is not None and _COLOR_KEYS_GLOBAL is not None and not force_reload:
        return _COLOR_TEXT_MATRIX_GLOBAL, _COLOR_KEYS_GLOBAL

    with _COLOR_TEXT_CACHE_LOCK:
        if _COLOR_TEXT_MATRIX_GLOBAL is not None and _COLOR_KEYS_GLOBAL is not None and not force_reload:
            return _COLOR_TEXT_MATRIX_GLOBAL, _COLOR_KEYS_GLOBAL

        canonical_palette = {
            'negro': 'black',
            'blanco': 'white',
            'gris': 'gray',
            'azul': 'blue',
            'celeste': 'light blue',
            'verde': 'green',
            'rojo': 'red',
            'rosa': 'pink',
            'marron': 'brown',
            'beige': 'beige',
            'amarillo': 'yellow',
            'violeta': 'purple',
            'naranja': 'orange',
        }

        if model is None or processor is None:
            model, processor = get_clip_model()

        color_texts = [
            f"a photo of a {en_name} garment"
            for _, en_name in canonical_palette.items()
        ]
        color_keys = list(canonical_palette.keys())

        with torch.no_grad():
            color_text_inputs = processor(
                text=color_texts,
                return_tensors="pt",
                padding=True,
                truncation=True
            )
            color_text_features = model.get_text_features(**color_text_inputs)
            color_text_features = color_text_features / color_text_features.norm(dim=-1, keepdim=True)

        _COLOR_TEXT_MATRIX_GLOBAL = color_text_features.cpu().numpy().astype(np.float32)
        _COLOR_KEYS_GLOBAL = color_keys

    return _COLOR_TEXT_MATRIX_GLOBAL, _COLOR_KEYS_GLOBAL


def warmup_clip_color_cache() -> bool:
    """Warmup explícito de CLIP + matriz de colores durante startup."""
    try:
        model, processor = get_clip_model()
        _build_global_color_text_cache(model=model, processor=processor)
        railway_log("✅ Warmup CLIP color cache completado")
        return True
    except Exception as e:
        railway_log(f"⚠️ Warmup CLIP color cache falló: {e}")
        return False

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


# 🔍 Helper para logs que funcionen en Railway (Gunicorn)
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
        print(f"⚠️ Error construyendo CLIP prompt para categoría: {e}")
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

    # DEPRECATED: Legacy endpoint deshabilitado para detectar usos en pruebas
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

        # Cargar configuración de atributos para filtrar exposición
        exposed_keys = set()
        try:
            from app.models.product_attribute_config import ProductAttributeConfig
            configs = ProductAttributeConfig.query.filter_by(client_id=client.id).all()
            for cfg in configs:
                if cfg.expose_in_search:
                    exposed_keys.add((cfg.key or '').strip().lower())
        except Exception:
            pass

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
                                # Mensaje genérico y útil sin asumir vertical específico
                return jsonify({
                    "success": False,
                    "error": "category_not_detected",
                    "message": f"La imagen no coincide con los productos disponibles en {client.name}",
                    "details": "No pudimos identificar productos de nuestro catálogo en esta imagen. Por favor, intenta con una foto clara de un producto similar a los que ofrecemos.",
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

                        # Filtrado de atributos por configuración (case-insensitive)
                        try:
                            if product.attributes:
                                if exposed_keys:
                                    ek = {str(k).strip().lower() for k in exposed_keys}
                                    prod_attrs = {k: v for k, v in product.attributes.items() if str(k).strip().lower() in ek}
                                else:
                                    prod_attrs = dict(product.attributes)
                            else:
                                prod_attrs = {}
                        except Exception:
                            prod_attrs = {}

                        prod_dict = {
                            "id": str(product.id),
                            "name": product.name,
                            "sku": product.sku,
                            "price": float(product.price) if product.price else None,
                            "stock": product.stock,
                            "category": category.name,
                            "image_url": image_base64,  # âœ… BASE64 desde BD
                            "similarity": float(score),
                            "attributes": prod_attrs,
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
            # Mensaje genérico y útil sin asumir vertical específico
            # Mensaje genérico y útil sin asumir vertical específico
            return jsonify({
                "success": False,
                "error": "category_not_detected",
                "message": f"La imagen no coincide con los productos disponibles en {client.name}",
                "details": f"No pudimos identificar productos de nuestro catálogo en esta imagen (confianza máxima: {category_confidence:.1%}). Por favor, intenta con una foto clara de un producto similar a los que ofrecemos.",
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


def text_search():
    """DEPRECATED: Endpoint removido. Usar /api/search/text del blueprint search_text."""
    return jsonify({
        "success": False,
        "error": "deprecated_endpoint",
        "message": "Este endpoint está deprecado. Use /api/search/text del nuevo blueprint search_text.",
        "migration_url": "/api/search/text"
    }), 410


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

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


# normalize_color está en app.utils.colors.normalize_color

# Caché ligera en memoria POR PROCESO para evitar recomputar embeddings repetidos
# durante una única request en llamadas a colors_are_similar dentro de _calculate_attribute_match.
# Clave: ('detected', color_a, color_b) o ('query', word, color_b)
_color_sim_cache = {}

def _calculate_attribute_match(query_lower: str, attributes: dict, category: str = None,
                               detected_color: str = None, detected_tipo: str = None,
                               color_embeddings_map: dict = None) -> float:
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
        color_embeddings_map: Mapa precargado de embeddings {color_lower: np.array}
    """
    score = 0.0
    other_attr_score = 0.0  # Limitar contribuciÃ³n de atributos NO color
    query_words = set(query_lower.split())

    # Usar mapa precargado o dict vacío si no se provee
    color_emb_map = color_embeddings_map or {}

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
                    # PRIORIDAD: NO llamar LLM/normalizador aquí. Usar solo mapa precargado.
                    if detected_color:
                        dc = detected_color.lower()
                        # Match exacto rápido
                        if dc == v_lower:
                            score += 0.50
                            break

                        # Comparación por embeddings precargados (coseno)
                        ea = color_emb_map.get(dc)
                        eb = color_emb_map.get(v_lower)
                        if ea is not None and eb is not None:
                            denom = (np.linalg.norm(ea) * np.linalg.norm(eb))
                            sim = float(np.dot(ea, eb) / denom) if denom else 0.0
                            if sim >= 0.75:
                                score += 0.50
                                break
                            # Soft-boost proporcional hasta +0.20
                            soft_boost = min(0.20, max(0.0, (sim / 0.75) * 0.20))
                            if soft_boost > 0:
                                score += soft_boost
                                break
                    # Si no hay detected_color o no hay embedding disponible, no sumar por color aquí
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


def _best_color_similarity(detected_color: str, attributes: dict, color_embeddings_map: dict = None) -> float:
    """
    Calcula la mejor similitud semÃ¡ntica (coseno) entre el color detectado por LLM
    y los valores de atributos de color del producto. Devuelve un valor en [0,1].

    Se usa como desempate/ranking cuando no hay match por encima del umbral.

    Args:
        detected_color: Color detectado por LLM normalizer
        attributes: Atributos JSONB del producto
        color_embeddings_map: Mapa precargado de embeddings {color_lower: np.array}
    """
    if not detected_color or not attributes:
        return 0.0

    try:
        import numpy as np

        # Usar mapa precargado o dict vacío
        color_emb_map = color_embeddings_map or {}

        # 🔥 USAR MAPA PRECARGADO en lugar de query SQL
        ea = color_emb_map.get(detected_color.lower())
        if ea is None:
            return 0.0

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
                    # 🔥 USAR MAPA PRECARGADO en lugar de query SQL
                    eb = color_emb_map.get(str(v).lower())
                    if eb is not None:
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

@bp.route("/clients/list", methods=["GET"])
def list_clients():
    """Lista todos los clientes activos con sus API keys (para testing)."""
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
# ESTADO: Eliminado de la API pública (ruta deshabilitada)
# ============================================================================

@bp.route("/search/gpt4v-unified", methods=["POST", "OPTIONS"])  # Ruta habilitada para demo local
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

        # Configuración por cliente (api_settings)
        try:
            client_api_settings = json.loads(client.api_settings) if client.api_settings else {}
            if not isinstance(client_api_settings, dict):
                client_api_settings = {}
        except Exception:
            client_api_settings = {}
        color_priority_enabled = bool(client_api_settings.get('color_priority_enabled', False))

        railway_log(f"✅ Cliente autenticado: {client.name}")
        railway_log(f"⚙️ Config cliente: color_priority_enabled={color_priority_enabled}")

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
                client_id=str(client.id),
                industry=client.industry if hasattr(client, 'industry') else 'general'
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

            # Log de descripciones detalladas
            for idx, prenda in enumerate(prendas, 1):
                desc = prenda.get('descripcion', 'N/A')
                tipo = prenda.get('tipo', 'N/A')
                railway_log(f"   Prenda {idx}: {tipo} - {desc}")
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
        start_embed = time.time()

        start_load = time.time()
        image = load_image_from_source(image_data)
        railway_log(f"   ⏱️ Imagen cargada en {(time.time()-start_load):.3f}s")

        # Pre-resize para acelerar procesamiento (PIL thumbnail es mucho más rápido que processor resize)
        # CLIP igual va a resize a 224x224, así que empezar desde 512x512 no pierde calidad
        start_resize = time.time()
        from PIL import Image as PILImage
        if max(image.size) > 512:
            image.thumbnail((512, 512), PILImage.Resampling.LANCZOS)
            railway_log(f"   ⏱️ Pre-resize a {image.size[0]}x{image.size[1]} en {(time.time()-start_resize):.3f}s")

        start_model = time.time()
        model, processor = get_clip_model()
        railway_log(f"   ⏱️ Modelo obtenido en {(time.time()-start_model):.3f}s")

        with torch.no_grad():
            start_process = time.time()
            inputs = processor(images=image, return_tensors="pt")
            railway_log(f"   ⏱️ Imagen procesada en {(time.time()-start_process):.3f}s")

            start_features = time.time()
            image_features = model.get_image_features(**inputs)
            railway_log(f"   ⏱️ Features extraídas en {(time.time()-start_features):.3f}s")

            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            query_embedding = image_features.cpu().numpy().flatten()

        railway_log(f"🔍 Embedding generado en {(time.time()-start_embed):.3f}s total, buscando productos...")

        results_by_category = {}
        total_products_found = 0

        # Si Vision está deshabilitado o no detectó categorías, buscar en todas las categorías disponibles
        categories_to_search = list(set(categories_detected)) if categories_detected else categories_list

        # ===================================================================
        # OPTIMIZACIÓN 1: Resolver todas las categorías primero
        # ===================================================================
        from sqlalchemy import func
        from sqlalchemy.orm import joinedload

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

        # Resolver todas las categorías y obtener sus IDs
        categories_found = {}
        category_ids = []
        for category_name in categories_to_search:
            category = _resolve_category(category_name)
            if category:
                categories_found[category.id] = category_name
                category_ids.append(category.id)
            else:
                railway_log(f"⚠️ Categoría '{category_name}' no encontrada en BD")

        if not category_ids:
            railway_log("⚠️ No se encontraron categorías válidas")
            # Continuar con results_by_category vacío
        else:
            # ===================================================================
            # OPTIMIZACIÓN 2: Cache de configuración de atributos (UNA VEZ)
            # ===================================================================
            exposed_keys_cache = None
            exposed_labels_map = {}
            exposed_types_map = {}
            try:
                total_configs = db.session.execute(
                    text(
                        """
                        SELECT COUNT(*) as total
                        FROM product_attribute_config
                        WHERE client_id = :client_id
                        """
                    ),
                    {"client_id": client.id},
                ).fetchone()

                if total_configs and total_configs[0] == 0:
                    # Sin configuración, exponer todo y sin mapas auxiliares
                    exposed_keys_cache = None
                    exposed_labels_map = {}
                    exposed_types_map = {}
                else:
                    rows = db.session.execute(
                        text(
                            """
                            SELECT key, label, type
                            FROM product_attribute_config
                            WHERE client_id = :client_id AND expose_in_search = true
                            """
                        ),
                        {"client_id": client.id},
                    ).fetchall()
                    # Case-insensitive: normalizar claves a minúsculas para comparar con JSONB
                    exposed_keys_cache = set()
                    for r in rows:
                        if not r:
                            continue
                        key = str(r[0]).strip() if r[0] is not None else ''
                        label = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ''
                        atype = str(r[2]).strip().lower() if len(r) > 2 and r[2] is not None else ''
                        if key:
                            kl = key.lower()
                            exposed_keys_cache.add(kl)
                            if label:
                                exposed_labels_map[kl] = label
                            if atype:
                                exposed_types_map[kl] = atype
                    railway_log(f"✅ Config cache: {len(exposed_keys_cache)} atributos expuestos (case-insensitive)")
            except Exception as e:
                railway_log(f"⚠️ Error consultando product_attribute_config: {e}")
                db.session.rollback()
                exposed_keys_cache = None
                exposed_labels_map = {}
                exposed_types_map = {}

            # ===================================================================
            # OPTIMIZACIÓN 3: Batch Query - Traer TODOS los productos de una vez
            # ===================================================================
            start_batch = time.time()
            products_query = Product.query.filter(
                Product.client_id == client.id,
                Product.category_id.in_(category_ids),
                Product.is_active == True
            ).join(Image).filter(
                Image.is_processed == True,
                Image.clip_embedding != None
            ).options(
                joinedload(Product.category)   # Eager loading solo de categoría
            ).distinct()

            all_products = products_query.all()
            railway_log(f"⚡ Batch query: {len(all_products)} productos en {(time.time()-start_batch):.3f}s")

            # Pre-cargar TODAS las imágenes en una sola query (optimización manual)
            product_ids = [p.id for p in all_products]
            images_by_product = {}
            if product_ids:
                all_images = Image.query.filter(
                    Image.product_id.in_(product_ids),
                    Image.is_processed == True,
                    Image.clip_embedding != None
                ).all()

                for img in all_images:
                    images_by_product.setdefault(img.product_id, []).append(img)

                railway_log(f"⚡ Pre-cargadas {len(all_images)} imágenes")

            # Agrupar productos por categoría en memoria
            products_by_category = {}
            for product in all_products:
                cat_id = product.category_id
                products_by_category.setdefault(cat_id, []).append(product)

            # Cache por request para inferencia de color CLIP (evita recalcular por categoría)
            color_text_matrix_cache = None
            color_keys_cache = None

            # ===================================================================
            # OPTIMIZACIÓN 4: Vectorización - Calcular similitudes en batch
            # ===================================================================
            for cat_id, products in products_by_category.items():
                category_name = categories_found.get(cat_id)
                if not category_name:
                    continue

                railway_log(f"   📦 {category_name}: {len(products)} productos")

                # Preparar embeddings y referencias de productos
                product_embeddings = []
                product_refs = []

                for product in products:
                    # Usar imágenes pre-cargadas en lugar de acceso lazy
                    product_images = images_by_product.get(product.id, [])

                    # Seleccionar imagen procesada con embedding válido
                    img_obj = None
                    for img in product_images:
                        if img.is_processed and img.clip_embedding and img.embedding_vector:
                            img_obj = img
                            break

                    if not img_obj or not img_obj.embedding_vector:
                        continue

                    product_embeddings.append(img_obj.embedding_vector)
                    product_refs.append((product, img_obj))

                if not product_embeddings:
                    railway_log(f"      ⚠️ No hay embeddings válidos en {category_name}")
                    results_by_category[category_name] = {
                        'products': [],
                        'total_in_category': len(products),
                        'results_returned': 0
                    }
                    continue

                # Convertir todos los embeddings a matriz numpy (UNA operación)
                start_vectorize = time.time()
                embeddings_matrix = np.array(product_embeddings, dtype=np.float32)

                # Calcular TODAS las similitudes a la vez (vectorizado)
                similarities = np.dot(embeddings_matrix, query_embedding)

                # Crear lista de resultados con similitud
                product_similarities = []
                for idx, (product, img) in enumerate(product_refs):
                    sim = float(similarities[idx])

                    # Aplicar threshold
                    if sim >= threshold:
                        product_similarities.append({
                            'product': product,
                            'similarity': sim,
                            'image': img
                        })

                railway_log(f"      ⚡ Similitudes calculadas en {(time.time()-start_vectorize):.3f}s")

                # Si no hay productos que pasen threshold, agregar categoría vacía con mensaje
                if not product_similarities:
                    railway_log(f"      ⚠️ Ningún producto supera threshold {threshold:.2f} en {category_name}")
                    results_by_category[category_name] = {
                        'products': [],
                        'total_in_category': len(products),
                        'results_returned': 0,
                        'no_similar_message': f"No se encontraron productos similares en {category_name}. Intenta con otra imagen o ajusta la búsqueda."
                    }
                    continue

                # Ordenar por similitud descendente
                product_similarities.sort(key=lambda x: x['similarity'], reverse=True)

                # NO limitar aún - aplicar fusión a TODOS los que pasan threshold
                # Esto permite que productos semánticamente relevantes (ej: "medio delantal")
                # pero con similitud visual más baja lleguen al pool de fusión
                fusion_candidates = product_similarities

                # Cache de embeddings de imagen para fusiones texto↔imagen
                top_image_embeddings = {
                    str(r['product'].id): r['image'].embedding_vector
                    for r in fusion_candidates
                    if getattr(r['image'], 'embedding_vector', None)
                }

                # Serializar resultados (sobre TODOS los candidatos que pasan threshold)
                products_data = []
                for result in fusion_candidates:
                    p = result['product']
                    img = result['image']

                    # Obtener imagen primaria (usar imágenes pre-cargadas)
                    primary_image = None
                    product_images = images_by_product.get(p.id, [])
                    for img_item in product_images:
                        if img_item.is_primary:
                            primary_image = img_item
                            break
                    if not primary_image:
                        primary_image = img

                    image_url = primary_image.optimized_url if primary_image else None  # Base64 cacheado

                    # Preparar atributos filtrados y extraer product_url
                    product_attrs = {}
                    product_url_value = None
                    product_color_value = None
                    try:
                        if hasattr(p, 'attributes') and p.attributes:
                            # Extraer color del producto desde atributos crudos (para re-ranking interno)
                            for color_key in ('color', 'colour', 'color_principal', 'color_secundario'):
                                raw_color = p.attributes.get(color_key)
                                if not raw_color:
                                    continue
                                if isinstance(raw_color, dict):
                                    product_color_value = raw_color.get('value') or raw_color.get('label') or raw_color.get('name')
                                elif isinstance(raw_color, list) and raw_color:
                                    first_val = raw_color[0]
                                    if isinstance(first_val, dict):
                                        product_color_value = first_val.get('value') or first_val.get('label') or first_val.get('name')
                                    else:
                                        product_color_value = first_val
                                else:
                                    product_color_value = raw_color
                                if product_color_value:
                                    break

                            # 1) Extraer url_producto del JSONB (siempre, ignorar filtros)
                            raw_url = p.attributes.get('url_producto')
                            if isinstance(raw_url, dict):
                                product_url_value = raw_url.get('value') or raw_url.get('url') or None
                            else:
                                product_url_value = raw_url

                            # 2) Filtrar atributos según configuración (usar cache)
                            if exposed_keys_cache is not None:
                                product_attrs = {
                                    k: v for k, v in p.attributes.items()
                                    if (str(k).strip().lower() in exposed_keys_cache)
                                }
                            else:
                                product_attrs = dict(p.attributes)
                    except Exception as e:
                        railway_log(f"⚠️ Error procesando atributos de {p.id}: {e}")
                        product_attrs = {}

                    # Priorizar external_url (Tiendanube/externo) sobre url_producto (atributo custom)
                    final_product_url = None
                    if hasattr(p, 'external_url') and p.external_url:
                        final_product_url = p.external_url
                    elif product_url_value:
                        final_product_url = product_url_value

                    products_data.append({
                        'id': str(p.id),
                        'name': p.name,
                        'sku': p.sku,
                        'category': category_name,
                        'price': float(p.price) if p.price else None,
                        'image_url': image_url,
                        'similarity_score': result['similarity'],
                        'attributes': product_attrs,
                        '__product_color': product_color_value,
                        'stock': p.stock if hasattr(p, 'stock') and p.stock is not None else 0,
                        'product_url': final_product_url
                    })

                # ===================================================================
                # RE-RANKING POR DESCRIPCIÓN DE GPT-4V (si Vision está habilitado)
                # ===================================================================
                if vision_enabled and prendas:
                    try:
                        # Buscar descripción para esta categoría en los prendas de GPT-4V
                        gpt4v_description = None
                        for prenda in prendas:
                            if prenda.get('categoria_sugerida') == category_name:
                                # Intentar obtener descripción de varios campos posibles
                                gpt4v_description = (
                                    prenda.get('descripcion') or
                                    prenda.get('tipo') or
                                    prenda.get('description')
                                )
                                break

                        # Si hay descripción y cliente es Goody, aplicar re-ranking custom
                        if gpt4v_description and client.name.lower() == 'goody':
                            try:
                                # 1) Fusionar similitud visual (imagen↔imagen) con texto↔imagen usando CLIP
                                try:
                                    model, processor = get_clip_model()
                                    with torch.no_grad():
                                        text_inputs = processor(
                                            text=[gpt4v_description],
                                            return_tensors="pt",
                                            padding=True,
                                            truncation=True
                                        )
                                        text_features = model.get_text_features(**text_inputs)
                                        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                                        text_embedding = text_features.squeeze().cpu().numpy().astype(np.float32)

                                    # Calcular similitud texto↔imagen por producto
                                    fused_count = 0
                                    filtered_count = 0
                                    text_boost_weight = 0.30  # Boost aditivo del texto (máx +30%)

                                    products_after_fusion = []
                                    for p in products_data:
                                        pid = p.get('id')
                                        img_emb = top_image_embeddings.get(pid)
                                        if img_emb is None:
                                            continue

                                        img_vec = np.array(img_emb, dtype=np.float32)
                                        norm = np.linalg.norm(img_vec)
                                        if norm == 0:
                                            continue
                                        img_vec = img_vec / norm

                                        visual_score = p['similarity_score']
                                        text_sim = float(np.dot(img_vec, text_embedding))

                                        # Modelo ADITIVO: texto como boost sobre visual (nunca penaliza)
                                        text_contribution = text_sim * text_boost_weight
                                        fused_score = min(visual_score + text_contribution, 1.0)

                                        # Filtrar productos que caen bajo threshold tras fusión
                                        if fused_score < threshold:
                                            filtered_count += 1
                                            continue

                                        p['similarity_score'] = fused_score
                                        p['_hybrid_similarity'] = {
                                            'visual': visual_score,
                                            'text_image': text_sim,
                                            'text_boost': text_contribution,
                                            'boost_weight': text_boost_weight
                                        }
                                        products_after_fusion.append(p)
                                        fused_count += 1

                                    # Reemplazar products_data con productos filtrados
                                    products_data = products_after_fusion

                                    if fused_count > 0:
                                        products_data.sort(key=lambda x: x['similarity_score'], reverse=True)
                                        if filtered_count > 0:
                                            railway_log(f"   🔀 Boost textual aditivo aplicado a {fused_count} productos (peso={text_boost_weight}), {filtered_count} eliminados por threshold")
                                        else:
                                            railway_log(f"   🔀 Boost textual aditivo aplicado a {fused_count} productos (peso={text_boost_weight})")

                                        # Log top 20 productos post-fusión (para debug)
                                        railway_log(f"   📊 Top-20 post-boost:")
                                        for idx, p in enumerate(products_data[:20], 1):
                                            hybrid = p.get('_hybrid_similarity', {})
                                            railway_log(
                                                f"      {idx}. {p['name'][:55]}: "
                                                f"final={p['similarity_score']:.4f} "
                                                f"(v={hybrid.get('visual', 0):.4f} + "
                                                f"boost={hybrid.get('text_boost', 0):.4f})"
                                            )

                                        # Expandir pool para re-ranking (8x el límite final = 24 productos)
                                        # Esto da más oportunidades a productos semánticamente relevantes
                                        fusion_limit = max_results * 8
                                        if len(products_data) > fusion_limit:
                                            railway_log(f"   ✂️ Limitando de {len(products_data)} a {fusion_limit} productos para re-ranking")
                                            products_data = products_data[:fusion_limit]

                                except Exception as fusion_error:
                                    railway_log(f"⚠️ Error en fusión visual+texto: {fusion_error}")

                                # 2) Re-ranking custom por descripción (tokens en nombres)
                                from app.search_modules import has_custom_module, get_client_module

                                if has_custom_module(client.name.lower()):
                                    module = get_client_module(client.name.lower())

                                    # Llamar a función de re-ranking si existe
                                    if hasattr(module, 'rerank_visual_results_by_description'):
                                        railway_log(f"   🎯 Re-ranking visual por descripción: '{gpt4v_description[:60]}...'")

                                        # Convertir products_data al formato para re-ranking
                                        results_for_rerank = [
                                            {
                                                'name': p['name'],
                                                'score': p['similarity_score']
                                            }
                                            for p in products_data
                                        ]

                                        # Aplicar re-ranking
                                        reranked = module.rerank_visual_results_by_description(
                                            results_for_rerank,
                                            gpt4v_description
                                        )

                                        # Re-ordenar products_data según nuevo ranking
                                        # El re-ranking devuelve la lista re-ordenada con scores actualizados
                                        products_reranked_dict = {r['name']: r for r in reranked}

                                        # Actualizar scores en products_data
                                        for p in products_data:
                                            if p['name'] in products_reranked_dict:
                                                rerank_info = products_reranked_dict[p['name']]
                                                # Actualizar score y guardar info de boost
                                                p['similarity_score'] = rerank_info.get('score', p['similarity_score'])
                                                if 'boost_info' in rerank_info:
                                                    p['_boost_applied'] = rerank_info['boost_info']

                                        # Re-ordenar por nuevo score
                                        products_data.sort(key=lambda x: x['similarity_score'], reverse=True)

                                        railway_log(f"   ✅ Re-ranking aplicado a {len(products_data)} productos")

                                        # Log top 12 productos post-reranking
                                        railway_log(f"   📊 Top-12 post-reranking:")
                                        for idx, p in enumerate(products_data[:12], 1):
                                            boost_info = p.get('_boost_applied', {})
                                            matches_str = ', '.join(boost_info.get('matches', []))
                                            railway_log(
                                                f"      {idx}. {p['name'][:50]}: "
                                                f"score={p['similarity_score']:.4f}, "
                                                f"boost={boost_info.get('factor', 1.0):.2f} "
                                                f"[{matches_str[:60]}]"
                                            )
                            except ImportError:
                                # Módulos custom no disponibles, continuar sin re-ranking
                                pass
                    except Exception as e:
                        railway_log(f"⚠️ Error en re-ranking visual: {e}")
                        import traceback
                        traceback.print_exc()
                        # Continuar sin re-ranking

                # Prioridad por color (opcional por cliente)
                if color_priority_enabled and vision_enabled and prendas and products_data:
                    try:
                        canonical_palette = {
                            'negro': 'black',
                            'blanco': 'white',
                            'gris': 'gray',
                            'azul': 'blue',
                            'celeste': 'light blue',
                            'verde': 'green',
                            'rojo': 'red',
                            'rosa': 'pink',
                            'marron': 'brown',
                            'beige': 'beige',
                            'amarillo': 'yellow',
                            'violeta': 'purple',
                            'naranja': 'orange',
                        }
                        color_aliases = {
                            'negro': 'negro', 'black': 'negro',
                            'blanco': 'blanco', 'white': 'blanco', 'crudo': 'blanco', 'off white': 'blanco', 'offwhite': 'blanco',
                            'gris': 'gris', 'gray': 'gris', 'grey': 'gris',
                            'azul': 'azul', 'blue': 'azul', 'marino': 'azul', 'navy': 'azul', 'jean': 'azul', 'denim': 'azul',
                            'celeste': 'celeste', 'light blue': 'celeste',
                            'verde': 'verde', 'green': 'verde',
                            'rojo': 'rojo', 'red': 'rojo', 'bordo': 'rojo', 'burgundy': 'rojo',
                            'rosa': 'rosa', 'rosado': 'rosa', 'pink': 'rosa',
                            'marron': 'marron', 'marrón': 'marron', 'brown': 'marron', 'chocolate': 'marron', 'habano': 'marron', 'tostado': 'marron',
                            'beige': 'beige', 'arena': 'beige',
                            'amarillo': 'amarillo', 'yellow': 'amarillo',
                            'violeta': 'violeta', 'morado': 'violeta', 'purple': 'violeta',
                            'naranja': 'naranja', 'orange': 'naranja',
                        }

                        def _normalize_text_local(value: str) -> str:
                            s = str(value or '').strip().lower()
                            s = s.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                            s = re.sub(r'[^a-z\s]', ' ', s)
                            s = re.sub(r'\s+', ' ', s).strip()
                            return s

                        def _canonicalize_color_local(raw_color):
                            if not raw_color:
                                return None

                            normalized = _normalize_text_local(raw_color)
                            if not normalized:
                                return None

                            for alias, canonical in color_aliases.items():
                                pattern = rf'(^|\s){re.escape(alias)}(\s|$)'
                                if re.search(pattern, normalized):
                                    return canonical

                            return None

                        if color_text_matrix_cache is None or color_keys_cache is None:
                            color_text_matrix_cache, color_keys_cache = _build_global_color_text_cache(
                                model=model,
                                processor=processor
                            )

                        color_text_matrix = color_text_matrix_cache
                        color_keys = color_keys_cache

                        def _infer_color_from_clip_embedding(embedding_vector):
                            if embedding_vector is None:
                                return None, 0.0
                            emb = np.asarray(embedding_vector, dtype=np.float32)
                            emb_norm = np.linalg.norm(emb)
                            if emb_norm == 0:
                                return None, 0.0
                            emb = emb / emb_norm
                            sims = np.dot(color_text_matrix, emb)
                            best_idx = int(np.argmax(sims))
                            return color_keys[best_idx], float(sims[best_idx])

                        detected_color_for_category = None
                        detected_description_for_category = None
                        for prenda in prendas:
                            if prenda.get('categoria_sugerida') == category_name:
                                if not detected_description_for_category:
                                    detected_description_for_category = (
                                        prenda.get('descripcion') or
                                        prenda.get('description') or
                                        prenda.get('tipo')
                                    )
                                detected_color_for_category = prenda.get('color') or prenda.get('color_detectado')
                                if detected_color_for_category:
                                    break

                        detected_color_norm = _canonicalize_color_local(detected_color_for_category)
                        detected_color_source = 'prenda' if detected_color_norm else None

                        if not detected_color_norm:
                            inferred_query_color, inferred_query_conf = _infer_color_from_clip_embedding(query_embedding)
                            if inferred_query_color:
                                detected_color_norm = inferred_query_color
                                detected_color_source = 'clip_query'
                                railway_log(
                                    f"   🎨 Color inferido por CLIP (query) en '{category_name}': color='{detected_color_norm}', score={inferred_query_conf:.4f}"
                                )

                        if detected_color_norm:
                            color_boost = 0.12
                            boosted_count = 0
                            inferred_catalog_color_count = 0
                            name_fallback_color_count = 0

                            for prod in products_data:
                                product_color_norm = _canonicalize_color_local(prod.get('__product_color'))

                                if not product_color_norm:
                                    inferred_product_color, inferred_product_conf = _infer_color_from_clip_embedding(
                                        top_image_embeddings.get(prod.get('id'))
                                    )
                                    if inferred_product_color:
                                        product_color_norm = inferred_product_color
                                        inferred_catalog_color_count += 1
                                        prod['__product_color_inferred'] = {
                                            'color': inferred_product_color,
                                            'score': round(inferred_product_conf, 4)
                                        }

                                if not product_color_norm:
                                    product_color_norm = _canonicalize_color_local(prod.get('name'))
                                    if product_color_norm:
                                        name_fallback_color_count += 1

                                if not product_color_norm:
                                    continue

                                if product_color_norm == detected_color_norm:
                                    prod['similarity_score'] = min(1.0, float(prod.get('similarity_score', 0.0)) + color_boost)
                                    boosted_count += 1

                            if boosted_count > 0:
                                products_data.sort(key=lambda x: x.get('similarity_score', 0.0), reverse=True)
                                railway_log(
                                    f"   🎨 Prioridad color activa en '{category_name}': color='{detected_color_norm}', fuente='{detected_color_source}', boost={color_boost}, afectados={boosted_count}, inferidos_catalogo={inferred_catalog_color_count}, fallback_nombre={name_fallback_color_count}"
                                )
                    except Exception as color_priority_error:
                        railway_log(f"⚠️ Error aplicando prioridad por color: {color_priority_error}")

                # Aplicar límite por categoría SIEMPRE (independiente de la rama de procesamiento)
                effective_max_results = max(1, int(max_results))
                if len(products_data) > effective_max_results:
                    railway_log(
                        f"   ✂️ Limitar categoría '{category_name}' de {len(products_data)} a {effective_max_results} productos"
                    )
                    products_data = products_data[:effective_max_results]

                # Limpiar campos internos de cálculo antes de responder
                for prod in products_data:
                    prod.pop('__product_color', None)
                    prod.pop('__product_color_inferred', None)

                total_products_found += len(products_data)

                results_by_category[category_name] = {
                    'products': products_data,
                    'total_in_category': len(products),
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
                "similarity_threshold": threshold,
                # Mapas auxiliares para UI: etiquetas y tipos de atributos expuestos
                "exposed_attribute_labels": exposed_labels_map,
                "exposed_attribute_types": exposed_types_map
            }
        }

        railway_log(f"✅ Búsqueda completada: {total_products_found} productos en {processing_time:.0f}ms")

        # 📊 ANALYTICS: Registrar búsqueda (async)
        try:
            # Extraer categorías detectadas y matcheadas
            cats_detected = categories_detected if categories_detected else []
            cats_matched = [name for name, data in results_by_category.items() if data.get('results_returned', 0) > 0]
            cats_missing = [c for c in cats_detected if c not in cats_matched]

            SearchLog.log_search(
                client_id=client.id,
                search_type='gpt4v_visual',
                query_text=None,
                image_url=None,  # No guardamos imagen por privacidad
                categories_detected=cats_detected,
                categories_matched=cats_matched,
                categories_missing=cats_missing,
                results_count=total_products_found,
                response_time_ms=int(processing_time),
                threshold_used=threshold
            )
        except Exception as log_err:
            railway_log(f"⚠️ Error logging analytics: {log_err}")

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



