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
import inspect

# Modelo liviano multilingüe
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
_model = None
_model_last_used_ts = None  # Timestamp de último uso
_model_cleanup_thread_started = False
_model_lock = threading.Lock()
_model_load_block_until = 0.0  # Cooldown tras fallo de carga para evitar reintentos costosos
_model_last_load_error = None
_minilm_cache_dir = os.getenv("MINILM_CACHE_DIR")

if _minilm_cache_dir:
    try:
        os.makedirs(_minilm_cache_dir, exist_ok=True)
    except Exception:
        pass

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
    global _model, _model_load_block_until, _model_last_load_error
    import time
    t_start = time.time()

    # Asegurar hilo de limpieza iniciado una vez
    _start_minilm_cleanup_thread_once()

    with _model_lock:
        now_ts = _now_ts()
        if _model is None and now_ts < _model_load_block_until:
            cooldown_left = int(_model_load_block_until - now_ts)
            raise RuntimeError(
                f"MiniLM en cooldown tras fallo de carga ({cooldown_left}s restantes): {_model_last_load_error}"
            )

        if _model is None:
            print(f"🔄 [MiniLM] Cargando modelo {MODEL_NAME} desde disco...", flush=True)
            local_only = os.getenv("MINILM_LOCAL_FILES_ONLY", "true").strip().lower() in ("1", "true", "yes", "on")
            try:
                if local_only and not os.getenv("HF_HUB_OFFLINE"):
                    os.environ["HF_HUB_OFFLINE"] = "1"

                ctor_params = inspect.signature(SentenceTransformer.__init__).parameters
                kwargs = {}
                if _minilm_cache_dir and "cache_folder" in ctor_params:
                    kwargs["cache_folder"] = _minilm_cache_dir
                if "local_files_only" in ctor_params:
                    kwargs["local_files_only"] = local_only

                _model = SentenceTransformer(MODEL_NAME, **kwargs)
            except Exception as e:
                _model = None
                _model_last_load_error = str(e)
                retry_cooldown = int(os.getenv("MINILM_RETRY_COOLDOWN_SECONDS", "600"))
                _model_load_block_until = _now_ts() + retry_cooldown
                raise

            _model.loaded_at = _now_ts()  # Marcar timestamp de carga
            _model_last_load_error = None
            _model_load_block_until = 0.0
            print(f"✅ [MiniLM] Modelo cargado en {time.time()-t_start:.2f}s", flush=True)
        else:
            print(f"♻️ [MiniLM] Usando modelo YA CARGADO en memoria (singleton activo)", flush=True)
        # Marcar uso cada vez que se obtiene el modelo
        _touch_model_last_used()
        return _model


