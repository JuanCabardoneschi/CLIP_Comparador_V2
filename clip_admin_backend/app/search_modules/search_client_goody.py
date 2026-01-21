"""
Módulo de Búsqueda Personalizado: Goody

Cliente: Goody
Slug: goody
Industria: Textil / Ropa profesional para gastronomía

Categorías principales:
- Delantales (pechera, medio, chef, etc.)
- Chaquetas
- Pantalones
- Camisas
- Accesorios

Problema resuelto:
1. Diferenciar tipos de delantal (pechera vs medio vs chef)
2. Detectar patrones/estampados específicos
3. Búsqueda especializada para uniformes de restaurantes/cafeterías
"""

from typing import List, Optional, Set
from app.models.category import Category


# ============================================================================
# CONFIGURACIÓN ESPECÍFICA DE GOODY
# ============================================================================

# Mapa de variantes ortográficas y plurales
VARIANTS_MAP = {
    # Delantales
    "delantal": "delantal",
    "delantales": "delantal",
    "mandil": "delantal",
    "mandiles": "delantal",
    "pechera": "pechera",
    "pecheras": "pechera",

    # Chaquetas
    "chaqueta": "chaqueta",
    "chaquetas": "chaqueta",
    "saco": "chaqueta",
    "sacos": "chaqueta",
    "campera": "chaqueta",
    "camperas": "chaqueta",

    # Pantalones
    "pantalon": "pantalon",
    "pantalones": "pantalon",

    # Camisas
    "camisa": "camisa",
    "camisas": "camisa",
    "chomba": "camisa",
    "chombas": "camisa",
}

# Tipos funcionales de delantal
APRON_TYPES = {
    "pechera": ["pechera", "pecheras", "bib"],
    "medio": ["medio", "media", "cintura", "waist"],
    "chef": ["chef", "cocinero"],
    "bar": ["bar", "barman", "bartender"],
    "sommelier": ["sommelier", "vino"],
}

# Patrones y estampados
PATTERN_KEYWORDS = {
    # Patrones florales
    "floral": ["flores", "flor", "florecido", "floreado", "floral"],

    # Patrones náuticos/marineros
    "nautico": ["barcos", "barco", "anclas", "ancla", "marinero", "nautico", "marine"],

    # Patrones geométricos
    "geometrico": ["cuadros", "cuadro", "rayas", "raya", "patron", "geometrico", "geometric"],

    # Lisos/sin patrón
    "liso": ["liso", "lisa", "sin patron", "sin estampado", "simple", "plain"],

    # Específicos de Goody
    "jean": ["jean", "denim", "mezclilla"],
    "cuero": ["cuero", "leather"],
    "loneta": ["loneta", "canvas"],
    "punto": ["punto", "knit"],
}

# Colores comunes (para evitar filtrado erróneo)
COLOR_TOKENS = {
    "rojo", "verde", "azul", "negro", "blanco", "marron", "gris",
    "beige", "rosa", "amarillo", "violeta", "celeste", "naranja",
    "caramelo", "maiz", "oscuro", "claro"
}

# Modificadores a ignorar en name_en
NAME_EN_IGNORE_MODIFIERS = {
    "unisex", "professional", "classic", "modern", "premium"
}

# Sinónimos adicionales por categoría
CATEGORY_SYNONYMS = {
    "delantal": ["mandil", "pechera"],
    "chaqueta": ["saco", "campera", "jacket"],
    "pantalon": ["pants", "trousers"],
    "camisa": ["shirt", "chomba"],
}


# ============================================================================
# FUNCIONES DE NORMALIZACIÓN
# ============================================================================

def normalize_tokens(text: str) -> List[str]:
    """
    Normaliza tokens para Goody.

    Aplica:
    - Conversión a minúsculas
    - Mapeo de variantes ortográficas
    - Eliminación de stopwords irrelevantes

    Args:
        text: Texto a normalizar

    Returns:
        Lista de tokens normalizados
    """
    import re

    # Minúsculas y limpieza
    text = text.lower().strip()

    # Tokenización simple
    tokens = re.findall(r'\b\w+\b', text)

    # Normalizar usando VARIANTS_MAP
    normalized = []
    for token in tokens:
        normalized_token = VARIANTS_MAP.get(token, token)
        if normalized_token and normalized_token not in COLOR_TOKENS:
            normalized.append(normalized_token)

    return normalized


