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
            model_name = os.getenv("SPACY_MODEL", "es_core_news_sm")
            # Deshabilitar componentes no necesarios para reducir overhead
            _SPACY_NLP = spacy.load(model_name, disable=["parser", "ner", "textcat"])
            railway_log(f"spaCy cargado: {model_name}")
            print(f"✅ spaCy modelo '{model_name}' cargado exitosamente", flush=True)
        except Exception as e:
            railway_log(f"❌ CRITICAL: spaCy no disponible: {e}")
            print(f"❌ CRITICAL: spaCy no disponible: {e}", flush=True)
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
    print(f"[RAILWAY] {message}", file=sys.stderr, flush=True)


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
    """DEPRECATED: redirige al endpoint unificado `/api/search`.

    Mantener un único punto público evita divergencias entre rutas. Esta
    ruta se conserva solo por compatibilidad y responde con 307 para
    preservar método y cuerpo de la petición.
    """
    if request.method == 'OPTIONS':
        # Responder preflight de forma consistente
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    # 307 mantiene el método POST y el cuerpo en la redirección
    return redirect(url_for('api.visual_search'), code=307)

# Función movida a app.blueprints.search_visual


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


def text_search():
    """
    ⚠️⚠️⚠️ DEPRECATED - NO USAR ⚠️⚠️⚠️

    Este endpoint está OBSOLETO y será removido en futuras versiones.

    USE EN SU LUGAR: /api/search/text (nuevo endpoint con Two-Stage Retrieval)

    El nuevo sistema implementa:
    - Two-Stage Retrieval (SQL + CLIP reranking)
    - Auto-generación de sinónimos con GPT-4
    - PostgreSQL SIMILAR TO para fuzzy matching
    - CLIP text-to-text embeddings

    Migración:
    - Old: POST /api/search/text (este endpoint)
    - New: POST /api/search/text (blueprint search_text)

    Esta función ya NO está registrada como ruta.
    El widget V3 ya usa el nuevo endpoint.

    ===================================================================
    DOCUMENTACIÓN ORIGINAL (DEPRECADA):
    ===================================================================
    Endpoint de búsqueda por texto con vectorización optimizada.
    Endpoint de bÃºsqueda textual hÃ­brida (CLIP + Atributos + Tags)

    Headers:
        X-API-Key: API Key del cliente

    JSON Body:
        query: Texto de bÃºsqueda (ej: "camisa blanca", "delantal marrÃ³n")
        limit: NÃºmero de resultados (default: 10, max: 50)
    """
    # ⚠️ ESTA FUNCIÓN YA NO SE USA
    # ⚠️ El código debajo solo se mantiene para referencia histórica
    # ⚠️ TODO: Remover en próxima versión mayor

    return jsonify({
        "success": False,
        "error": "deprecated_endpoint",
        "message": "Este endpoint está deprecado. Use /api/search/text del nuevo blueprint search_text.",
        "migration_url": "/api/search/text",
        "new_system": "Two-Stage Retrieval con auto-sinónimos GPT-4"
    }), 410  # 410 Gone = recurso removido permanentemente

    # CÓDIGO ORIGINAL DEPRECADO (NO EJECUTAR):
    """
    Endpoint de bÃºsqueda textual hÃ­brida (CLIP + Atributos + Tags)

    Headers:
        X-API-Key: API Key del cliente

    JSON Body:
        query: Texto de bÃºsqueda (ej: "camisa blanca", "delantal marrÃ³n")
        limit: NÃºmero de resultados (default: 10, max: 50)
    """
    # Imports necesarios para el scope de la función
    import json
    import numpy as np
    from app.models.embedding import Embedding

    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    import uuid
    start_time = time.time()
    request_id = str(uuid.uuid4())
    # Contenedor de métricas por fase
    t_norm_end = t_clip_model_end = t_text_embed_end = t_category_detection_end = t_sql_end = 0.0
    original_N = final_N = 0

    try:
        # Log temprano para verificar llegada de requests incluso si falla la API Key
        print(f"[REQ {request_id}] TEXT SEARCH HIT: path={request.path} from={request.remote_addr} has_key={'X-API-Key' in request.headers}", flush=True)
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

        print(f"[REQ {request_id}] TEXT SEARCH: Query='{query_text}' Client={client.name} Limit={limit}", flush=True)

        # --- LLM Normalization (con vocabulario dinÃ¡mico del cliente) ---
        # 🚫 DESACTIVADO TEMPORALMENTE: MiniLM no aporta valor vs tokens y agrega latencia
        # t_before_norm = time.time()
        # print(f"[REQ {request_id}] ⏱️ ANTES normalize_query: t={time.time()-start_time:.3f}s", flush=True)
        # llm_norm = normalize_query(query_text, client_id=client.id)
        # print(f"[REQ {request_id}] ⏱️ DESPUÉS normalize_query: t={time.time()-start_time:.3f}s (normalize tomó {time.time()-t_before_norm:.3f}s)", flush=True)
        # print(f"[REQ {request_id}] DEBUG: normalize_query completado", flush=True)
        # print(f"[REQ {request_id}] LLM Normalizer: tipo={llm_norm.get('tipo')}, color={llm_norm.get('color')}, contexto={llm_norm.get('contexto')}")
        llm_norm = {'tipo': None, 'color': None, 'contexto': []}  # Placeholder para mantener compatibilidad
        t_norm_end = time.time()

        # Extraer campos del normalizador para usar en boosts
        detected_color = llm_norm.get('color', '').lower() if llm_norm.get('color') else None
        detected_tipo = llm_norm.get('tipo', '').lower() if llm_norm.get('tipo') else None

        # Helpers para normalizar colores y detectar color explícito
        def _strip_accents(s: str) -> str:
            try:
                import unicodedata as _ud
                return ''.join(c for c in _ud.normalize('NFD', s) if _ud.category(c) != 'Mn')
            except Exception:
                return s

        def _canonical_color(s: str) -> str:
            """Normaliza colores eliminando acentos y espacios (sin hardcodear sinónimos)"""
            if not s:
                return s
            s0 = _strip_accents(str(s).lower()).strip()
            # Corrección de typo común
            if s0 == 'baige':
                s0 = 'beige'
            return s0

        # spaCy es OBLIGATORIO para tokenización con lematización
        import unicodedata

        def tokenize(texto: str):
            """
            Tokeniza texto usando spaCy (OBLIGATORIO).
            Aplica lematización automática y filtrado de stopwords nativo.
            """
            nlp = _get_spacy_nlp()
            if nlp is None:
                error_msg = "🚨 CRITICAL: spaCy no está disponible. El sistema requiere spaCy para tokenización."
                print(f"[REQ {request_id}] {error_msg}", flush=True)
                raise RuntimeError(error_msg)

            doc = nlp(texto or "")
            toks = set()
            for tok in doc:
                # Filtrar tokens no alfabéticos y stopwords (spaCy ya los detecta)
                if not tok.is_alpha or tok.is_stop:
                    continue
                # Lema normalizado: minúsculas, sin acentos, solo alfanuméricos
                lemma = tok.lemma_.lower()
                lemma = ''.join(c for c in unicodedata.normalize('NFD', lemma) if unicodedata.category(c) != 'Mn')
                lemma = re.sub(r"[^a-z0-9]+", "", lemma)
                if lemma and len(lemma) >= 2:
                    toks.add(lemma)
            return toks

        # Extraer color directamente de la query usando vocabulario dinámico del cliente
        # spaCy ya normaliza plurales/género en tokenize()
        from app.utils.llm_query_normalizer import _extract_client_vocabulary
        client_vocab = _extract_client_vocabulary(client.id)
        client_colors = set(client_vocab.get('colores', []))

        # Usar tokenize() que ya aplica lematización via spaCy si está habilitado
        query_token_set = tokenize(query_text)
        query_colors = [t for t in query_token_set if t in client_colors]
        explicit_color_from_query = False
        if query_colors:
            # Priorizar color explícito en query sobre LLM normalizer
            canon_llm_color = _canonical_color(detected_color) if detected_color else None
            if canon_llm_color != query_colors[0]:
                print(f"[REQ {request_id}] 🎨 Color query ('{query_colors[0]}') difiere de LLM ('{canon_llm_color}') → usando query")
                detected_color = query_colors[0]
                llm_norm['color'] = detected_color  # Actualizar también el dict que se devuelve
            else:
                detected_color = canon_llm_color
            explicit_color_from_query = True
        else:
            detected_color = _canonical_color(detected_color) if detected_color else None

        # Contexto puede ser lista o string
        contexto_raw = llm_norm.get('contexto')
        if isinstance(contexto_raw, list):
            detected_context = contexto_raw  # Ya es lista
        elif isinstance(contexto_raw, str):
            detected_context = [contexto_raw.lower()]
        else:
            detected_context = None        # Expandir modificadores de color con colores del cliente
        expanded_query = expand_color_modifiers(query_text, client_id=str(client.id))
        if expanded_query != query_text:
            print(f"ðŸ”„ Query expandido: '{query_text}' -> '{expanded_query}'")

        # Generar embedding CLIP del texto de búsqueda (usar query expandido)
        import time as _t
        _t0 = _t.time()
        print(f"[REQ {request_id}] DEBUG: entrando a get_clip_model()", flush=True)
        model, processor = get_clip_model()
        print(f"[REQ {request_id}] DEBUG: get_clip_model listo en {(_t.time()-_t0):.2f}s", flush=True)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        t_clip_model_end = time.time()

        _t1 = _t.time()
        with torch.no_grad():
            text_inputs = processor(text=[expanded_query], return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            query_embedding = text_features.cpu().numpy()[0]
        print(f"[REQ {request_id}] DEBUG: embedding texto generado en {(_t.time()-_t1):.2f}s", flush=True)
        t_text_embed_end = time.time()

        # Usar query expandido para matching de atributos tambiÃ©n
        query_lower = expanded_query.lower()

        # Intentar detectar categorÃ­a en el query mediante tokens normalizados
        detected_category = None
        detected_category_via = None  # 'name' | 'name_en' | 'alt' | 'tokens' | 'llm'
        category_substitution_info = None  # Mensaje para UI cuando hay sustitución/similitud
        categories = Category.query.filter_by(client_id=client.id, is_active=True).all()


        query_tokens = tokenize(expanded_query)
        print(f"[REQ {request_id}] Query tokens: {query_tokens}")

        # DetecciÃ³n mejorada: evaluar TODAS las categorÃ­as y elegir la mejor coincidencia
        # Buscar coincidencia priorizando matches más largos/específicos
        best_category = None
        best_score = 0
        best_match_length = 0  # Longitud del match (para priorizar matches más largos)

        # 1. Prioridad: Buscar match de palabra completa con scoring por longitud
        query_normalized = expanded_query.lower().strip()
        query_tokens = set(query_normalized.split())  # Tokens del query

        # Evaluar TODAS las categorías y quedarnos con el mejor match
        for category in categories:
            # Tokenizar nombres de categorías
            name_tokens = set(category.name.lower().split())
            name_en_tokens = set(category.name_en.lower().split()) if category.name_en else set()

            # Calcular intersección (tokens compartidos)
            name_intersection = query_tokens & name_tokens
            name_en_intersection = query_tokens & name_en_tokens

            # Priorizar el match con MÁS tokens en común
            if name_intersection and len(name_intersection) > best_match_length:
                detected_category = category
                detected_category_via = 'name'
                best_match_length = len(name_intersection)
                print(f"[REQ {request_id}] Mejor match encontrado: {category.name} ({len(name_intersection)} tokens)")

            if name_en_intersection and len(name_en_intersection) > best_match_length:
                detected_category = category
                detected_category_via = 'name_en'
                best_match_length = len(name_en_intersection)
                print(f"[REQ {request_id}] Mejor match encontrado: {category.name} via name_en ({len(name_en_intersection)} tokens)")

        # Si detectamos por token matching, confirmar
        if detected_category:
            print(f"[REQ {request_id}] Categoría detectada por token matching: {detected_category.name}")

        # Fallback: alternative_terms (búsqueda EXACTA en lista separada por comas)
        if not detected_category:
            for category in categories:
                alt = getattr(category, 'alternative_terms', None)
                if alt:
                    alt_terms = [t.strip().lower() for t in str(alt).split(',')]
                    # Buscar match exacto en alternative_terms
                    if query_normalized in alt_terms:
                        detected_category = category
                        detected_category_via = 'alt'
                        print(f"[REQ {request_id}] Categoría detectada por alternative_term exacto: {category.name}")
                        break

        # 2. Si no hay coincidencia, usar similitud semántica CLIP/MiniLM
        if not detected_category:
            # Usar CLIP text embedding + centroides en lugar de MiniLM
            candidates = []  # Para debugging
            for category in categories:
                # Solo categorías con productos activos
                if Product.query.filter_by(category_id=category.id, client_id=client.id).count() == 0:
                    continue
                # Obtener centroide CLIP de la categoría (no MiniLM)
                centroid = category.get_centroid_embedding(auto_calculate=False)
                if centroid is None:
                    continue

                # Similitud coseno con CLIP (ya tenemos query_embedding de línea 1619)
                similarity = float(np.dot(query_embedding, centroid) / (np.linalg.norm(query_embedding) * np.linalg.norm(centroid)))
                candidates.append((category, similarity))

                if similarity > best_score:
                    best_score = similarity
                    best_category = category

            if candidates:
                # Log top 5 candidatos ordenados por similitud
                sorted_candidates = sorted(candidates, key=lambda x: x[1], reverse=True)[:5]
                print(f"[REQ {request_id}] Candidatos de categoría CLIP: {[(c[0].name, f'{c[1]:.2f}') for c in sorted_candidates]}", flush=True)

            # Umbral mínimo de similitud CLIP (0.55 = similar, CLIP es más preciso que MiniLM)
            SEMANTIC_THRESHOLD = 0.55
            if best_category and best_score >= SEMANTIC_THRESHOLD:
                detected_category = best_category
                detected_category_via = 'semantic'
                print(f"[REQ {request_id}] Categoría detectada por CLIP centroid (score={best_score:.3f}): {detected_category.name}", flush=True)

        # 2.b Ya no usamos fallback de Levenshtein - similitud semántica lo reemplaza

        # Si detectamos por similitud semántica (no literal), exponer mensaje de sustitución como 'similar'
        if detected_category and detected_category_via == 'semantic':
            category_substitution_info = {
                "match_type": "similar",
                "requested_text": query_text,
                "matched_category": detected_category.name,
                "similarity": round(best_score, 3)
            }
            print(f"[REQ {request_id}] ⚠️ Match similar por similitud semántica: '{query_text}' → '{detected_category.name}' score={best_score:.3f}")

        # Nueva lógica de selección de categoría con LLM: exacta / similar / ninguna (solo si no hubo match previo)
        if not detected_category:
            from sentence_transformers import util
            llm_model = get_model()
            query_emb = llm_model.encode(expanded_query.lower(), convert_to_tensor=False)

            cat_sims = []
            for cat in categories:
                # Solo categorías con productos activos
                if Product.query.filter_by(category_id=cat.id, client_id=client.id).count() == 0:
                    continue
                # 🔥 USAR CACHÉ DE EMBEDDINGS en lugar de recalcular
                cat_emb = _get_category_embedding(cat.name, str(client.id))
                sim = float(util.cos_sim(query_emb, cat_emb)[0][0])
                cat_sims.append((cat, sim))

            if not cat_sims:
                print(f"[REQ {request_id}] ❌ Sin categorías con productos para este cliente")
                print(f"[TEXT_SEARCH] END 404 no_categories in {round(time.time()-start_time,3)}s")
                return jsonify({
                    "success": False,
                    "error": "no_categories",
                    "message": "El cliente no tiene categorías con productos activos.",
                    "processing_time": round(time.time() - start_time, 3)
                }), 404

            # Ordenar por similitud
            cat_sims.sort(key=lambda x: x[1], reverse=True)
            best_cat, best_sim = cat_sims[0]
            print(f"[REQ {request_id}] LLM categoría top: {best_cat.name} sim={best_sim:.3f}")

            LITERAL_THRESHOLD = 0.90
            SIMILAR_THRESHOLD = 0.55  # Bajado de 0.65 para permitir queries con modificadores de color (ej: "campera roja" = 0.599)

            # Preparar contenedor para información de sustitución (similar match por LLM)

            # Normalización simple para comparación literal
            import unicodedata
            def _norm(s: str) -> str:
                s = ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
                s = re.sub(r"[^a-z0-9]+", " ", s).strip()
                return s

            literal_match = _norm(best_cat.name) == _norm(expanded_query)

            if literal_match or best_sim >= LITERAL_THRESHOLD:
                detected_category = best_cat
                print(f"[REQ {request_id}] ✅ Match literal categoría: {best_cat.name}")
            elif best_sim >= SIMILAR_THRESHOLD:
                detected_category = best_cat

                category_substitution_info = {
                    "match_type": "similar",
                    "requested_text": query_text,
                    "matched_category": best_cat.name,
                    "similarity": round(best_sim, 3)
                }
                print(f"[REQ {request_id}] ⚠️ Match similar categoría: '{query_text}' → '{best_cat.name}' sim={best_sim:.3f}")
            else:
                print(f"[REQ {request_id}] ❌ Ninguna categoría relevante (max_sim={best_sim:.3f})")
                available_categories = [c.name for c in categories if Product.query.filter_by(category_id=c.id, client_id=client.id).count() > 0]
                print(f"[TEXT_SEARCH] END controlled no-category (200) in {round(time()-start_time,3)}s")
                return jsonify({
                    "success": False,
                    "error": "product_not_in_catalog",
                    "message": f"No comercializamos productos relacionados con '{query_text}'.",
                    "query": query_text,
                    "available_categories": available_categories,
                    "results": [],
                    "processing_time": round(time.time() - start_time, 3)
                }), 200

        # Fin detección de categoría (tokens + LLM)
        t_category_detection_end = time.time()

        # 🔗 DETECCIÓN DE CATEGORÍAS HERMANAS (solo si NO hay exact match)
        # Si category_substitution_info existe = NO fue exact match → buscar hermanas
        if detected_category and category_substitution_info:
            from sentence_transformers import util
            sibling_categories = []
            try:
                SIBLING_THRESHOLD = 0.75  # Umbral para considerar "hermanas"
                detected_cat_emb = _get_category_embedding(detected_category.name, str(client.id))

                # Obtener TODAS las categorías del cliente (excepto la detectada)
                all_categories = Category.query.filter_by(
                    client_id=client.id,
                    is_active=True
                ).filter(Category.id != detected_category.id).all()

                for other_cat in all_categories:
                    # Solo categorías con productos
                    if Product.query.filter_by(category_id=other_cat.id, client_id=client.id).count() == 0:
                        continue

                    other_cat_emb = _get_category_embedding(other_cat.name, str(client.id))
                    if not other_cat_emb or not detected_cat_emb:
                        continue

                    # Similitud entre categorías (no query)
                    cat_to_cat_sim = float(util.cos_sim(detected_cat_emb, other_cat_emb)[0][0])
                    if cat_to_cat_sim >= SIBLING_THRESHOLD:
                        sibling_categories.append({
                            "name": other_cat.name,
                            "similarity_to_detected": round(cat_to_cat_sim, 3)
                        })

                if sibling_categories:
                    # Ordenar por similitud descendente
                    sibling_categories.sort(key=lambda x: x['similarity_to_detected'], reverse=True)
                    # Limitar a top 5
                    sibling_categories = sibling_categories[:5]
                    category_substitution_info['sibling_categories'] = sibling_categories
                    print(f"[REQ {request_id}] 🔗 Categorías hermanas detectadas: {[s['name'] for s in sibling_categories]}")
            except Exception as e:
                print(f"[REQ {request_id}] ⚠️ Error detectando hermanas: {e}")
                import traceback
                traceback.print_exc()

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
                    print(f"[REQ {request_id}] FUSION: alpha={alpha} beta_tag={beta_tag} phrases={len(tag_phrases)} tags={len(inferred_tags)}")
        except Exception as _e:
            # Fallback silencioso: si algo falla seguimos con embedding original
            print(f"âš ï¸ FUSION skip: {_e}")
            import traceback
            traceback.print_exc()


        # Consultar productos con embeddings (de imágenes principales), atributos y tags
        _t2 = _t.time()
        print(f"[REQ {request_id}] DEBUG: iniciando query SQL de productos...", flush=True)
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
            print(f"[REQ {request_id}] Filtrando productos por categoría: {detected_category.name}")
        else:
            print(f"[REQ {request_id}] Búsqueda SIN filtro de categoría (global)")

        products = products_query.all()
        print(f"[REQ {request_id}] DEBUG: query SQL ejecutada en {(_t.time()-_t2):.2f}s → {len(products)} productos", flush=True)
        t_sql_end = time.time()

        # 🔄 FALLBACK A CATEGORÍAS HERMANAS: Si categoría detectada está vacía, intentar con hermanas
        original_category_name = None
        used_sibling_category = False
        if detected_category and len(products) == 0:
            print(f"⚠️ TEXT SEARCH: Categoría '{detected_category.name}' sin productos → Intentando categorías hermanas...")

            # Verificar si hay categorías hermanas detectadas previamente
            if category_substitution_info and 'sibling_categories' in category_substitution_info:
                sibling_categories = category_substitution_info['sibling_categories']
                print(f"[REQ {request_id}] 🔗 Intentando buscar en {len(sibling_categories)} categorías hermanas")

                original_category_name = detected_category.name

                # Intentar con cada categoría hermana hasta encontrar productos
                for sibling in sibling_categories:
                    sibling_cat = Category.query.filter_by(
                        client_id=client.id,
                        name=sibling['name'],
                        is_active=True
                    ).first()

                    if sibling_cat:
                        print(f"[REQ {request_id}] 🔍 Probando categoría hermana: {sibling_cat.name}")

                        # Buscar productos en categoría hermana
                        sibling_products_query = db.session.query(
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
                            Product.category_id == sibling_cat.id,
                            Image.clip_embedding.isnot(None)
                        )

                        sibling_products = sibling_products_query.all()

                        if len(sibling_products) > 0:
                            print(f"[REQ {request_id}] ✅ Encontrados {len(sibling_products)} productos en categoría hermana '{sibling_cat.name}'")
                            products = sibling_products
                            detected_category = sibling_cat
                            used_sibling_category = True
                            break

            # Si aún no hay productos después de probar hermanas, retornar error 404
            if len(products) == 0:
                print(f"⚠️ TEXT SEARCH: No hay productos ni en categoría original ni en hermanas → Retornando error 404")
                available_categories = [cat.name for cat in categories if Product.query.filter_by(category_id=c.id, client_id=client.id).count() > 0]
                print(f"[TEXT_SEARCH] END 404 category_empty (tried siblings) in {round(time.time()-start_time,3)}s")
                return jsonify({
                    "success": False,
                    "error": "category_empty",
                    "message": f"No tenemos productos en '{original_category_name or detected_category.name}' actualmente.",
                    "detected_category": original_category_name or detected_category.name,
                    "available_categories": available_categories[:10],
                    "suggestion_message": "Explora nuestras categorías disponibles.",
                    "processing_time": round(time.time() - start_time, 3)
                }), 404

        print(f"[REQ {request_id}] TEXT SEARCH: Analizando {len(products)} productos...")
        _post_sql_t = _t.time()
        print(f"[REQ {request_id}] DEBUG: post-SQL → iniciando scoring VECTORIZADO de productos | query='{query_text}'", flush=True)

        # ========================================================================
        # OPTIMIZACIÓN VECTORIZADA: Parse todos los embeddings una sola vez
        # ========================================================================
        _parse_start = _t.time()
        embeddings_matrix = []
        valid_products = []
        skipped_count = 0
        skip_reasons = {"json_parse": 0, "invalid_array": 0, "wrong_shape": 0, "other": 0}

        for prod in products:
            embedding = prod.clip_embedding
            if isinstance(embedding, str):
                try:
                    embedding = json.loads(embedding)
                except Exception as e:
                    print(f"[REQ {request_id}] ⚠️ SKIP producto {prod.name} ({prod.sku}): error parsing JSON embedding: {e}", flush=True)
                    skipped_count += 1
                    skip_reasons["json_parse"] += 1
                    continue  # Skip productos con embeddings inválidos

            try:
                emb = np.array(embedding, dtype=np.float32)
                if not np.all(np.isfinite(emb)):
                    print(f"[REQ {request_id}] ⚠️ SKIP producto {prod.name} ({prod.sku}): embedding contiene valores no finitos (NaN/Inf)", flush=True)
                    skipped_count += 1
                    skip_reasons["invalid_array"] += 1
                    continue
                if emb.shape[0] != 512:
                    print(f"[REQ {request_id}] ⚠️ SKIP producto {prod.name} ({prod.sku}): embedding tiene shape={emb.shape} (esperado: 512)", flush=True)
                    skipped_count += 1
                    skip_reasons["wrong_shape"] += 1
                    continue
                embeddings_matrix.append(emb)
                valid_products.append(prod)
            except Exception as e:
                print(f"[REQ {request_id}] ⚠️ SKIP producto {prod.name} ({prod.sku}): error convirtiendo a numpy: {e}", flush=True)
                skipped_count += 1
                skip_reasons["other"] += 1
                continue

        print(f"[REQ {request_id}] PARSING: {len(valid_products)} válidos de {len(products)} productos (skipped={skipped_count}, reasons={skip_reasons})", flush=True)

        if not embeddings_matrix:
            print(f"[TEXT_SEARCH] END 404 no_valid_embeddings in {round(time.time()-start_time,3)}s")
            print(f"[TEXT_SEARCH_MODE] full query='{query_text}' time={round(time.time()-start_time,3)}s results=0 (no_valid_embeddings)", flush=True)
            return jsonify({
                "success": False,
                "error": "no_valid_embeddings",
                "message": "No se encontraron productos con embeddings válidos. Se intentó búsqueda larga (full pipeline).",
                "processing_mode": "full",
                "processing_time": round(time.time() - start_time, 3)
            }), 404

        # Convertir a matriz numpy (N x 512)
        E = np.vstack(embeddings_matrix).astype(np.float32)
        N = E.shape[0]
        _parse_elapsed = _t.time() - _parse_start
        print(f"[REQ {request_id}] VECTORIZED: parsed {N} embeddings in {_parse_elapsed:.3f}s", flush=True)

        # ========================================================================
        # CÁLCULO VECTORIZADO DE SIMILITUDES (una sola operación matricial)
        # ========================================================================
        _sim_start = _t.time()

        # Normalizar query embedding (una vez)
        q_norm = np.linalg.norm(query_embedding)
        if q_norm == 0 or not np.isfinite(q_norm):
            clip_similarities = np.zeros(N, dtype=np.float32)
        else:
            query_normalized = query_embedding / q_norm

            # Normalizar cada embedding en la matriz
            emb_norms = np.linalg.norm(E, axis=1, keepdims=True)
            emb_norms[emb_norms == 0] = 1.0  # Evitar división por cero
            E_normalized = E / emb_norms

            # Producto matricial: (N x 512) @ (512 x 1) = (N x 1)
            clip_similarities = E_normalized @ query_normalized
            clip_similarities = clip_similarities.astype(np.float32)

        _sim_elapsed = _t.time() - _sim_start
        print(f"[REQ {request_id}] VECTORIZED: computed {N} similarities in {_sim_elapsed:.3f}s", flush=True)

        # =============================================================
        # TOP-K TEMPRANO (memoria) PARA REDUCIR COSTO DEL BOOST LOOP
        # =============================================================
        # --------------------------------------------------------------------
        # [BACKLOG OPCIONAL] pgvector / Indexado en BD
        # Contexto: Con los volúmenes actuales (< ~200 productos activos por cliente)
        # el filtrado TOP-K en memoria + embeddings en JSON/text es suficiente y
        # mantiene la latencia muy baja (el parsing y cálculo vectorizado es << 0.2s).
        # Escenario futuro: cuando se escale a miles (1k+) de productos por cliente o
        # decenas de miles globales multi‑tenant, convendrá mover embeddings a una
        # columna vector (pgvector) y ejecutar el TOP-K directamente en PostgreSQL para
        # reducir transferencia y parsing.
        # Pasos estimados para futura migración:
        #   1. ALTER TABLE images ADD COLUMN clip_embedding_vec vector(512);
        #   2. Backfill: UPDATE images SET clip_embedding_vec = to_vector(JSON/array);
        #   3. Crear índice apropiado (ej: ivfflat u hnsw) según patrón de consultas:
        #        CREATE INDEX ON images USING ivfflat (clip_embedding_vec vector_cosine_ops)
        #        WITH (lists = 100);
        #   4. Ajustar query:
        #        SELECT ... FROM images
        #        WHERE product_id IN (...) AND clip_embedding_vec IS NOT NULL
        #        ORDER BY clip_embedding_vec <-> :query_embedding
        #        LIMIT :topk_limit;
        #   5. Medir latencia y comparar: parsing_embeddings + similarities actuales
        #        vs tiempo de ejecución del ORDER BY <-> LIMIT en PostgreSQL.
        # Criterio de activación: cuando parse_embeddings > 0.15s de forma consistente
        # o N promedio por cliente supere ~1000 y latencia total se acerque a >1.5s.
        # Nota: Mantener esta sección como referencia; no implementar hasta cumplir
        # condiciones anteriores.
        # --------------------------------------------------------------------
        # Recuperar topk_limit con fallback seguro (algunas implementaciones de system_config.get lanzan excepción si la clave no existe)
        try:
            topk_limit_cfg = system_config.get('search', 'topk_limit')  # sin valor por defecto para evitar error interno
            topk_limit = int(topk_limit_cfg) if topk_limit_cfg is not None else 300
        except Exception:
            topk_limit = 300
        original_N = N
        topk_elapsed = 0.0
        if N > topk_limit:
            _topk_start = _t.time()
            # Selección parcial sin ordenar todo el array completo (argpartition) y luego orden descendente dentro del Top-K
            top_indices = np.argpartition(clip_similarities, -topk_limit)[-topk_limit:]
            top_indices = top_indices[np.argsort(clip_similarities[top_indices])[::-1]]
            E = E[top_indices]
            clip_similarities = clip_similarities[top_indices]
            valid_products = [valid_products[i] for i in top_indices]
            N = len(valid_products)
            topk_elapsed = _t.time() - _topk_start
            print(f"[REQ {request_id}] TOPK: reducido de {original_N} a {N} en {topk_elapsed:.3f}s (limite={topk_limit})", flush=True)
        else:
            print(f"[REQ {request_id}] TOPK: sin reducción (N={N} ≤ limite={topk_limit})", flush=True)

        # ========================================================================
        # PRE-CARGAR COLOR EMBEDDINGS (evitar N+1 queries en loop)
        # ========================================================================
        _preload_start = _t.time()
        _preload_elapsed = 0.0
        color_embeddings_map = {}  # {color_lower: np.array}

        if detected_color:
            # Extraer todos los colores únicos de productos
            unique_colors = set()
            unique_colors.add(_canonical_color(detected_color))

            for prod in valid_products:
                if prod.attributes:
                    for attr_key, attr_value in prod.attributes.items():
                        if attr_key and attr_key.lower() in ['color', 'colour', 'color_principal', 'color_secundario']:
                            if isinstance(attr_value, str):
                                unique_colors.add(_canonical_color(attr_value))
                            elif isinstance(attr_value, list):
                                for v in attr_value:
                                    if v:
                                        unique_colors.add(_canonical_color(str(v)))

            # Batch query de embeddings
            if unique_colors:
                color_keys = [f"color:{c}" for c in unique_colors]
                emb_objects = Embedding.query.filter(Embedding.key.in_(color_keys), Embedding.type == 'color').all()

                for emb in emb_objects:
                    color_name = emb.key.replace('color:', '')
                    try:
                        color_embeddings_map[color_name] = np.array(json.loads(emb.embedding), dtype=np.float32)
                    except Exception:
                        pass

                _preload_elapsed = (_t.time()-_preload_start)
                print(f"[REQ {request_id}] PRELOAD: {len(color_embeddings_map)}/{len(unique_colors)} color embeddings in {_preload_elapsed:.3f}s", flush=True)

        # ========================================================================
        # CÁLCULO DE BOOSTS (aún requiere loop pero sin parsing/dot-product)
        # ========================================================================
        _boost_start = _t.time()
        results = []
        print(f"[REQ {request_id}] BOOST_LOOP: starting for {N} products", flush=True)

        for idx, (prod, clip_similarity) in enumerate(zip(valid_products, clip_similarities)):
            # Boost por atributos (pasamos el mapa de embeddings precargados)
            attr_boost = _calculate_attribute_match(
                query_lower, prod.attributes, prod.category_name,
                detected_color, detected_tipo, color_embeddings_map
            )

            # Boost por nombre y tags
            name_boost = _calculate_name_match(query_lower, prod.name, getattr(prod, 'sku', None))
            tag_boost = _calculate_tag_match(query_lower, prod.tags)
            tag_name_boost = min(1.0, tag_boost + name_boost)

            # Similitud de color (pasamos el mapa precargado)
            color_sim = _best_color_similarity(detected_color, prod.attributes, color_embeddings_map) if detected_color else 0.0

            # Prioridad por match exacto de atributo de color si el usuario pidió color
            exact_attr_color_match = False
            near_attr_color_match = False
            if detected_color and prod.attributes:
                try:
                    attr_val = prod.attributes.get('color')
                    if isinstance(attr_val, str):
                        norm_attr = _canonical_color(attr_val)
                        dc = _canonical_color(detected_color)
                        exact_attr_color_match = (norm_attr == dc)
                    elif isinstance(attr_val, list):
                        dc = _canonical_color(detected_color)
                        vals = {_canonical_color(v) for v in attr_val}
                        exact_attr_color_match = (dc in vals)
                except Exception:
                    exact_attr_color_match = False

            # Cercanía por embeddings: si no es exacto pero la similitud supera umbral "near"
            try:
                NEAR_THRESHOLD = 0.60
                if detected_color and (not exact_attr_color_match) and (color_sim >= NEAR_THRESHOLD):
                    near_attr_color_match = True
            except Exception:
                pass
            # Color group y priority
            if detected_color:
                if exact_attr_color_match:
                    # Forzar mayor prioridad si el atributo coincide exactamente con el color pedido
                    color_group = 0
                    color_priority = 3
                elif near_attr_color_match:
                    # Colores cercanos al solicitado tienen mayor prioridad que no relacionados
                    color_group = 0
                    color_priority = 2
                elif color_sim >= 0.75:
                    color_group = 0
                    color_priority = 2
                elif color_sim >= 0.45:
                    color_group = 1
                    color_priority = 1
                else:
                    color_group = 2
                    color_priority = 0
            else:
                color_group = 2
                color_priority = 0

            # Score final híbrido
            color_weight = 0.1 if detected_color and explicit_color_from_query else 0.05
            final_score = (
                float(clip_similarity) * 0.5 +
                attr_boost * 0.35 +
                color_sim * color_weight +
                tag_name_boost * 0.1
            )
            if detected_color and near_attr_color_match:
                final_score += 0.02

            results.append({
                'product_id': str(prod.id),
                'name': prod.name,
                'sku': prod.sku,
                'price': float(prod.price) if prod.price else None,
                'category': prod.category_name,
                'attributes': prod.attributes,
                'tags': prod.tags or "",
                'image_url': prod.cloudinary_url,
                'clip_similarity': round(float(clip_similarity), 4),
                'attr_boost': round(attr_boost, 4),
                'tag_boost': round(tag_boost, 4),
                'color_similarity': round(color_sim, 4),
                'color_group': color_group,
                'color_priority': color_priority,
                'exact_attr_color_match': exact_attr_color_match,
                'near_attr_color_match': near_attr_color_match,
                'name_boost': round(name_boost, 4),
                'final_score': round(final_score, 4)
            })

        _boost_elapsed = _t.time() - _boost_start
        print(f"[REQ {request_id}] BOOST_LOOP: COMPLETED in {_boost_elapsed:.3f}s for {N} products", flush=True)
        print(f"[REQ {request_id}] VECTORIZED: computed boosts for {N} products in {_boost_elapsed:.3f}s", flush=True)

        # Si la query incluye color, priorizar match/color mÃ¡s cercano antes que score puro.
        _scoring_elapsed = _t.time() - _post_sql_t
        print(f"[REQ {request_id}] DEBUG: scoring completado en {_scoring_elapsed:.2f}s para {len(results)} productos", flush=True)
        print(f"[REQ {request_id}] SORTING: starting with {len(results)} results", flush=True)
        _sort_t = _t.time()
        if detected_color:
            results.sort(key=lambda x: (x.get('color_priority', 0), x.get('color_similarity', 0.0), x['final_score']), reverse=True)
        else:
            results.sort(key=lambda x: x['final_score'], reverse=True)
        _sort_elapsed = _t.time() - _sort_t
        print(f"[REQ {request_id}] SORTING: COMPLETED in {_sort_elapsed:.3f}s", flush=True)

        # Limitar resultados
        results = results[:limit]
        print(f"[REQ {request_id}] DEBUG: ordenamiento y limit completados en {_sort_elapsed:.2f}s (top={limit})", flush=True)

        elapsed_time = time.time() - start_time


        # 🎯 Análisis de calidad de match en lugar de fallback global
        # En vez de reintentar globalmente, analizamos QUÉ encontramos y damos contexto al usuario

        if len(results) == 0:
            # No hay resultados - analizar por qué y dar feedback útil
            match_quality = "none"

            # Verificar si la categoría existe
            if detected_category:
                category_product_count = len([p for p in products if p.category_id == detected_category.id])

                # Recolectar colores disponibles de los productos cargados para esta categoría
                available_colors_set = set()
                try:
                    for prod in products:
                        if getattr(prod, 'category_id', None) != detected_category.id:
                            continue
                        attrs = getattr(prod, 'attributes', None)
                        if not attrs:
                            continue
                        val = attrs.get('color')
                        if isinstance(val, str) and val.strip():
                            available_colors_set.add(val.strip().lower())
                        elif isinstance(val, list) and val:
                            for v in val:
                                if v:
                                    available_colors_set.add(str(v).strip().lower())
                except Exception as _e:
                    print(f"[REQ {request_id}] ⚠️ Error obteniendo colores disponibles en 0-results: {_e}")

                colors_list = sorted(list(available_colors_set)) if available_colors_set else []

                if category_product_count == 0:
                    partial_match_info = {
                        "message": f"Tu búsqueda de {query_text.lower()} se interpretó dentro de la categoría {detected_category.name}, pero actualmente no tenemos productos en esa categoría.",
                        "suggestion": "Podés explorar otras categorías de nuestro catálogo.",
                        "reason": "empty_category"
                    }
                else:
                    # Categoría tiene productos pero ninguno matcheó - probablemente por atributos/color
                    base_msg = f"Tu búsqueda de {query_text.lower()} se interpretó dentro de la categoría {detected_category.name}. "

                    if explicit_color_from_query and detected_color:
                        # Mensaje específico de color no disponible + listar alternativas desde all_available_values (categoría)
                        if colors_list:
                            others_text = ", ".join(colors_list)
                            # Requerimiento: incluir la categoría en la frase
                            message = f"No tenemos {detected_category.name} disponible en color '{detected_color.lower()}'. Tenemos disponible en: {others_text}."
                            partial_match_info = {
                                "message": message,
                                "available_colors": colors_list,
                                "requested_color": detected_color.lower(),
                                "reason": "color_not_available"
                            }
                        else:
                            # Sin colores detectables en atributos
                            partial_match_info = {
                                "message": base_msg + f"No encontramos coincidencias exactas.",
                                "suggestion": "Probá buscar sin especificar color o características tan específicas.",
                                "reason": "no_attribute_match"
                            }
                    else:
                        # Sin color explícito: mensaje genérico de no match en atributos
                        partial_match_info = {
                            "message": base_msg + "No encontramos coincidencias exactas.",
                            "suggestion": "Probá usar términos más generales o quitar filtros muy específicos.",
                            "reason": "no_attribute_match"
                        }
            else:
                # No se detectó categoría o búsqueda global falló
                partial_match_info = {
                    "message": f"No encontramos productos que coincidan con tu búsqueda de {query_text.lower()}.",
                    "suggestion": "Intentá usar términos más generales o explorá nuestro catálogo completo.",
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
            # 'attribute_match_score' no existe en los resultados; usar 'attr_boost' (presente en cada item)
            best_attr_score = best_result.get('attr_boost', 0.0)

            # Determinar calidad del match
            print(f"[REQ {request_id}] QUALITY CHECK: best_color_sim={best_color_sim:.3f} (thresholds: exact≥0.75, partial≥0.60)")
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

                print(f"[REQ {request_id}] Iniciando consulta de colores disponibles")
                print(f"[REQ {request_id}]   - match_quality: {match_quality}")
                print(f"[REQ {request_id}]   - detected_color: {detected_color}")
                print(f"[REQ {request_id}]   - detected_category: {detected_category.name if detected_category else None}")
                print(f"[REQ {request_id}]   - client_id: {client.id}")

                try:
                    # Query directa a BD para obtener colores únicos de productos en esta categoría
                    color_query = db.session.query(
                        func.jsonb_extract_path_text(Product.attributes, 'color').label('color')
                    ).filter(
                        Product.client_id == client.id,
                        Product.category_id == detected_category.id if detected_category else True,
                        func.jsonb_extract_path_text(Product.attributes, 'color').isnot(None),
                        func.jsonb_extract_path_text(Product.attributes, 'color') != ''
                    ).distinct();

                    print(f"[REQ {request_id}]   - Ejecutando query SQL...")
                    color_results = color_query.all();
                    print(f"[REQ {request_id}]   - Resultados obtenidos: {len(color_results)} rows");

                    for row in color_results:
                        print(f"[REQ {request_id}]   - Row color: '{row.color}'")
                        if row.color and row.color.strip():
                            available_colors.add(row.color.strip().upper())

                    print(f"[REQ {request_id}] Colores disponibles en categoría: {available_colors}")

                except Exception as e:
                    print(f"⚠️ Error consultando colores: {e}")
                    import traceback
                    traceback.print_exc()

                    # Fallback: extraer de los resultados actuales
                    print(f"[REQ {request_id}]   - Usando fallback: extraer de resultados actuales")
                    for r in results[:10]:
                        prod_id = r['product_id']
                        product = next((p for p in products if str(p.id) == prod_id), None)
                        if product and product.attributes:
                            prod_color = product.attributes.get('color')
                            print(f"[REQ {request_id}]   - Producto {product.name}: color={prod_color}")
                            if prod_color:
                                available_colors.add(prod_color)

                if available_colors:
                    colors_list = sorted(list(available_colors))
                    # Priorizar detected_category sobre LLM's detected_tipo
                    category_name = (detected_category.name if detected_category else None) or detected_tipo or 'productos'

                    # Construir texto amigable de búsqueda
                    search_query_text = query_text.lower()

                    # Determinar si hubo sustitución de categoría (match similar, no exacto)
                    has_category_substitution = 'category_substitution_info' in locals() and category_substitution_info is not None

                    # Detectar el color de los productos que estamos mostrando (el "más cercano")
                    shown_colors = set()
                    for r in results[:3]:  # Top 3 resultados
                        prod_id = r['product_id']
                        product = next((p for p in products if str(p.id) == prod_id), None)
                        if product and product.attributes:
                            prod_color = product.attributes.get('color')
                            if prod_color:
                                shown_colors.add(prod_color)

                    # Excluir colores mostrados de la lista de "también disponibles"
                    other_colors = [c.lower() for c in colors_list if c.lower() not in shown_colors]

                    if match_quality == "poor":
                        # Mensaje amigable cuando NO hay el color solicitado
                        message = ""

                        # Solo mencionar interpretación de categoría si hubo sustitución (match similar O categoría hermana)
                        if has_category_substitution or used_sibling_category:
                            if used_sibling_category and original_category_name:
                                # Mensaje específico para categoría hermana
                                message = f"Tu búsqueda de {search_query_text} no encontró resultados en {original_category_name}, pero encontramos opciones en {category_name}. "
                            else:
                                # Mensaje normal de interpretación de categoría
                                message = f"Tu búsqueda de {search_query_text} se interpretó dentro de la categoría {category_name}. "

                        # Solo mencionar color si el usuario lo pidió explícitamente
                        if explicit_color_from_query:
                            # Requerimiento: incluir categoría
                            message += f"No tenemos {category_name.lower()} disponible en color '{detected_color.lower()}'"

                            if shown_colors:
                                if len(shown_colors) == 1:
                                    closest = list(shown_colors)[0]
                                    message += f", pero encontramos opciones en {closest}."
                                else:
                                    closest_list = ', '.join(sorted(shown_colors))
                                    message += f", pero encontramos opciones en {closest_list}."
                            else:
                                message += "."

                            if other_colors:
                                if len(other_colors) == 1:
                                    message += f" También podés elegir {other_colors[0]}."
                                else:
                                    others_text = ', '.join(other_colors[:-1]) + f" y {other_colors[-1]}"
                                    message += f" También podés elegir entre otros colores disponibles: {others_text}."
                        else:
                            # No color explícito → solo mostrar productos disponibles sin mencionar color
                            if not message:  # Si no hay mensaje de categoría
                                message = f"Encontramos estas opciones para tu búsqueda."

                        # Agregar sugerencia de categorías hermanas si están disponibles
                        if category_substitution_info and 'sibling_categories' in category_substitution_info:
                            sibling_cats = category_substitution_info['sibling_categories']
                            # Filtrar hermanas con alta similitud (>0.75) y que no sean la categoría actual
                            relevant_siblings = [
                                cat for cat in sibling_cats
                                if cat.get('similarity', 0) > 0.75 and cat.get('name') != category_name
                            ]
                            if relevant_siblings:
                                sibling_names = [cat['name'] for cat in relevant_siblings[:2]]  # Máximo 2
                                if len(sibling_names) == 1:
                                    message += f" También puedes explorar productos en {sibling_names[0]}."
                                elif len(sibling_names) == 2:
                                    message += f" También puedes explorar productos en {sibling_names[0]} o {sibling_names[1]}."

                        partial_match_info = {
                            "message": message,
                            "requested_color": detected_color.upper() if explicit_color_from_query else None,
                            "reason": "color_not_available" if explicit_color_from_query else "no_color_requested"
                        }
                    else:  # partial
                        # Mensaje para coincidencia parcial (color similar pero no exacto)
                        message = ""

                        # Solo mencionar interpretación de categoría si hubo sustitución (match similar O categoría hermana)
                        if has_category_substitution or used_sibling_category:
                            if used_sibling_category and original_category_name:
                                # Mensaje específico para categoría hermana
                                message = f"Tu búsqueda de {search_query_text} no encontró resultados en {original_category_name}, pero encontramos opciones en {category_name}. "
                            else:
                                # Mensaje normal de interpretación de categoría
                                message = f"Tu búsqueda de {search_query_text} se interpretó dentro de la categoría {category_name}. "

                        # Solo mencionar color si el usuario lo pidió explícitamente
                        if explicit_color_from_query:
                            # Requerimiento: incluir categoría
                            message += f"No tenemos {category_name.lower()} disponible en color '{detected_color.lower()}'"

                            if shown_colors:
                                if len(shown_colors) == 1:
                                    closest = list(shown_colors)[0]
                                    message += f", pero encontramos opciones en {closest}."
                                else:
                                    closest_list = ', '.join(sorted(shown_colors))
                                    message += f", pero encontramos opciones en {closest_list}."

                            if other_colors:
                                if len(other_colors) == 1:
                                    message += f" También disponible: {other_colors[0]}."
                                else:
                                    others_text = ', '.join(other_colors[:-1]) + f" y {other_colors[-1]}"
                                    message += f" Otros colores disponibles: {others_text}."
                        else:
                            # No color explícito → solo mostrar productos disponibles sin mencionar color
                            if not message:  # Si no hay mensaje de categoría
                                message = f"Encontramos estas opciones para tu búsqueda."

                        # Agregar sugerencia de categorías hermanas si están disponibles
                        if category_substitution_info and 'sibling_categories' in category_substitution_info:
                            sibling_cats = category_substitution_info['sibling_categories']
                            # Filtrar hermanas con alta similitud (>0.75) y que no sean la categoría actual
                            relevant_siblings = [
                                cat for cat in sibling_cats
                                if cat.get('similarity', 0) > 0.75 and cat.get('name') != category_name
                            ]
                            if relevant_siblings:
                                sibling_names = [cat['name'] for cat in relevant_siblings[:2]]  # Máximo 2
                                if len(sibling_names) == 1:
                                    message += f" También puedes explorar productos en {sibling_names[0]}."
                                elif len(sibling_names) == 2:
                                    message += f" También puedes explorar productos en {sibling_names[0]} o {sibling_names[1]}."

                        partial_match_info = {
                            "message": message,
                            "available_colors": colors_list if explicit_color_from_query else None,
                            "requested_color": detected_color if explicit_color_from_query else None,
                            "reason": "partial_color_match" if explicit_color_from_query else "no_color_requested"
                        }

        print(f"[REQ {request_id}] TEXT SEARCH: {len(results)} resultados en {elapsed_time:.3f}s | query='{query_text}'", flush=True)
        print(f"[REQ {request_id}] MATCH QUALITY: {match_quality}", flush=True)
        print(f"[REQ {request_id}] DETECTED COLOR: {detected_color}", flush=True)
        print(f"[REQ {request_id}] PARTIAL MATCH INFO: {partial_match_info}", flush=True)

        # Construir contexto de categoría (tipo de match + hermanas)
        match_type = None
        match_similarity = None
        if detected_category:
            if detected_category_via in ("name", "name_en", "alt"):
                match_type = "exact"
            elif detected_category_via == "semantic":
                match_type = "similar"
                try:
                    match_similarity = round(float(best_score), 3)
                except Exception:
                    match_similarity = None
            else:
                # LLM branch puede haber fijado category_substitution_info
                match_type = "similar" if category_substitution_info else "exact"
                try:
                    if category_substitution_info and 'similarity' in category_substitution_info:
                        match_similarity = category_substitution_info['similarity']
                except Exception:
                    match_similarity = None

        sibling_suggestions = []
        if detected_category:
            try:
                from sentence_transformers import util as _st_util
                selected_emb = _get_category_embedding(detected_category.name, str(client.id))
                if selected_emb is not None:
                    sugg = []
                    for oc in categories:
                        if oc.id == detected_category.id:
                            continue
                        oc_emb = _get_category_embedding(oc.name, str(client.id))
                        if oc_emb is None:
                            continue
                        sim = float(_st_util.cos_sim(selected_emb, oc_emb)[0][0])
                        sugg.append((oc, sim))
                    sugg.sort(key=lambda x: x[1], reverse=True)
                    for oc, sim in sugg[:5]:
                        if sim >= 0.75:
                            sibling_suggestions.append({
                                "id": str(oc.id),
                                "name": oc.name,
                                "similarity": round(sim, 3)
                            })
            except Exception as _e:
                print(f"[REQ {request_id}] ⚠️ Error generando hermanas: {_e}")

        # Construir info de color: solicitado vs usado (si se reemplazó)
        color_info = None
        try:
            requested_color = (detected_color.lower() if detected_color else None)
            # Colores mostrados en resultados (top)
            shown_colors = []
            for r in results:
                prod = next((p for p in products if str(p.id) == r['product_id']), None)
                if prod and getattr(prod, 'attributes', None):
                    val = prod.attributes.get('color')
                    if isinstance(val, str) and val:
                        shown_colors.append(val.lower())
                    elif isinstance(val, list) and val:
                        shown_colors.extend([str(v).lower() for v in val if v])
            # Colores disponibles en la categoría (a partir de productos cargados)
            available_colors_set = set()
            for prod in products:
                if getattr(prod, 'attributes', None):
                    val = prod.attributes.get('color')
                    if isinstance(val, str) and val:
                        available_colors_set.add(val.lower())
                    elif isinstance(val, list) and val:
                        for v in val:
                            if v:
                                available_colors_set.add(str(v).lower())
            # Decidir reemplazo: si el color pedido no existe, elegir el más aproximado (por similitud)
            used_color = None
            replaced = False
            if requested_color:
                if requested_color not in available_colors_set:
                    replaced = True
                    # Elegir el color más aproximado por similitud de embeddings
                    if available_colors_set:
                        requested_emb = _get_color_embedding(requested_color)
                        if requested_emb is not None:
                            best_sim = -1.0
                            best_color = None
                            for avail_color in available_colors_set:
                                avail_emb = _get_color_embedding(avail_color)
                                if avail_emb is not None:
                                    # Similitud coseno
                                    sim = float(np.dot(requested_emb, avail_emb) / (np.linalg.norm(requested_emb) * np.linalg.norm(avail_emb)))
                                    if sim > best_sim:
                                        best_sim = sim
                                        best_color = avail_color
                            used_color = best_color if best_color else (list(available_colors_set)[0] if available_colors_set else None)
                        else:
                            # Fallback si no hay embedding: primer color disponible
                            used_color = list(available_colors_set)[0] if available_colors_set else None
                    else:
                        used_color = None
                else:
                    used_color = requested_color
            color_info = {
                "requested": requested_color,
                "used": used_color,
                "replaced": replaced,
                "available_in_category": sorted(list(available_colors_set))[:20]
            }
        except Exception as _e:
            print(f"[REQ {request_id}] ⚠️ Error construyendo color_info: {_e}")

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
            "detected_attributes": detected_attributes,
            "search_context": {
                "category": ({
                    "id": str(detected_category.id),
                    "name": detected_category.name,
                    "match_type": match_type,
                    **({"similarity": match_similarity} if match_similarity is not None else {}),
                    **({"sibling_suggestions": sibling_suggestions} if sibling_suggestions else {})
                } if detected_category else None),
                "color": color_info
            }
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
        _resp_t = _t.time()
        resp = jsonify(response)
        try:
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        except Exception:
            pass
        print(f"[REQ {request_id}] DEBUG: respuesta JSON construida en {(_t.time()-_resp_t):.2f}s | post-SQL total={( _t.time()-_post_sql_t):.2f}s | query='{query_text}'", flush=True)
        print(f"[TEXT_SEARCH] END OK {len(results)} results match_quality={match_quality} time={round(time.time()-start_time,3)}s")
        print(f"[TEXT_SEARCH_MODE] full query='{query_text}' time={round(time.time()-start_time,3)}s results={len(results)}", flush=True)

        # ================= METRICS JSON CONSOLIDADO =====================
        try:
            metrics_payload = {
                "request_id": request_id,
                "query": query_text,
                "original_N": original_N,
                "final_N": N,
                "topk_limit": topk_limit,
                "times": {
                    "normalize": round(t_norm_end - start_time, 3),
                    "clip_model": round(t_clip_model_end - t_norm_end, 3),
                    "text_embed": round(t_text_embed_end - t_clip_model_end, 3),
                    "category_detect": round(t_category_detection_end - t_text_embed_end, 3),
                    "sql_products": round(t_sql_end - t_category_detection_end, 3),
                    "parse_embeddings": round(_parse_elapsed, 3),
                    "similarities": round(_sim_elapsed, 3),
                    "topk": round(topk_elapsed, 3),
                    "preload_colors": round((_preload_elapsed if detected_color else 0.0), 3),
                    "boost_loop": round(_boost_elapsed, 3),
                    "sort": round(_sort_elapsed, 3),
                    "total": round(elapsed_time, 3)
                }
            }
            print(f"[TEXT_SEARCH_METRICS] {json.dumps(metrics_payload, ensure_ascii=False)}", flush=True)
        except Exception as _m_err:
            print(f"[TEXT_SEARCH_METRICS] ERROR serializando métricas: {_m_err}")
        return resp

    except Exception as e:
        import traceback
        print(f"[TEXT_SEARCH] END 500 error='{e}' time={round(time.time()-start_time,3)}s")
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

@bp.route("/search/unified", methods=["POST", "OPTIONS"])
def unified_search():
    """
    Endpoint simplificado de búsqueda visual (requiere categoría pre-detectada).

    La detección de categoría se realiza previamente con GPT-4 Vision en /api/gpt4v/detect.
    Este endpoint solo busca productos similares dentro de la categoría especificada.

    Headers:
        X-API-Key: API Key del cliente

    Body (multipart/form-data o JSON):
        image: Archivo imagen o base64 (requerido)
        category: Nombre de categoría (requerido, debe existir en BD)
        max_results: Productos a retornar (default: 5)

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

            total_products_found += len(products_data);

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


