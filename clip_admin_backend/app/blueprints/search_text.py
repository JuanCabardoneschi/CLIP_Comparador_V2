"""
🆕 NUEVO SISTEMA DE BÚSQUEDA TEXTUAL V2
Two-Stage Retrieval: SQL Fuzzy Match + CLIP Reranking
"""

from flask import Blueprint, request, jsonify
from flask_cors import CORS
from app import db
from app.models.client import Client
from app.models.category import Category
from app.models.product import Product
from app.models.image import Image
from sqlalchemy import text, func
import time
import numpy as np
import torch

# Importar CLIP
from app.blueprints.embeddings import get_clip_model
from typing import List, Set

# Reutilizar normalizador spaCy del blueprint API (sin duplicar lógica)
try:
    from app.blueprints.api import _get_spacy_nlp  # type: ignore
except Exception:
    _get_spacy_nlp = None  # fallback si no está disponible por algún motivo

# 🆕 Sistema de módulos personalizados por cliente
from app.search_modules import get_client_module, has_custom_module
from app.utils.llm_query_normalizer import extract_query_attributes

bp = Blueprint("search_text", __name__)

# Habilitar CORS
CORS(bp, origins=["*"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "X-API-Key"])


def _build_user_feedback(query_text: str, formatted_results: list, detected_category_info: dict = None, client_id: str = None, attrs_requested: dict = None, contradictions: list = None, not_configured: list = None, all_available_values: dict = None):
    """Feedback dinámico para el usuario (no hardcodeado).

    Reglas:
    - Categoría: si la query se reinterpretó, se explica la sustitución.
    - Color: se normaliza ("blanca"→"blanco", "verdes"→"verde") usando utilidades existentes.
      Si el color solicitado NO existe en los resultados, se ofrecen alternativas similares calculadas
      con embeddings de color (si existen) o fallback léxico.
    - Atributos: lista lo que se detectó, contradicciones y atributos no configurados.
    - Filtrado: cuando se filtra por atributos, muestra los valores disponibles para ese atributo.
    - Independiente del cliente (permite módulos custom pero con fallback genérico).
    """
    from app.utils.colors import normalize_color  # import interno para evitar dependencias circulares
    try:
        from app.blueprints.api import _get_color_embedding  # type: ignore
    except Exception:
        _get_color_embedding = None

    # Nota: no devolvemos temprano aunque no haya resultados;
    # construimos igualmente el feedback (p.ej., listar colores disponibles)

    # Tokenización básica (agregar luego spaCy si se requiere mayor robustez)
    raw_tokens = [t.strip(".,;:!?") for t in query_text.lower().split() if t.strip()]

    # Limitar llamadas al normalizador LLM SOLO a tokens que pueden ser colores
    base_color_candidates = {
        'rojo','verde','azul','negro','blanco','marron','marrón','gris','beige','rosa','amarillo','violeta',
        'celeste','naranja','plateado','caramelo','turquesa','fucsia','habano','bordo','bordó','lila','magenta',
        'morado','cian','cyan','ocre','mostaza','chocolate'
    }

    # Detectar posible color solicitado (tomar el primero que normalice distinto de None)
    requested_color = None
    requested_color_raw = None
    for tok in raw_tokens:
        if tok not in base_color_candidates:
            continue  # evitar disparar LLM para tokens no-color (p.ej., 'short')
        # Guardar el primer token candidato a color para mensajes, incluso si no normaliza
        if requested_color_raw is None:
            requested_color_raw = tok
        norm = normalize_color(tok, client_id=client_id)
        if norm:
            requested_color = norm
            break

    # Extraer colores disponibles en resultados (normalizados)
    available_colors = []
    for r in formatted_results:
        color_val = (r.get('attributes') or {}).get('color')
        if color_val:
            norm_col = normalize_color(color_val.lower(), client_id=client_id) or color_val.lower()
            if norm_col not in available_colors:
                available_colors.append(norm_col)

    shown_categories = []
    for r in formatted_results:
        cat = r.get('category')
        if cat and cat not in shown_categories:
            shown_categories.append(cat)

    parts = []

    # Categoría - usar SOLO las categorías que realmente aparecen en los resultados
    if detected_category_info:
        req_term = detected_category_info.get('requested_term')
        matched_categories = detected_category_info.get('matched_categories', [])
        if req_term and matched_categories:
            # Solo si hubo reinterpretación
            if req_term.lower() not in [c.lower() for c in matched_categories]:
                # Usar shown_categories (categorías reales en resultados) en lugar de matched_categories
                if shown_categories:
                    if len(shown_categories) == 1:
                        cat_text = shown_categories[0]
                    elif len(shown_categories) == 2:
                        cat_text = f"{shown_categories[0]} y {shown_categories[1]}"
                    else:
                        cat_text = f"{', '.join(shown_categories[:-1])} y {shown_categories[-1]}"
                    parts.append(f"Buscaste '{req_term}', mostrando resultados de {cat_text}")

    # Atributos solicitados - mostrar valores disponibles (EXCEPTO color, que tiene lógica especial)
    if attrs_requested and all_available_values:
        # Cargar mapa key -> etiqueta
        label_map = {}
        if client_id:
            try:
                from app.models.product_attribute_config import ProductAttributeConfig
                cfgs = ProductAttributeConfig.query.filter_by(client_id=client_id).all()
                for c in cfgs:
                    k = (c.key or '').strip().lower()
                    if not k:
                        continue
                    label_map[k] = (c.label or k)
            except Exception:
                label_map = {}

        import unicodedata as _ud
        def _norm(x):
            if x is None:
                return ''
            txt = str(x).strip().lower()
            txt = ''.join(ch for ch in _ud.normalize('NFD', txt) if _ud.category(ch) != 'Mn')
            if txt in ('si','sí'):
                return 'si'
            return txt
        def _fmt_val(x):
            n = _norm(x)
            if n == 'si':
                return 'Sí'
            if n == 'no':
                return 'No'
            return str(x).upper()

        for attr_key, attr_value in attrs_requested.items():
            # Saltar 'color': tiene lógica especial más abajo
            if str(attr_key).lower() == 'color':
                continue

            available_vals = all_available_values.get(attr_key, [])
            if not available_vals:
                continue

            # Mostrar etiqueta si existe
            display_key = label_map.get(attr_key, attr_key)

            # Comparación acento-insensible y unificada para sí/no
            req_norm = _norm(attr_value)
            avail_norm = [_norm(v) for v in available_vals]

            if req_norm and req_norm in avail_norm:
                # Valor solicitado está disponible → listar disponibles (formateados)
                parts.append(f"Tenemos disponibles en {display_key}: {', '.join(_fmt_val(v) for v in available_vals)}")
            else:
                parts.append(
                    f"No disponemos en {display_key}: '{_fmt_val(attr_value)}'. "
                    f"Tenemos disponibles en {display_key}: {', '.join(_fmt_val(v) for v in available_vals)}"
                )

    # Atributos no configurados
    if not_configured:
        attrs_str = ', '.join([f"'{a}'" for a in not_configured])
        if len(not_configured) == 1:
            parts.append(f"El atributo {attrs_str} no está configurado para este catálogo")
        else:
            parts.append(f"Los atributos {attrs_str} no están configurados para este catálogo")

    # Banner inteligente de color solicitado
    try:
        if requested_color_raw:
            if requested_color:
                # Informar interpretación si hubo mapeo
                if requested_color_raw.lower() != requested_color.lower():
                    parts.append(f"Interpretamos '{requested_color_raw}' como color '{requested_color}'")

                # Si el color no está disponible en los resultados, calcular similares y sugerir
                if requested_color not in available_colors:
                    # Calcular colores similares desde el token ORIGINAL para sugerencias
                    similar_suggestions = []
                    try:
                        from app.utils.colors import _get_color_embedding  # type: ignore
                        import numpy as _np
                        # Usar requested_color_raw para calcular similares, NO requested_color
                        emb_target = _get_color_embedding(requested_color_raw, client_id=client_id)
                        if emb_target is not None:
                            scored = []
                            for c in available_colors:
                                emb_c = _get_color_embedding(c, client_id=client_id)
                                if emb_c is None:
                                    continue
                                sim = float(_np.dot(emb_target, emb_c) / (_np.linalg.norm(emb_target) * _np.linalg.norm(emb_c)))
                                scored.append((c, sim))
                            scored.sort(key=lambda x: x[1], reverse=True)
                            # Top 3 con umbral 0.70 para asegurar relevancia
                            similar_suggestions = [c for c, s in scored if s >= 0.70][:3]
                    except Exception:
                        similar_suggestions = []

                    # Mensaje informativo según si hay similares disponibles
                    if similar_suggestions:
                        # Incluir categoría si es posible
                        cat_for_msg = None
                        try:
                            if shown_categories:
                                cat_for_msg = shown_categories[0]
                            elif detected_category_info and detected_category_info.get('matched_categories'):
                                cat_for_msg = detected_category_info.get('matched_categories')[0]
                        except Exception:
                            cat_for_msg = None
                        if not cat_for_msg:
                            cat_for_msg = 'productos'

                        parts.append(
                            f"No tenemos {cat_for_msg} disponible en color '{requested_color}' en este momento. "
                            f"Te mostramos los colores más cercanos: {', '.join(similar_suggestions)}"
                        )
                    else:
                        # Si no hay colores similares, listar TODOS los colores disponibles en la categoría
                        # Usar all_available_values (colores antes del filtrado) si available_colors está vacío
                        colors_to_show = available_colors if available_colors else []

                        if not colors_to_show and all_available_values and 'color' in all_available_values:
                            # Normalizar colores de all_available_values
                            from app.utils.colors import normalize_color as _nc
                            colors_to_show = []
                            for c in all_available_values['color']:
                                normalized = _nc(str(c).lower(), client_id=client_id) or str(c).lower()
                                if normalized not in colors_to_show:
                                    colors_to_show.append(normalized)

                        if colors_to_show:
                            # Incluir categoría si es posible
                            cat_for_msg = None
                            try:
                                if shown_categories:
                                    cat_for_msg = shown_categories[0]
                                elif detected_category_info and detected_category_info.get('matched_categories'):
                                    cat_for_msg = detected_category_info.get('matched_categories')[0]
                            except Exception:
                                cat_for_msg = None
                            if not cat_for_msg:
                                cat_for_msg = 'productos'

                            parts.append(
                                f"No tenemos {cat_for_msg} disponible en color '{requested_color}'. "
                                f"Tenemos disponible en: {', '.join(colors_to_show)}"
                            )
                        else:
                            parts.append(f"No encontramos productos en esta categoría")
                else:
                    # El color solicitado SÍ está disponible: informar otros colores disponibles también
                    # Usar all_available_values (todos los colores ANTES del filtrado) en lugar de available_colors
                    all_colors_in_category = []
                    if all_available_values and 'color' in all_available_values:
                        all_colors_in_category = [normalize_color(c.lower(), client_id=client_id) or c.lower()
                                                   for c in all_available_values['color']]
                        # Deduplicar y quitar el color solicitado
                        all_colors_in_category = sorted(list(set([c for c in all_colors_in_category if c != requested_color])))

                    if all_colors_in_category:
                        parts.append(f"También tenemos disponible en: {', '.join(all_colors_in_category)}")
            else:
                # No se reconoció el token como color
                parts.append(
                    f"No reconocemos '{requested_color_raw}' como color. Si te refieres a un color, usa 'color={requested_color_raw}'."
                )
    except Exception:
        pass

    # Contradicciones
    if contradictions:
        parts.append(f"Tu búsqueda contiene criterios contradictorios: {', '.join(contradictions)}")

    # Final
    if not parts:
        if len(shown_categories) == 1:
            parts.append(f"Mostrando {len(formatted_results)} resultados en '{shown_categories[0]}'")
        else:
            parts.append(f"Encontramos {len(formatted_results)} productos para tu búsqueda")

    message = '. '.join(parts) + '.'
    return {
        'message': message,
        'has_results': bool(formatted_results),
        'result_count': len(formatted_results),
        'categories_shown': shown_categories,
        'colors_available': available_colors or None,
        'requested_color': requested_color,
        'attributes_requested': attrs_requested or {},
        'attributes_not_configured': not_configured or [],
        'contradictions': contradictions or []
    }


