"""
Normalizador semántico de queries usando Sentence Transformers (MiniLM)
Extrae color, tipo y contexto de la consulta del usuario DINÁMICAMENTE desde BD del cliente.
USA EMBEDDINGS SEMÁNTICOS para matching flexible.
"""
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
import time
import json
import threading
import os

# Modelo liviano multilingüe
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
_model = None
_model_last_used_ts = None  # Timestamp de último uso
_model_cleanup_thread_started = False
_model_lock = threading.Lock()

# Caché de vocabulario por cliente (evita queries repetidas)
_VOCABULARY_CACHE = {}
_VOCABULARY_CACHE_TTL = 300  # 5 minutos de TTL


def _now_ts() -> float:
    return time.time()


def _touch_model_last_used():
    """Marca el último uso del modelo MiniLM"""
    global _model_last_used_ts
    _model_last_used_ts = _now_ts()


def _get_minilm_idle_timeout_seconds() -> int:
    """
    Obtiene el timeout de inactividad para descargar MiniLM.
    Usa el MISMO timeout que CLIP para consistencia.

    Prioridad:
    1) system_config.json: clip.idle_timeout_minutes
    2) Env var CLIP_IDLE_TIMEOUT_MINUTES
    3) Env var CLIP_IDLE_TIMEOUT_SECONDS
    4) Default: 120 minutos (2 horas)
    """
    try:
        from app.utils.system_config import system_config
        minutes = system_config.get('clip', 'idle_timeout_minutes', 120)
        return int(minutes) * 60
    except Exception:
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


def _start_minilm_cleanup_thread_once():
    """Inicia un hilo daemon que descarga MiniLM tras inactividad (mismo sistema que CLIP)."""
    global _model_cleanup_thread_started
    if _model_cleanup_thread_started:
        return

    _model_cleanup_thread_started = True
    import logging
    logging.getLogger("minilm_model").info("[MiniLM] Hilo de limpieza iniciado")

    def _worker():
        global _model, _model_last_used_ts
        while True:
            try:
                idle_timeout = _get_minilm_idle_timeout_seconds()
                check_every = 300  # 5 minutos
                time.sleep(check_every)
                with _model_lock:
                    if _model is None:
                        continue
                    now = _now_ts()
                    if _model_last_used_ts is None:
                        # Nunca usado desde carga: descargar si pasó el timeout
                        if hasattr(_model, 'loaded_at'):
                            idle_for = now - _model.loaded_at
                        else:
                            idle_for = idle_timeout + 1
                        if idle_for >= idle_timeout:
                            _model = None
                            print(f"🧹 MiniLM descargado por inactividad tras arranque (sin uso, timeout {idle_timeout}s)")
                            logging.getLogger("minilm_model").info(f"[MiniLM] Modelo descargado de memoria por inactividad tras arranque (timeout {idle_timeout}s)")
                        continue
                    idle_for = now - _model_last_used_ts
                    if idle_for >= idle_timeout:
                        _model = None
                        print(f"🧹 MiniLM descargado por inactividad (idle {int(idle_for)}s ≥ {idle_timeout}s)")
                        logging.getLogger("minilm_model").info(f"[MiniLM] Modelo descargado de memoria por inactividad (idle {int(idle_for)}s ≥ {idle_timeout}s)")
            except Exception as _e:
                logging.getLogger("minilm_model").error(f"[MiniLM] Error en hilo de limpieza: {_e}")
                continue

    t = threading.Thread(target=_worker, name="minilm-idle-cleanup", daemon=True)
    t.start()


def get_model():
    """Cargar modelo MiniLM con singleton y auto-descarga por inactividad (mismo sistema que CLIP)."""
    global _model
    import time
    t_start = time.time()

    # Asegurar hilo de limpieza iniciado una vez
    _start_minilm_cleanup_thread_once()

    with _model_lock:
        if _model is None:
            print(f"🔄 [MiniLM] Cargando modelo {MODEL_NAME} desde disco...", flush=True)
            _model = SentenceTransformer(MODEL_NAME)
            _model.loaded_at = _now_ts()  # Marcar timestamp de carga
            print(f"✅ [MiniLM] Modelo cargado en {time.time()-t_start:.2f}s", flush=True)
        else:
            print(f"♻️ [MiniLM] Usando modelo YA CARGADO en memoria (singleton activo)", flush=True)
        # Marcar uso cada vez que se obtiene el modelo
        _touch_model_last_used()
        return _model


