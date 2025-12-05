#!/usr/bin/env python3
"""
TEST: Generador automático de alternative_terms usando estrategia híbrida.

Prueba aislada sin modificar el sistema existente.
"""

import sys
import os
import re
from typing import Set, List
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Agregar path del backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

print("=" * 80)
print("🧪 TEST: Generador Automático de Alternative Terms")
print("=" * 80)


# ============================================================================
# VOCABULARIO FASHION GENÉRICO (Fallback)
# ============================================================================

FASHION_VOCABULARY_ES = {
    # Tops
    'remera', 'camiseta', 't-shirt', 'playera', 'polera',
    'musculosa', 'tank top', 'sin mangas', 'camiseta sin mangas',
    'top', 'crop top', 'remera corta', 'camisa corta',
    'blusa', 'camisa',

    # Bottoms
    'pantalón', 'pantalones', 'jean', 'jeans', 'vaquero', 'denim',
    'short', 'shorts', 'shores', 'bermuda', 'bermudas', 'pantalón corto',
    'pollera', 'falda', 'skirt',
    'calza', 'legging', 'malla',

    # Outerwear
    'campera', 'chaqueta', 'jacket', 'saco', 'blazer',
    'abrigo', 'coat', 'cardigan', 'suéter', 'sweater', 'buzo',

    # Dresses
    'vestido', 'dress', 'maxi', 'midi', 'mini',

    # Swimwear
    'bikini', 'malla', 'traje de baño', 'bañador', 'swimsuit',

    # Descriptores de estilo
    'manga corta', 'manga larga', 'sin mangas',
    'tiro alto', 'tiro bajo', 'cintura alta', 'cintura baja',
    'ajustado', 'holgado', 'oversize', 'slim fit', 'regular fit',
    'boca ancha', 'bota ancha', 'recto', 'chupin', 'skinny',
}

STOPWORDS_ES = {
    'de', 'con', 'sin', 'para', 'por', 'el', 'la', 'los', 'las',
    'un', 'una', 'unos', 'unas', 'y', 'o', 'del', 'al',
}


# ============================================================================
# FUNCIÓN 1: Extraer vocabulario del cliente (desde productos reales)
# ============================================================================

def get_client_vocabulary(client_id: str) -> Set[str]:
    """
    Extrae vocabulario único de los productos del cliente.
    En producción, esto cachearía el resultado por cliente.
    """
    try:
        from app import create_app
        from app.models.product import Product

        app = create_app()

        with app.app_context():
            # Obtener muestra de productos del cliente
            products = Product.query.filter_by(
                client_id=client_id,
                is_active=True
            ).limit(500).all()

            if not products:
                return set()

            vocab = set()

            for product in products:
                # Extraer de nombre
                if product.name:
                    tokens = re.findall(r'\b[a-záéíóúñ]{3,}\b', product.name.lower())
                    vocab.update(tokens)

                # Extraer de descripción (primeras 200 chars)
                if product.description:
                    desc_snippet = product.description[:200].lower()
                    tokens = re.findall(r'\b[a-záéíóúñ]{3,}\b', desc_snippet)
                    vocab.update(tokens)

                # Extraer de atributos (ej: color, talle, etc)
                if product.attributes and isinstance(product.attributes, dict):
                    for value in product.attributes.values():
                        if isinstance(value, str):
                            tokens = re.findall(r'\b[a-záéíóúñ]{3,}\b', value.lower())
                            vocab.update(tokens)

            # Filtrar stopwords
            vocab = vocab - STOPWORDS_ES

            print(f"  📚 Vocabulario del cliente: {len(vocab)} términos únicos")
            print(f"  📝 Muestra: {list(vocab)[:15]}")

            return vocab

    except Exception as e:
        print(f"  ⚠️  Error extrayendo vocabulario del cliente: {e}")
        return set()


# ============================================================================
# FUNCIÓN 2: Generar alternative_terms con MiniLM
# ============================================================================

