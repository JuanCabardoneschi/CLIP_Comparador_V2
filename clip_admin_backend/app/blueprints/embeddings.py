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
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models.image import Image
from app.utils.system_config import system_config
from app.models.product import Product
from app.models.client import Client
from app.utils.permissions import requires_role, requires_client_scope, filter_by_client_scope
from app.models.category import Category
from app.utils.logging_config import (
    log_error, log_embedding, log_verbose, log_system,
    LogCategory
)

bp = Blueprint('embeddings', __name__)

def load_image_from_source(source):
    """Cargar imagen desde múltiples fuentes.

    Soporta:
    - Objeto PIL.Image (lo retorna tal cual)
    - Bytes (abre desde buffer)
    - data URL (data:image/...;base64,AAAA)
    - URL http/https
    - Ruta local de archivo
    - Base64 crudo (cadena larga sin prefijo data:)
    """
    import logging
    log = logging.getLogger("clip_model")

    # 1) PIL ya construido
    if isinstance(source, PILImage.Image):
        return source

    # 2) Bytes en memoria
    if isinstance(source, (bytes, bytearray)):
        try:
            return PILImage.open(BytesIO(source)).convert('RGB')
        except Exception as e:
            log.error(f"❌ Error abriendo imagen desde bytes: {e}")
            raise

    # 3) Cadena de texto: detectar tipo
    if isinstance(source, str):
        s = source.strip()

        # 3.a) data URL base64
        if s.lower().startswith('data:'):
            try:
                import base64
                # Formato esperado: data:<mime>;base64,<payload>
                # Buscar la coma que separa cabecera de payload
                comma_idx = s.find(',')
                if comma_idx == -1:
                    raise ValueError('data URL inválida (sin coma)')
                payload = s[comma_idx + 1:]
                img_bytes = base64.b64decode(payload)
                log.info("🧩 Cargando imagen desde data URL base64")
                return PILImage.open(BytesIO(img_bytes)).convert('RGB')
            except Exception as e:
                log.error(f"❌ Error cargando imagen desde data URL: {e}")
                raise

        # 3.b) URL http/https
        if s.lower().startswith('http://') or s.lower().startswith('https://'):
            try:
                log.info(f"🌐 Descargando imagen desde URL: {s[:80]}...")

                # OPTIMIZACIÓN: Usar sesión con connection pooling y configuración optimizada
                session = requests.Session()
                session.mount('https://', requests.adapters.HTTPAdapter(
                    pool_connections=10,
                    pool_maxsize=20,
                    max_retries=2
                ))

                # Headers optimizados para Cloudinary
                headers = {
                    'User-Agent': 'Mozilla/5.0 (compatible; CLIP-Comparador/2.0)',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive'
                }

                # Timeout reducido: 10s conexión, 20s lectura
                response = session.get(s, headers=headers, timeout=(10, 20), stream=True)
                response.raise_for_status()

                # Cargar directamente desde stream (más eficiente en memoria)
                image = PILImage.open(BytesIO(response.content)).convert('RGB')
                log.info("✅ Imagen descargada exitosamente desde URL")
                return image
            except Exception as e:
                log.error(f"❌ Error cargando imagen desde URL {s}: {e}")
                raise

        # 3.c) Ruta local existente
        if os.path.exists(s):
            try:
                log.info(f"📁 Cargando imagen desde archivo local: {s}")
                return PILImage.open(s).convert('RGB')
            except Exception as e:
                log.error(f"❌ Error abriendo imagen local {s}: {e}")
                raise

        # 3.d) Intentar como base64 crudo
        try:
            import base64
            img_bytes = base64.b64decode(s, validate=True)
            log.info("🧩 Cargando imagen desde base64 crudo")
            return PILImage.open(BytesIO(img_bytes)).convert('RGB')
        except Exception:
            # No parece base64 válido; reportar error
            log.error("❌ Fuente de imagen no reconocida (no es URL, archivo, data URL ni base64 válido)")
            raise ValueError("Fuente de imagen no reconocida: use URL http/https, data URL o base64 válido")

    # Tipo no soportado
    log.error(f"❌ Tipo de fuente no soportado: {type(source)}")


def preload_images_parallel(image_records, max_workers=5):
    """Pre-descarga imágenes en paralelo para acelerar procesamiento en Railway.

    OPTIMIZACIÓN RAILWAY: Descarga múltiples imágenes simultáneamente usando ThreadPoolExecutor.
    Esto aprovecha el ancho de banda de Railway y reduce significativamente el tiempo total.

    Args:
        image_records: Lista de objetos Image con cloudinary_url
        max_workers: Número de threads paralelos (default: 5)

    Returns:
        dict: Mapeo de image.id -> PIL.Image precargada
    """
    import logging
    log = logging.getLogger("clip_model")

    preloaded_images = {}

    # Crear sesión HTTP compartida con connection pooling
    session = requests.Session()
    session.mount('https://', requests.adapters.HTTPAdapter(
        pool_connections=max_workers,
        pool_maxsize=max_workers * 2,
        max_retries=2
    ))

    headers = {
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (CLIP-Embeddings)'
    }

    def download_single_image(img_record):
        """Descarga una sola imagen con manejo de errores"""
        try:
            if not img_record.cloudinary_url:
                log.warning(f"⚠️ {img_record.filename} sin URL de Cloudinary")
                return (img_record.id, None, f"No URL disponible")

            log.info(f"⬇️ Descargando {img_record.filename}...")
            response = session.get(
                img_record.cloudinary_url,
                headers=headers,
                timeout=(10, 20),  # 10s connect, 20s read
                stream=True
            )
            response.raise_for_status()

            # Convertir a PIL Image
            pil_image = PILImage.open(BytesIO(response.content)).convert('RGB')
            log.info(f"✅ {img_record.filename} descargada ({len(response.content)} bytes)")

            return (img_record.id, pil_image, None)

        except Exception as e:
            log.error(f"❌ Error descargando {img_record.filename}: {e}")
            return (img_record.id, None, str(e))

    # Descargar en paralelo con ThreadPoolExecutor
    log.info(f"🚀 Iniciando descarga paralela de {len(image_records)} imágenes con {max_workers} workers")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Enviar todas las descargas al pool
        future_to_image = {
            executor.submit(download_single_image, img): img
            for img in image_records
        }

        # Recolectar resultados a medida que completan
        for future in as_completed(future_to_image):
            img_id, pil_image, error = future.result()

            if pil_image is not None:
                preloaded_images[img_id] = pil_image
            elif error:
                # Registrar error pero continuar con el resto
                preloaded_images[img_id] = error  # Guardar error para manejo posterior

    elapsed = time.time() - start_time
    success_count = sum(1 for v in preloaded_images.values() if isinstance(v, PILImage.Image))
    log.info(f"✅ Descarga paralela completa: {success_count}/{len(image_records)} exitosas en {elapsed:.2f}s")

    return preloaded_images
    raise TypeError("Tipo de fuente no soportado para imagen")

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

                            # OPTIMIZACIÓN RAILWAY: Forzar garbage collection agresivo
                            import gc
                            gc.collect()  # Recolección estándar
                            gc.collect()  # Segunda pasada para objetos cíclicos

                            log_system(f"CLIP descargado por inactividad tras arranque (sin uso, timeout {idle_timeout}s)")
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

                        # OPTIMIZACIÓN RAILWAY: Forzar garbage collection agresivo
                        import gc
                        gc.collect()  # Recolección estándar
                        gc.collect()  # Segunda pasada para objetos cíclicos

                        log_system(f"CLIP descargado por inactividad (idle {int(idle_for)}s >= {idle_timeout}s) + GC ejecutado")
                        logging.getLogger("clip_model").info(f"[CLIP] Modelo descargado de memoria por inactividad (idle {int(idle_for)}s ≥ {idle_timeout}s)")
                    else:
                        log_verbose(LogCategory.EMBEDDING, f"[CLIP] Model NOT unloaded: inactivity {int(idle_for)}s < {idle_timeout}s threshold.")
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
            log_system(f"Modelo cambio de {_clip_current_model_name} a {model_name}. Recargando...")
            _clip_model = None
            _clip_processor = None
            _clip_current_model_name = None
            # Limpiar GPU si estaba en uso
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        if _clip_model is None:
            log_embedding(f"Cargando modelo CLIP {model_name} ({model_id})...")
            try:
                _clip_model = CLIPModel.from_pretrained(model_id)
                _clip_model.loaded_at = time.time()
                _clip_processor = CLIPProcessor.from_pretrained(model_id)
                _clip_current_model_name = model_name

                # Configurar para CPU/GPU
                _clip_model.eval()
                if torch.cuda.is_available():
                    log_system("GPU disponible, usando CUDA")
                    _clip_model = _clip_model.cuda()
                else:
                    log_system("Usando CPU para CLIP")

                log_embedding(f"Modelo CLIP {model_name} cargado exitosamente")
            except Exception as e:
                log_error(f"Error cargando CLIP: {e}")
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

        # Si hay recorte manual registrado en la imagen, preparar PIL recortada como override
        pil_override = None
        if image_obj and hasattr(image_obj, 'has_crop') and image_obj.has_crop():
            try:
                raw_img = load_image_from_source(image_obj.display_url)
                pil_override = image_obj.apply_crop_to_pil(raw_img)
                context_info['manual_crop_applied'] = True
                context_info['manual_crop_box'] = image_obj.get_crop_box()
            except Exception as ce:
                log_error(f"Error aplicando recorte manual: {ce}")
                context_info['manual_crop_applied'] = False

        # Generar embedding optimizado (usa PIL override si existe)
        if context_info and context_info.get('enable_optimization', True):
            embedding, metadata = generate_optimized_embedding(
                image_path, model, processor, context_info, pil_override=pil_override
            )
            log_embedding(f"Embedding optimizado generado: {len(embedding)} dimensiones")
            log_verbose(LogCategory.EMBEDDING, f"Metodos usados: {metadata.get('optimization_method')}")
            return embedding, metadata
        else:
            # Fallback a embedding simple
            embedding = generate_simple_embedding(image_path, model, processor, pil_override=pil_override)
            metadata = {'optimization_method': 'simple', 'embedding_dim': len(embedding)}
            log_embedding(f"Embedding simple generado: {len(embedding)} dimensiones")
            return embedding, metadata

    except Exception as e:
        log_error(f"Error generando embedding: {e}")
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

        # Adjuntar información de recorte si existe en la imagen
        if hasattr(image_obj, 'has_crop') and image_obj.has_crop():
            box = image_obj.get_crop_box()
            context['crop_box'] = box
            context['has_manual_crop'] = bool(image_obj.is_crop_manual)

        context['enable_optimization'] = True
        return context

    except Exception as e:
        log_error(f"Error obteniendo contexto: {e}")
        return {'enable_optimization': False}