def verify_api_key():
    """Valida API Key del request"""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return None, "API Key requerida"

    client = Client.query.filter_by(api_key=api_key).first()
    if not client:
        return None, "API Key inválida"

    return client, None


def expand_query_with_synonyms(query_text: str, client_id: str, client_slug: str = None):
    """
    Expande query con sinónimos de categorías del cliente.

    🆕 DELEGACIÓN A MÓDULO PERSONALIZADO:
    Si existe módulo custom para el cliente, usa su lógica.
    Sino, usa expansión genérica con alternative_terms.

    Returns:
        List[str]: Lista de tokens expandidos con sinónimos
    """
    # 🆕 Intentar usar módulo personalizado
    if client_slug and has_custom_module(client_slug):
        module = get_client_module(client_slug)
        try:
            categories = Category.query.filter_by(client_id=client_id).all()
        except Exception as e:
            # Rollback y fallback a expansión mínima si la transacción está abortada
            try:
                db.session.rollback()
            except Exception:
                pass
            print(f"⚠️ [Módulo Custom] Error consultando categorías para expansión: {e}")
            return query_text.lower().split()
        result = module.expand_query(query_text, categories)
        print(f"✅ [Módulo Custom] Expansión personalizada: {len(result)} términos")
        return result

    # Fallback genérico (original)
    tokens = query_text.lower().split()
    expanded = set(tokens)

    # Buscar en alternative_terms de categorías
    try:
        categories = Category.query.filter_by(client_id=client_id).all()
    except Exception as e:
        # Si la transacción está abortada, hacer rollback y fallback sin sinónimos
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"⚠️ [Genérico] Error obteniendo categorías para sinónimos: {e}. Usando tokens básicos.")
        return list(expanded)

    for cat in categories:
        if not cat.alternative_terms:
            continue

        cat_synonyms = [s.strip() for s in cat.alternative_terms.split(',')]

        # Si algún token del query coincide con sinónimos, agregar todos
        for token in tokens:
            if token in cat_synonyms:
                expanded.update(cat_synonyms)
                print(f"🔍 Token '{token}' expandido con sinónimos de '{cat.name}': {cat_synonyms[:5]}...")
                break

    result = list(expanded)
    print(f"📝 [Genérico] Query expandido: '{query_text}' → {len(result)} términos: {result[:10]}...")
    return result


