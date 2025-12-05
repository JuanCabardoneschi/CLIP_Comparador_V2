#!/usr/bin/env python3
"""
TEST: Generador automático de alternative_terms usando MiniLM.
Versión standalone sin dependencias de Flask/SQLAlchemy.
"""

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

print("=" * 80)
print("🧪 TEST: Generador de Alternative Terms con MiniLM")
print("=" * 80)

# Vocabulario fashion genérico
FASHION_VOCABULARY_ES = [
    # Tops
    'remera', 'camiseta', 't-shirt', 'playera', 'polera',
    'musculosa', 'tank top', 'sin mangas', 'camiseta sin mangas', 'remera sin mangas',
    'top', 'crop top', 'remera corta', 'camisa corta',
    'blusa', 'camisa',

    # Bottoms
    'pantalón', 'pantalones', 'jean', 'jeans', 'vaquero', 'denim',
    'short', 'shorts', 'shores', 'bermuda', 'bermudas', 'pantalón corto', 'short tiro alto', 'short tiro bajo',
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

print("\n🔄 Cargando modelo MiniLM...")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
print("✅ Modelo cargado exitosamente\n")


def generate_alternative_terms_minilm(
    category_name: str,
    max_terms: int = 5,
    similarity_threshold: float = 0.35
):
    """
    Genera alternative_terms usando similitud semántica con MiniLM.
    """
    print(f"{'='*80}")
    print(f"📝 Generando alternative_terms para: '{category_name}'")
    print(f"{'='*80}")

    # Embedding de la categoría
    print(f"  🔍 Generando embedding para '{category_name}'...")
    cat_embedding = model.encode([category_name.lower()])[0]

    # Filtrar vocabulario: remover términos que ya están en category_name
    category_tokens = set(category_name.lower().split())
    filtered_vocab = [
        term for term in FASHION_VOCABULARY_ES
        if term not in category_name.lower()  # No incluir si ya está completo
    ]

    print(f"  📚 Vocabulario candidato: {len(filtered_vocab)} términos")

    # Embeddings del vocabulario
    print(f"  🔍 Generando embeddings para vocabulario...")
    vocab_embeddings = model.encode(filtered_vocab)

    # Calcular similitudes
    print(f"  🧮 Calculando similitudes semánticas...")
    similarities = cosine_similarity([cat_embedding], vocab_embeddings)[0]

    # Crear pares (término, similitud) y filtrar por umbral
    candidates = [
        (term, sim)
        for term, sim in zip(filtered_vocab, similarities)
        if sim >= similarity_threshold
    ]

    # Ordenar por similitud descendente
    candidates.sort(key=lambda x: x[1], reverse=True)

    print(f"\n  📊 Top 10 términos más similares:")
    for i, (term, sim) in enumerate(candidates[:10], 1):
        print(f"     {i:2d}. '{term}' → {sim:.3f}")

    # Tomar top N
    top_candidates = candidates[:max_terms]
    result = ', '.join([term for term, _ in top_candidates])

    print(f"\n  🎯 RESULTADO ({len(top_candidates)} términos):")
    print(f"     {result}")
    print(f"{'='*80}\n")

    return result


def run_tests():
    """Ejecutar pruebas con categorías reales"""

    print("\n" + "="*80)
    print("🧪 INICIANDO PRUEBAS")
    print("="*80 + "\n")

    test_cases = [
        "remeras manga corta",
        "remera musculosas",
        "top",
        "shores tiro alto",
        "shores tiro bajo",
        "bikinis",
        "pantalones de jeans chupin",
        "pantalon de jeans boca ancha",
    ]

    results = []

    for category_name in test_cases:
        alternative_terms = generate_alternative_terms_minilm(category_name)
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
        alt = result['alternative_terms'] or '(vacío)'
        print(f"     → {alt}")

    # Comparación con valores manuales de Eve's Store
    print("\n" + "="*80)
    print("🔍 COMPARACIÓN CON VALORES MANUALES (Eve's Store)")
    print("="*80)

    manual_values = {
        'remera musculosas': 'remera sin mangas, camiseta sin mangas',
        'top': 'remera corta, camisa corta',
        'shores tiro alto': 'short tiro alto',
        'shores tiro bajo': 'short tiro bajo',
        'bikinis': 'traje de baño',
    }

    for cat, manual in manual_values.items():
        auto_result = next((r['alternative_terms'] for r in results if r['category'] == cat), '')
        print(f"\n  {cat}:")
        print(f"    Manual:      {manual}")
        print(f"    Auto-gen:    {auto_result}")

        # Comparar términos
        manual_set = set(t.strip() for t in manual.split(','))
        auto_set = set(t.strip() for t in auto_result.split(',')) if auto_result else set()

        overlap = manual_set & auto_set
        missing = manual_set - auto_set
        extra = auto_set - manual_set

        if overlap:
            print(f"    ✅ Coincidencias: {overlap}")
        if missing:
            print(f"    ⚠️  Faltantes: {missing}")
        if extra:
            print(f"    ℹ️  Extras: {extra}")

    print("\n" + "="*80)
    print("✅ Pruebas completadas")
    print("="*80)


if __name__ == '__main__':
    try:
        run_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Prueba interrumpida por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error en prueba: {e}")
        import traceback
        traceback.print_exc()
