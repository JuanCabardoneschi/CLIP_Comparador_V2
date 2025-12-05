"""
Servicio para auto-generación de alternative_terms en categorías.
Utiliza MiniLM para similitud semántica con vocabulario por industria.
"""

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Vocabulario fashion en español (argentino/latinoamericano)
FASHION_VOCABULARY_ES = [
    # Tops
    'remera', 'camiseta', 't-shirt', 'playera', 'polera',
    'musculosa', 'tank top', 'sin mangas', 'camiseta sin mangas', 'remera sin mangas',
    'top', 'crop top', 'remera corta', 'camisa corta',
    'blusa', 'camisa',

    # Bottoms
    'pantalón', 'pantalones', 'jean', 'jeans', 'vaquero', 'denim',
    'short', 'shorts', 'shores', 'bermuda', 'bermudas', 'pantalón corto',
    'short tiro alto', 'short tiro bajo',
    'pollera', 'falda', 'skirt',

    # Swimwear
    'bikini', 'malla', 'traje de baño', 'bañador', 'swimsuit',

    # Outerwear
    'campera', 'chaqueta', 'jacket', 'saco', 'blazer',

    # Descriptores
    'manga corta', 'manga larga',
    'tiro alto', 'tiro bajo', 'cintura alta', 'cintura baja',
    'boca ancha', 'recto', 'chupin', 'skinny',
]

# Grupos de categorías para filtrado (evita mezclar tops con bottoms, etc.)
FASHION_CATEGORY_GROUPS = {
    'tops': {
        'remera', 'remeras', 'camiseta', 'camisetas', 't-shirt',
        'musculosa', 'musculosas', 'tank top',
        'top', 'tops', 'crop top',
        'blusa', 'blusas', 'camisa', 'camisas'
    },
    'bottoms': {
        'pantalón', 'pantalones', 'jean', 'jeans',
        'short', 'shorts', 'shores', 'bermuda', 'bermudas',
        'pollera', 'polleras', 'falda', 'faldas', 'skirt'
    },
    'swimwear': {
        'bikini', 'bikinis', 'malla', 'mallas',
        'traje de baño', 'bañador', 'swimsuit'
    }
}

# Mapeo de grupos a vocabulario permitido
FASHION_GROUP_VOCABULARY = {
    'tops': [
        'remera', 'camiseta', 't-shirt', 'playera', 'polera',
        'musculosa', 'tank top', 'sin mangas', 'camiseta sin mangas', 'remera sin mangas',
        'top', 'crop top', 'remera corta', 'camisa corta',
        'blusa', 'camisa',
        'manga corta', 'manga larga', 'sin mangas'
    ],
    'bottoms': [
        'pantalón', 'pantalones', 'jean', 'jeans', 'vaquero', 'denim',
        'short', 'shorts', 'shores', 'bermuda', 'bermudas', 'pantalón corto',
        'short tiro alto', 'short tiro bajo',
        'pollera', 'falda', 'skirt',
        'tiro alto', 'tiro bajo', 'cintura alta', 'cintura baja',
        'boca ancha', 'recto', 'chupin', 'skinny'
    ],
    'swimwear': [
        'bikini', 'malla', 'traje de baño', 'bañador', 'swimsuit'
    ]
}

# Modelo global (se carga una sola vez)
_model = None


def _get_model():
    """Lazy loading del modelo MiniLM."""
    global _model
    if _model is None:
        logger.info("Cargando modelo SentenceTransformer (MiniLM)...")
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logger.info("✅ Modelo MiniLM cargado exitosamente")
    return _model


