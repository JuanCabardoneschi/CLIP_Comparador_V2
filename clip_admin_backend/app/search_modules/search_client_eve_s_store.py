"""
Módulo de Búsqueda Personalizado: Eve's Store

Cliente: Eve's Store
Slug: eve-s-store
Industria: Textil / Ropa femenina

Categorías principales:
- shores tiro alto / shores tiro bajo (shorts)
- remeras manga corta / remeras manga larga
- pantalones

Problema resuelto:
- "short verde" traía remeras porque "shores" no normalizaba a "short"
- Múltiples variantes ortográficas necesitan mapeo explícito
"""

from typing import List, Optional, Set
from app.models.category import Category


# ============================================================================
# CONFIGURACIÓN ESPECÍFICA DE EVE'S STORE
# ============================================================================

# Mapa de variantes ortográficas y plurales
# CRÍTICO: NO incluir sinónimos semánticos aquí (ej: "bermuda" NO es variante de "short")
# Los sinónimos semánticos van en CATEGORY_SYNONYMS para expansión, NO para normalización
VARIANTS_MAP = {
    # Shorts (problema principal) - solo variantes ortográficas
    "short": "short",
    "shorts": "short",
    "shore": "short",
    "shores": "short",
    # ❌ REMOVIDO: "bermuda": "short" - bermudas es categoría separada

    # Remeras
    "remera": "remera",
    "remeras": "remera",
    "camiseta": "remera",
    "camisetas": "remera",
    "polera": "remera",
    "poleras": "remera",

    # Pantalones
    "pantalon": "pantalon",
    "pantalones": "pantalon",
    "jean": "pantalon",
    "jeans": "pantalon",

    # Gorras
    "gorra": "gorra",
    "gorras": "gorra",
    "gorro": "gorra",
    "gorros": "gorra",
    "cap": "gorra",
    "caps": "gorra",

    # Bermudas (categoría separada, no colapsar con shorts)
    "bermuda": "bermuda",
    "bermudas": "bermuda",
}

# Colores a excluir del filtrado de categoría
COLOR_TOKENS = {
    "rojo", "verde", "azul", "negro", "blanco", "marron", "gris",
    "beige", "rosa", "amarillo", "violeta", "celeste", "naranja"
}

# Modificadores a ignorar en name_en (no son categorías, son descriptores)
# Estos tokens se ignoran al procesar name_en de categorías para evitar falsos matches
# Ejemplo: "short sleeve t-shirt" → ignora "short" pero mantiene "sleeve", "shirt"
NAME_EN_IGNORE_MODIFIERS = {
    "short", "long",      # largo de prendas
    "high", "low",        # altura/tiro
    "rise",               # tiro (inglés)
    "sleeve",             # manga (demasiado genérico)
}

# Sinónimos adicionales por categoría (además de alternative_terms de BD)
# Estos se usan SOLO para expansión de búsqueda (expand_query)
# NO se usan para detección de categorías (detect_category_filter)
CATEGORY_SYNONYMS = {
    "short": ["shore", "shores", "shorts"],  # ❌ REMOVIDO: "bermuda" - es categoría separada
    "remera": ["camiseta", "polera", "top"],
    "pantalon": ["jean", "jeans"],
    "gorra": ["cap", "gorro"],
    "bermuda": ["bermudas"],  # ✅ AGREGADO: bermudas como categoría propia
}


# ============================================================================
# FUNCIONES DE NORMALIZACIÓN
# ============================================================================

def normalize_tokens(text: str) -> List[str]:
    """
    Normaliza tokens para Eve's Store.

    Aplica:
    1. Lowercase y split por espacios/guiones
    2. Mapeo de variantes (VARIANTS_MAP)
    3. Filtrado de stopwords comunes

    Args:
        text: Texto a normalizar (query del usuario o nombre de categoría)

    Returns:
        Lista de tokens normalizados
    """
    if not text:
        return []

    # Lowercase y split
    raw_tokens = text.lower().replace('-', ' ').replace('_', ' ').split()

    # Aplicar mapeo de variantes
    normalized = []
    for token in raw_tokens:
        # Limpiar caracteres especiales
        clean_token = ''.join(c for c in token if c.isalpha())
        if not clean_token:
            continue

        # Aplicar variante si existe
        mapped_token = VARIANTS_MAP.get(clean_token, clean_token)

        # Filtrar stopwords básicas
        if mapped_token not in {'de', 'del', 'la', 'el', 'y', 'con', 'sin'}:
            normalized.append(mapped_token)

    return normalized


