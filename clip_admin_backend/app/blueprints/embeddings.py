import logging
# Configuración explícita del logger 'clip_model' para que los logs salgan por consola (Railway)
clip_logger = logging.getLogger("clip_model")
clip_logger.setLevel(logging.INFO)
if not clip_logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    handler.setFormatter(formatter)
    clip_logger.addHandler(handler)
"""
Blueprint de Embeddings CLIP
Administración y generación de embeddings para búsqueda visual
"""

import os
import ssl

# Configurar SSL para descargas de modelos ANTES de importar transformers
# Usar certificados del sistema en lugar de PostgreSQL
import certifi
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['CURL_CA_BUNDLE'] = certifi.where()

import json
import requests
from io import BytesIO
from datetime import datetime
from PIL import Image as PILImage
import torch
from transformers import CLIPProcessor, CLIPModel
import numpy as np
import threading
import time

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.image import Image
from app.utils.system_config import system_config
from app.models.product import Product
from app.models.client import Client
from app.utils.permissions import requires_role, requires_client_scope, filter_by_client_scope

bp = Blueprint('embeddings', __name__)

def load_image_from_source(source):
    """Cargar imagen desde URL de Cloudinary"""
    try:
        import logging
        logging.getLogger("clip_model").info(f"🌐 Descargando imagen desde Cloudinary: {source[:80]}...")
        response = requests.get(source, timeout=30)
        response.raise_for_status()
        image = PILImage.open(BytesIO(response.content)).convert('RGB')
        logging.getLogger("clip_model").info(f"✅ Imagen descargada exitosamente desde Cloudinary")
        return image
    except Exception as e:
        import logging
        logging.getLogger("clip_model").error(f"❌ Error cargando imagen desde Cloudinary {source}: {e}")
        raise

# Variables globales para el modelo CLIP
_clip_model = None
_clip_processor = None
_clip_current_model_name = None  # Rastrear qué modelo está cargado
_clip_last_used_ts = None  # epoch seconds de último uso
_clip_cleanup_thread_started = False
_clip_lock = threading.Lock()
_clip_idle_timeout_cache = None  # Cache del timeout en segundos

# Mapeo de nombres de modelo amigables a identificadores HuggingFace
CLIP_MODEL_MAP = {
    "ViT-B/16": "openai/clip-vit-base-patch16",
    "ViT-B/32": "openai/clip-vit-base-patch32",
    "ViT-L/14": "openai/clip-vit-large-patch14"
}


def reload_clip_config():
    """Fuerza recarga de configuración de CLIP (llamado desde system_config_admin al guardar)."""
    global _clip_idle_timeout_cache
    with _clip_lock:
        _clip_idle_timeout_cache = None
        from app.utils.system_config import system_config
        minutes = system_config.get('clip', 'idle_timeout_minutes', 120)
    import logging
    logging.getLogger("clip_model").info(f"🔄 Configuración CLIP recargada | Nuevo timeout: {minutes} minutos")


def _now_ts() -> float:
    return time.time()


def _touch_clip_last_used():
    global _clip_last_used_ts
    _clip_last_used_ts = _now_ts()
    # logging eliminado por requerimiento


def _get_idle_timeout_seconds() -> int:
    """Obtiene el timeout de inactividad para descargar CLIP.

    Prioridad:
    1) Cache global (si fue invalidado por reload_clip_config)
    2) app.utils.system_config.system_config.get('clip', 'idle_timeout_minutes')
    3) Env var CLIP_IDLE_TIMEOUT_MINUTES
    4) Env var CLIP_IDLE_TIMEOUT_SECONDS
    5) Default: 120 minutos
    """
    global _clip_idle_timeout_cache

    # Si hay cache válido, usarlo
    if _clip_idle_timeout_cache is not None:
        return _clip_idle_timeout_cache

    # Intentar leer desde sistema de configuración central
    try:
        from app.utils.system_config import system_config
        minutes = system_config.get('clip', 'idle_timeout_minutes', 120)
        _clip_idle_timeout_cache = int(minutes) * 60
        return _clip_idle_timeout_cache
    except Exception:
        # Continuar con fallbacks si falla
        pass

    # Variables de entorno
    minutes_env = os.getenv('CLIP_IDLE_TIMEOUT_MINUTES')
    if minutes_env and minutes_env.isdigit():
        return int(minutes_env) * 60

    seconds_env = os.getenv('CLIP_IDLE_TIMEOUT_SECONDS')
    if seconds_env and seconds_env.isdigit():
        return int(seconds_env)

    # Default: 2 horas
    return 120 * 60