def _normalize_tokens_es(text: str) -> List[str]:
    """Tokeniza y lematiza en español usando spaCy si está disponible.
    Fallback: split básico en minúsculas.
    """
    if not text:
        return []

    # Mapa mínimo de variantes comunes del dominio textil
    variants_map = {
        "shorts": "short",
        "shores": "short",
        "remeras": "remera",
        "pantalones": "pantalon",
        "gorras": "gorra",
        "gorros": "gorro",
    }

    try:
        if _get_spacy_nlp:
            nlp = _get_spacy_nlp()
        else:
            nlp = None
        if nlp is not None:
            doc = nlp(text.lower())
            toks = []
            for t in doc:
                if not t.is_alpha or t.is_stop:
                    continue
                lemma = t.lemma_.strip().lower()
                lemma = variants_map.get(lemma, lemma)
                if lemma:
                    toks.append(lemma)
            return toks
    except Exception:
        # Fallback simple si spaCy falla
        pass

    # Fallback: dividir por espacios + normalización mínima
    toks = []
    for raw in text.lower().replace('-', ' ').split():
        tok = variants_map.get(raw, raw)
        # Singularizar simple: quitar sufijo 's' si aplica (no agresivo)
        if tok.endswith('s') and len(tok) > 3:
            tok = tok[:-1]
        if tok.isalpha():
            toks.append(tok)
    return toks