def expand_query(query: str, categories: List[Category]) -> List[str]:
    """
    Expande query con sinónimos específicos de Eve's Store.

    Args:
        query: Query original del usuario
        categories: Categorías del cliente (para leer alternative_terms)

    Returns:
        Lista expandida de términos de búsqueda
    """
    tokens = normalize_tokens(query)
    expanded = set(tokens)

    # 1. Agregar sinónimos hardcodeados
    for token in tokens:
        if token in CATEGORY_SYNONYMS:
            expanded.update(CATEGORY_SYNONYMS[token])

    # 2. Agregar alternative_terms de categorías que matchean
    for cat in categories:
        if not cat.alternative_terms:
            continue

        cat_synonyms = [s.strip() for s in cat.alternative_terms.split(',') if s.strip()]
        normalized_synonyms = [normalize_tokens(syn)[0] for syn in cat_synonyms if normalize_tokens(syn)]

        # Si algún token del query está en los sinónimos, agregar todos
        if any(token in normalized_synonyms for token in tokens):
            expanded.update(normalized_synonyms)

    result = list(expanded)
    print(f"🔍 [Eve's Store] Query expandido: '{query}' → {len(result)} términos: {result[:10]}")
    return result


def detect_category_filter(query_tokens: List[str], categories: List[Category]) -> Optional[List[str]]:
    """
    Detecta si el query menciona UNA sola categoría raíz y devuelve IDs para filtrar.

    Lógica específica de Eve's Store:
    - "short verde" → detecta "short" → filtra por shores tiro alto/bajo SOLAMENTE
    - "remera negra" → detecta "remera" → filtra por remeras manga corta/larga
    - "short remera" → detecta 2 raíces → NO filtra (búsqueda mixta)

    CRÍTICO: NO normalizar nombres de categorías para evitar colapsar categorías distintas.
    "bermudas" NO debe colapsar con "shores" aunque ambos sean "shorts" semánticamente.

    Args:
        query_tokens: Tokens normalizados del query (sin colores)
        categories: Lista de categorías del cliente

    Returns:
        Lista de category IDs si debe filtrar, None si no
    """
    # Filtrar colores del query
    filtered_tokens = [t for t in query_tokens if t not in COLOR_TOKENS]

    if not filtered_tokens:
        print("🔍 [Eve's Store] No hay tokens no-color, sin filtro")
        return None

    # Construir tokens de cada categoría con ESTRATEGIA HÍBRIDA:
    # - Nombre español: normalizado con VARIANTS_MAP (para "shores" → "short")
    # - name_en: SOLO palabras clave (primer token), NO frases completas
    # - alternative_terms: SIN normalizar (evita colapsar "bermuda" con "short")
    category_tokens_map = {}  # category_id -> (set of tokens, category_name)
    for cat in categories:
        cat_tokens = set()

        # Tokens del nombre de categoría: NORMALIZAR con VARIANTS_MAP
        # Esto permite que "shores tiro alto" sea detectado por query "short"
        cat_tokens.update(normalize_tokens(cat.name))

        # Tokens del name_en: SOLO agregar tokens clave, ignorando modificadores
        # Evita que "short sleeve t-shirt" matchee con query "short"
        # Solo agrega "sleeve" y "shirt" como tokens relevantes, NO "short"
        if cat.name_en:
            name_en_tokens = cat.name_en.strip().lower().split()
            # Filtrar modificadores genéricos (configurables en NAME_EN_IGNORE_MODIFIERS)
            for token in name_en_tokens:
                if token not in NAME_EN_IGNORE_MODIFIERS:
                    cat_tokens.add(token)

        # Tokens de alternative_terms: NO NORMALIZAR (lowercase + split únicamente)
        # Esto evita que "bermuda verde" en alternative_terms colapse con "short"
        if cat.alternative_terms:
            for term in cat.alternative_terms.split(','):
                # Solo lowercase y split, SIN VARIANTS_MAP
                cat_tokens.update(term.strip().lower().split())

        category_tokens_map[cat.id] = (cat_tokens, cat.name)

    # Detectar matches: (category_id, matched_token, category_name)
    matched = []
    for cat_id, (cat_tokens, cat_name) in category_tokens_map.items():
        for query_token in filtered_tokens:
            # Match EXACTO (sin VARIANTS_MAP) para evitar colapsar "bermudas" con "shores"
            if query_token in cat_tokens:
                matched.append((cat_id, query_token, cat_name))
                print(f"   DEBUG: '{query_token}' matchea con categoría '{cat_name}' (tokens: {cat_tokens})")
                break  # Solo un match por categoría

    if not matched:
        print("🔍 [Eve's Store] Sin coincidencias de categoría, sin filtro")
        return None, None  # 🆕 Retornar también metadata

    # Agrupar por token del query (NO por root normalizado)
    # Ejemplo: "short" agrupa ["shores tiro alto", "shores tiro bajo"]
    #          "bermuda" agrupa ["bermudas"] (categoría separada)
    token_to_cats = {}
    for cat_id, matched_token, cat_name in matched:
        token_to_cats.setdefault(matched_token, []).append((cat_id, cat_name))

    print(f"   DEBUG: token_to_cats = {token_to_cats}")

    # Si hay UN SOLO token del query que matchea → aplicar filtro
    if len(token_to_cats) == 1:
        sole_token = next(iter(token_to_cats.keys()))
        category_info = token_to_cats[sole_token]
        category_ids = [cat_id for cat_id, _ in category_info]
        cat_names = [cat_name for _, cat_name in category_info]

        print(f"🔒 [Eve's Store] Filtro activado: token='{sole_token}' → categorías={cat_names}")

        # 🆕 Construir metadata de detección
        detection_metadata = {
            "requested_term": sole_token,  # Token que el usuario escribió
            "matched_categories": cat_names,  # Categorías reales en BD
            "match_type": "category_filter"
        }

        return category_ids, detection_metadata
    else:
        # Múltiples tokens del query matchean categorías diferentes → sin filtro (búsqueda mixta)
        matched_tokens = list(token_to_cats.keys())
        print(f"🔍 [Eve's Store] Múltiples tokens detectados: {matched_tokens} → sin filtro (búsqueda mixta)")
        return None, None  # 🆕 Retornar también metadata