def extract_query_attributes(query: str, client_id: str) -> dict:
    """
    Extrae atributos de la consulta usando el contexto real del cliente.

    Estrategia:
    - Lee ProductAttributeConfig del cliente (type: list/text/number/url)
    - Para type=list con options.values: intenta match semántico (MiniLM) y léxico
    - Detecta contradicciones básicas (ej: "con bolsillos" vs "sin bolsillos")

    Returns:
        {
          'attributes': { key: value_detected, ... },
          'attributes_confidence': { key: 'lexical' | 'boolean' | 'semantic', ... },  # 🆕 Confianza por atributo
          'requested_count': int,
          'contradictions': [ ... ],
          'not_configured': [ ... ],
          'notes': [ ... ]
        }
    """
    from app.models.product_attribute_config import ProductAttributeConfig
    from app import db
    import re as _re

    attrs_detected = {}
    attrs_confidence = {}  # 🆕 Guardar nivel de confianza por atributo
    contradictions = []
    notes = []
    not_configured = []  # 🆕 Atributos solicitados pero no en ProductAttributeConfig

    if not query or not client_id:
        return {
            'attributes': attrs_detected,
            'attributes_confidence': attrs_confidence,  # 🆕
            'requested_count': 0,
            'contradictions': contradictions,
            'not_configured': not_configured,
            'notes': notes,
        }

    # Cargar configs
    try:
        configs = ProductAttributeConfig.query.filter_by(client_id=client_id).all()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        configs = []

    # Construir set de keys configurados para detección rápida
    configured_keys = {(cfg.key or '').strip().lower() for cfg in configs if cfg.key}

    q_lower = query.lower()
    tokens = [t for t in _re.split(r"[^a-záéíóúñ0-9]+", q_lower) if t]
    tokens_set = set(tokens)

    # Helper para match semántico sobre listas de opciones
    def _semantic_pick(option_values: list, threshold: float = 0.65):  # 🔥 Threshold más estricto: 0.55 → 0.65
        try:
            model = get_model()
            # Representar la consulta y opciones
            opts = [str(v).lower() for v in option_values if v]
            if not opts:
                return None
            q_vec = model.encode([q_lower])[0]
            opt_vecs = model.encode(opts)
            sims = cosine_similarity([q_vec], opt_vecs)[0]
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])
            if best_sim >= threshold:
                return opts[best_idx]
        except Exception:
            return None
        return None

    # Reglas simples para booleanos comunes
    def _detect_boolean_from_text(key: str):
        # Patrón general para "con X" / "sin X"
        # Soporta claves tipo "con_bolsillo" y variantes en singular/plural
        base = key
        if key.startswith('con_'):
            base = key[4:]
        base = base.replace('_', ' ')

        con_pat = _re.compile(rf"\bcon\s+{_re.escape(base)}(?:es|s)?\b")
        sin_pat = _re.compile(rf"\bsin\s+{_re.escape(base)}(?:es|s)?\b")

        # Compatibilidad con nombres exactos de la clave
        con_pat2 = _re.compile(rf"\bcon\s+{_re.escape(key)}s?\b")
        sin_pat2 = _re.compile(rf"\bsin\s+{_re.escape(key)}s?\b")

        has_con = bool(con_pat.search(q_lower) or con_pat2.search(q_lower))
        has_sin = bool(sin_pat.search(q_lower) or sin_pat2.search(q_lower))
        if has_con and has_sin:
            contradictions.append(f"Atributo '{key}': 'con' y 'sin' al mismo tiempo")
            return None
        if has_con:
            return 'si'
        if has_sin:
            return 'no'
        # Fallback implícito: si la clave es 'con_X' y aparece el sustantivo solo (sing/plural) sin 'con'/'sin'
        # Ej: query "delantales beige bolsillos" debe activar con_bolsillo=si
        if key.startswith('con_'):
            singular = base.strip()
            # Variantes morfológicas comunes (singular, plural, plural 'es')
            variants = {singular}
            if singular.endswith(('a','o','e')):
                variants.add(singular + 's')
                if singular.endswith('e'):
                    variants.add(singular + 'es')
            else:
                # Para terminaciones típicas añadir 's' y 'es'
                variants.update({singular + 's', singular + 'es'})
            if any(v in tokens_set for v in variants):
                return 'si'
        return None

    for cfg in configs:
        key = (cfg.key or '').strip().lower()
        if not key:
            continue

        # type=list con opciones
        if cfg.type == 'list':
            # Obtener lista de valores permitidos
            values = []
            if isinstance(cfg.options, dict) and 'values' in cfg.options:
                values = cfg.options.get('values') or []
            elif isinstance(cfg.options, list):
                values = cfg.options

            values = [str(v).strip() for v in values if v]
            # Heurística 1: match léxico directo (con límites de palabra)
            lex_hit = None
            for v in values:
                v_low = v.lower()
                # Si el atributo es color, tolerar variantes morfológicas comunes (negro/negras/negros, azul/azules)
                if key == 'color':
                    variants = {v_low}
                    if v_low.endswith('o'):
                        variants.update({v_low[:-1] + 'a', v_low + 's', v_low[:-1] + 'as', v_low[:-1] + 'os'})
                    elif v_low.endswith('a'):
                        variants.add(v_low + 's')
                    elif v_low.endswith('e'):
                        variants.update({v_low + 's', v_low + 'es'})
                    elif v_low.endswith(('n', 'r', 'l')):
                        variants.add(v_low + 'es')
                    if any(var in tokens_set for var in variants):
                        lex_hit = v
                        break
                else:
                    # Coincidencia exacta por token o frase multi-palabra con bordes
                    if ' ' in v_low:
                        if _re.search(rf"\b{_re.escape(v_low)}\b", q_lower):
                            lex_hit = v
                            break
                    else:
                        if v_low in tokens_set:
                            lex_hit = v
                            break

            # Heurística 2: booleanos comunes por lenguaje natural
            bool_guess = None
            if set(["si", "sí", "no"]) & set(map(lambda x: x.lower(), values)):
                # El atributo soporta sí/no
                bool_guess = _detect_boolean_from_text(key)

            # Heurística 3: match semántico (MiniLM) si no hay lex/boolean
            # 🚫 DESACTIVADO: match semántico causa falsos positivos ("bermudas" → "plateado")
            # Solo usamos detección léxica o booleana (alta confianza)

            # Establecer valor SOLO si hay confianza alta (léxico o booleano)
            if lex_hit:
                attrs_detected[key] = lex_hit.lower()
                attrs_confidence[key] = 'lexical'
            elif bool_guess:
                attrs_detected[key] = bool_guess.lower()
                attrs_confidence[key] = 'boolean'
            # else: NO detectar nada (evita falsos positivos semánticos)

        # type=text: intentar detectar palabra clave si aparece exacto
        elif cfg.type == 'text':
            # evitar texto libre ambiguo, sólo si la palabra del atributo aparece con un valor claro
            # ejemplo: material: algodón
            # buscar patrón "algodón" en texto si el key es material
            # si no hay vocab, dejamos que pase
            if key in {"material", "talla", "color"}:
                # intento directo básico
                # material: buscar palabras típicas
                common_vals = []
                if key == 'material':
                    common_vals = ['algodón', 'poliéster', 'jean', 'gabardina', 'lycra']
                elif key == 'talla':
                    common_vals = ['xs', 's', 'm', 'l', 'xl']
                elif key == 'color':
                    common_vals = []  # color lo maneja colors.py en otra etapa
                for v in common_vals:
                    # Solo match exacto por token para evitar falsos positivos (p.ej. 's' en 'camisas')
                    if v in tokens_set:
                        attrs_detected[key] = v
                        break

    # 🆕 Detectar atributos solicitados no configurados (ej. "bolsillos" si no está en config)
    # Heurística: buscar patrones "con X" donde X no está en configured_keys
    con_pattern = _re.compile(r"\bcon\s+(\w+)s?\b")
    sin_pattern = _re.compile(r"\bsin\s+(\w+)s?\b")

    for match in con_pattern.finditer(q_lower):
        candidate = match.group(1).strip()
        if candidate:
            # Evitar falsos "no configurado" cuando existe una clave tipo con_<candidate>
            singular = candidate[:-1] if candidate.endswith('s') else candidate
            mapped_key = f"con_{singular}"
            if mapped_key in configured_keys:
                # Ya hay una clave configurada equivalente; no marcar como no configurado
                continue
            if candidate not in configured_keys and candidate not in not_configured:
                # Atributo mencionado pero no configurado
                not_configured.append(candidate)
                # También registrarlo para contabilizar solicitud
                attrs_detected[candidate] = True

    for match in sin_pattern.finditer(q_lower):
        candidate = match.group(1).strip()
        if candidate:
            singular = candidate[:-1] if candidate.endswith('s') else candidate
            mapped_key = f"con_{singular}"
            if mapped_key in configured_keys:
                # Existe configuración equivalente (con_*)
                continue
            if candidate not in configured_keys and candidate not in not_configured:
                not_configured.append(candidate)
                attrs_detected[candidate] = False

    return {
        'attributes': attrs_detected,
        'attributes_confidence': attrs_confidence,  # 🆕
        'requested_count': len(attrs_detected),
        'contradictions': contradictions,
        'not_configured': not_configured,
        'notes': notes,
    }


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

    # Validar client_id antes de queries BD
    if not client_id:
        print("⚠️ _extract_client_vocabulary llamado sin client_id, retornando vocabulario vacío")
        return {'colores': [], 'tipos': [], 'contextos': []}

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