def generate_optimized_embedding(image_path_or_url, model, processor, context_info, pil_override=None):
    """Generar embedding optimizado usando múltiples técnicas"""

    # Cargar imagen (local o URL) o usar recorte manual override
    image = pil_override if pil_override is not None else load_image_from_source(image_path_or_url)

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


# ---------------------- QA SCORE TEMPORAL ----------------------
@bp.route('/api/qa-score', methods=['POST'])
@login_required
def qa_score():
    """Endpoint temporal para evaluar score de similitud de una imagen contra dos prompts
    (ej: Delantal Completo vs Medio Delantal). Se usará internamente para medir impacto del recorte.
    Request JSON: { image_url: str, product_id: str }
    Response JSON: { ok: bool, positive_label, negative_label, positive_score, negative_score }
    """
    data = request.get_json(silent=True) or {}
    image_url = data.get('image_url')
    product_id = data.get('product_id')
    if not image_url:
        return jsonify({'ok': False, 'error': 'image_url requerido'}), 400

    # Cargar modelo/processor
    try:
        model, processor = get_clip_model()
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Error cargando modelo: {e}'}), 500

    # Obtener categoría para decidir prompts (si hay producto)
    positive_label = 'Delantal Completo'
    negative_label = 'Medio Delantal'
    try:
        if product_id:
            prod = Product.query.filter_by(id=product_id).first()
            if prod and prod.category and prod.category.name_en:
                # Heurística: si la categoría contiene 'full' => positivo es esa, negativo es medio
                cname = (prod.category.name_en or '').lower()
                if 'full' in cname or 'completo' in cname:
                    positive_label = 'Full apron professional kitchen garment front chest coverage'
                    negative_label = 'Half apron waist-down kitchen garment'
                elif 'medio' in cname or 'half' in cname:
                    positive_label = 'Half apron waist-down kitchen garment'
                    negative_label = 'Full apron professional kitchen garment front chest coverage'
    except Exception:
        pass

    try:
        pil_img = load_image_from_source(image_url)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Error cargando imagen: {e}'}), 400

    # Preparar batch (imagen + dos textos)
    try:
        inputs = processor(text=[positive_label, negative_label], images=pil_img, return_tensors="pt", padding=True)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Error procesando entrada: {e}'}), 500

    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}

    with torch.no_grad():
        image_features = model.get_image_features(**{k: v for k, v in inputs.items() if k in ['pixel_values']})
        text_features = model.get_text_features(**{k: v for k, v in inputs.items() if k in ['input_ids', 'attention_mask']})

    # Normalizar
    image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
    text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)

    # Similaridades
    sims = (image_features @ text_features.T).cpu().numpy()[0]
    positive_score = float(sims[0])
    negative_score = float(sims[1])

    return jsonify({
        'ok': True,
        'positive_label': positive_label,
        'negative_label': negative_label,
        'positive_score': positive_score,
        'negative_score': negative_score
    })

def generate_simple_embedding(image_path_or_url, model, processor, pil_override=None):
    """Generar embedding simple (fallback)"""

    # Cargar y procesar imagen (local o URL) o usar override recortado
    image = pil_override if pil_override is not None else load_image_from_source(image_path_or_url)

    # Procesar imagen con manejo de errores
    try:
        inputs = processor(images=image, return_tensors="pt")
    except Exception as e:
        log_error(f"Error en procesador embeddings (linea 173): {e}")
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
        log_error(f"Error en procesador embeddings (linea 194): {e}")
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
            log_error(f"Error con prompt '{prompt}': {e}")
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