def detect_category_group(category_name: str) -> Optional[str]:
    """
    Detecta a qué grupo pertenece la categoría (tops/bottoms/swimwear).

    Args:
        category_name: Nombre de la categoría (ej: "remera manga corta", "pantalon de jean")

    Returns:
        str: 'tops', 'bottoms', 'swimwear' o None (desconocido)

    Examples:
        >>> detect_category_group("remera manga corta")
        'tops'
        >>> detect_category_group("pantalon de jeans chupin")
        'bottoms'
        >>> detect_category_group("bikinis")
        'swimwear'
    """
    if not category_name:
        return None

    tokens = set(category_name.lower().split())

    # Buscar coincidencia directa en grupos
    for group_name, group_terms in FASHION_CATEGORY_GROUPS.items():
        if tokens & group_terms:  # Intersección no vacía
            logger.debug(f"🔍 Categoría '{category_name}' detectada como grupo '{group_name}'")
            return group_name

    logger.debug(f"⚠️ Categoría '{category_name}' no coincide con ningún grupo conocido")
    return None


def generate_alternative_terms(
    category_name: str,
    max_terms: int = 5,
    similarity_threshold: float = 0.50
) -> Optional[str]:
    """
    Genera alternative_terms para una categoría usando similitud semántica.

    Args:
        category_name: Nombre de la categoría (ej: "remeras manga corta")
        max_terms: Máximo de términos alternativos a generar
        similarity_threshold: Umbral mínimo de similitud (0.0-1.0)

    Returns:
        String con términos separados por comas, o None si no hay términos
        Ejemplo: "camiseta, t-shirt, remera corta"
    """
    try:
        if not category_name or not category_name.strip():
            return None

        category_name = category_name.strip().lower()

        # Detectar grupo de categoría para filtrado
        category_group = detect_category_group(category_name)

        # Seleccionar vocabulario basado en grupo detectado
        if category_group and category_group in FASHION_GROUP_VOCABULARY:
            vocabulary = FASHION_GROUP_VOCABULARY[category_group]
            logger.info(f"🎯 Usando vocabulario filtrado para grupo '{category_group}' ({len(vocabulary)} términos)")
        else:
            # Fallback: usar vocabulario completo si no se detecta grupo
            vocabulary = FASHION_VOCABULARY_ES
            logger.info(f"📚 Usando vocabulario completo ({len(vocabulary)} términos)")

        # Obtener modelo
        model = _get_model()

        # Embedding de la categoría
        cat_embedding = model.encode([category_name])[0]

        # Filtrar vocabulario: remover términos que ya están en category_name
        filtered_vocab = [
            term for term in vocabulary  # ← Usar vocabulario filtrado por grupo
            if term not in category_name  # No incluir si ya está completo
        ]

        if not filtered_vocab:
            logger.info(f"No hay vocabulario candidato para '{category_name}'")
            return None

        # Embeddings del vocabulario
        vocab_embeddings = model.encode(filtered_vocab)

        # Calcular similitudes
        similarities = cosine_similarity([cat_embedding], vocab_embeddings)[0]

        # Crear pares (término, similitud) y filtrar por umbral
        candidates = [
            (term, sim)
            for term, sim in zip(filtered_vocab, similarities)
            if sim >= similarity_threshold
        ]

        if not candidates:
            logger.info(f"No hay términos con similitud >= {similarity_threshold} para '{category_name}'")
            return None

        # Ordenar por similitud descendente y tomar top N
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = candidates[:max_terms]

        # Crear string de resultado
        result = ', '.join([term for term, _ in top_candidates])

        logger.info(f"✅ Generated alternative_terms for '{category_name}': {result}")
        logger.debug(f"   Top similarities: {[(t, f'{s:.3f}') for t, s in top_candidates]}")

        return result

    except Exception as e:
        logger.error(f"Error generando alternative_terms para '{category_name}': {e}", exc_info=True)
        return None


def generate_alternative_terms_batch(category_names: list[str], **kwargs) -> dict[str, Optional[str]]:
    """
    Genera alternative_terms para múltiples categorías en batch.
    Más eficiente que llamar generate_alternative_terms() múltiples veces.

    Args:
        category_names: Lista de nombres de categorías
        **kwargs: Parámetros adicionales para generate_alternative_terms()

    Returns:
        Dict con {category_name: alternative_terms}
    """
    results = {}

    try:
        for name in category_names:
            results[name] = generate_alternative_terms(name, **kwargs)

        return results

    except Exception as e:
        logger.error(f"Error en generación batch: {e}", exc_info=True)
        return results