def _semantic_match(query: str, vocabulary: list, client_id: int, threshold: float = 0.5, query_emb=None) -> str:
    """
    Encuentra la mejor coincidencia semántica usando embeddings cacheados.

    Args:
        query: Texto de búsqueda
        vocabulary: Lista de términos candidatos del cliente
        threshold: Similitud mínima para considerar match (0-1)
        query_emb: Embedding pre-calculado de la query (opcional, evita recalcular)

    Returns:
        Mejor match o None si no supera threshold
    """
    import time
    t_start = time.time()

    if not vocabulary:
        return None

    # Si no hay embedding pre-calculado, calcularlo
    if query_emb is None:
        model = get_model()
        t_encode = time.time()
        query_emb = model.encode([query.lower()])[0]
        print(f"⏱️ [_semantic_match] query encode: {time.time()-t_encode:.3f}s", flush=True)
    # Si ya existe, reutilizarlo (OPTIMIZACIÓN)
    else:
        if isinstance(query_emb, list):
            query_emb = np.array(query_emb, dtype=np.float32)

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

    # Si no hay embeddings en BD, calcular en vivo (fallback para vocabulario nuevo)
    missing_terms = [v for v in vocab_lower if v not in vocab_embeddings]
    if missing_terms:
        print(f"⚠️ {len(missing_terms)} términos sin embedding en BD, calculando: {', '.join(missing_terms[:5])}{'...' if len(missing_terms) > 5 else ''}")
        # Asegurar que el modelo esté cargado
        if 'model' not in locals():
            model = get_model()
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
    similarities = cosine_similarity([query_emb], vocab_embs)[0]    # Encontrar el mejor match
    max_idx = np.argmax(similarities)
    max_sim = similarities[max_idx]

    print(f"⏱️ [_semantic_match] TOTAL: {time.time()-t_start:.3f}s (vocab={len(vocabulary)}, cached={len(vocab_embeddings)}, missing={len(missing_terms)})", flush=True)

    if max_sim >= threshold:
        print(f"  🎯 Match: '{query}' → '{vocabulary[max_idx]}' (sim={max_sim:.3f})")
        return vocabulary[max_idx]

    return None