def generate_alternative_terms_from_vocab(
    category_name: str,
    vocabulary: Set[str],
    max_terms: int = 5,
    similarity_threshold: float = 0.35
) -> List[str]:
    """
    Genera alternative_terms usando similitud semántica (MiniLM).

    Args:
        category_name: Nombre de la categoría (ej: "remeras manga corta")
        vocabulary: Set de términos candidatos
        max_terms: Máximo número de términos alternativos
        similarity_threshold: Umbral mínimo de similitud (0-1)

    Returns:
        Lista de términos alternativos ordenados por similitud
    """
    try:
        from sentence_transformers import SentenceTransformer

        print(f"\n  🔍 Generando embeddings para '{category_name}'...")

        # Cargar modelo MiniLM
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

        # Embedding de la categoría
        cat_embedding = model.encode([category_name.lower()])[0]

        # Filtrar vocabulario: remover términos que ya están en category_name
        category_tokens = set(category_name.lower().split())
        filtered_vocab = [term for term in vocabulary if term not in category_tokens]

        if not filtered_vocab:
            print("  ⚠️  No hay términos candidatos después del filtrado")
            return []

        # Embeddings del vocabulario
        vocab_list = list(filtered_vocab)
        vocab_embeddings = model.encode(vocab_list)

        # Calcular similitudes
        similarities = cosine_similarity([cat_embedding], vocab_embeddings)[0]

        # Crear pares (término, similitud) y filtrar por umbral
        candidates = [
            (term, sim)
            for term, sim in zip(vocab_list, similarities)
            if sim >= similarity_threshold
        ]

        # Ordenar por similitud descendente
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Tomar top N
        top_candidates = candidates[:max_terms]

        print(f"  ✅ Encontrados {len(top_candidates)} términos candidatos:")
        for term, sim in top_candidates:
            print(f"     - '{term}' (similitud: {sim:.3f})")

        return [term for term, _ in top_candidates]

    except Exception as e:
        print(f"  ❌ Error generando alternative_terms: {e}")
        import traceback
        traceback.print_exc()
        return []


# ============================================================================
# FUNCIÓN 3: Estrategia híbrida (con fallback)
# ============================================================================

def auto_generate_alternative_terms(
    category_name: str,
    client_id: str = None,
    max_terms: int = 5
) -> str:
    """
    Estrategia híbrida para generar alternative_terms:
    1. Si hay productos del cliente → usar vocabulario del cliente
    2. Si no hay productos → usar vocabulario fashion genérico
    3. Filtrar términos ya presentes en category_name

    Returns:
        String con términos separados por coma (ej: "remera, camiseta, t-shirt")
    """
    print(f"\n{'='*80}")
    print(f"📝 Generando alternative_terms para: '{category_name}'")
    print(f"{'='*80}")

    # Paso 1: Intentar con vocabulario del cliente
    vocabulary = set()

    if client_id:
        print(f"  🔄 Intentando extraer vocabulario del cliente {client_id}...")
        client_vocab = get_client_vocabulary(client_id)

        if len(client_vocab) >= 30:  # Umbral mínimo
            print(f"  ✅ Usando vocabulario del cliente ({len(client_vocab)} términos)")
            vocabulary = client_vocab
        else:
            print(f"  ⚠️  Vocabulario del cliente insuficiente ({len(client_vocab)} términos)")

    # Paso 2: Fallback a vocabulario genérico
    if not vocabulary:
        print(f"  🔄 Usando vocabulario fashion genérico...")
        vocabulary = FASHION_VOCABULARY_ES
        print(f"  ✅ Vocabulario genérico: {len(vocabulary)} términos")

    # Paso 3: Generar alternative_terms con MiniLM
    alternative_terms = generate_alternative_terms_from_vocab(
        category_name,
        vocabulary,
        max_terms=max_terms
    )

    result = ', '.join(alternative_terms) if alternative_terms else ''

    print(f"\n  🎯 RESULTADO: '{result}'")
    print(f"{'='*80}\n")

    return result


# ============================================================================
# CASOS DE PRUEBA
# ============================================================================

def run_tests():
    """Ejecutar casos de prueba con categorías reales"""

    print("\n" + "="*80)
    print("🧪 INICIANDO PRUEBAS")
    print("="*80)

    # Casos de prueba (categorías de TiendaNube)
    test_cases = [
        ("remeras manga corta", "747ff760-8eae-46e8-94ca-8ad076370316"),
        ("remera musculosas", "747ff760-8eae-46e8-94ca-8ad076370316"),
        ("top", "747ff760-8eae-46e8-94ca-8ad076370316"),
        ("shores tiro alto", "747ff760-8eae-46e8-94ca-8ad076370316"),
        ("bikinis", "747ff760-8eae-46e8-94ca-8ad076370316"),
    ]

    results = []

    for category_name, client_id in test_cases:
        alternative_terms = auto_generate_alternative_terms(category_name, client_id)
        results.append({
            'category': category_name,
            'alternative_terms': alternative_terms
        })

    # Resumen final
    print("\n" + "="*80)
    print("📊 RESUMEN DE RESULTADOS")
    print("="*80)

    for result in results:
        print(f"\n  📂 {result['category']}")
        print(f"     → {result['alternative_terms'] or '(vacío)'}")

    print("\n" + "="*80)
    print("✅ Pruebas completadas")
    print("="*80)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    try:
        run_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Prueba interrumpida por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error en prueba: {e}")
        import traceback
        traceback.print_exc()