# ============================================================================
# FUNCIONES DE EXPANSIÓN DE QUERY
# ============================================================================

def expand_query(query: str) -> List[str]:
    """
    Expande query con sinónimos relevantes para Goody.

    Example:
        "delantal" → ["delantal", "mandil", "pechera"]
        "chaqueta chef" → ["chaqueta chef", "saco chef", "campera chef"]

    Args:
        query: Query original

    Returns:
        Lista de queries expandidas (original + sinónimos)
    """
    queries = [query.lower()]

    # Expandir con sinónimos de categoría
    for base_term, synonyms in CATEGORY_SYNONYMS.items():
        if base_term in query.lower():
            for synonym in synonyms:
                expanded = query.lower().replace(base_term, synonym)
                if expanded not in queries:
                    queries.append(expanded)

    return queries[:5]  # Limitar a 5 queries máximo


# ============================================================================
# DETECCIÓN DE TIPO DE DELANTAL
# ============================================================================

def detect_apron_type(query_tokens: List[str]) -> Optional[str]:
    """
    Detecta el tipo específico de delantal mencionado en la búsqueda.

    Args:
        query_tokens: Tokens normalizados del query

    Returns:
        Tipo de delantal detectado o None

    Example:
        ["delantal", "pechera", "negro"] → "pechera"
        ["medio", "delantal", "azul"] → "medio"
    """
    for apron_type, keywords in APRON_TYPES.items():
        for keyword in keywords:
            if keyword in query_tokens:
                return apron_type

    return None


# ============================================================================
# DETECCIÓN DE PATRÓN/ESTAMPADO
# ============================================================================

def detect_pattern(query_tokens: List[str]) -> Optional[str]:
    """
    Detecta el patrón/estampado mencionado en la búsqueda.

    Args:
        query_tokens: Tokens normalizados del query

    Returns:
        Tipo de patrón detectado o None

    Example:
        ["delantal", "flores"] → "floral"
        ["chaqueta", "rayas"] → "geometrico"
    """
    for pattern_type, keywords in PATTERN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_tokens:
                return pattern_type

    return None


# ============================================================================
# DETECCIÓN DE FILTRO POR CATEGORÍA
# ============================================================================

def detect_category_filter(query_tokens: List[str], categories: List[Category]) -> Optional[List[str]]:
    """
    Detecta si el query menciona categorías específicas para filtrar.

    Específico para Goody:
    - Detecta tipos de prendas (delantal, chaqueta, pantalón)
    - NO filtra por colores
    - Ignora modificadores irrelevantes

    Args:
        query_tokens: Tokens normalizados del query
        categories: Categorías disponibles del cliente

    Returns:
        Lista de category slugs a filtrar, o None
    """
    matched_categories = set()

    # Tokenizar nombres de categorías
    for category in categories:
        cat_name_lower = category.name.lower()
        cat_slug = category.slug

        # Tokens de la categoría
        cat_tokens = set(cat_name_lower.split())

        # Ignorar tokens de modificadores
        cat_tokens = cat_tokens - NAME_EN_IGNORE_MODIFIERS

        # Match si hay intersección con query (excluyendo colores)
        query_set = set(query_tokens) - COLOR_TOKENS

        if cat_tokens & query_set:
            matched_categories.add(cat_slug)

    return list(matched_categories) if matched_categories else None


# ============================================================================
# FILTRADO POST-BÚSQUEDA (CUSTOM)
# ============================================================================