# ============================================================================
# FUNCIONES DE BÚSQUEDA (Two-Stage Retrieval)
# ============================================================================

def stage1_broad_recall(query_text: str, client_id: str, top_n: int = 100):
    """
    STAGE 1: Recall amplio con SQL SIMILAR TO + filtro de categoría específico.

    Args:
        query_text: Query del usuario
        client_id: ID del cliente
        top_n: Número de candidatos a retornar

    Returns:
        Lista de Product objects candidatos
    """
    from app.models.product import Product
    from app.models.category import Category
    from app import db
    from sqlalchemy import or_, and_

    print(f"\n{'─'*70}")
    print(f"🔍 [EVE'S STORE] STAGE 1: Broad Recall")
    print(f"{'─'*70}")

    # Obtener categorías del cliente
    categories = Category.query.filter_by(client_id=client_id, is_active=True).all()
    print(f"📁 Categorías disponibles: {len(categories)}")
    for cat in categories:
        print(f"   • {cat.name} (id: {str(cat.id)[:8]}...)")

    # Expandir query con sinónimos de Eve's Store
    expanded_terms = expand_query(query_text, categories)
    print(f"📝 Query expandido: '{query_text}' → {expanded_terms}")

    # Normalizar query original
    query_tokens = normalize_tokens(query_text)
    print(f"🔤 Tokens normalizados: {query_tokens}")

    # ⭐ DETECTAR FILTRO DE CATEGORÍA (función específica de Eve's Store)
    category_filter_ids, detection_metadata = detect_category_filter(query_tokens, categories)

    if category_filter_ids:
        filtered_cat_names = [c.name for c in categories if c.id in category_filter_ids]
        print(f"🔒 FILTRO DE CATEGORÍA ACTIVADO:")
        print(f"   → Buscando SOLO en: {filtered_cat_names}")
        print(f"   → Excluidas: {[c.name for c in categories if c.id not in category_filter_ids]}")
    else:
        print(f"🌐 Sin filtro de categoría - buscando en TODAS las categorías")
        detection_metadata = None  # No hay detección si no hay filtro

    # Construir patterns SQL SIMILAR TO (fuzzy)
    patterns = []
    for term in expanded_terms:
        # SIMILAR TO pattern: %(term)%
        patterns.append(f"%{term}%")

    # Construir query SQL con SIMILAR TO
    query = Product.query.filter(
        Product.client_id == client_id,
        Product.is_active == True
    )

    # ⭐ APLICAR FILTRO DE CATEGORÍA SI SE DETECTÓ
    if category_filter_ids:
        query = query.filter(Product.category_id.in_(category_filter_ids))
        print(f"✅ Filtro SQL aplicado: category_id IN ({len(category_filter_ids)} categorías)")

    # Aplicar patterns SIMILAR TO en name, description, SKU
    if patterns:
        pattern_conditions = []
        for pattern in patterns:
            pattern_conditions.append(
                or_(
                    Product.name.ilike(pattern),
                    Product.description.ilike(pattern),
                    Product.sku.ilike(pattern)
                )
            )

        # OR entre todos los patterns
        query = query.filter(or_(*pattern_conditions))

    # Limitar resultados
    candidates = query.limit(top_n).all()

    print(f"⚡ STAGE 1 completado: {len(candidates)} productos candidatos")
    if candidates:
        # Mostrar muestra de productos encontrados
        print(f"📦 Muestra de productos (primeros 5):")
        for idx, prod in enumerate(candidates[:5], 1):
            cat_name = prod.category.name if prod.category else "Sin categoría"
            color = prod.attributes.get('color', 'N/A') if prod.attributes else 'N/A'
            print(f"   {idx}. {prod.name} - {cat_name} - Color: {color}")
    else:
        print(f"⚠️  No se encontraron candidatos - ampliar términos de búsqueda")
    print(f"{'─'*70}\n")

    # 🆕 Retornar tupla con candidatos Y metadata de detección
    return candidates, detection_metadata