def _category_tokens(cat: Category) -> Set[str]:
    """Construye el set de tokens normalizados de una categoría combinando
    name, name_en y alternative_terms (cuando existen).
    """
    tokens: Set[str] = set()
    # name y name_en
    if getattr(cat, 'name', None):
        tokens.update(_normalize_tokens_es(cat.name))
    if getattr(cat, 'name_en', None):
        tokens.update(_normalize_tokens_es(cat.name_en))
    # alternative_terms (coma separada, puede contener frases)
    if getattr(cat, 'alternative_terms', None):
        for term in [s.strip() for s in cat.alternative_terms.split(',') if s.strip()]:
            tokens.update(_normalize_tokens_es(term))
    return {t for t in tokens if t}


def stage1_broad_recall(query_text: str, client_id: str, client_slug: str = None, top_n: int = 50):
    """
    STAGE 1: Broad Recall
    Búsqueda rápida en BD usando PostgreSQL SIMILAR TO

    🆕 DELEGACIÓN A MÓDULO PERSONALIZADO:
    - Normalización de tokens
    - Detección de filtro de categoría
    - Expansión de sinónimos

    Returns:
        List[Product]: Candidatos (max top_n)
    """
    start_time = time.time()

    # 1️⃣ Expandir query con sinónimos (delega a módulo custom si existe)
    expanded_tokens = expand_query_with_synonyms(query_text, client_id, client_slug)

    # 1.1 Detectar categorías para filtrar (delega a módulo custom si existe)
    categories = Category.query.filter_by(client_id=client_id).all()
    category_filter_ids = []
    detection_metadata = None  # 🆕 Capturar metadata de detección

    # 🆕 Intentar usar módulo personalizado para detección de filtro
    if client_slug and has_custom_module(client_slug):
        module = get_client_module(client_slug)
        # Normalizar tokens del query usando el módulo
        query_tokens = module.normalize_tokens(query_text)
        # Detectar filtro de categoría (puede retornar tupla con metadata)
        result = module.detect_category_filter(query_tokens, categories)

        # Manejar ambos casos: (ids, metadata) o solo ids
        if isinstance(result, tuple):
            category_filter_ids, detection_metadata = result
        else:
            category_filter_ids = result
            detection_metadata = None

        if category_filter_ids:
            print(f"✅ [Módulo Custom] Filtro de categoría aplicado: {len(category_filter_ids)} categorías")
        else:
            print(f"📝 [Módulo Custom] Sin filtro de categoría (búsqueda amplia)")
    else:
        # Fallback genérico (lógica original con normalización básica)
        original_tokens = _normalize_tokens_es(query_text)
        color_tokens = {"rojo", "verde", "azul", "negro", "blanco", "marron", "gris", "beige", "rosa", "amarillo", "violeta"}
        filtered_query_tokens = [t for t in original_tokens if t not in color_tokens]

        matched_by_name = []  # [(cat_id, root_token)]
        for cat in categories:
            tokens_cat = _category_tokens(cat)
            for qt in filtered_query_tokens:
                if qt in tokens_cat:
                    matched_by_name.append((cat.id, qt))
                    break

        root_to_cats = {}
        for cid, root in matched_by_name:
            root_to_cats.setdefault(root, []).append(cid)

        if len(root_to_cats) == 1:
            sole_root = next(iter(root_to_cats.keys()))
            category_filter_ids = root_to_cats[sole_root]
            print(f"🔒 [Genérico] Filtro de categoría aplicado: root='{sole_root}' ids={category_filter_ids}")
        else:
            category_filter_ids = []

    # Normalizar category_filter_ids para SQL (None si vacío)
    if not category_filter_ids:
        category_filter_ids = []

    # 2️⃣ Construir pattern para SIMILAR TO
    # SIMILAR TO usa regex-like: %(term1|term2|term3)%
    pattern = f"%({'|'.join(expanded_tokens)})%"

    # 3️⃣ Query SQL flexible
    sql = text("""
        SELECT DISTINCT p.id
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.client_id = :client_id
        AND p.is_active = TRUE
        AND ((:use_filter = FALSE) OR p.category_id = ANY(:category_ids))
        AND (
            -- Buscar en nombre del producto
            LOWER(p.name) SIMILAR TO :pattern
            OR
            -- Buscar en atributos JSONB (verificar que sea objeto válido)
            (
                p.attributes IS NOT NULL
                AND jsonb_typeof(p.attributes) = 'object'
                AND EXISTS (
                    SELECT 1 FROM jsonb_each_text(p.attributes) attr
                    WHERE LOWER(attr.value) SIMILAR TO :pattern
                )
            )
            OR
            -- Buscar en categoría
            (
                LOWER(c.name) SIMILAR TO :pattern
                OR LOWER(c.name_en) SIMILAR TO :pattern
                OR LOWER(c.alternative_terms) SIMILAR TO :pattern
            )
        )
        LIMIT :limit
    """)

    product_ids = db.session.execute(sql, {
        "client_id": client_id,
        "pattern": pattern,
        "limit": top_n,
        "use_filter": bool(category_filter_ids),
        "category_ids": category_filter_ids if category_filter_ids else [None]
    }).fetchall()

    # Cargar productos completos
    products = []
    for row in product_ids:
        product = Product.query.get(row[0])
        if product:
            products.append(product)

    elapsed = time.time() - start_time
    print(f"⚡ STAGE 1: {len(products)} candidatos en {elapsed:.3f}s")

    # 🆕 Retornar también metadata de detección (si existe)
    return products, detection_metadata