def _semantic_match_multiple(query: str, vocabulary: list, client_id: int, threshold: float = 0.4, top_k: int = 3, query_emb=None) -> list:
    """
    Encuentra múltiples coincidencias semánticas usando embeddings cacheados.

    Args:
        query: Texto de búsqueda
        vocabulary: Lista de términos candidatos
        threshold: Similitud mínima
        top_k: Máximo de matches a retornar
        query_emb: Embedding pre-calculado de la query (opcional, se calcula si es None)

    Returns:
        Lista de matches ordenados por similitud
    """
    import time
    t_start = time.time()

    if not vocabulary:
        return []

    # Si NO tenemos el embedding pre-calculado, lo calculamos
    if query_emb is None:
        model = get_model()
        t_encode = time.time()
        query_emb = model.encode([query.lower()])[0]
        print(f"⏱️ [_semantic_match_multiple] query encode: {time.time()-t_encode:.3f}s", flush=True)
    else:
        # Convertir a numpy array si viene como lista
        query_emb = np.array(query_emb) if not isinstance(query_emb, np.ndarray) else query_emb

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

    # Si no hay embeddings en BD, calcular en vivo (fallback para vocabulario nuevo)
    missing_terms = [v for v in vocab_lower if v not in vocab_embeddings]
    if missing_terms:
        print(f"⚠️ {len(missing_terms)} términos sin embedding en BD, calculando: {', '.join(missing_terms[:5])}{'...' if len(missing_terms) > 5 else ''}")
        # Asegurar que el modelo esté cargado
        if 'model' not in locals():
            model = get_model()
        missing_embs = model.encode(missing_terms)
        for term, emb in zip(missing_terms, missing_embs):
            vocab_embeddings[term] = emb

        # Guardar embeddings nuevos en la BD para futuras búsquedas (solo si client_id válido)
        if client_id:
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

    print(f"⏱️ [_semantic_match_multiple] TOTAL: {time.time()-t_start:.3f}s (vocab={len(vocabulary)}, cached={len(vocab_embeddings)}, missing={len(missing_terms)})", flush=True)

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
        colores = vocab['colores']  # Solo colores de BD del cliente
        tipos = vocab['tipos']
        contextos = vocab['contextos']

        print(f"📚 VOCAB: {len(colores)} colores, {len(tipos)} tipos, {len(contextos)} contextos (todos de BD)")
    else:
        # Fallback a listas vacías si no hay client_id
        colores = []
        tipos = []
        contextos = []

    # MATCHING SEMÁNTICO con LLM (no substring!)
    # Thresholds optimizados para balance entre precisión y recall:
    # - Color: 0.45 (captura variantes: "azul" ≈ "celeste", "marino")
    # - Tipo: 0.50 (categoría con flexibilidad: "jean" ≈ "pantalón", "vaquero")
    # - Contexto: 0.40 (más flexible para estilos/ocasiones)
    color = _semantic_match(query, colores, client_id, threshold=0.45, query_emb=emb) if colores else None
    tipo = _semantic_match(query, tipos, client_id, threshold=0.50, query_emb=emb) if tipos else None
    contexto = _semantic_match_multiple(query, contextos, client_id, threshold=0.40, top_k=2, query_emb=emb) if contextos else []

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

