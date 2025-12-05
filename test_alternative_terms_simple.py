#!/usr/bin/env python3
"""
TEST SIMPLIFICADO: Simular generación de alternative_terms sin MiniLM.

Muestra qué términos se generarían basándose en reglas simples + similitud de palabras.
"""

from typing import Set, List
from difflib import SequenceMatcher

print("=" * 80)
print("🧪 TEST SIMPLIFICADO: Generador de Alternative Terms")
print("   (Sin dependencias de ML - solo reglas lingüísticas)")
print("=" * 80)

# Vocabulario fashion genérico
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

    # Swimwear
    'bikini', 'malla', 'traje de baño', 'bañador', 'swimsuit',

    # Outerwear
    'campera', 'chaqueta', 'jacket', 'saco', 'blazer',

    # Descriptores
    'manga corta', 'manga larga', 'sin mangas',
    'tiro alto', 'tiro bajo', 'cintura alta', 'cintura baja',
    'boca ancha', 'recto', 'chupin', 'skinny',
}

# Reglas de sinónimos directos
SYNONYM_RULES = {
    'remera': ['camiseta', 't-shirt', 'playera'],
    'remeras': ['camisetas', 'playeras'],
    'musculosa': ['sin mangas', 'tank top'],
    'musculosas': ['sin mangas', 'tank top'],
    'top': ['remera corta', 'crop top'],
    'pantalón': ['jean', 'jeans'],
    'pantalones': ['jeans'],
    'short': ['shores', 'bermuda'],
    'shorts': ['shores', 'bermudas'],
    'shores': ['short', 'bermuda'],
    'bikini': ['traje de baño', 'malla'],
    'bikinis': ['traje de baño'],
}

# Reglas de expansión por contexto
CONTEXT_RULES = {
    'manga corta': ['remera', 'camiseta'],
    'sin mangas': ['musculosa', 'top'],
    'tiro alto': ['cintura alta', 'high waist'],
    'tiro bajo': ['cintura baja', 'low waist'],
}


def string_similarity(a: str, b: str) -> float:
    """Calcula similitud entre dos strings (0-1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def generate_alternative_terms_simple(category_name: str, max_terms: int = 5) -> List[str]:
    """
    Genera alternative_terms usando reglas simples + similitud de strings.
    """
    category_lower = category_name.lower()
    category_tokens = set(category_lower.split())
    alternatives = set()

    print(f"\n📝 Procesando: '{category_name}'")
    print(f"   Tokens: {category_tokens}")

    # Paso 1: Aplicar reglas de sinónimos directos
    for token in category_tokens:
        if token in SYNONYM_RULES:
            synonyms = SYNONYM_RULES[token]
            alternatives.update(synonyms)
            print(f"   ✅ Sinónimos directos de '{token}': {synonyms}")

    # Paso 2: Aplicar reglas de contexto
    for context_phrase, expansions in CONTEXT_RULES.items():
        if context_phrase in category_lower:
            alternatives.update(expansions)
            print(f"   ✅ Expansión por contexto '{context_phrase}': {expansions}")

    # Paso 3: Buscar términos similares en vocabulario (SequenceMatcher)
    for vocab_term in FASHION_VOCABULARY_ES:
        # Saltar si ya está en alternatives o en category_tokens
        if vocab_term in alternatives or vocab_term in category_tokens:
            continue

        # Calcular similitud con cada token de la categoría
        for token in category_tokens:
            similarity = string_similarity(token, vocab_term)
            if similarity > 0.7:  # umbral de similitud
                alternatives.add(vocab_term)
                print(f"   ✅ Similitud '{token}' ↔ '{vocab_term}': {similarity:.2f}")
                break

    # Filtrar términos que ya están en el nombre original
    filtered = [t for t in alternatives if t not in category_lower]

    # Limitar a max_terms
    result = filtered[:max_terms]

    print(f"   🎯 Términos generados: {result}")

    return result


def run_tests():
    """Ejecutar pruebas con categorías reales"""

    print("\n" + "="*80)
    print("🧪 INICIANDO PRUEBAS")
    print("="*80)

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
        alternative_terms_list = generate_alternative_terms_simple(category_name)
        alternative_terms = ', '.join(alternative_terms_list)

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
        if overlap:
            print(f"    ✅ Coincidencias: {overlap}")
        else:
            print(f"    ⚠️  Sin coincidencias directas")

    print("\n" + "="*80)
    print("✅ Pruebas completadas")
    print("="*80)


if __name__ == '__main__':
    run_tests()