def stage2_precise_rerank(query_text: str, candidates: list, limit: int = 10):
    """
    STAGE 2: Precise Reranking
    Re-ordena candidatos usando similitud CLIP text-to-text

    Returns:
        List[dict]: Productos ordenados con scores
    """
    if not candidates:
        return []

    start_time = time.time()

    # 1️⃣ Obtener modelo CLIP
    clip_model, clip_processor = get_clip_model()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 2️⃣ Generar embedding del query
    query_prompt = f"a photo of {query_text}"

    with torch.no_grad():
        query_inputs = clip_processor(text=[query_prompt], return_tensors="pt", padding=True).to(device)
        query_embedding = clip_model.get_text_features(**query_inputs)
        query_embedding = query_embedding / query_embedding.norm(dim=-1, keepdim=True)
        query_vec = query_embedding.cpu().numpy()[0]

    # 3️⃣ Calcular similitud con TEXTO de cada producto
    scored_candidates = []

    for product in candidates:
        # Construir descripción textual del producto
        product_parts = [product.name]

        # Agregar atributos relevantes
        if product.attributes:
            for key in ['color', 'tipo', 'material', 'talla']:
                if key in product.attributes and product.attributes[key]:
                    product_parts.append(str(product.attributes[key]))

        # Agregar categoría
        if product.category:
            product_parts.append(product.category.name)
            if product.category.name_en:
                product_parts.append(product.category.name_en)

        product_text = " ".join(product_parts)
        product_prompt = f"a photo of {product_text}"

        # Generar embedding del producto
        with torch.no_grad():
            prod_inputs = clip_processor(text=[product_prompt], return_tensors="pt", padding=True).to(device)
            prod_embedding = clip_model.get_text_features(**prod_inputs)
            prod_embedding = prod_embedding / prod_embedding.norm(dim=-1, keepdim=True)
            prod_vec = prod_embedding.cpu().numpy()[0]

        # Similitud coseno
        similarity = float(np.dot(query_vec, prod_vec))

        scored_candidates.append({
            'product': product,
            'similarity': similarity,
            'product_text': product_text
        })

    # 4️⃣ Ordenar por similitud
    scored_candidates.sort(key=lambda x: x['similarity'], reverse=True)

    # 5️⃣ Limitar resultados
    top_results = scored_candidates[:limit]

    elapsed = time.time() - start_time
    print(f"🎯 STAGE 2: Top {len(top_results)} rerankeados en {elapsed:.3f}s")

    # Log top 3
    for i, result in enumerate(top_results[:3], 1):
        print(f"   {i}. {result['product'].name} (sim: {result['similarity']:.3f})")

    return top_results