def filter_results_by_apron_type(results: List[dict], apron_type: str) -> List[dict]:
    """
    Filtra resultados de delantales por tipo específico.

    Args:
        results: Lista de productos con score
        apron_type: Tipo detectado ("pechera", "medio", "chef", etc.)

    Returns:
        Resultados filtrados/re-rankeados
    """
    if not apron_type:
        return results

    # Palabras clave del tipo
    keywords = APRON_TYPES.get(apron_type, [])

    # Re-rankear: boost si el nombre contiene el tipo
    for result in results:
        product_name = result.get('name', '').lower()

        # Boost score si coincide el tipo
        if any(kw in product_name for kw in keywords):
            result['score'] = result.get('score', 0) * 1.3  # 30% boost
        # Penalizar si NO coincide (pero es un delantal)
        elif 'delantal' in product_name and apron_type != 'delantal':
            result['score'] = result.get('score', 0) * 0.7  # 30% penalización

    # Re-ordenar por score actualizado
    results.sort(key=lambda x: x.get('score', 0), reverse=True)

    return results


def filter_results_by_pattern(results: List[dict], pattern_type: str) -> List[dict]:
    """
    Filtra resultados por patrón/estampado.

    Args:
        results: Lista de productos con score
        pattern_type: Tipo detectado ("floral", "nautico", "geometrico", "liso", etc.)

    Returns:
        Resultados filtrados/re-rankeados
    """
    if not pattern_type:
        return results

    # Palabras clave del patrón
    keywords = PATTERN_KEYWORDS.get(pattern_type, [])

    # Re-rankear: boost si el nombre contiene el patrón
    for result in results:
        product_name = result.get('name', '').lower()

        # Boost score si coincide el patrón
        if any(kw in product_name for kw in keywords):
            result['score'] = result.get('score', 0) * 1.5  # 50% boost

    # Re-ordenar por score actualizado
    results.sort(key=lambda x: x.get('score', 0), reverse=True)

    return results


# ============================================================================
# RE-RANKING POR DESCRIPCIÓN DE IA (BÚSQUEDA VISUAL)
# ============================================================================

def extract_keywords_from_description(description: str) -> dict:
    """
    Extrae keywords de tipo y patrón desde descripción de IA (GPT-4V, etc.)

    Diseñado para procesar descripciones en lenguaje natural como:
    - "delantal floral en tonos rosados"
    - "delantal con diseño de flores"
    - "apron with floral pattern in pink tones"

    Args:
        description: Descripción en lenguaje natural de la IA

    Returns:
        Dict con claves 'apron_type', 'pattern', 'color'

    Example:
        >>> extract_keywords_from_description("delantal floral en tonos rosados")
        {
            'apron_type': 'delantal',
            'pattern': 'floral',
            'color': 'rosado',
            'keywords': ['floral', 'rosado'],
            'confidence': 'medium'
        }
    """
    description_lower = description.lower()
    tokens = normalize_tokens(description_lower)

    result = {
        'apron_type': None,
        'pattern': None,
        'color': None,
        'keywords': [],
        'confidence': 'low'
    }

    # Detectar tipo de delantal
    apron_type = detect_apron_type(tokens)
    if apron_type:
        result['apron_type'] = apron_type
        result['keywords'].append(apron_type)
        result['confidence'] = 'high'

    # Detectar patrón
    pattern = detect_pattern(tokens)
    if pattern:
        result['pattern'] = pattern
        result['keywords'].append(pattern)
        result['confidence'] = 'high'

    # Detectar colores mencionados
    colors_found = []
    for color_name, color_keywords in [
        ('rosado', ['rosado', 'rosa', 'pink']),
        ('blanco', ['blanco', 'white']),
        ('negro', ['negro', 'black']),
        ('azul', ['azul', 'blue']),
        ('verde', ['verde', 'green']),
        ('rojo', ['rojo', 'red']),
        ('amarillo', ['amarillo', 'yellow']),
        ('gris', ['gris', 'gray']),
        ('marrón', ['marrón', 'marron', 'brown']),
    ]:
        for keyword in color_keywords:
            if keyword in description_lower:
                colors_found.append(color_name)
                result['keywords'].append(color_name)
                if result['confidence'] == 'low':
                    result['confidence'] = 'medium'
                break

    if colors_found:
        result['color'] = colors_found[0]  # Primer color detectado

    return result