def _start_cleanup_thread_once():
    """Inicia un hilo daemon que descarga el modelo tras inactividad."""
    global _clip_cleanup_thread_started
    if _clip_cleanup_thread_started:
        return

    _clip_cleanup_thread_started = True
    import logging
    logging.getLogger("clip_model").info("[CLIP] Hilo de limpieza iniciado")

    def _worker():
        global _clip_model, _clip_processor, _clip_last_used_ts
        while True:
            try:
                idle_timeout = _get_idle_timeout_seconds()
                check_every = 300  # 5 minutos fijo
                time.sleep(check_every)
                with _clip_lock:
                    if _clip_model is None:
                        continue
                    now = _now_ts()
                    if _clip_last_used_ts is None:
                        # Nunca usado: descargar si pasó el timeout desde arranque
                        if hasattr(_clip_model, 'loaded_at'):
                            idle_for = now - _clip_model.loaded_at
                        else:
                            idle_for = idle_timeout + 1  # Forzar si no hay timestamp
                        if idle_for >= idle_timeout:
                            try:
                                if torch.cuda.is_available():
                                    torch.cuda.empty_cache()
                            except Exception:
                                pass
                            _clip_model = None
                            _clip_processor = None
                            _clip_current_model_name = None
                            print(f"🧹 CLIP descargado por inactividad tras arranque (sin uso, timeout {idle_timeout}s)")
                            logging.getLogger("clip_model").info(f"[CLIP] Modelo descargado de memoria por inactividad tras arranque (timeout {idle_timeout}s)")
                        continue
                    idle_for = now - _clip_last_used_ts
                    if idle_for >= idle_timeout:
                        try:
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()
                        except Exception:
                            pass
                        _clip_model = None
                        _clip_processor = None
                        _clip_current_model_name = None
                        print(f"🧹 CLIP descargado por inactividad (idle {int(idle_for)}s ≥ {idle_timeout}s)")
                        logging.getLogger("clip_model").info(f"[CLIP] Modelo descargado de memoria por inactividad (idle {int(idle_for)}s ≥ {idle_timeout}s)")
            except Exception as _e:
                logging.getLogger("clip_model").error(f"[CLIP] Error en hilo de limpieza: {_e}")
                continue

    t = threading.Thread(target=_worker, name="clip-idle-cleanup", daemon=True)
    t.start()

def get_clip_model():
    """Cargar modelo CLIP una sola vez (singleton con auto-descarga por inactividad)."""
    global _clip_model, _clip_processor, _clip_current_model_name

    # Asegurar hilo de limpieza iniciado una vez
    _start_cleanup_thread_once()

    with _clip_lock:
        # Obtener modelo desde configuración
        model_name = system_config.get('clip', 'model_name', 'ViT-B/16')
        model_id = CLIP_MODEL_MAP.get(model_name, CLIP_MODEL_MAP['ViT-B/16'])

        # Si el modelo cambió en la configuración, descargar el actual y cargar el nuevo
        if _clip_model is not None and _clip_current_model_name != model_name:
            print(f"⚠️ Modelo cambió de {_clip_current_model_name} a {model_name}. Recargando...")
            _clip_model = None
            _clip_processor = None
            _clip_current_model_name = None
            # Limpiar GPU si estaba en uso
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        if _clip_model is None:
            print(f"🔄 Cargando modelo CLIP {model_name} ({model_id})...")
            try:
                _clip_model = CLIPModel.from_pretrained(model_id)
                _clip_model.loaded_at = time.time()
                _clip_processor = CLIPProcessor.from_pretrained(model_id)
                _clip_current_model_name = model_name

                # Configurar para CPU/GPU
                _clip_model.eval()
                if torch.cuda.is_available():
                    print("🔥 GPU disponible, usando CUDA")
                    _clip_model = _clip_model.cuda()
                else:
                    print("💻 Usando CPU para CLIP")

                print(f"✅ Modelo CLIP {model_name} cargado exitosamente")
            except Exception as e:
                print(f"❌ Error cargando CLIP: {e}")
                raise

        # Marcar último uso y devolver
        _touch_clip_last_used()
        return _clip_model, _clip_processor