@bp.route("/search/text", methods=["POST", "OPTIONS"])
def text_search():
    """
    🆕 NUEVO ENDPOINT DE BÚSQUEDA TEXTUAL V2

    Two-Stage Retrieval:
    1. SQL Broad Recall con sinónimos auto-generados
    2. CLIP Reranking text-to-text

    Headers:
        X-API-Key: API Key del cliente

    JSON Body:
        query: Texto de búsqueda (ej: "short rojo")
        limit: Número de resultados (default: 10, max: 50)

    Returns:
        {
            "success": true,
            "query": "short rojo",
            "expanded_terms": ["short", "shorts", "bermuda", "rojo", ...],
            "stage1_candidates": 50,
            "results": [
                {
                    "id": "...",
                    "name": "...",
                    "price": 1500,
                    "similarity": 0.89,
                    "image": "https://...",
                    "category": "shores tiro alto",
                    "attributes": {...}
                }
            ],
            "processing_time": 0.85
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

    # Rollback defensivo inicial para limpiar cualquier transacción abortada previa
    try:
        db.session.rollback()
    except Exception:
        pass

    try:
        # Validar API Key
        client, error = verify_api_key()
        if error:
            return jsonify({
                "success": False,
                "error": "unauthorized",
                "message": error
            }), 401

        # Obtener parámetros
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "bad_request",
                "message": "Query requerido"
            }), 400

        query_text = data.get('query', '').strip()
        if not query_text:
            return jsonify({
                "success": False,
                "error": "bad_request",
                "message": "Query vacío"
            }), 400

        limit = min(int(data.get('limit', 10)), 50)

        print(f"\n{'='*60}")
        print(f"🔍 NUEVA BÚSQUEDA TEXTUAL V2")
        print(f"Query: '{query_text}' | Cliente: {client.name} | Limit: {limit}")
        print(f"{'='*60}")

        # Obtener slug del cliente para módulo personalizado
        client_slug = getattr(client, 'slug', None)

        # STAGE 1: Broad Recall (SQL) con delegación a módulo custom
        candidates, detection_metadata = stage1_broad_recall(query_text, client.id, client_slug, top_n=50)

        # 🚫 VALIDACIÓN CRÍTICA: Si no hay categoría válida detectada, NO continuar
        if not detection_metadata or not detection_metadata.get('matched_categories'):
            # Obtener todas las categorías comercializables del cliente
            available_categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
            available_names = [cat.name for cat in available_categories]
            # Mensaje especial para el usuario
            user_feedback = {
                "message": f"La categoría solicitada no se encuentra entre las comercializables. Categorías disponibles: {', '.join(available_names)}.",
                "has_results": False,
                "categories_available": available_names
            }
            response_data = {
                "success": True,
                "query": query_text,
                "expanded_terms": expand_query_with_synonyms(query_text, client.id, client_slug),
                "stage1_candidates": 0,
                "total_results": 0,
                "processing_time": round(time.time() - start_time, 3),
                "search_module": "custom" if (client_slug and has_custom_module(client_slug)) else "generic",
                "user_feedback": user_feedback,
                "results": [],
                "results_by_category": {},
                "group_by_category": False
            }
            response = jsonify(response_data)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
            return response

        if not candidates:
            # Si hay categoría válida pero no hay candidatos (caso raro)
            user_feedback = {
                "message": "No se encontraron productos en las categorías detectadas.",
                "has_results": False
            }
            response_data = {
                "success": True,
                "query": query_text,
                "expanded_terms": expand_query_with_synonyms(query_text, client.id, client_slug),
                "stage1_candidates": 0,
                "total_results": 0,
                "processing_time": round(time.time() - start_time, 3),
                "search_module": "custom" if (client_slug and has_custom_module(client_slug)) else "generic",
                "user_feedback": user_feedback,
                "results": [],
                "results_by_category": {},
                "group_by_category": False
            }
            response = jsonify(response_data)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
            return response

        # Extraer atributos solicitados en la query (contexto del cliente)
        attr_info = extract_query_attributes(query_text, client.id)

        # 🟡 Si no se detectó color por léxico, inferirlo semánticamente y usar el flujo normal
        try:
            requested_attrs = attr_info.get('attributes', {}) or {}
            from app.utils.colors import normalize_color

            # Solo intentar normalizar tokens que NO sean categorías (evitar "delantal" → "bordo")
            # Obtener categorías del cliente para filtrarlas
            category_tokens = set()
            try:
                categories = Category.query.filter_by(client_id=client.id).all()
                for cat in categories:
                    if cat.name:
                        category_tokens.update([t.lower() for t in cat.name.split()])
                    if hasattr(cat, 'alternative_terms') and cat.alternative_terms:
                        category_tokens.update([t.lower().strip() for t in cat.alternative_terms.split(',') if t.strip()])
            except Exception:
                pass

            raw_tokens = [t.strip(".,;:!?") for t in query_text.lower().split() if t.strip()]
            semantic_color = None
            for tok in raw_tokens:
                if len(tok) < 3:
                    continue
                # Saltar si es una categoría conocida
                if tok in category_tokens:
                    print(f"🔍 [Inferencia color] Saltando '{tok}' (es categoría)")
                    continue
                print(f"🔍 [Inferencia color] Intentando normalizar '{tok}'...")
                c = normalize_color(tok, client_id=client.id)
                if c:
                    semantic_color = c
                    print(f"🔍 [Inferencia color] '{tok}' → '{c}'")
                    break
                else:
                    print(f"🔍 [Inferencia color] '{tok}' no se reconoció como color")

            if semantic_color:
                prev_color = requested_attrs.get('color')
                # Reemplazar si no había color o el detectado previo difiere del semántico
                if (not prev_color) or (prev_color and prev_color.lower() != semantic_color.lower()):
                    requested_attrs['color'] = semantic_color
                    attr_info['attributes'] = requested_attrs
                    attr_info['requested_count'] = len(requested_attrs)
                    print(f"🎨 Color forzado por semántica: '{semantic_color}' (antes='{prev_color}')")
            else:
                print(f"🔍 [Inferencia color] No se detectó ningún color en los tokens")
        except Exception as _e:
            print(f"⚠️ Inferencia semántica de color falló: {_e}")

        # STAGE 2: Precise Reranking (CLIP)
        scored_results = stage2_precise_rerank(query_text, candidates, limit=limit)

        # Calcular cumplimiento de atributos por producto
        requested_attrs = attr_info.get('attributes', {})
        requested_count = int(attr_info.get('requested_count', 0))

        # Formatear resultados
        formatted_results = []
        for result in scored_results:
            product = result['product']

            # Obtener imagen principal
            primary_image = Image.query.filter_by(
                product_id=product.id,
                is_primary=True
            ).first()

            if not primary_image:
                primary_image = Image.query.filter_by(
                    product_id=product.id
                ).first()

            # Atributos del producto
            prod_attrs = product.attributes or {}

            # Matching de atributos solicitados
            matched = {}
            for k, v in requested_attrs.items():
                pv = prod_attrs.get(k)
                if pv is None:
                    continue
                # soportalistas: si pv es lista
                if isinstance(pv, list):
                    if any(str(x).lower() == str(v).lower() for x in pv):
                        matched[k] = v
                else:
                    if str(pv).lower() == str(v).lower():
                        matched[k] = v

            matched_count = len(matched)
            match_ratio = float(matched_count / requested_count) if requested_count > 0 else 0.0

            formatted_results.append({
                "id": product.id,
                "name": product.name,
                "price": float(product.price) if product.price is not None else None,
                "similarity": round(result['similarity'], 3),
                # Ordenamiento: primero por atributos cumplidos, luego por similitud
                # El widget usa final_score para badge. Mantenemos similitud y exponemos match_ratio aparte
                "final_score": round(result['similarity'], 3),
                "image": primary_image.display_url if primary_image else None,
                "image_url": primary_image.display_url if primary_image else None,  # Widget espera este campo
                "category": product.category.name if product.category else None,
                "attributes": prod_attrs,
                "attributes_matched": matched,
                "attributes_match_count": matched_count,
                "attributes_match_ratio": round(match_ratio, 3),
                "sku": product.sku,
                "stock": product.stock
            })

        # 🔍 FILTRADO POR ATRIBUTOS SOLICITADOS
        # Si se solicitaron atributos, mostrar productos que cumplan:
        # - Si se pidió color: preferir coincidencia estricta por color
        # - En caso contrario: al menos 1 atributo solicitado
        if requested_count > 0:
            # Antes de filtrar, recopilar todos los valores disponibles para cada atributo solicitado
            all_available_values = {}
            for attr_key in requested_attrs.keys():
                available_vals = set()
                for r in formatted_results:
                    prod_attrs = r.get('attributes', {})
                    val = prod_attrs.get(attr_key)
                    if val is not None:
                        if isinstance(val, list):
                            for v in val:
                                available_vals.add(str(v))
                        else:
                            available_vals.add(str(val))
                all_available_values[attr_key] = sorted(list(available_vals))

            # Si se solicitó color, filtrar por coincidencia EXACTA o similares si no hay exactos
            color_req_key = next((k for k in requested_attrs.keys() if str(k).lower() == 'color'), None)
            filtered_results = []
            if color_req_key:
                color_value = str(requested_attrs.get(color_req_key, '')).lower()
                # 1) Intentar coincidencias exactas
                exact_matches = [
                    r for r in formatted_results
                    if str(r.get('attributes', {}).get('color', '')).lower() == color_value
                ]

                if exact_matches:
                    filtered_results = exact_matches
                    print(f"🎨 Filtrado por color exacto '{color_value}': {len(exact_matches)} productos")
                else:
                    # 2) No hay exactos: buscar colores similares y filtrar por esos
                    print(f"🎨 No hay color exacto '{color_value}', buscando similares...")
                    try:
                        from app.utils.colors import _get_color_embedding
                        target_emb = _get_color_embedding(color_value, client_id=client.id)
                        similar_colors = []

                        if target_emb is not None and all_available_values.get(color_req_key):
                            available_product_colors = [str(v).lower() for v in all_available_values[color_req_key]]
                            scored = []
                            for c in set(available_product_colors):
                                emb_c = _get_color_embedding(c, client_id=client.id)
                                if emb_c is None:
                                    continue
                                denom = (np.linalg.norm(target_emb) * np.linalg.norm(emb_c))
                                if denom == 0:
                                    continue
                                sim = float(np.dot(target_emb, emb_c) / denom)
                                scored.append((c, sim))

                            # Ordenar y tomar top-3 con umbral 0.65 (más permisivo que antes)
                            scored.sort(key=lambda x: x[1], reverse=True)
                            THRESH = 0.65
                            TOPK = 3
                            similar_colors = [c for c, s in scored if s >= THRESH][:TOPK]
                            print(f"🎨 Colores similares encontrados: {similar_colors}")

                        if similar_colors:
                            similar_set = set(similar_colors)
                            filtered_results = [
                                r for r in formatted_results
                                if str(r.get('attributes', {}).get('color', '')).lower() in similar_set
                            ]
                            print(f"🎨 Filtrado por colores similares: {len(filtered_results)} productos")
                        else:
                            # 3) Sin similares: devolver vacío
                            filtered_results = []
                            print(f"🎨 No se encontraron colores similares a '{color_value}'")
                    except Exception as e:
                        print(f"⚠️ Error buscando colores similares: {e}")
                        filtered_results = []

                formatted_results = filtered_results
            else:
                # Filtrar: mantener solo productos que cumplan AL MENOS 1 atributo solicitado
                filtered_results = [r for r in formatted_results if r.get("attributes_match_count", 0) > 0]
                # Para otros atributos, mantener fallback de no filtrar si quedaría vacío
                if filtered_results:
                    formatted_results = filtered_results

            # Reordenar: por cantidad de atributos cumplidos, luego stock, luego similitud
            formatted_results.sort(
                key=lambda r: (
                    r.get("attributes_match_count", 0),
                    1 if (r.get("stock") or 0) > 0 else 0,
                    r.get("similarity", 0.0)
                ),
                reverse=True
            )
        else:
            # Si no hubo atributos solicitados, priorizar stock disponible y luego similitud
            all_available_values = {}
            formatted_results.sort(
                key=lambda r: (
                    1 if (r.get("stock") or 0) > 0 else 0,
                    r.get("similarity", 0.0)
                ),
                reverse=True
            )

        # Respuesta final
        elapsed = time.time() - start_time

        print(f"✅ Búsqueda completada: {len(formatted_results)} resultados en {elapsed:.3f}s")
        print(f"{'='*60}\n")

        # 🔍 CONSTRUIR FEEDBACK DESCRIPTIVO (concepto del método deprecado)
        user_feedback = _build_user_feedback(
            query_text=query_text,
            formatted_results=formatted_results,
            detected_category_info=detection_metadata,  # Usar metadata de stage1
            client_id=client.id,
            attrs_requested=requested_attrs,
            contradictions=attr_info.get('contradictions', []),
            not_configured=attr_info.get('not_configured', []),
            all_available_values=all_available_values  # Valores disponibles para los atributos filtrados
        )

        # Cargar atributos visibles (expose_in_search=True) para el frontend
        exposed_attribute_keys = []
        exposed_attribute_labels = {}
        try:
            from app.models.product_attribute_config import ProductAttributeConfig
            configs = ProductAttributeConfig.query.filter_by(client_id=client.id).all()
            for cfg in configs:
                if cfg.expose_in_search:
                    key_l = (cfg.key or '').strip().lower()
                    exposed_attribute_keys.append(key_l)
                    exposed_attribute_labels[key_l] = (cfg.label or cfg.key or key_l)
        except Exception:
            pass

        # ⭐ AGRUPACIÓN POR CATEGORÍAS HERMANAS
        # Si detection_metadata indica múltiples categorías hermanas, agrupar resultados
        results_by_category = {}
        group_by_category = False

        if detection_metadata and len(detection_metadata.get('matched_categories', [])) > 1:
            # Hay múltiples categorías hermanas detectadas
            group_by_category = True
            for result in formatted_results:
                cat_name = result.get('category', 'Sin categoría')
                if cat_name not in results_by_category:
                    results_by_category[cat_name] = []
                results_by_category[cat_name].append(result)

        response_data = {
            "success": True,
            "query": query_text,
            "expanded_terms": expand_query_with_synonyms(query_text, client.id, client_slug),
            "stage1_candidates": len(candidates),
            "total_results": len(formatted_results),
            "processing_time": round(elapsed, 3),
            "search_module": "custom" if (client_slug and has_custom_module(client_slug)) else "generic",
            "user_feedback": user_feedback,
            "group_by_category": group_by_category,
            "exposed_attribute_keys": exposed_attribute_keys,  # 🆕 Lista de atributos visibles
            "exposed_attribute_labels": exposed_attribute_labels  # 🆕 Mapa key->etiqueta
        }

        if group_by_category:
            # Enviar resultados agrupados por categoría
            response_data["results_by_category"] = results_by_category
            response_data["results"] = []  # Vacío cuando se agrupa
        else:
            # Enviar resultados en lista plana (comportamiento original)
            response_data["results"] = formatted_results

        response = jsonify(response_data)

        # Agregar headers CORS explícitamente
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'

        return response

    except Exception as e:
        import traceback
        traceback.print_exc()

        response = jsonify({
            "success": False,
            "error": "internal_error",
            "message": str(e)
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 500