def normaliza_color(color_query: str, client_id: int | None = None) -> str | None:
    """
    Normaliza SOLO el color de una cadena usando el vocabulario del cliente y matching semántico.

    - Mantiene intacta la función legacy normalize_query() para otros usos.
    - Evita calcular tipo/contexto y reduce latencia.

    Args:
        color_query: Texto del color a normalizar (ej: "chocolate", "azul marino")
        client_id: ID del cliente para extraer vocabulario específico

    Returns:
        Color normalizado (string) o None si no supera el umbral.
    """
    import time as _t
    t0 = _t.time()
    try:
        q = (color_query or "").strip()
        if not q:
            return None

        print(f"🔍 [normaliza_color] INICIO para '{q}'")

        model = get_model()
        print(f"🔍 [normaliza_color] get_model() listo en {_t.time()-t0:.2f}s")

        q_lower = q.lower()
        t_encode = _t.time()
        emb = model.encode(q_lower)
        print(f"🔍 [normaliza_color] encode() tomó {_t.time()-t_encode:.2f}s (t={_t.time()-t0:.2f}s)")

        colores = []
        if client_id:
            print(f"🔍 [normaliza_color] Cargando vocab cliente en {_t.time()-t0:.2f}s")
            vocab = _extract_client_vocabulary(client_id)
            colores = vocab.get('colores') or []
            print(f"📚 [normaliza_color] VOCAB: {len(colores)} colores")

        if not colores:
            return None

        # Solo matching de color (sin tipo ni contexto)
        color = _semantic_match(q, colores, client_id, threshold=0.45, query_emb=emb)
        return color
    except Exception as _e:
        print(f"⚠️ [normaliza_color] Error: {_e}")
        return None