def generate_clip_embedding(image_path, image_obj=None):
    """Generar embedding CLIP optimizado usando contexto del cliente y categoría"""
    try:
        import logging
        logging.getLogger("clip_model").info(f"[REQUEST] Comparación recibida")

        model, processor = get_clip_model()
        _touch_clip_last_used()

        # Obtener información contextual del producto/imagen
        context_info = get_image_context(image_obj) if image_obj else {}

        # Generar embedding optimizado
        if context_info and context_info.get('enable_optimization', True):
            embedding, metadata = generate_optimized_embedding(
                image_path, model, processor, context_info
            )
            print(f"✅ Embedding optimizado generado: {len(embedding)} dimensiones")
            print(f"📊 Métodos usados: {metadata.get('optimization_method')}")
            return embedding, metadata
        else:
            # Fallback a embedding simple
            embedding = generate_simple_embedding(image_path, model, processor)
            metadata = {'optimization_method': 'simple', 'embedding_dim': len(embedding)}
            print(f"✅ Embedding simple generado: {len(embedding)} dimensiones")
            return embedding, metadata

    except Exception as e:
        print(f"❌ Error generando embedding: {e}")
        return None, None

def get_image_context(image_obj):
    """Obtener contexto completo para optimización de embedding"""
    try:
        from app.models.client import Client
        from app.models.category import Category
        from app.models.product import Product

        context = {}

        if not image_obj:
            return context

        # Obtener producto asociado
        product = Product.query.filter_by(id=image_obj.product_id).first()
        if not product:
            return context

        # Obtener cliente e industria
        client = Client.query.filter_by(id=product.client_id).first()
        if client:
            context['client_industry'] = client.industry or 'general'
            context['client_name'] = client.name

        # Obtener categoría y características
        category = Category.query.filter_by(id=product.category_id).first()
        if category:
            context['category_name'] = category.name_en or category.name
            context['category_features'] = {
                'clip_prompt': category.clip_prompt,
                'visual_features': category.visual_features,
                'confidence_threshold': category.confidence_threshold
            }

        # Obtener tags del producto
        if hasattr(product, 'tags') and product.tags:
            context['product_tags'] = [tag.strip() for tag in product.tags.split(',')]

        context['enable_optimization'] = True
        return context

    except Exception as e:
        print(f"⚠️ Error obteniendo contexto: {e}")
        return {'enable_optimization': False}

def generate_optimized_embedding(image_path_or_url, model, processor, context_info):
    """Generar embedding optimizado usando múltiples técnicas"""

    # Cargar imagen (local o URL)
    image = load_image_from_source(image_path_or_url)

    embeddings_list = []
    prompts_used = []

    # 1. Embedding base (imagen sola)
    base_embedding = generate_image_only_embedding(image, model, processor)
    embeddings_list.append(base_embedding)
    prompts_used.append("image_only")

    # 2. Embeddings contextuales si hay información disponible
    if context_info.get('category_name'):
        contextual_embeddings = generate_contextual_embeddings(
            image, model, processor, context_info
        )
        embeddings_list.extend(contextual_embeddings['embeddings'])
        prompts_used.extend(contextual_embeddings['prompts'])

    # 3. Fusionar embeddings
    if len(embeddings_list) > 1:
        final_embedding = fuse_embeddings_weighted(embeddings_list, context_info)
    else:
        final_embedding = embeddings_list[0]

    # 4. Normalizar embedding final
    final_embedding = normalize_embedding(final_embedding)

    # 5. Crear metadata
    metadata = {
        'optimization_method': 'contextual_fusion',
        'industry': context_info.get('client_industry', 'unknown'),
        'category': context_info.get('category_name', 'unknown'),
        'prompts_used': prompts_used,
        'num_embeddings_fused': len(embeddings_list),
        'embedding_dim': len(final_embedding),
        'confidence_score': calculate_embedding_confidence(embeddings_list)
    }

    return final_embedding, metadata

def generate_simple_embedding(image_path_or_url, model, processor):
    """Generar embedding simple (fallback)"""

    # Cargar y procesar imagen (local o URL)
    image = load_image_from_source(image_path_or_url)

    # Procesar imagen con manejo de errores
    try:
        inputs = processor(images=image, return_tensors="pt")
    except Exception as e:
        print(f"🔧 DEBUG: Error en procesador embeddings (línea 173): {e}")
        # Fallback: usar solo argumentos posicionales
        inputs = processor(image, return_tensors="pt")

    # Mover a GPU si está disponible
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}

    # Generar embedding
    with torch.no_grad():
        image_features = model.get_image_features(**inputs)

    # Normalizar y convertir
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    embedding = image_features.cpu().numpy().flatten().tolist()

    return embedding