def _save_color_embeddings(client_id: int, new_embeddings: dict):
    """Guarda embeddings de colores nuevos en la BD (merge con existentes)"""
    from app import db
    from sqlalchemy import text

    try:
        # Leer vocabulario actual
        row = db.session.execute(
            text("SELECT vocabulary FROM client_vocabulary_cache WHERE client_id = :cid"),
            {"cid": str(client_id)}
        ).fetchone()

        if not row:
            return

        vocab = row[0] if isinstance(row[0], dict) else json.loads(row[0])

        # Merge embeddings nuevos con existentes
        if 'color_embeddings' not in vocab:
            vocab['color_embeddings'] = {}

        vocab['color_embeddings'].update(new_embeddings)

        # Update en BD
        db.session.execute(
            text("""
                UPDATE client_vocabulary_cache
                SET vocabulary = CAST(:vocab AS JSONB), updated_at = NOW()
                WHERE client_id = :cid
            """),
            {"cid": str(client_id), "vocab": json.dumps(vocab)}
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


def _extract_client_vocabulary(client_id: int) -> dict:
    """
    Extrae vocabulario dinámico desde la BD del cliente CON CACHÉ en memoria

    Returns:
        dict con 'colores', 'colores_especificos', 'tipos', 'contextos' basados en datos reales
    """
    # Check caché
    cache_key = f"vocab_{client_id}"
    if cache_key in _VOCABULARY_CACHE:
        cached_vocab, cached_time = _VOCABULARY_CACHE[cache_key]
        if time.time() - cached_time < _VOCABULARY_CACHE_TTL:
            print(f"📦 VOCAB CACHE HIT: {client_id}")
            return cached_vocab

    from app import db
    from app.models.category import Category
    from app.models.product import Product
    from app.models.product_attribute_config import ProductAttributeConfig
    from sqlalchemy import text, func

    # 0) Intentar leer desde client_vocabulary_cache (DB cache persistente)
    try:
        row = db.session.execute(
            text("""
                SELECT vocabulary
                FROM client_vocabulary_cache
                WHERE client_id = :client_id
            """),
            {"client_id": str(client_id)}
        ).fetchone()

        if row and row[0]:
            vocab_value = row[0]
            if isinstance(vocab_value, str):
                try:
                    vocab_value = json.loads(vocab_value)
                except Exception:
                    vocab_value = None

            if isinstance(vocab_value, dict):
                # Normalizar a listas seguras
                result = {
                    'colores': list(vocab_value.get('colores', []) or []),
                    'tipos': list(vocab_value.get('tipos', []) or []),
                    'contextos': list(vocab_value.get('contextos', []) or []),
                }
                _VOCABULARY_CACHE[cache_key] = (result, time.time())
                print(f"💾 VOCAB (DB cache) cargado: {client_id} → c={len(result['colores'])} t={len(result['tipos'])} x={len(result['contextos'])}")
                return result
    except Exception as e:
        print(f"⚠️ Error leyendo client_vocabulary_cache: {e}")

    vocabulary = {
        'colores_especificos': set(),  # Colores de productos (azul, rojo, violeta)
        'colores_genericos': set(),    # Variaciones genéricas (multicolor, colorido)
        'tipos': set(),
        'contextos': set()
    }

    # 1A. COLORES DESDE CONFIGURACIÓN JSONB: Leer opciones definidas en attribute_configs
    try:
        color_configs = ProductAttributeConfig.query.filter_by(
            client_id=client_id,
            key='color'
        ).all()

        for config in color_configs:
            if config.type == 'list' and config.options:
                # Opciones es JSONB, puede ser lista o string JSON
                if isinstance(config.options, list):
                    for option in config.options:
                        if option and len(option) > 2:
                            vocabulary['colores_especificos'].add(option.lower().strip())
                elif isinstance(config.options, str):
                    import json
                    try:
                        options_list = json.loads(config.options)
                        for option in options_list:
                            if option and len(option) > 2:
                                vocabulary['colores_especificos'].add(option.lower().strip())
                    except:
                        pass

        if vocabulary['colores_especificos']:
            print(f"📋 Colores desde config JSONB: {len(vocabulary['colores_especificos'])} opciones")

    except Exception as e:
        print(f"⚠️ Error extrayendo colores desde config: {e}")

    # 1B. COLORES DESDE PRODUCTOS: Valores reales en attributes->>'color'
    try:
        color_rows = db.session.execute(
            text("""
                SELECT DISTINCT LOWER(TRIM(p.attributes->>'color')) as color
                FROM products p
                WHERE p.client_id = :client_id
                  AND p.attributes ? 'color'
                  AND NULLIF(TRIM(p.attributes->>'color'), '') IS NOT NULL
            """),
            {"client_id": client_id}
        ).fetchall()

        for row in color_rows:
            if row[0]:
                # Dividir si hay múltiples colores separados por comas/espacios
                colors = re.split(r'[,/\s]+', row[0].lower())
                for c in colors:
                    c_clean = c.strip()
                    if len(c_clean) > 2 and c_clean not in ['de', 'con', 'sin']:
                        vocabulary['colores_especificos'].add(c_clean)

    except Exception as e:
        print(f"⚠️ Error extrayendo colores desde productos: {e}")

    # Variaciones genéricas (solo si NO hay color específico en query)
    vocabulary['colores_genericos'] = {
        'multicolor', 'colorido', 'de colores', 'estampado', 'brillante',
        'oscuro', 'claro', 'pastel', 'mate', 'metalizado'
    }

    # 2. TIPOS: Desde nombres de categorías del cliente
    try:
        categories = Category.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        for cat in categories:
            # Extraer palabras clave del nombre de categoría
            # Ej: "GORROS – GORRAS (HATS - CAPS)" → ["gorros", "gorras", "hats", "caps"]
            # Eliminar símbolos y separar palabras
            clean_name = re.sub(r'[–\-()]+', ' ', cat.name.lower())
            words = re.findall(r'\b[a-záéíóúñ]{3,}\b', clean_name)
            vocabulary['tipos'].update(words)

            # También agregar el nombre completo limpio
            if len(cat.name) > 3:
                vocabulary['tipos'].add(cat.name.lower().strip())

    except Exception as e:
        print(f"⚠️ Error extrayendo tipos: {e}")

    # 3. CONTEXTOS: Desde tags de productos del cliente
    try:
        # 🔥 OPTIMIZACIÓN: Usar SQL directo en lugar de cargar todos los productos
        # Extraer tags únicos con agregación SQL (mucho más rápido que Python loop)
        tag_rows = db.session.execute(
            text("""
                SELECT DISTINCT UNNEST(string_to_array(tags, ',')) as tag
                FROM products
                WHERE client_id = :client_id
                  AND tags IS NOT NULL
                  AND tags != ''
            """),
            {"client_id": client_id}
        ).fetchall()

        for row in tag_rows:
            tag = row[0].strip().lower() if row[0] else None
            if tag and len(tag) > 2:
                vocabulary['contextos'].add(tag)

        print(f"🏷️ Contextos extraídos: {len(vocabulary['contextos'])} tags únicos")

    except Exception as e:
        print(f"⚠️ Error extrayendo contextos: {e}")

    # Convertir sets a listas
    result = {
        'colores': list(vocabulary['colores_especificos']),
        'tipos': list(vocabulary['tipos']),
        'contextos': list(vocabulary['contextos'])
    }

    # Guardar en caché (fallback dinámico si no existía en DB cache)
    _VOCABULARY_CACHE[cache_key] = (result, time.time())
    print(f"💾 VOCAB CACHED (fallback dinámico): {client_id} ({len(result['colores'])} colors, {len(result['tipos'])} tipos, {len(result['contextos'])} contextos)")

    return result


def _semantic_match(query: str, vocabulary: list, client_id: int, threshold: float = 0.5) -> str:
    """
    Encuentra la mejor coincidencia semántica usando embeddings cacheados.

    Args:
        query: Texto de búsqueda
        vocabulary: Lista de términos candidatos del cliente
        threshold: Similitud mínima para considerar match (0-1)

    Returns:
        Mejor match o None si no supera threshold
    """
    if not vocabulary:
        return None

    model = get_model()

    # Encodear SOLO la query (rápido: 1 item)
    query_emb = model.encode([query.lower()])[0]

    # 🔥 OPTIMIZACIÓN: Leer embeddings pre-calculados desde BD
    from app.models.embedding import Embedding
    from app import db
    from sqlalchemy import text
    import json

    # Buscar embeddings de vocabulario en BD
    vocab_lower = [v.lower() for v in vocabulary]
    vocab_embeddings = {}

    # 1) Intentar obtener desde client_vocabulary_cache.color_embeddings (específico por cliente)
    try:
        row = db.session.execute(
            text("""
                SELECT vocabulary
                FROM client_vocabulary_cache
                WHERE client_id = :cid
            """),
            {"cid": str(client_id)}
        ).fetchone()
        if row and row[0]:
            vocab_row = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            color_embs = vocab_row.get('color_embeddings') or {}
            for term in vocab_lower:
                if term in color_embs:
                    try:
                        vocab_embeddings[term] = np.array(color_embs[term], dtype=np.float32)
                    except Exception:
                        pass
    except Exception:
        pass

    # 2) Completar faltantes leyendo desde tabla Embedding
    # Query en batch para todos los términos del vocabulario
    db_embeddings = Embedding.query.filter(
        Embedding.key.in_([f"vocab:{term}" for term in vocab_lower if term not in vocab_embeddings])
    ).all()

    for emb_obj in db_embeddings:
        term = emb_obj.key.replace("vocab:", "")
        try:
            vocab_embeddings[term] = np.array(json.loads(emb_obj.embedding), dtype=np.float32)
        except Exception:
            continue

    # Si no hay embeddings en BD, calcular en vivo (fallback para vocabulario nuevo)
    missing_terms = [v for v in vocab_lower if v not in vocab_embeddings]
    if missing_terms:
        print(f"⚠️ {len(missing_terms)} términos sin embedding en BD, calculando: {', '.join(missing_terms[:5])}{'...' if len(missing_terms) > 5 else ''}")
        missing_embs = model.encode(missing_terms)
        for term, emb in zip(missing_terms, missing_embs):
            vocab_embeddings[term] = emb

        # Guardar embeddings nuevos en la BD para futuras búsquedas
        try:
            _save_color_embeddings(client_id, {term: emb.tolist() for term, emb in zip(missing_terms, missing_embs)})
            print(f"✅ {len(missing_terms)} embeddings guardados en BD para futuras búsquedas")
        except Exception as e:
            print(f"⚠️ Error guardando embeddings: {e}")

    # Construir matriz de embeddings en el orden original
    vocab_embs = np.array([vocab_embeddings[v] for v in vocab_lower if v in vocab_embeddings])

    if len(vocab_embs) == 0:
        return None

    # Calcular similitudes coseno
    similarities = cosine_similarity([query_emb], vocab_embs)[0]

    # Encontrar el mejor match
    max_idx = np.argmax(similarities)
    max_sim = similarities[max_idx]

    if max_sim >= threshold:
        print(f"  🎯 Match: '{query}' → '{vocabulary[max_idx]}' (sim={max_sim:.3f})")
        return vocabulary[max_idx]

    return None


def _semantic_match_multiple(query: str, vocabulary: list, client_id: int, threshold: float = 0.4, top_k: int = 3) -> list:
    """
    Encuentra múltiples coincidencias semánticas usando embeddings cacheados.

    Args:
        query: Texto de búsqueda
        vocabulary: Lista de términos candidatos
        threshold: Similitud mínima
        top_k: Máximo de matches a retornar

    Returns:
        Lista de matches ordenados por similitud
    """
    if not vocabulary:
        return []

    model = get_model()

    # Encodear SOLO la query (rápido: 1 item)
    query_emb = model.encode([query.lower()])[0]

    # 🔥 OPTIMIZACIÓN: Leer embeddings pre-calculados desde BD
    from app.models.embedding import Embedding
    from app import db
    from sqlalchemy import text
    import json

    # Buscar embeddings de vocabulario en BD
    vocab_lower = [v.lower() for v in vocabulary]
    vocab_embeddings = {}

    # 1) Intentar obtener desde client_vocabulary_cache.color_embeddings (específico por cliente)
    try:
        row = db.session.execute(
            text("""
                SELECT vocabulary
                FROM client_vocabulary_cache
                WHERE client_id = :cid
            """),
            {"cid": str(client_id)}
        ).fetchone()
        if row and row[0]:
            vocab_row = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            color_embs = vocab_row.get('color_embeddings') or {}
            for term in vocab_lower:
                if term in color_embs:
                    try:
                        vocab_embeddings[term] = np.array(color_embs[term], dtype=np.float32)
                    except Exception:
                        pass
    except Exception:
        pass

    # 2) Completar faltantes leyendo desde tabla Embedding
    # Query en batch para todos los términos del vocabulario
    db_embeddings = Embedding.query.filter(
        Embedding.key.in_([f"vocab:{term}" for term in vocab_lower if term not in vocab_embeddings])
    ).all()

    for emb_obj in db_embeddings:
        term = emb_obj.key.replace("vocab:", "")
        try:
            vocab_embeddings[term] = np.array(json.loads(emb_obj.embedding), dtype=np.float32)
        except Exception:
            continue

    # Si no hay embeddings en BD, calcular en vivo (fallback)
    missing_terms = [v for v in vocab_lower if v not in vocab_embeddings]
    if missing_terms:
        print(f"⚠️ {len(missing_terms)} términos sin embedding en BD, calculando: {', '.join(missing_terms[:5])}{'...' if len(missing_terms) > 5 else ''}")
        missing_embs = model.encode(missing_terms)
        for term, emb in zip(missing_terms, missing_embs):
            vocab_embeddings[term] = emb

        # Guardar embeddings nuevos en la BD para futuras búsquedas
        try:
            _save_color_embeddings(client_id, {term: emb.tolist() for term, emb in zip(missing_terms, missing_embs)})
            print(f"✅ {len(missing_terms)} embeddings guardados en BD para futuras búsquedas")
        except Exception as e:
            print(f"⚠️ Error guardando embeddings: {e}")

    # Construir matriz de embeddings en el orden original
    vocab_embs = np.array([vocab_embeddings[v] for v in vocab_lower if v in vocab_embeddings])

    if len(vocab_embs) == 0:
        return []

    # Calcular similitudes
    similarities = cosine_similarity([query_emb], vocab_embs)[0]

    # Filtrar por threshold y ordenar
    matches = []
    for idx, sim in enumerate(similarities):
        if sim >= threshold:
            matches.append((vocabulary[idx], sim))

    # Ordenar por similitud descendente y tomar top_k
    matches.sort(key=lambda x: x[1], reverse=True)

    if matches:
        print(f"  🎯 Matches contextos: {[(m[0], f'{m[1]:.3f}') for m in matches[:top_k]]}")

    return [match[0] for match in matches[:top_k]]


def _detect_ambiguous_terms(query: str, vocabulary: dict) -> dict:
    """
    Detecta términos genéricos/ambiguos en la query y sugiere refinamientos.

    Args:
        query: Query del usuario
        vocabulary: Vocabulario del cliente (colores, tipos, contextos)

    Returns:
        dict con sugerencias de refinamiento si la query es ambigua
    """
    query_lower = query.lower()
    suggestions = {
        'is_ambiguous': False,
        'ambiguous_terms': [],
        'suggestions': {}
    }

    # Palabras genéricas que indican necesidad de refinamiento
    generic_color_terms = ['color', 'colores', 'colorido', 'colorida']
    generic_style_terms = ['estilo', 'tipo', 'modelo', 'diseño']

    # Detectar si hay términos genéricos
    for term in generic_color_terms:
        if term in query_lower:
            suggestions['is_ambiguous'] = True
            suggestions['ambiguous_terms'].append(term)
            # Sugerir colores disponibles del cliente
            if vocabulary.get('colores'):
                suggestions['suggestions']['colores'] = vocabulary['colores'][:8]  # Top 8

    for term in generic_style_terms:
        if term in query_lower:
            suggestions['is_ambiguous'] = True
            suggestions['ambiguous_terms'].append(term)
            # Sugerir contextos disponibles del cliente
            if vocabulary.get('contextos'):
                suggestions['suggestions']['contextos'] = vocabulary['contextos'][:8]

    return suggestions


def normalize_query(query: str, client_id: int = None) -> dict:
    """
    Extrae color, tipo y contexto de la consulta usando:
    - Vocabulario dinámico del cliente (desde BD)
    - Matching semántico (LLM embeddings)

    Args:
        query: Texto de búsqueda del usuario
        client_id: ID del cliente para extraer vocabulario específico

    Returns:
        dict: {'tipo': ..., 'color': ..., 'contexto': [...], 'query': ..., 'embedding': [...]}
    """
    import time
    t0 = time.time()
    print(f"🔍 [normalize_query] INICIO para '{query}'")

    query_lower = query.lower()
    print(f"🔍 [normalize_query] Llamando get_model() en {time.time()-t0:.2f}s")

    model = get_model()
    print(f"🔍 [normalize_query] get_model() completado en {time.time()-t0:.2f}s")

    print(f"🔍 [normalize_query] Llamando model.encode() para '{query_lower}' en {time.time()-t0:.2f}s")
    t_encode_start = time.time()
    emb = model.encode(query_lower)
    print(f"🔍 [normalize_query] model.encode() completado en {time.time()-t0:.2f}s (encode tomó {time.time()-t_encode_start:.2f}s)")
    print(f"🔍 [normalize_query] Llamando _extract_client_vocabulary() en {time.time()-t0:.2f}s")
    if client_id:
        vocab = _extract_client_vocabulary(client_id)
        print(f"🔍 [normalize_query] _extract_client_vocabulary() completado en {time.time()-t0:.2f}s")
        colores_db = vocab['colores']
        tipos = vocab['tipos']
        contextos = vocab['contextos']

        # COMBINADO: Colores de BD + paleta estándar (para detectar colores que NO tenemos)
        # Esto permite que el sistema detecte cuando el usuario busca un color que NO existe
        paleta_estandar = [
            'negro', 'blanco', 'gris', 'azul', 'rojo', 'verde', 'amarillo',
            'naranja', 'rosa', 'violeta', 'morado', 'marrón', 'beige', 'celeste',
            'marino', 'turquesa', 'fucsia', 'bordó', 'dorado', 'plateado'
        ]

        # Combinar y eliminar duplicados
        colores = list(set(colores_db + paleta_estandar))

        print(f"📚 VOCAB: {len(colores)} colores ({len(colores_db)} BD + paleta estándar), {len(tipos)} tipos, {len(contextos)} contextos")
    else:
        # Fallback a listas mínimas si no hay client_id
        colores = ['negro', 'blanco', 'azul', 'rojo', 'verde', 'amarillo', 'gris']
        tipos = ['delantal', 'camisa', 'pantalon', 'gorra', 'gorro']
        contextos = ['casual', 'formal', 'deportivo']

    # MATCHING SEMÁNTICO con LLM (no substring!)
    # Thresholds optimizados para balance entre precisión y recall:
    # - Color: 0.45 (captura variantes: "azul" ≈ "celeste", "marino")
    # - Tipo: 0.50 (categoría con flexibilidad: "jean" ≈ "pantalón", "vaquero")
    # - Contexto: 0.40 (más flexible para estilos/ocasiones)
    color = _semantic_match(query, colores, client_id, threshold=0.45) if colores else None
    tipo = _semantic_match(query, tipos, client_id, threshold=0.50) if tipos else None
    contexto = _semantic_match_multiple(query, contextos, client_id, threshold=0.40, top_k=2) if contextos else []

    # Detectar queries ambiguas y generar sugerencias
    ambiguity_check = _detect_ambiguous_terms(query, vocab if client_id else {})

    result = {
        'tipo': tipo,
        'color': color,
        'contexto': contexto,
        'query': query,
        'embedding': emb.tolist()
    }

    # Agregar sugerencias si la query es ambigua
    if ambiguity_check['is_ambiguous']:
        result['needs_refinement'] = True
        result['ambiguous_terms'] = ambiguity_check['ambiguous_terms']
        result['suggestions'] = ambiguity_check['suggestions']
        print(f"💡 QUERY AMBIGUA detectada: {ambiguity_check['ambiguous_terms']}")
        print(f"   Sugerencias: {list(ambiguity_check['suggestions'].keys())}")
    else:
        result['needs_refinement'] = False

    return result


if __name__ == "__main__":
    # Prueba rápida
    ejemplos = [
        "delantal amarillo para cocina resistente a manchas",
        "camisa azul marino de invierno",
        "guardapolvo blanco escolar unisex",
        "vestido rosa casual verano",
        "pantalon negro industrial impermeable"
    ]
    for q in ejemplos:
        print(f"Query: {q}")
        print(normalize_query(q))
        print()