def rerank_visual_results_by_description(results: List[dict], description: str) -> List[dict]:
    """
    Re-rankea resultados visuales basándose en descripción de IA.

    Procesa la descripción generada por GPT-4V/IA y boosteamos resultados
    que coinciden con los patrones, tipos y colores detectados.

    Args:
        results: Resultados de búsqueda visual (con 'score', 'similarity', u 'original_index')
        description: Descripción de IA de la imagen

    Returns:
        Resultados re-rankeados con scores actualizados y metadata de boost

    Example:
        >>> results = [
        ...     {'name': 'Delantal Floral Rosa', 'score': 0.85, 'original_index': 0},
        ...     {'name': 'Delantal Western', 'score': 0.80, 'original_index': 1}
        ... ]
        >>> desc = "delantal con flores en tonos rosados"
        >>> rerank_visual_results_by_description(results, desc)
        # Delantal Floral Rosa recibe boost +40% por patrón floral
    """
    if not results or not description or len(description) < 10:
        return results

    # Extraer keywords de la descripción
    keywords_info = extract_keywords_from_description(description)

    # Si la confianza es baja, no hacer cambios significativos
    if keywords_info['confidence'] == 'low':
        return results

    print(f"🔍 [GOODY] Re-ranking visual: detectados patrón='{keywords_info['pattern']}', tipo='{keywords_info['apron_type']}', color='{keywords_info['color']}'")

    # Re-rankear cada resultado
    for result in results:
        product_name = result.get('name', '').lower()
        boost_factor = 1.0
        matches = []

        # Boost por patrón detectado
        if keywords_info['pattern']:
            pattern_keywords = PATTERN_KEYWORDS.get(keywords_info['pattern'], [])
            for keyword in pattern_keywords:
                if keyword.lower() in product_name:
                    boost_factor *= 1.4  # +40% per pattern match
                    matches.append(f"patrón:{keyword}")
                    break

        # Boost por tipo de delantal detectado
        if keywords_info['apron_type']:
            apron_keywords = APRON_TYPES.get(keywords_info['apron_type'], [])
            for keyword in apron_keywords:
                if keyword.lower() in product_name:
                    boost_factor *= 1.2  # +20% per type match
                    matches.append(f"tipo:{keyword}")
                    break

        # Boost por color (más suave)
        if keywords_info['color']:
            color_name = keywords_info['color']
            if color_name.lower() in product_name:
                boost_factor *= 1.1  # +10% per color match
                matches.append(f"color:{color_name}")

        # Aplicar boost al score
        if matches:
            old_score = result.get('score', result.get('similarity', 0.0))
            new_score = old_score * boost_factor
            result['score'] = new_score
            result['similarity'] = new_score
            result['boost_factor'] = boost_factor
            result['boost_info'] = {
                'factor': boost_factor,
                'matches': matches
            }
        else:
            # Sin matches, preservar original_index y asegurar scores
            if 'original_index' not in result:
                result['original_index'] = results.index(result)
            result['boost_factor'] = 1.0
            result['boost_info'] = {'factor': 1.0, 'matches': []}

    # Re-ordenar por score
    results.sort(key=lambda x: x.get('score', x.get('similarity', 0.0)), reverse=True)

    return results



# ============================================================================
# FUNCIÓN PRINCIPAL DE POST-PROCESAMIENTO
# ============================================================================

def post_process_results(results: List[dict], original_query: str) -> List[dict]:
    """
    Post-procesa resultados aplicando filtros custom de Goody.

    Esta función se llama desde el endpoint de búsqueda después del CLIP search.

    Args:
        results: Resultados de CLIP search
        original_query: Query original del usuario

    Returns:
        Resultados filtrados y re-rankeados
    """
    # Normalizar query
    query_tokens = normalize_tokens(original_query)

    # Detectar tipo de delantal
    apron_type = detect_apron_type(query_tokens)
    if apron_type:
        results = filter_results_by_apron_type(results, apron_type)

    # Detectar patrón
    pattern = detect_pattern(query_tokens)
    if pattern:
        results = filter_results_by_pattern(results, pattern)

    return results