def generate_image_only_embedding(image, model, processor):
    """Generar embedding solo de imagen"""

    # Procesar imagen con manejo de errores
    try:
        inputs = processor(images=image, return_tensors="pt")
    except Exception as e:
        print(f"🔧 DEBUG: Error en procesador embeddings (línea 194): {e}")
        # Fallback: usar solo argumentos posicionales
        inputs = processor(image, return_tensors="pt")

    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}

    with torch.no_grad():
        image_features = model.get_image_features(**inputs)

    return image_features.cpu().numpy().flatten()

def generate_contextual_embeddings(image, model, processor, context_info):
    """Generar embeddings usando prompts contextuales"""

    embeddings = []
    prompts = []

    # Obtener prompts basados en contexto
    contextual_prompts = create_contextual_prompts(context_info)

    for prompt in contextual_prompts:
        try:
            # Procesar imagen y texto juntos
            inputs = processor(
                text=[prompt],
                images=image,
                return_tensors="pt",
                padding=True
            )

            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                # Obtener features combinadas
                image_features = model.get_image_features(pixel_values=inputs['pixel_values'])
                text_features = model.get_text_features(input_ids=inputs['input_ids'])

                # Combinar con pesos (más peso a imagen)
                combined_features = 0.75 * image_features + 0.25 * text_features
                embedding = combined_features.cpu().numpy().flatten()

            embeddings.append(embedding)
            prompts.append(prompt)

        except Exception as e:
            print(f"⚠️ Error con prompt '{prompt}': {e}")
            continue

    return {'embeddings': embeddings, 'prompts': prompts}

def create_contextual_prompts(context_info):
    """Crear prompts contextuales basados en información disponible"""

    prompts = []
    category = context_info.get('category_name', '').lower()
    industry = context_info.get('client_industry', 'general')

    # Prompts basados en industria
    industry_prompts = {
        'textil': [
            f"a high quality photo of {category} clothing item",
            f"professional product photo of {category} fashion",
            f"{category} textile with clear details"
        ],
        'calzado': [
            f"a clear photo of {category} footwear",
            f"professional shoe photography of {category}",
            f"{category} footwear with visible details"
        ],
        'general': [
            f"a clear photo of {category}",
            f"product photography of {category}",
            f"{category} item with visible details"
        ]
    }

    # Usar prompts de la industria o general
    base_prompts = industry_prompts.get(industry, industry_prompts['general'])
    prompts.extend(base_prompts[:2])  # Máximo 2 prompts base

    # Agregar prompt personalizado de categoría si existe
    category_features = context_info.get('category_features', {})
    if category_features.get('clip_prompt'):
        prompts.append(category_features['clip_prompt'])

    # Agregar prompt con tags si existen
    product_tags = context_info.get('product_tags', [])
    if product_tags:
        tag_text = ', '.join(product_tags[:3])
        prompts.append(f"a {category} that is {tag_text}")

    return prompts[:3]  # Máximo 3 prompts contextuales

def fuse_embeddings_weighted(embeddings_list, context_info):
    """Fusionar embeddings con pesos adaptativos"""

    if len(embeddings_list) == 1:
        return embeddings_list[0]

    # Calcular pesos adaptativos
    weights = [1.5]  # Peso mayor para embedding base

    # Pesos menores para embeddings contextuales
    for i in range(1, len(embeddings_list)):
        weights.append(1.0)

    # Ajustar según confianza de categoría
    category_features = context_info.get('category_features', {})
    confidence_threshold = category_features.get('confidence_threshold', 0.75)

    if confidence_threshold > 0.8:
        # Alta confianza -> más peso a contextuales
        for i in range(1, len(weights)):
            weights[i] *= 1.2

    # Normalizar pesos
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]

    # Fusionar con weighted average
    stacked_embeddings = np.stack(embeddings_list)
    fused_embedding = np.average(stacked_embeddings, axis=0, weights=weights)

    return fused_embedding

def normalize_embedding(embedding):
    """Normalizar embedding para comparación coseno"""
    embedding_array = np.array(embedding)
    norm = np.linalg.norm(embedding_array)
    if norm > 0:
        return (embedding_array / norm).tolist()
    return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)