def _process_pending_background(client_id, app):
    """Función interna para procesar embeddings en background thread.

    Esta función se ejecuta en un thread separado y no bloquea la respuesta HTTP.
    Permite cerrar el navegador mientras continúa el procesamiento.

    Args:
        client_id: ID del cliente a procesar
        app: Instancia de Flask app para context
    """
    with app.app_context():
        try:
            log_embedding(f"[BACKGROUND] Iniciando procesamiento para client_id={client_id}")

            # Obtener imágenes pendientes
            pending_images = Image.query.filter_by(
                client_id=client_id,
                is_processed=False,
                upload_status='pending'
            ).all()

            if not pending_images:
                log_verbose(LogCategory.EMBEDDING, "[BACKGROUND] No hay imagenes pendientes para procesar")
                return

            processed_count = 0
            batch_size = 5
            total_images = len(pending_images)

            log_embedding(f"[BACKGROUND] Procesamiento de {total_images} imagenes con CLIP iniciado")

            for i in range(0, total_images, batch_size):
                batch = pending_images[i:i + batch_size]

                # Pre-descargar imágenes en paralelo
                log_verbose(LogCategory.EMBEDDING, f"[BACKGROUND] Pre-descargando {len(batch)} imagenes en paralelo...")
                preloaded_cache = preload_images_parallel(batch, max_workers=5)

                for image in batch:
                    try:
                        log_verbose(LogCategory.EMBEDDING, f"[BACKGROUND] Procesando {image.filename}...")

                        if not image.cloudinary_url:
                            log_error(f"[BACKGROUND] Error: {image.filename} no tiene URL de Cloudinary")
                            image.upload_status = 'failed'
                            image.error_message = "No hay URL de Cloudinary disponible"
                            continue

                        # Usar imagen pre-descargada del cache
                        cached_item = preloaded_cache.get(image.id)

                        if cached_item is None:
                            log_verbose(LogCategory.EMBEDDING, f"[BACKGROUND] {image.filename} no encontrada en cache, descargando...")
                            image_source = image.cloudinary_url
                        elif isinstance(cached_item, str):
                            raise Exception(f"Error en descarga paralela: {cached_item}")
                        else:
                            image_source = cached_item
                            log_verbose(LogCategory.EMBEDDING, f"[BACKGROUND] Usando imagen pre-descargada de {image.filename}")

                        # Generar embedding optimizado con CLIP
                        embedding, metadata = generate_clip_embedding(image_source, image)

                        if embedding is None:
                            raise Exception("Error generando embedding")

                        # Guardar embedding y metadata
                        image.clip_embedding = json.dumps(embedding)
                        image.is_processed = True
                        image.upload_status = 'completed'
                        image.updated_at = datetime.utcnow()

                        if hasattr(image, 'metadata') and metadata:
                            image.metadata = json.dumps(metadata)

                        processed_count += 1

                        method = metadata.get('optimization_method', 'unknown') if metadata else 'unknown'
                        confidence = metadata.get('confidence_score', 0) if metadata else 0
                        log_verbose(LogCategory.EMBEDDING, f"[BACKGROUND] {image.filename} procesado con {method} (confianza: {confidence:.3f})")

                        # Actualizar tags contextuales del producto
                        if image.product:
                            try:
                                from app.services.attribute_autofill_service import AttributeAutofillService
                                result = AttributeAutofillService.autofill_product_attributes(
                                    image.product,
                                    overwrite=False
                                )
                                if result['success'] and result['tags']:
                                    image.product.tags = result['tags']
                                    log_verbose(LogCategory.EMBEDDING, f"  [BACKGROUND] Tags actualizados para {image.product.name}: {result['tags']}")
                            except Exception as tag_error:
                                log_error(f"[BACKGROUND] Error actualizando tags de {image.product.name}: {tag_error}")

                    except Exception as e:
                        log_error(f"[BACKGROUND] Error procesando {image.filename}: {e}")
                        image.upload_status = 'failed'
                        image.error_message = str(e)

                # Commit por lote
                db.session.commit()
                log_verbose(LogCategory.EMBEDDING, f"[BACKGROUND] Lote guardado: {processed_count}/{total_images} imagenes procesadas")

                # Actualizar centroides de categorías afectadas
                affected_categories = set()
                for image in batch:
                    if image.product and image.product.category and image.is_processed:
                        affected_categories.add(image.product.category)

                for category in affected_categories:
                    try:
                        if category.needs_centroid_update():
                            category.update_centroid_embedding(force_recalculate=False)
                            log_verbose(LogCategory.EMBEDDING, f"[BACKGROUND] Centroide actualizado para categoria: {category.name}")
                    except Exception as e:
                        log_error(f"[BACKGROUND] Error actualizando centroide de {category.name}: {e}")

                # Commit de centroides
                if affected_categories:
                    try:
                        db.session.commit()
                        log_verbose(LogCategory.EMBEDDING, f"[BACKGROUND] {len(affected_categories)} centroides actualizados")
                    except Exception as e:
                        log_error(f"[BACKGROUND] Error guardando centroides: {e}")
                        db.session.rollback()

            log_embedding(f"[BACKGROUND] Procesamiento completado: {processed_count}/{total_images} imagenes procesadas exitosamente")

        except Exception as e:
            log_error(f"[BACKGROUND] Error critico en procesamiento: {e}")
            db.session.rollback()
        finally:
            # Limpiar sesión de DB
            db.session.remove()
            log_system("[BACKGROUND] Thread de procesamiento finalizado")


@bp.route("/process_pending", methods=["POST"])
@login_required
def process_pending():
    """Procesar imágenes pendientes de forma síncrona.

    IMPORTANTE: Procesamiento síncrono para Railway.
    Railway puede matar threads daemon rápidamente, por lo que procesamos
    directamente en la request con timeout extendido.
    """
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

        total_images = len(pending_images)
        processed_count = 0
        batch_size = 5

        log_embedding(f"Procesamiento de {total_images} imagenes con CLIP iniciado")

        for i in range(0, total_images, batch_size):
            batch = pending_images[i:i + batch_size]

            # Pre-descargar imágenes en paralelo
            log_verbose(LogCategory.EMBEDDING, f"Pre-descargando {len(batch)} imagenes en paralelo...")
            preloaded_cache = preload_images_parallel(batch, max_workers=5)

            for image in batch:
                try:
                    log_verbose(LogCategory.EMBEDDING, f"Procesando {image.filename}...")

                    if not image.cloudinary_url:
                        log_error(f"Error: {image.filename} no tiene URL de Cloudinary")
                        image.upload_status = 'failed'
                        image.error_message = "No hay URL de Cloudinary disponible"
                        continue

                    # Usar imagen pre-descargada del cache
                    cached_item = preloaded_cache.get(image.id)

                    if cached_item is None:
                        log_verbose(LogCategory.EMBEDDING, f"{image.filename} no encontrada en cache, descargando...")
                        image_source = image.cloudinary_url
                    elif isinstance(cached_item, str):
                        raise Exception(f"Error en descarga paralela: {cached_item}")
                    else:
                        image_source = cached_item
                        log_verbose(LogCategory.EMBEDDING, f"Usando imagen pre-descargada de {image.filename}")

                    # Generar embedding optimizado con CLIP
                    embedding, metadata = generate_clip_embedding(image_source, image)

                    if embedding is None:
                        raise Exception("Error generando embedding")

                    # Guardar embedding y metadata
                    image.clip_embedding = json.dumps(embedding)
                    image.is_processed = True
                    image.upload_status = 'completed'
                    image.updated_at = datetime.utcnow()

                    if hasattr(image, 'metadata') and metadata:
                        image.metadata = json.dumps(metadata)

                    processed_count += 1

                    method = metadata.get('optimization_method', 'unknown') if metadata else 'unknown'
                    confidence = metadata.get('confidence_score', 0) if metadata else 0
                    log_verbose(LogCategory.EMBEDDING, f"{image.filename} procesado con {method} (confianza: {confidence:.3f})")

                except Exception as e:
                    log_error(f"Error procesando {image.filename}: {e}")
                    image.upload_status = 'failed'
                    image.error_message = str(e)

            # Commit por lote
            db.session.commit()
            log_verbose(LogCategory.EMBEDDING, f"Lote guardado: {processed_count}/{total_images} imagenes procesadas")

        log_embedding(f"Procesamiento completado: {processed_count}/{total_images} imagenes procesadas exitosamente")

        return jsonify({
            "success": True,
            "message": f"Procesamiento completado: {processed_count}/{total_images} imágenes procesadas.",
            "processed_count": processed_count,
            "total_count": total_images,
            "background": False
        })

    except Exception as e:
        log_error(f"Error en procesamiento: {e}")
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


# ============================================================================
# PÁGINA DE PRUEBA: DETECCIÓN MULTI-CATEGORÍA (MULTI-CROP)
# ============================================================================
@bp.route("/test/multicrop", methods=["GET"])
def test_multicrop_page():
    """Renderiza una página simple para probar la detección multi-categoría.

    Permite:
    - Subir una imagen (archivo local)
    - Elegir el cliente
    - Ver categorías detectadas con su score y crop ganador
    """
    try:
        clients = Client.query.filter_by(is_active=True).order_by(Client.name.asc()).all()
    except Exception:
        clients = []
    return render_template("embeddings/test_multicrop.html", clients=clients)


