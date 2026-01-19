"""
Módulo de Búsqueda Personalizado: Demo Store

Cliente: Demo Store
Slug: demo-store
Industria: Textil / Uniformes y ropa de trabajo

Categorías principales:
- AMBO VESTIR HOMBRE - DAMA
- BUZOS
- CAMISAS HOMBRE-DAMA
- CARDIGAN HOMBRE - DAMA
- CASACAS
- CHALECO DAMA-HOMBRE
- CHAQUETAS
- Delantal Completo
- GORROS - GORRAS
- Medio Delantal
- ZAPATO DAMA
- ZUECOS

Características especiales:
- Orientado a uniformes corporativos y ropa de trabajo
- Categorías con género específico (HOMBRE/DAMA)
- Productos con colores variados (PLATEADO, VIOLETA, CARAMELO, CELESTE, etc.)
"""

from typing import List, Optional, Set
from app.models.category import Category


# ============================================================================
# CONFIGURACIÓN ESPECÍFICA DE DEMO STORE
# ============================================================================

# Mapa de variantes ortográficas y plurales
VARIANTS_MAP = {
    # Delantales
    "delantal": "delantal",
    "delantales": "delantal",
    "mandil": "delantal",
    "mandiles": "delantal",

    # Ambos
    "ambo": "ambo",
    "ambos": "ambo",
    "uniforme": "ambo",
    "uniformes": "ambo",

    # Camisas
    "camisa": "camisa",
    "camisas": "camisa",

    # Chaquetas/Casacas
    "chaqueta": "chaqueta",
    "chaquetas": "chaqueta",
    "casaca": "casaca",
    "casacas": "casaca",
    "chamarra": "chaqueta",
    "chamarras": "chaqueta",

    # Buzos
    "buzo": "buzo",
    "buzos": "buzo",
    "sudadera": "buzo",
    "sudaderas": "buzo",

    # Cardigan
    "cardigan": "cardigan",
    "cardigans": "cardigan",
    "rebeca": "cardigan",
    "rebecas": "cardigan",

    # Chalecos
    "chaleco": "chaleco",
    "chalecos": "chaleco",

    # Gorros/Gorras
    "gorro": "gorro",
    "gorros": "gorro",
    "gorra": "gorro",
    "gorras": "gorro",
    "cap": "gorro",
    "caps": "gorro",

    # Zapatos/Zuecos
    "zapato": "zapato",
    "zapatos": "zapato",
    "zueco": "zueco",
    "zuecos": "zueco",
    "calzado": "zapato",
}

# Colores a excluir del filtrado de categoría
COLOR_TOKENS = {
    "rojo", "verde", "azul", "negro", "blanco", "marron", "gris",
    "beige", "rosa", "amarillo", "violeta", "celeste", "naranja",
    "plateado", "caramelo", "turquesa", "fucsia"
}

# Sinónimos adicionales por categoría (además de alternative_terms de BD)
CATEGORY_SYNONYMS = {
    "delantal": ["mandil", "delantales"],
    "ambo": ["uniforme", "uniformes"],
    "camisa": ["camisas"],
    "chaqueta": ["chaquetas", "casaca", "casacas", "chamarra"],
    "buzo": ["buzos", "sudadera"],
    "cardigan": ["cardigans", "rebeca"],
    "chaleco": ["chalecos"],
    "gorro": ["gorros", "gorra", "gorras", "cap"],
    "zapato": ["zapatos", "calzado"],
    "zueco": ["zuecos"],
}


# ============================================================================
# FUNCIONES DE NORMALIZACIÓN
# ============================================================================

def normalize_tokens(text: str) -> List[str]:
    """
    Normaliza tokens para Demo Store.

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
        if mapped_token not in {'de', 'del', 'la', 'el', 'y', 'con', 'sin', 'en'}:
            normalized.append(mapped_token)

    return normalized


def expand_query(query: str, categories: List[Category]) -> List[str]:
    """
    Expande query con sinónimos específicos de Demo Store.

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
    print(f"🔍 [Demo Store] Query expandido: '{query}' → {len(result)} términos: {result[:10]}")
    return result