def calculate_embedding_confidence(embeddings_list):
    """Calcular score de confianza basado en consistencia"""

    if len(embeddings_list) < 2:
        return 1.0

    # Normalizar todos los embeddings
    normalized_embeddings = []
    for emb in embeddings_list:
        emb_array = np.array(emb)
        norm = np.linalg.norm(emb_array)
        if norm > 0:
            normalized_embeddings.append(emb_array / norm)
        else:
            normalized_embeddings.append(emb_array)

    # Calcular similitudes coseno entre todos los pares
    similarities = []
    for i in range(len(normalized_embeddings)):
        for j in range(i + 1, len(normalized_embeddings)):
            sim = np.dot(normalized_embeddings[i], normalized_embeddings[j])
            similarities.append(sim)

    # Confianza = similitud promedio
    return float(np.mean(similarities)) if similarities else 1.0


@bp.route("/")
@login_required
@requires_role('SUPER_ADMIN', 'STORE_ADMIN')
@requires_client_scope
def index():
    """Panel principal de administración de embeddings"""

    # Obtener estadísticas de embeddings con filtro de cliente
    images_query = Image.query
    images_query = filter_by_client_scope(images_query)

    total_images = images_query.count()
    processed_images = images_query.filter_by(is_processed=True).count()

    pending_images_query = Image.query
    pending_images_query = filter_by_client_scope(pending_images_query)
    pending_images = pending_images_query.filter_by(
        is_processed=False,
        upload_status='pending'
    ).count()

    failed_images_query = Image.query
    failed_images_query = filter_by_client_scope(failed_images_query)
    failed_images = failed_images_query.filter_by(
        upload_status='failed'
    ).count()

    # Obtener imágenes con detalles (aplicando filtro de cliente)
    images_detail_query = Image.query
    images_detail_query = filter_by_client_scope(images_detail_query)
    images = images_detail_query.join(Product, Image.product_id == Product.id)\
        .add_columns(Product.name.label('product_name'))\
        .order_by(Image.created_at.desc()).all()

    return render_template("embeddings/index.html",
                           total_images=total_images,
                           processed_images=processed_images,
                           pending_images=pending_images,
                           failed_images=failed_images,
                           images=images)