@bp.route("/test/multicrop/detect", methods=["POST"])
def api_test_multicrop_detect():
    """Endpoint de prueba que recibe una imagen subida y devuelve categorías detectadas.

    Request (multipart/form-data):
        - file: imagen
        - client_id: uuid del cliente

    Response (application/json):
        {
          success: true,
          client: { id, name },
          results: [ { category_id, category_name, score, best_crop, crop_scores, passes_threshold } ]
        }
    """
    try:
        # Validaciones básicas
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "Falta el archivo de imagen (file)"}), 400
        file = request.files['file']
        client_id = request.form.get('client_id')
        if not client_id:
            return jsonify({"success": False, "message": "Falta client_id"}), 400

        client = Client.query.get(client_id)
        if not client:
            return jsonify({"success": False, "message": "Cliente no encontrado"}), 404

        # Cargar imagen en memoria como PIL
        try:
            img = PILImage.open(BytesIO(file.read())).convert('RGB')
        except Exception as e:
            return jsonify({"success": False, "message": f"No se pudo leer la imagen: {e}"}), 400

        # Ejecutar detección con estrategia multi-crop
        # Si se recibió un recorte manual (x,y,w,h) aplicar antes de generar crops
        manual_crop = None
        try:
            cx = request.form.get('crop_x'); cy = request.form.get('crop_y'); cw = request.form.get('crop_w'); ch = request.form.get('crop_h')
            if all([cx, cy, cw, ch]):
                cx = int(float(cx)); cy = int(float(cy)); cw = int(float(cw)); ch = int(float(ch))
                # Sanitizar límites
                cx = max(0, cx); cy = max(0, cy)
                cw = max(1, min(cw, img.width - cx))
                ch = max(1, min(ch, img.height - cy))
                manual_crop = (cx, cy, cx+cw, cy+ch)
                img = img.crop(manual_crop)
                clip_logger.info(f"✂️ Recorte manual aplicado: {manual_crop}")
        except Exception as ce:
            clip_logger.warning(f"⚠️ Recorte manual ignorado por error: {ce}")

        # Flag de detección automática (Grounding DINO)
        use_grounding = request.form.get('use_grounding') in ('1', 'true', 'on', 'yes')
        grounding_meta = None

        if use_grounding:
            try:
                from app.utils.grounding_dino import detect_and_crop
                # Obtener nombres de categorías activas para prompt
                active_categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
                category_names = [c.name for c in active_categories]
                cropped_img, meta = detect_and_crop(img, category_names)
                grounding_meta = meta
                img_for_clip = cropped_img
                clip_logger.info(f"🎯 Grounding DINO: label={meta.get('label')} score={meta.get('score')}")
            except Exception as ge:
                clip_logger.warning(f"⚠️ Grounding DINO falló: {ge}. Usando imagen original.")
                img_for_clip = img
        else:
            img_for_clip = img

        # Flag: permitir mostrar ambos delantales (no excluir par delantal)
        allow_apron_pair = request.form.get('allow_apron_pair') in ('1', 'true', 'on', 'yes')

        results = detect_categories_multi_crop(
            img_for_clip,
            client_id=client.id,
            top_k=10,
            apply_pair_exclusion=(not allow_apron_pair)
        )

        # Parámetros opcionales para logging manual
        expected_category = request.form.get('expected_category')  # nombre esperado (libre)
        tester_note = request.form.get('note')  # nota libre del tester

        # Enriquecer resultados con metadata de recorte si hubo
        if manual_crop:
            for r in results:
                r['manual_crop'] = {
                    'x': manual_crop[0], 'y': manual_crop[1],
                    'width': manual_crop[2]-manual_crop[0], 'height': manual_crop[3]-manual_crop[1]
                }

        # Si hubo recorte por grounding, adjuntar a resultados
        if grounding_meta:
            for r in results:
                r['grounding'] = grounding_meta

        log_id = _log_multicrop_test(
            client=client,
            results=results,
            expected_category=expected_category,
            tester_note=tester_note
        )

        return jsonify({
            "success": True,
            "client": {"id": client.id, "name": client.name},
            "results": results,
            "log_id": log_id,
            "expected_category": expected_category,
            "tester_note": tester_note
        })
    except Exception as e:
        clip_logger.error(f"❌ Error en /embeddings/test/multicrop/detect: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

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

        # Simulación temporal con dimensión dinámica basada en modelo configurado
        from app.utils.system_config import system_config
        model_name = system_config.get('clip', 'model_name', 'ViT-B/16')
        embedding_dim = 768 if 'L/14' in model_name else 512

        image.is_processed = True
        image.clip_embedding = json.dumps([0.1] * embedding_dim)
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


# ======================================================
# UTILIDAD: Logging de pruebas multicrop (JSONL)
# ======================================================
def _log_multicrop_test(client, results, expected_category=None, tester_note=None):
    """Guarda una entrada JSONL con el resultado de la prueba multicrop.

    Estructura:
        {
          timestamp: ISO,
          client_id: str,
          client_name: str,
          expected_category: str|None,
          top_prediction: {category_id, category_name, score},
          all_results: [...],
          tester_note: str|None
        }
    """
    try:
        ts = datetime.utcnow().isoformat()
        top_pred = results[0] if results else None
        # Detectar si alguno de los resultados trae metadata de recorte manual
        crop_meta = None
        for r in results:
            if isinstance(r, dict) and r.get('manual_crop'):
                crop_meta = r['manual_crop']
                break
        entry = {
            "timestamp": ts,
            "client_id": str(client.id),  # Convertir UUID a string
            "client_name": client.name,
            "expected_category": expected_category,
            "top_prediction": top_pred,
            "all_results": results,
            "tester_note": tester_note,
            "manual_crop": crop_meta
        }

        # Directorio logs
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)

        # Archivo por día
        day_str = datetime.utcnow().strftime('%Y%m%d')
        log_file = os.path.join(base_dir, f'multicrop_tests_{day_str}.jsonl')

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

        return f"{day_str}-{int(time.time())}"
    except Exception as e:
        clip_logger.error(f"⚠️ Error logueando prueba multicrop: {e}")
        return None


@bp.route("/test/multicrop/logs", methods=["GET"])
@login_required
@requires_role('SUPER_ADMIN', 'STORE_ADMIN')
@requires_client_scope
def list_multicrop_logs():
    """Lista entradas de log multicrop del día indicado (o día actual)."""
    date_str = request.args.get('date')
    limit = int(request.args.get('limit', 50))
    if limit < 1: limit = 1
    if limit > 500: limit = 500

    if not date_str:
        date_str = datetime.utcnow().strftime('%Y%m%d')

    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    log_file = os.path.join(base_dir, f'multicrop_tests_{date_str}.jsonl')

    entries = []
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        # Filtrar por client scope si corresponde
                        # current_user.client_id podría restringir
                        if hasattr(current_user, 'client_id') and current_user.client_id:
                            if str(obj.get('client_id')) != str(current_user.client_id):
                                continue
                        entries.append(obj)
                    except Exception:
                        continue
        # Ordenar descendente por timestamp
        entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        entries = entries[:limit]
        return jsonify({"success": True, "entries": entries, "date": date_str})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@bp.route("/test/multicrop/logs/dates", methods=["GET"])
@login_required
@requires_role('SUPER_ADMIN', 'STORE_ADMIN')
@requires_client_scope
def list_multicrop_log_dates():
    """Devuelve lista de días disponibles con archivos de log multicrop."""
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    dates = []
    try:
        if os.path.exists(base_dir):
            for fn in os.listdir(base_dir):
                if fn.startswith('multicrop_tests_') and fn.endswith('.jsonl'):
                    # Extraer YYYYMMDD
                    part = fn.replace('multicrop_tests_', '').replace('.jsonl', '')
                    if part.isdigit() and len(part) == 8:
                        dates.append(part)
        dates.sort(reverse=True)
        return jsonify({"success": True, "dates": dates[:30]})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@bp.route("/recalculate-centroids", methods=["POST"])
