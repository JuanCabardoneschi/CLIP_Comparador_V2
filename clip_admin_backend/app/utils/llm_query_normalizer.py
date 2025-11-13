"""
Normalizador semántico de queries usando Sentence Transformers (MiniLM)
Extrae color, tipo y contexto de la consulta del usuario DINÁMICAMENTE desde BD del cliente.
USA EMBEDDINGS SEMÁNTICOS para matching flexible.
"""
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

# Modelo liviano multilingüe
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _extract_client_vocabulary(client_id: int) -> dict:
    """
    Extrae vocabulario dinámico desde la BD del cliente

    Returns:
        dict con 'colores', 'colores_especificos', 'tipos', 'contextos' basados en datos reales
    """
    from app import db
    from app.models.category import Category
    from app.models.product import Product
    from app.models.product_attribute_config import ProductAttributeConfig
    from sqlalchemy import text, func

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
        products = Product.query.filter_by(client_id=client_id).all()

        for product in products:
            if product.tags:
                tags = [t.strip().lower() for t in product.tags.split(',')]
                vocabulary['contextos'].update(t for t in tags if len(t) > 2)

    except Exception as e:
        print(f"⚠️ Error extrayendo contextos: {e}")

    # Convertir sets a listas
    return {
        'colores': list(vocabulary['colores_especificos']),
        'tipos': list(vocabulary['tipos']),
        'contextos': list(vocabulary['contextos'])
    }


def _semantic_match(query: str, vocabulary: list, threshold: float = 0.5) -> str:
    """
    Encuentra la mejor coincidencia semántica usando embeddings del LLM.

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

    # Encodear query y vocabulario
    query_emb = model.encode([query.lower()])
    vocab_embs = model.encode([v.lower() for v in vocabulary])

    # Calcular similitudes coseno
    similarities = cosine_similarity(query_emb, vocab_embs)[0]

    # Encontrar el mejor match
    max_idx = np.argmax(similarities)
    max_sim = similarities[max_idx]

    if max_sim >= threshold:
        print(f"  🎯 Match: '{query}' → '{vocabulary[max_idx]}' (sim={max_sim:.3f})")
        return vocabulary[max_idx]

    return None


def _semantic_match_multiple(query: str, vocabulary: list, threshold: float = 0.4, top_k: int = 3) -> list:
    """
    Encuentra múltiples coincidencias semánticas.

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

    # Encodear query y vocabulario
    query_emb = model.encode([query.lower()])
    vocab_embs = model.encode([v.lower() for v in vocabulary])

    # Calcular similitudes
    similarities = cosine_similarity(query_emb, vocab_embs)[0]

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
    query_lower = query.lower()
    model = get_model()
    emb = model.encode(query_lower)

    # Obtener vocabulario dinámico del cliente
    if client_id:
        vocab = _extract_client_vocabulary(client_id)
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
    color = _semantic_match(query, colores, threshold=0.45) if colores else None
    tipo = _semantic_match(query, tipos, threshold=0.50) if tipos else None
    contexto = _semantic_match_multiple(query, contextos, threshold=0.40, top_k=2) if contextos else []

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