@bp.route("/stats", methods=["GET"])
@login_required
@requires_role('SUPER_ADMIN', 'STORE_ADMIN')
@requires_client_scope
def get_stats():
    """Obtener estadísticas actualizadas de embeddings en tiempo real"""

    try:
        # Obtener estadísticas actualizadas con filtro de cliente
        images_query = Image.query
        images_query = filter_by_client_scope(images_query)

        total_images = images_query.count()
        processed_images = images_query.filter_by(is_processed=True).count()

        pending_images_query = Image.query
        pending_images_query = filter_by_client_scope(pending_images_query)
        pending_images = pending_images_query.filter_by(
            is_processed=False,
            upload_status='pending'
        ).count()

        failed_images = Image.query.filter_by(
            client_id=current_user.client_id,
            upload_status='failed'
        ).count()

        # Calcular progreso
        progress_percentage = 0
        if total_images > 0:
            progress_percentage = round((processed_images / total_images) * 100, 1)

        return jsonify({
            "success": True,
            "stats": {
                "total": total_images,
                "processed": processed_images,
                "pending": pending_images,
                "failed": failed_images,
                "progress_percentage": progress_percentage
            }
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/process_pending", methods=["POST"])
@login_required
def process_pending():
    """Procesar todas las imágenes pendientes"""
    if not current_user.client_id:
        return jsonify({"success": False, "message": "Usuario no asignado a cliente"})

    try:
        # Obtener imágenes pendientes
        pending_images = Image.query.filter_by(
            client_id=current_user.client_id,
            is_processed=False,
            upload_status='pending'
        ).all()

        if not pending_images:
            return jsonify({"success": False, "message": "No hay imágenes pendientes para procesar"})

        # Procesar embeddings por lotes para permitir progreso en tiempo real
        processed_count = 0
        batch_size = 3  # Reducir a 3 para CLIP (más pesado)
        total_images = len(pending_images)

        print(f"🚀 Iniciando procesamiento de {total_images} imágenes con CLIP")

        for i in range(0, total_images, batch_size):
            batch = pending_images[i:i + batch_size]

            for image in batch:
                try:
                    print(f"🔄 Procesando {image.filename}...")

                    # SOLO usar Cloudinary - no hay fallback local
                    if not image.cloudinary_url:
                        print(f"❌ Error: {image.filename} no tiene URL de Cloudinary")
                        # Mantener coherencia de estados: usar 'failed'
                        image.upload_status = 'failed'
                        image.error_message = "No hay URL de Cloudinary disponible"
                        continue

                    image_source = image.cloudinary_url
                    print(f"🌐 Procesando desde Cloudinary: {image_source}")

                    # Generar embedding optimizado con CLIP
                    embedding, metadata = generate_clip_embedding(image_source, image)

                    if embedding is None:
                        raise Exception("Error generando embedding")

                    # Guardar embedding y metadata en la base de datos
                    image.clip_embedding = json.dumps(embedding)
                    image.is_processed = True
                    image.upload_status = 'completed'
                    image.updated_at = datetime.utcnow()

                    # Guardar metadata si hay espacio (opcional)
                    if hasattr(image, 'metadata') and metadata:
                        image.metadata = json.dumps(metadata)

                    processed_count += 1

                    # Log de información de optimización
                    method = metadata.get('optimization_method', 'unknown') if metadata else 'unknown'
                    confidence = metadata.get('confidence_score', 0) if metadata else 0
                    print(f"✅ {image.filename} procesado con {method} (confianza: {confidence:.3f})")

                except Exception as e:
                    print(f"❌ Error procesando {image.filename}: {e}")
                    image.upload_status = 'failed'
                    image.error_message = str(e)

            # Commit por lote para que el polling pueda ver progreso
            db.session.commit()
            print(f"💾 Lote guardado: {processed_count}/{total_images} imágenes procesadas")

            # 🎯 ACTUALIZAR CENTROIDES de categorías afectadas en este lote
            affected_categories = set()
            for image in batch:
                if image.product and image.product.category and image.is_processed:
                    affected_categories.add(image.product.category)

            for category in affected_categories:
                try:
                    if category.needs_centroid_update():
                        category.update_centroid_embedding(force_recalculate=False)
                        print(f"📊 Centroide actualizado para categoría: {category.name}")
                except Exception as e:
                    print(f"⚠️ Error actualizando centroide de {category.name}: {e}")

            # Commit de centroides actualizados
            if affected_categories:
                try:
                    db.session.commit()
                    print(f"✅ {len(affected_categories)} centroides actualizados")
                except Exception as e:
                    print(f"⚠️ Error guardando centroides: {e}")
                    db.session.rollback()

        return jsonify({
            "success": True,
            "message": f"Se procesaron {processed_count} embeddings correctamente"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/process-single/<image_id>", methods=["POST"])
@login_required
def process_single(image_id):
    """Procesar embedding de una imagen específica"""
    image = Image.query.filter_by(
        id=image_id,
        client_id=current_user.client_id
    ).first_or_404()

    try:
        # TODO: Integrar CLIP real
        # embedding = generate_clip_embedding(image_path)
        # image.clip_embedding = json.dumps(embedding.tolist())

        # Simulación
        image.is_processed = True
        image.clip_embedding = json.dumps([0.1] * 512)
        image.upload_status = 'completed'
        image.error_message = None
        image.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Embedding generado correctamente"
        })

    except Exception as e:
        db.session.rollback()
        image.upload_status = 'failed'
        image.error_message = str(e)
        db.session.commit()

        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/clear-failed", methods=["POST"])
@login_required
def clear_failed():
    """Limpiar embeddings fallidos para reprocesar"""
    if not current_user.client_id:
        return jsonify({"success": False, "message": "Usuario no asignado a cliente"})

    try:
        failed_images = Image.query.filter_by(
            client_id=current_user.client_id,
            upload_status='failed'
        ).all()

        cleared_count = 0
        for image in failed_images:
            image.upload_status = 'completed'
            image.error_message = None
            image.is_processed = False
            cleared_count += 1

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Se limpiaron {cleared_count} errores. Las imágenes están listas para reprocesar."
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@bp.route("/reset-all", methods=["POST"])
@login_required
def reset_all():
    """Resetear todos los embeddings para regenerar"""
    if not current_user.client_id:
        return jsonify({"success": False, "message": "Usuario no asignado a cliente"})

    try:
        all_images = Image.query.filter_by(client_id=current_user.client_id).all()

        reset_count = 0
        for image in all_images:
            image.is_processed = False
            image.clip_embedding = None
            image.upload_status = 'pending'  # 🔥 CAMBIO: Marcar como pendiente para reprocesar
            image.error_message = None
            reset_count += 1

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Se resetearon {reset_count} embeddings. Listos para regenerar."
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})