@login_required
@requires_role('SUPER_ADMIN', 'STORE_ADMIN')
@requires_client_scope
def recalculate_centroids():
    """Recalcula los centroides de todas las categorías del cliente actual.

    Forzado (force=True) para garantizar consistencia luego de reembedding.
    """
    try:
        # Determinar client_id según el scope del usuario
        client_id = getattr(current_user, 'client_id', None)
        if not client_id:
            return jsonify({"success": False, "message": "Usuario no asignado a cliente"}), 400

        clip_logger.info(f"🔄 Recalculando centroides para cliente {client_id} (forzado)")
        stats = Category.recalculate_all_centroids(client_id=client_id, force=True)

        return jsonify({
            "success": True,
            "message": "Recalculo de centroides completado",
            "stats": stats
        })
    except Exception as e:
        db.session.rollback()
        clip_logger.error(f"❌ Error recalculando centroides: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================================
# MULTI-CROP DETECTION SYSTEM
# Sistema de detección multi-categoría con crops multi-escala
# ============================================================================

def generate_multi_scale_crops(image):
    """
    Genera crops multi-escala de una imagen para reducir ruido de catálogo sucio.

    Estrategia:
    - full: Imagen completa (contexto global)
    - center_60: Centro 60% (reduce bordes/fondo, enfoca torso)
    - upper_50: Mitad superior (gorros, camisas, accesorios superiores)
    - lower_50: Mitad inferior (pantalones, zapatos, faldas)
    - left_50: Mitad izquierda (asimetría, logos laterales)
    - right_50: Mitad derecha (asimetría, logos laterales)

    Args:
        image: PIL.Image o ruta de imagen

    Returns:
        dict: {
            'full': PIL.Image,
            'center_60': PIL.Image,
            'upper_50': PIL.Image,
            'lower_50': PIL.Image,
            'left_50': PIL.Image,
            'right_50': PIL.Image
        }
    """
    # Cargar imagen si es ruta o bytes
    if isinstance(image, str):
        image = load_image_from_source(image)
    elif isinstance(image, (bytes, bytearray)):
        # Soporte para bytes provenientes de request.files['image'].read()
        import io as _io
        try:
            image = PILImage.open(_io.BytesIO(image)).convert('RGB')
        except Exception as _e:
            raise ValueError(f"No se pudo cargar imagen desde bytes: {_e}")
    elif not isinstance(image, PILImage.Image):
        raise ValueError(f"Tipo de imagen inválido: {type(image)}")

    w, h = image.size

    # Nuevos crops para mejorar discriminación delantal completo vs medio:
    # upper_torso: zona de pechera + cuello (primer ~60% vertical centrado horizontal)
    # chest_focus: región más concentrada en pecho (30%–55% vertical y 15% laterales recortados)
    upper_torso_box = (int(w*0.1), 0, int(w*0.9), int(h*0.6))
    chest_focus_box = (int(w*0.15), int(h*0.08), int(w*0.85), int(h*0.55))

    crops = {
        'full': image,
        'center_60': image.crop((int(w*0.2), int(h*0.2), int(w*0.8), int(h*0.8))),
        'upper_50': image.crop((0, 0, w, int(h*0.5))),
        'lower_50': image.crop((0, int(h*0.5), w, h)),
        'left_50': image.crop((0, 0, int(w*0.5), h)),
        'right_50': image.crop((int(w*0.5), 0, w, h)),
        'upper_torso': image.crop(upper_torso_box),
        'chest_focus': image.crop(chest_focus_box)
    }

    return crops


def detect_categories_multi_crop(
    image_path_or_url,
    client_id,
    threshold=None,
    top_k=5,
    model=None,
    processor=None,
    apply_pair_exclusion: bool = True
):
    """
    Detecta categorías en imagen usando strategy multi-escala.

    Workflow:
    1. Obtiene categorías activas del cliente (via productos)
    2. Genera 6 crops de la imagen
    3. Encode clip_prompt de cada categoría
    4. Calcula similarity de cada crop vs cada prompt
    5. Aggregate score = max(crop_scores)  # El mejor crop gana
    6. Retorna top-k categorías sobre threshold

    Args:
        image_path_or_url: Ruta local o URL de Cloudinary
        client_id: UUID del cliente
        threshold: Score mínimo (default: client.category_confidence_threshold / 100)
        top_k: Número máximo de categorías a retornar
        model: Modelo CLIP (opcional, se carga si no se provee)
        processor: Procesador CLIP (opcional)

    Returns:
        list: [
            {
                'category_id': str,
                'category_name': str,
                'score': float,
                'best_crop': str,  # Qué crop tuvo mejor score
                'crop_scores': dict,  # Scores de cada crop
                'passes_threshold': bool
            }
        ]
    """
    # Cargar modelo si no se proveyó
    if model is None or processor is None:
        model, processor = get_clip_model()
        _touch_clip_last_used()

    # Obtener cliente y threshold
    from app.models.client import Client
    client = Client.query.get(client_id)
    if not client:
        raise ValueError(f"Cliente {client_id} no encontrado")

    if threshold is None:
        threshold = (client.category_confidence_threshold or 70) / 100.0

    # Obtener categorías activas del cliente (via productos)
    from app.models.category import Category
    from app.models.product import Product

    categories = db.session.query(Category).join(
        Product, Product.category_id == Category.id
    ).filter(
        Product.client_id == client_id,
        Product.is_active == True
    ).distinct().all()

    if not categories:
        clip_logger.warning(f"⚠️ Cliente {client.name} no tiene categorías activas")
        return []

    clip_logger.info(f"🔍 Detectando categorías para cliente {client.name}: {len(categories)} categorías activas")

    # Asegurar que, si hay uno de los delantales, también se evalúe su par aunque no tenga productos activos
    try:
        from sqlalchemy import func
        present = { (c.name or '').upper() for c in categories }
        need_full = ('MEDIO DELANTAL' in present) and ('DELANTAL COMPLETO' not in present)
        need_half = ('DELANTAL COMPLETO' in present) and ('MEDIO DELANTAL' not in present)
        extra = []
        if need_full:
            extra_full = db.session.query(Category).filter(func.upper(Category.name).like('%DELANTAL COMPLETO%')).first()
            if extra_full:
                extra.append(extra_full)
        if need_half:
            extra_half = db.session.query(Category).filter(func.upper(Category.name).like('%MEDIO DELANTAL%')).first()
            if extra_half:
                extra.append(extra_half)
        if extra:
            categories = list({c.id: c for c in [*categories, *extra]}.values())
            clip_logger.info(f"➕ Se agregaron {len(extra)} categorías pares para comparación (delantales)")
    except Exception as ex_extra:
        clip_logger.warning(f"⚠️ No se pudieron agregar categorías pares: {ex_extra}")

    # Generar crops
    crops = generate_multi_scale_crops(image_path_or_url)
    clip_logger.info(f"✂️ Generados {len(crops)} crops multi-escala")

    # Encode todos los crops
    crop_embeddings = {}
    for crop_name, crop_img in crops.items():
        crop_emb = generate_image_only_embedding(crop_img, model, processor)
        # Normalizar L2
        crop_emb = crop_emb / np.linalg.norm(crop_emb)
        crop_embeddings[crop_name] = crop_emb

    clip_logger.info(f"📊 Embeddings generados para {len(crop_embeddings)} crops")

    # Calcular scores por categoría
    results = []
    for cat in categories:
        name_upper = (cat.name or '').upper()

        # Prompt por defecto para categorías críticas si falta clip_prompt
        default_prompt = None
        if 'DELANTAL COMPLETO' in name_upper:
            default_prompt = "a professional photo of full bib apron with large chest panel, shoulder straps, neck tie, covers entire torso from chest to knees, industrial kitchen workwear"
        elif 'MEDIO DELANTAL' in name_upper:
            default_prompt = "a professional photo of waist apron without bib or chest coverage, tied only at waist level, covers hips and thighs, half apron, no shoulder straps"
        elif 'CASACA' in name_upper:
            default_prompt = "a professional photo of chef jacket with buttons or zipper closure, long sleeves, collar, white kitchen coat, culinary uniform top"

        if not cat.clip_prompt and not default_prompt:
            clip_logger.warning(f"⚠️ Categoría {cat.name} sin clip_prompt, saltando...")
            continue

        # Elegir prompt inicial (prioriza clip_prompt, sino default)
        prompt_text = cat.clip_prompt or default_prompt

        # Override de prompt para casos críticos (mantener consistencia)
        try:
            if 'DELANTAL COMPLETO' in name_upper:
                prompt_text = "a professional photo of full bib apron with large chest panel, shoulder straps, neck tie, covers entire torso from chest to knees, industrial kitchen workwear"
            elif 'MEDIO DELANTAL' in name_upper:
                prompt_text = "a professional photo of waist apron without bib or chest coverage, tied only at waist level, covers hips and thighs, half apron, no shoulder straps"
            elif 'CASACA' in name_upper:
                prompt_text = "a professional photo of chef jacket with buttons or zipper closure, long sleeves, collar, white kitchen coat, culinary uniform top"
        except Exception:
            pass

        # Pesos por región (crops) para discriminar mejor categorías ambiguas
        # Mantener simple: si un crop no está listado usa 1.0.
        region_weights = {}
        if 'DELANTAL COMPLETO' in name_upper:
            region_weights = {
                'chest_focus': 1.50,
                'upper_torso': 1.35,
                'upper_50': 1.20,
                'center_60': 1.00,
                'lower_50': 0.80,
                'left_50': 0.75,
                'right_50': 0.75,
                'full': 0.90
            }
        elif 'MEDIO DELANTAL' in name_upper:
            region_weights = {
                'lower_50': 1.45,
                'center_60': 1.10,
                'upper_torso': 0.70,
                'chest_focus': 0.60,
                'upper_50': 0.65,
                'left_50': 0.85,
                'right_50': 0.85,
                'full': 0.95
            }
        elif 'CASACA' in name_upper:
            region_weights = {
                'upper_torso': 1.35,
                'chest_focus': 1.30,
                'upper_50': 1.25,
                'center_60': 1.00,
                'lower_50': 0.70,
                'left_50': 0.90,
                'right_50': 0.90,
                'full': 0.95
            }

        text_inputs = processor(text=[prompt_text], return_tensors="pt", padding=True)
        if torch.cuda.is_available():
            text_inputs = {k: v.cuda() for k, v in text_inputs.items()}

        with torch.no_grad():
            text_features = model.get_text_features(**text_inputs)

        text_emb = text_features.cpu().numpy().flatten()
        text_emb = text_emb / np.linalg.norm(text_emb)

        # Calcular similarity de cada crop vs prompt
        crop_scores = {}
        weighted_crop_scores = {}
        for crop_name, crop_emb in crop_embeddings.items():
            score = np.dot(crop_emb, text_emb)
            crop_scores[crop_name] = float(score)
            weight = region_weights.get(crop_name, 1.0)
            weighted_crop_scores[crop_name] = float(score * weight)

        # Aggregate: max weighted score (el mejor crop ponderado gana)
        max_score = max(weighted_crop_scores.values())
        best_crop = max(weighted_crop_scores.items(), key=lambda x: x[1])[0]

        results.append({
            'category_id': str(cat.id),
            'category_name': cat.name,
            'score': max_score,
            'best_crop': best_crop,
            'crop_scores': crop_scores,              # scores crudos
            'weighted_crop_scores': weighted_crop_scores,  # scores tras ponderación
            'passes_threshold': max_score >= threshold
        })

    # Reglas post-proceso simples para delantal:
    # Si "Delantal Completo" presente y alguno de sus crops específicos (upper_torso/chest_focus)
    # supera cierta confianza relativa, suprimir "Medio Delantal" si su score < completo - margin.
    apron_full = next((r for r in results if 'DELANTAL COMPLETO' in r['category_name'].upper()), None)
    apron_half = next((r for r in results if 'MEDIO DELANTAL' in r['category_name'].upper()), None)
    if apron_full and apron_half:
        # Usar scores ponderados para evidencia por región
        w_scores_full = apron_full.get('weighted_crop_scores', apron_full.get('crop_scores', {}))
        full_upper_torso = w_scores_full.get('upper_torso', 0.0)
        full_chest_focus = w_scores_full.get('chest_focus', 0.0)
        evidence_score = max(full_upper_torso, full_chest_focus)
        margin = 0.06  # margen mínimo de diferencia requerido
        suppression_evidence_threshold = 0.20  # evidencia mínima en crops torso (ponderada)
        if apron_full['score'] > apron_half['score'] + margin and evidence_score >= suppression_evidence_threshold:
            apron_half['suppressed'] = True
            apron_half['suppression_reason'] = 'bib_detected'
        else:
            apron_half['suppressed'] = False

    # (Opcional) suprimir headwear si no hay evidencia en upper_torso/chest_focus
    headwear_candidates = [r for r in results if any(x in r['category_name'].upper() for x in ['GORRO', 'GORROS', 'GORRAS'])]
    for hw in headwear_candidates:
        w_scores_hw = hw.get('weighted_crop_scores', hw.get('crop_scores', {}))
        torso_evidence = max(w_scores_hw.get('upper_torso', 0.0), w_scores_hw.get('chest_focus', 0.0))
        if torso_evidence < 0.12:  # umbral suave para evitar suprimir en exceso
            hw['suppressed'] = True
            hw['suppression_reason'] = 'headwear_not_visible'
        else:
            hw['suppressed'] = hw.get('suppressed', False)

    # (La inserción de each result ahora ocurre dentro del loop antes de reglas)

    # Ordenar por score descendente
    results = sorted(results, key=lambda x: x['score'], reverse=True)

    # =============================
    # Exclusión dura de pares (opcional). Si apply_pair_exclusion=False se mantienen ambos.
    # =============================
    if apply_pair_exclusion:
        try:
            # Cargar reglas de exclusión desde BD (por cliente) con fallback a system_config
            from app.models.category_pair_exclusion import CategoryPairExclusion

            # Buscar regla activa para este cliente
            db_rules = CategoryPairExclusion.query.filter_by(
                client_id=client_id,
                is_active=True
            ).all()

            # Obtener configuración por defecto desde system_config
            default_config = system_config.get('pair_exclusion_rules', 'delantal', {})

            # Mapear categorías por nombre
            name_map = { (r['category_name'] or '').upper(): r for r in results }

            # Procesar cada regla de exclusión de la BD
            for rule in db_rules:
                # Buscar las categorías primaria y secundaria en los resultados
                primary_cat = next((r for r in results if r['category_id'] == str(rule.primary_category_id)), None)
                secondary_cat = next((r for r in results if r['category_id'] == str(rule.secondary_category_id)), None)

                if not primary_cat or not secondary_cat:
                    continue

                # Usar parámetros de la regla o defaults del config
                params = rule.params or {}
                tie_margin = params.get('tie_margin', default_config.get('tie_margin', 0.02))
                override_gap_max = params.get('override_gap_max', default_config.get('override_gap_max', 0.10))
                torso_evidence_min = params.get('torso_evidence_min', default_config.get('torso_evidence_min', 0.24))
                torso_advantage_min = params.get('torso_advantage_min', default_config.get('torso_advantage_min', 0.06))

                # Aplicar lógica de exclusión según el tipo de regla
                if rule.exclusion_rule == 'torso_evidence':
                    # Si alguno ya está suprimido, elegir el otro
                    if secondary_cat.get('suppressed') and not primary_cat.get('suppressed'):
                        chosen = primary_cat; other = secondary_cat
                        reason = 'secondary_suppressed'
                    elif primary_cat.get('suppressed') and not secondary_cat.get('suppressed'):
                        chosen = secondary_cat; other = primary_cat
                        reason = 'primary_suppressed'
                    else:
                        # Ambos activos: elegir por score, con desempate usando evidencia regional
                        if abs(primary_cat['score'] - secondary_cat['score']) <= tie_margin:
                            wp = primary_cat.get('weighted_crop_scores', {})
                            ws = secondary_cat.get('weighted_crop_scores', {})
                            torso_primary = max(wp.get('chest_focus', 0.0), wp.get('upper_torso', 0.0))
                            waist_secondary = ws.get('lower_50', 0.0)
                            if torso_primary >= waist_secondary + torso_advantage_min:
                                chosen = primary_cat; other = secondary_cat; reason = 'torso_evidence'
                            else:
                                chosen = secondary_cat; other = primary_cat; reason = 'waist_evidence'
                        else:
                            if primary_cat['score'] > secondary_cat['score']:
                                chosen = primary_cat; other = secondary_cat; reason = 'higher_score'
                            else:
                                # Regla de override suave
                                wp = primary_cat.get('weighted_crop_scores', {})
                                ws = secondary_cat.get('weighted_crop_scores', {})
                                torso_primary = max(wp.get('chest_focus', 0.0), wp.get('upper_torso', 0.0))
                                waist_secondary = ws.get('lower_50', 0.0)
                                torso_advantage = torso_primary - waist_secondary
                                if (secondary_cat['score'] - primary_cat['score']) <= override_gap_max and torso_primary >= torso_evidence_min and torso_advantage >= torso_advantage_min:
                                    chosen = primary_cat; other = secondary_cat; reason = 'torso_override'
                                else:
                                    chosen = secondary_cat; other = primary_cat; reason = 'higher_score'

                    other['excluded_pair'] = True
                    other['exclusion_reason'] = reason
                    chosen['exclusion_reason'] = reason
                    results = [r for r in results if r is not other]
                    clip_logger.info(f"🚫 Exclusión par aplicada (DB rule). Kept='{chosen['category_name']}' score={chosen['score']:.3f} reason={reason}")

            # Fallback: Si no hay reglas en BD, aplicar lógica hardcoded para delantales (compatibilidad)
            if not db_rules:
                full_key = next((k for k in name_map.keys() if 'DELANTAL COMPLETO' in k), None)
                half_key = next((k for k in name_map.keys() if 'MEDIO DELANTAL' in k), None)
                if full_key and half_key:
                    apron_full = name_map[full_key]
                    apron_half = name_map[half_key]

                    # Usar parámetros del default_config
                    tie_margin = default_config.get('tie_margin', 0.02)
                    override_gap_max = default_config.get('override_gap_max', 0.10)
                    torso_evidence_min = default_config.get('torso_evidence_min', 0.24)
                    torso_advantage_min = default_config.get('torso_advantage_min', 0.06)

                    # Si alguno ya está suprimido, elegir el otro
                    if apron_half.get('suppressed') and not apron_full.get('suppressed'):
                        chosen = apron_full; other = apron_half
                        reason = 'half_suppressed'
                    elif apron_full.get('suppressed') and not apron_half.get('suppressed'):
                        chosen = apron_half; other = apron_full
                        reason = 'full_suppressed'
                    else:
                        # Ambos activos: elegir por score, con desempate usando evidencia regional
                        if abs(apron_full['score'] - apron_half['score']) <= tie_margin:
                            wf = apron_full.get('weighted_crop_scores', {})
                            wh = apron_half.get('weighted_crop_scores', {})
                            torso_full = max(wf.get('chest_focus', 0.0), wf.get('upper_torso', 0.0))
                            waist_half = wh.get('lower_50', 0.0)
                            if torso_full >= waist_half + torso_advantage_min:
                                chosen = apron_full; other = apron_half; reason = 'torso_evidence'
                            else:
                                chosen = apron_half; other = apron_full; reason = 'waist_evidence'
                        else:
                            if apron_full['score'] > apron_half['score']:
                                chosen = apron_full; other = apron_half; reason = 'higher_score'
                            else:
                                # Regla de override suave
                                wf = apron_full.get('weighted_crop_scores', {})
                                wh = apron_half.get('weighted_crop_scores', {})
                                torso_full = max(wf.get('chest_focus', 0.0), wf.get('upper_torso', 0.0))
                                waist_half = wh.get('lower_50', 0.0)
                                torso_advantage = torso_full - waist_half
                                if (apron_half['score'] - apron_full['score']) <= override_gap_max and torso_full >= torso_evidence_min and torso_advantage >= torso_advantage_min:
                                    chosen = apron_full; other = apron_half; reason = 'torso_override'
                                else:
                                    chosen = apron_half; other = apron_full; reason = 'higher_score'

                    other['excluded_pair'] = True
                    other['exclusion_reason'] = reason
                    chosen['exclusion_reason'] = reason
                    results = [r for r in results if r is not other]
                    clip_logger.info(f"🚫 Exclusión par delantal aplicada (fallback). Kept='{chosen['category_name']}' score={chosen['score']:.3f} reason={reason}")
        except Exception as ex_pair:
            clip_logger.warning(f"⚠️ Error aplicando exclusión de par: {ex_pair}")

    # Filtrar por threshold preliminar
    passed = [r for r in results if r['passes_threshold']]

    # Logging detallado de TOP 5 (siempre, aunque no pasen el umbral)
    clip_logger.info("🔎 TOP 5 raw scores (antes de aplicar fallback):")
    for r in results[:5]:
        clip_logger.info(f"   {r['category_name']:<30s} score={r['score']:.3f} passes={r['passes_threshold']} best_crop={r['best_crop']}")

    # Si ninguna categoría pasa el umbral, aplicar estrategia de fallback:
    # - Usar top_k categorías crudas
    # - Marcar passes_threshold sólo para la mejor (winner) para evitar vacío total
    if not passed:
        clip_logger.warning("⚠️ Ninguna categoría supera el threshold. Aplicando fallback (top_k crudo).")
        if results:
            winner_score = results[0]['score']
            # Ajustar threshold dinámico (winner * 0.85) para marcar algunas como 'pasó'
            adaptive_cut = winner_score * 0.85
            for r in results[:top_k]:
                r['passes_threshold'] = r['score'] >= adaptive_cut
            clip_logger.info(f"🔧 Threshold adaptativo aplicado: {adaptive_cut:.3f} (85% del ganador {winner_score:.3f})")
        return results[:top_k]

    clip_logger.info(f"✅ Detección completa: {len(passed)}/{len(results)} categorías sobre threshold")
    for r in passed[:3]:
        clip_logger.info(f"   {r['category_name']}: score={r['score']:.3f} (best_crop={r['best_crop']})")

    # Retornar sólo las que pasan (limitadas a top_k)
    return passed[:top_k]


# ============================================================================
# UNIFIED CENTROID-BASED DETECTION (V2 - SaaS Ready)
# Sistema 100% dinámico basado en centroides + multi-crop
# Sin hardcoding de prompts, region weights ni palabras específicas
# ============================================================================

def detect_categories_centroid_based(
    image_path_or_url,
    client_id,
    threshold=None,
    top_k=5,
    model=None,
    processor=None,
    apply_pair_exclusion: bool = False
):
    """
    Detecta categorías usando SOLO centroides + multi-crop.

    Sistema 100% dinámico para SaaS multi-cliente:
    - NO requiere prompts hardcoded
    - NO requiere region weights específicos
    - NO busca palabras específicas ("delantal", "gorro", etc.)
    - Funciona con cualquier industria (ropa, muebles, electrónica, etc.)

    Workflow:
    1. Obtiene categorías del cliente que tienen centroides válidos
    2. Genera 8 crops multi-escala de la imagen query
    3. Genera embeddings de cada crop
    4. Compara cada crop vs centroide de cada categoría
    5. Score final = max similarity entre todos los crops
    6. Aplica CategoryPairExclusion desde BD (dinámico)
    7. Retorna top_k categorías sobre threshold

    Args:
        image_path_or_url: Ruta local o URL de imagen
        client_id: UUID del cliente
        threshold: Score mínimo (default: client.category_confidence_threshold / 100)
        top_k: Número máximo de categorías a retornar
        model: Modelo CLIP (opcional, se carga si no se provee)
        processor: Procesador CLIP (opcional)
        apply_pair_exclusion: Si aplica reglas de exclusión de pares desde BD

    Returns:
        list: [
            {
                'category_id': str,
                'category_name': str,
                'score': float,
                'best_crop': str,
                'crop_scores': dict,
                'passes_threshold': bool,
                'centroid_quality': dict  # metadata del centroide
            }
        ]
    """
    from app.models.client import Client
    from app.models.category import Category
    from app.models.product import Product

    # Cargar modelo CLIP si no se proveyó
    if model is None or processor is None:
        model, processor = get_clip_model()
        _touch_clip_last_used()

    # Obtener cliente y threshold
    client = Client.query.get(client_id)
    if not client:
        raise ValueError(f"Cliente {client_id} no encontrado")

    if threshold is None:
        threshold = (client.category_confidence_threshold or 70) / 100.0

    clip_logger.info(f"🔍 [UNIFIED] Detectando categorías para cliente {client.name} (threshold={threshold:.2f})")

    # Obtener categorías con centroides válidos
    categories_query = db.session.query(Category).join(
        Product, Product.category_id == Category.id
    ).filter(
        Product.client_id == client_id,
        Product.is_active == True,
        Category.centroid_embedding.isnot(None)  # CRÍTICO: solo categorías con centroide
    ).distinct()

    categories = categories_query.all()

    if not categories:
        clip_logger.warning(f"⚠️ Cliente {client.name} no tiene categorías con centroides válidos")
        return []

    clip_logger.info(f"📊 Evaluando {len(categories)} categorías con centroides válidos")

    # Bloque de diagnóstico detallado: logs paso a paso + captura de errores
    try:
        clip_logger.info("[UNIFIED][STEP A] Generando crops multi-escala…")
        # Generar crops multi-escala
        crops = generate_multi_scale_crops(image_path_or_url)
        clip_logger.info(f"✂️ Generados {len(crops)} crops: {list(crops.keys())}")

        # (Opcional) Log de tamaños por crop para diagnosticar imágenes atípicas
        try:
            sizes = {k: getattr(v, 'size', None) for k, v in crops.items()}
            clip_logger.info(f"[UNIFIED][STEP A.1] Tamaños de crops (ancho, alto): {sizes}")
        except Exception as e_sizes:
            clip_logger.warning(f"[UNIFIED][STEP A.1] No se pudieron loggear tamaños de crops: {e_sizes}")

        clip_logger.info("[UNIFIED][STEP B] Generando embeddings por crop…")
        # Generar embeddings para cada crop
        crop_embeddings = {}
        for crop_name, crop_img in crops.items():
            try:
                crop_emb = generate_image_only_embedding(crop_img, model, processor)
                # Normalizar L2
                crop_emb = crop_emb / np.linalg.norm(crop_emb)
                crop_embeddings[crop_name] = crop_emb
            except Exception as e_emb:
                clip_logger.error(f"[UNIFIED][STEP B] Error generando embedding para crop '{crop_name}': {e_emb}")
                import traceback as _tb
                clip_logger.error(_tb.format_exc())
                # Continuar con los otros crops para ver si el problema es específico
                continue

        clip_logger.info(f"📊 Embeddings generados para {len(crop_embeddings)} crops")

        clip_logger.info(f"[UNIFIED][STEP C] Calculando score por categoría… (n={len(categories)})")
        # Calcular scores por categoría
        results = []
        for idx, cat in enumerate(categories, start=1):
            try:
                # Cargar centroide
                centroid_data = json.loads(cat.centroid_embedding)
                centroid = np.array(centroid_data)
                centroid = centroid / np.linalg.norm(centroid)  # Normalizar

                # Calcular similarity de cada crop vs centroide
                crop_scores = {}
                for crop_name, crop_emb in crop_embeddings.items():
                    similarity = float(np.dot(crop_emb, centroid))
                    crop_scores[crop_name] = similarity

                # Score final = mejor crop (sin weights hardcoded)
                max_score = max(crop_scores.values())
                best_crop = max(crop_scores, key=crop_scores.get)

                results.append({
                    'category_id': str(cat.id),
                    'category_name': cat.name,
                    'score': max_score,
                    'best_crop': best_crop,
                    'crop_scores': crop_scores,
                    'passes_threshold': max_score >= threshold,
                    'centroid_quality': {
                        'image_count': cat.centroid_image_count or 0,
                        'last_updated': cat.centroid_updated_at.isoformat() if cat.centroid_updated_at else None
                    }
                })

                # Log de progreso cada 5 categorías
                if idx % 5 == 0:
                    clip_logger.info(f"[UNIFIED][STEP C] Progreso: {idx}/{len(categories)} categorías procesadas")

            except Exception as e_cat:
                clip_logger.error(f"❌ Error procesando categoría {cat.name}: {e_cat}")
                import traceback as _tb
                clip_logger.error(_tb.format_exc())
                continue

        # Ordenar por score descendente
        clip_logger.info(f"[UNIFIED][STEP D] Ordenando resultados… (n={len(results)})")
        results = sorted(results, key=lambda x: x['score'], reverse=True)

        # Aplicar CategoryPairExclusion desde BD (si está habilitado)
        if apply_pair_exclusion:
            before = len(results)
            results = apply_category_pair_exclusion(results, client_id, crop_embeddings)
            after = len(results)
            clip_logger.info(f"[UNIFIED][STEP E] Pair exclusion aplicado: {before} -> {after}")

    except Exception as e_top:
        # Log detallado del fallo y re-lanzar para que el endpoint devuelva 500 (con logs en servidor)
        clip_logger.error(f"[UNIFIED][ERROR] Fallo en pipeline unificado: {e_top}")
        import traceback as _tb
        clip_logger.error(_tb.format_exc())
        raise

    # Logging de resultados
    clip_logger.info(f"🔎 TOP 5 categorías detectadas:")
    for r in results[:5]:
        status = "✅" if r['passes_threshold'] else "⚠️"
        clip_logger.info(
            f"   {status} {r['category_name']:<30s} "
            f"score={r['score']:.3f} "
            f"best_crop={r['best_crop']} "
            f"(centroid: {r['centroid_quality']['image_count']} imgs)"
        )

    # Filtrar por threshold
    passed = [r for r in results if r['passes_threshold']]

    if not passed:
        clip_logger.warning("⚠️ Ninguna categoría supera threshold. Aplicando fallback.")
        if results:
            # Threshold adaptativo: 85% del mejor score
            winner_score = results[0]['score']
            adaptive_threshold = winner_score * 0.85
            for r in results[:top_k]:
                r['passes_threshold'] = r['score'] >= adaptive_threshold
                r['adaptive_threshold_applied'] = True
            clip_logger.info(f"🔧 Threshold adaptativo: {adaptive_threshold:.3f}")
        return results[:top_k]

    clip_logger.info(f"✅ Detección completa: {len(passed)}/{len(results)} categorías sobre threshold")
    return passed[:top_k]


def apply_category_pair_exclusion(results, client_id, crop_embeddings):
    """
    Aplica reglas de exclusión de pares desde CategoryPairExclusion (BD).

    100% dinámico: Lee reglas desde BD, no tiene lógica hardcoded.

    Args:
        results: Lista de resultados de detección
        client_id: ID del cliente
        crop_embeddings: Dict con embeddings de crops (para análisis regional)

    Returns:
        list: Resultados con exclusiones aplicadas
    """
    try:
        from app.models.category_pair_exclusion import CategoryPairExclusion

        # Cargar reglas activas para este cliente
        rules = CategoryPairExclusion.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        if not rules:
            clip_logger.info("ℹ️ No hay reglas de exclusión de pares configuradas")
            return results

        clip_logger.info(f"🔧 Aplicando {len(rules)} reglas de exclusión de pares")

        # Obtener configuración default desde system_config
        default_config = system_config.get('pair_exclusion_rules', {}).get('delantal', {})

        for rule in rules:
            # Buscar categorías primaria y secundaria en resultados
            primary = next((r for r in results if r['category_id'] == str(rule.primary_category_id)), None)
            secondary = next((r for r in results if r['category_id'] == str(rule.secondary_category_id)), None)

            if not primary or not secondary:
                continue

            # Parámetros de la regla (con fallback a defaults)
            params = rule.params or {}
            tie_margin = params.get('tie_margin', default_config.get('tie_margin', 0.02))

            # Lógica de exclusión según tipo de regla
            if rule.exclusion_rule == 'torso_evidence':
                # Comparar evidencia en crops de torso vs cintura
                torso_crops = ['chest_focus', 'upper_torso', 'upper_50']
                waist_crops = ['lower_50', 'center_60']

                torso_primary = max([primary['crop_scores'].get(c, 0.0) for c in torso_crops])
                waist_secondary = max([secondary['crop_scores'].get(c, 0.0) for c in waist_crops])

                torso_advantage_min = params.get('torso_advantage_min', default_config.get('torso_advantage_min', 0.06))

                # Si scores similares, decidir por evidencia regional
                if abs(primary['score'] - secondary['score']) <= tie_margin:
                    if torso_primary >= waist_secondary + torso_advantage_min:
                        chosen, excluded = primary, secondary
                        reason = 'torso_evidence_tie'
                    else:
                        chosen, excluded = secondary, primary
                        reason = 'waist_evidence_tie'
                else:
                    # Elegir por score mayor
                    if primary['score'] > secondary['score']:
                        chosen, excluded = primary, secondary
                        reason = 'higher_score'
                    else:
                        chosen, excluded = secondary, primary
                        reason = 'higher_score'

                # Marcar excluida
                excluded['excluded_by_pair_rule'] = True
                excluded['exclusion_reason'] = reason
                excluded['excluded_in_favor_of'] = chosen['category_name']

                # Remover de resultados
                results = [r for r in results if r['category_id'] != excluded['category_id']]

                clip_logger.info(
                    f"🚫 Exclusión aplicada: {excluded['category_name']} "
                    f"(score={excluded['score']:.3f}) excluida en favor de "
                    f"{chosen['category_name']} (score={chosen['score']:.3f}), razón={reason}"
                )

            elif rule.exclusion_rule == 'score_threshold':
                # Exclusión simple por diferencia de score
                min_score_diff = params.get('min_score_diff', 0.05)
                if primary['score'] > secondary['score'] + min_score_diff:
                    secondary['excluded_by_pair_rule'] = True
                    secondary['exclusion_reason'] = 'score_threshold'
                    results = [r for r in results if r['category_id'] != secondary['category_id']]
                    clip_logger.info(f"🚫 {secondary['category_name']} excluida por score_threshold")

        return results

    except Exception as e:
        clip_logger.error(f"❌ Error aplicando exclusión de pares: {e}")
        return results