def stage2_precise_rerank(query_text: str, candidates: List, limit: int = 20):
    """
    STAGE 2: Re-ranking preciso con CLIP text-to-text embeddings.

    Args:
        query_text: Query original del usuario
        candidates: Lista de Product objects de Stage 1
        limit: Número final de resultados

    Returns:
        Lista ordenada de dicts con productos y scores
    """
    print(f"\n{'─'*70}")
    print(f"🎯 [EVE'S STORE] STAGE 2: Precise Reranking con CLIP")
    print(f"{'─'*70}")
    print(f"📥 Entrada: {len(candidates)} candidatos de Stage 1")
    print(f"🎯 Target: Top {limit} resultados finales")

    if not candidates:
        print(f"⚠️  No hay candidatos para reranking")
        print(f"{'─'*70}\n")
        return []

    # Importar CLIP
    from app.blueprints.embeddings import get_clip_model
    import torch
    import numpy as np

    # Obtener modelo CLIP
    print(f"🔄 Cargando modelo CLIP ViT-B/16...")
    clip_model, clip_processor = get_clip_model()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"✅ CLIP cargado en: {device}")

    # Generar embedding del query
    print(f"📝 Generando embedding de query: '{query_text}'")
    with torch.no_grad():
        text_inputs = clip_processor(
            text=[query_text],
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(device)

        query_embedding = clip_model.get_text_features(**text_inputs)
        query_embedding = query_embedding / query_embedding.norm(dim=-1, keepdim=True)
        query_vec = query_embedding.squeeze(0).cpu().numpy()

    # Calcular similitud con cada candidato (usando embeddings de imágenes)
    print(f"🔢 Calculando similaridades con embeddings de imágenes...")
    results = []

    for product in candidates:
        # Obtener mejor imagen del producto
        best_image = None
        best_similarity = -1.0

        for img in product.images:
            if not img.clip_embedding:
                continue

            # Parsear embedding
            import json
            img_embedding = np.array(json.loads(img.clip_embedding), dtype=np.float32)

            # Calcular similitud coseno
            similarity = float(np.dot(query_vec, img_embedding))

            if similarity > best_similarity:
                best_similarity = similarity
                best_image = img

        # Si no hay embedding, skip
        if best_image is None or best_similarity <= 0:
            continue

        results.append({
            'product': product,
            'image': best_image,
            'similarity': best_similarity
        })

    # Ordenar por similitud descendente
    results.sort(key=lambda x: x['similarity'], reverse=True)

    # Limitar resultados
    results = results[:limit]

    print(f"✅ STAGE 2 completado: {len(results)} productos finales")
    if results:
        print(f"🏆 Top {min(3, len(results))} resultados:")
        for idx, res in enumerate(results[:3], 1):
            prod = res['product']
            cat_name = prod.category.name if prod.category else "Sin categoría"
            color = prod.attributes.get('color', 'N/A') if prod.attributes else 'N/A'
            print(f"   {idx}. {prod.name} (sim: {res['similarity']:.3f}) - {cat_name} - {color}")
    print(f"{'─'*70}\n")

    return results


# ============================================================================
# METADATA DEL MÓDULO
# ============================================================================

MODULE_INFO = {
    "client_name": "Eve's Store",
    "client_slug": "eve-s-store",
    "version": "1.0.0",
    "created": "2025-11-17",
    "description": "Módulo personalizado con normalización shores→short y filtrado de categoría"
}


def get_module_info():
    """Retorna metadata del módulo"""
    return MODULE_INFO