def filter_by_category(query_tokens: List[str], categories: List[Category]) -> Optional[List[str]]:
    """
    Detecta si query contiene términos de categoría y retorna IDs a filtrar.

    Args:
        query_tokens: Tokens normalizados del query
        categories: Categorías del cliente

    Returns:
        Lista de category_ids si se detectó categoría, None si no
    """
    # Eliminar colores del análisis
    category_query_tokens = [t for t in query_tokens if t not in COLOR_TOKENS]

    if not category_query_tokens:
        return None

    # Normalizar nombres de categorías
    matched_category_ids = []

    for cat in categories:
        # Normalizar nombre de categoría
        cat_tokens = normalize_tokens(cat.name)

        # Verificar si hay overlap entre query y categoría
        if any(token in cat_tokens for token in category_query_tokens):
            matched_category_ids.append(cat.id)
            continue

        # Verificar alternative_terms
        if cat.alternative_terms:
            alt_terms = [s.strip() for s in cat.alternative_terms.split(',') if s.strip()]
            alt_normalized = [normalize_tokens(term)[0] for term in alt_terms if normalize_tokens(term)]

            if any(token in alt_normalized for token in category_query_tokens):
                matched_category_ids.append(cat.id)

    if matched_category_ids:
        print(f"🔒 [Demo Store] Filtro de categoría activado: {len(matched_category_ids)} categorías")
        return matched_category_ids

    return None


def detect_category_filter(query_tokens: List[str], categories: List[Category]):
    """
    Detecta filtro de categoría y retorna (ids, metadata) para el pipeline V2.

    - No agrega fallback en el caller: si no hay detección inequívoca, devuelve ([], None).
    - La metadata incluye el término solicitado y los nombres de categorías matcheadas.
    """
    if not query_tokens:
        return [], None

    # Excluir colores del análisis
    tokens = [t for t in query_tokens if t not in COLOR_TOKENS]
    if not tokens:
        return [], None

    # Construir mapa token → categorías que matchean
    token_to_cat_ids = {}

    for cat in categories:
        cat_tokens = set(normalize_tokens(cat.name)) if getattr(cat, 'name', None) else set()

        alt_norm = set()
        if getattr(cat, 'alternative_terms', None):
            alt_terms = [s.strip() for s in cat.alternative_terms.split(',') if s.strip()]
            for term in alt_terms:
                ntoks = normalize_tokens(term)
                if ntoks:
                    alt_norm.add(ntoks[0])

        for qt in tokens:
            if qt in cat_tokens or qt in alt_norm:
                token_to_cat_ids.setdefault(qt, []).append(cat.id)

    if not token_to_cat_ids:
        # No hay evidencia suficiente → sin filtro
        return [], None

    # Si hay un único root token con matches, aplicamos filtro
    if len(token_to_cat_ids) == 1:
        root = next(iter(token_to_cat_ids.keys()))
        ids = token_to_cat_ids[root]
        matched_names = [c.name for c in categories if c.id in ids]
        print(f"🔒 [Demo Store] Filtro de categoría aplicado: token='{root}' → {len(ids)} categorías")
        return ids, { 'requested_term': root, 'matched_categories': matched_names }

    # Ambiguo: no forzamos filtro
    print(f"📝 [Demo Store] Detección de categoría ambigua: tokens={list(token_to_cat_ids.keys())}")
    return [], None


# ============================================================================
# FUNCIONES DE BÚSQUEDA (Two-Stage Retrieval)
# ============================================================================

def stage1_broad_recall(query_text: str, client_id: str, top_n: int = 100):
    """
    STAGE 1: Recall amplio con SQL SIMILAR TO (fuzzy matching).

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

    # Obtener categorías del cliente
    categories = Category.query.filter_by(client_id=client_id, is_active=True).all()

    # Expandir query con sinónimos de Demo Store
    expanded_terms = expand_query(query_text, categories)

    # Normalizar query original
    query_tokens = normalize_tokens(query_text)

    # Detectar si hay filtro de categoría
    category_filter_ids = filter_by_category(query_tokens, categories)

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

    # Aplicar filtro de categoría si se detectó
    if category_filter_ids:
        query = query.filter(Product.category_id.in_(category_filter_ids))

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

    print(f"📊 [Demo Store] Stage 1: {len(candidates)} candidatos encontrados")
    return candidates


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
    if not candidates:
        return []

    # Importar CLIP
    from app.blueprints.embeddings import get_clip_model
    import torch
    import numpy as np

    # Obtener modelo CLIP
    clip_model, clip_processor = get_clip_model()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Generar embedding del query
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

    print(f"🎯 [Demo Store] Stage 2: {len(results)} productos re-rankeados")
    return results
