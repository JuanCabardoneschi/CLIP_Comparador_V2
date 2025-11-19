"""
🧪 TEST_EXTRACTOR.PY
Herramienta standalone para testear el extractor spaCy de forma independiente

Uso:
    python tools/test_extractor.py "delantal con cierre al costado"
    python tools/test_extractor.py "short rojo con bolsillos grandes"
    python tools/test_extractor.py --batch  # Ejecutar suite completa de tests
"""

import sys
import os

# Agregar path del proyecto para importar módulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'clip_admin_backend'))

def test_extractor_single(query: str):
    """Testear una query individual"""
    from app.blueprints.search_text import _extract_key_terms_with_dependency_parsing

    print(f"\n{'#'*70}")
    print(f"TEST INDIVIDUAL: '{query}'")
    print(f"{'#'*70}")

    resultado = _extract_key_terms_with_dependency_parsing(query)

    print(f"\n{'='*70}")
    print(f"RESULTADO FINAL:")
    print(f"  Query original: '{query}'")
    print(f"  Términos extraídos: '{resultado}'")
    print(f"  Términos (lista): {resultado.split() if resultado else []}")
    print(f"{'='*70}\n")

    return resultado


def test_extractor_batch():
    """Ejecutar suite completa de casos de prueba"""
    from app.blueprints.search_text import _extract_key_terms_with_dependency_parsing

    # Suite de casos de prueba con resultados esperados
    test_cases = [
        # (query, expected_terms, descripción)
        ("delantal con cierre al costado", ["delantal", "cierre"],
         "Debe capturar 'delantal' y 'cierre', descartar 'costado' (nivel 2)"),

        ("delantal con bolsillos grandes", ["delantal", "bolsillos"],
         "Debe capturar 'delantal' y 'bolsillos', descartar 'grandes' (nivel 2)"),

        ("short rojo", ["short", "rojo"],
         "Debe capturar 'short' (principal) y 'rojo' (adjetivo nivel 1)"),

        ("short rojo con cierre largo", ["short", "rojo", "cierre"],
         "Debe capturar 'short', 'rojo' (nivel 1) y 'cierre' (nivel 1), descartar 'largo' (nivel 2)"),

        ("mostrame delantales con cierre al costado", ["delantales", "cierre"],
         "Debe ignorar verbo 'mostrame', capturar 'delantales' y 'cierre', descartar 'costado'"),

        ("busco top negro", ["top", "negro"],
         "Debe ignorar verbo 'busco', capturar 'top' (anglicismo) y 'negro'"),

        ("remera con bolsillos amplios al frente", ["remera", "bolsillos"],
         "Debe capturar 'remera' y 'bolsillos', descartar 'amplios' y 'frente' (nivel 2)"),

        ("pantalón verde con cierre lateral", ["pantalón", "verde", "cierre"],
         "Debe capturar 'pantalón', 'verde' (nivel 1) y 'cierre' (nivel 1), descartar 'lateral' (nivel 2)"),

        ("delantal", ["delantal"],
         "Solo categoría, sin modificadores"),

        ("gorra roja con logo grande", ["gorra", "roja", "logo"],
         "Debe capturar 'gorra', 'roja' (nivel 1) y 'logo' (nivel 1), descartar 'grande' (nivel 2)"),
    ]

    print(f"\n{'#'*70}")
    print(f"SUITE DE PRUEBAS - EXTRACTOR V2")
    print(f"{'#'*70}\n")

    resultados = []
    passed = 0
    failed = 0

    for i, (query, expected, descripcion) in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(test_cases)}: {descripcion}")
        print(f"{'='*70}")
        print(f"Query: '{query}'")
        print(f"Esperado: {expected}")

        resultado = _extract_key_terms_with_dependency_parsing(query)
        resultado_lista = sorted(resultado.split()) if resultado else []
        expected_sorted = sorted(expected)

        # Validar resultado
        match = resultado_lista == expected_sorted

        if match:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"\n{status}")
        print(f"  Obtenido: {resultado_lista}")
        print(f"  Esperado: {expected_sorted}")

        if not match:
            # Mostrar diferencias
            extra = set(resultado_lista) - set(expected_sorted)
            faltante = set(expected_sorted) - set(resultado_lista)
            if extra:
                print(f"  ⚠️ Extra (no deberían estar): {list(extra)}")
            if faltante:
                print(f"  ⚠️ Faltante (deberían estar): {list(faltante)}")

        resultados.append({
            'test_num': i,
            'query': query,
            'expected': expected_sorted,
            'obtained': resultado_lista,
            'passed': match,
            'descripcion': descripcion
        })

    # Resumen final
    print(f"\n{'='*70}")
    print(f"RESUMEN DE PRUEBAS")
    print(f"{'='*70}")
    print(f"Total: {len(test_cases)} tests")
    print(f"✅ Pasados: {passed} ({100*passed//len(test_cases)}%)")
    print(f"❌ Fallados: {failed} ({100*failed//len(test_cases)}%)")
    print(f"{'='*70}\n")

    # Listar solo tests fallados para revisión rápida
    if failed > 0:
        print(f"\n{'='*70}")
        print(f"TESTS FALLADOS (requieren revisión):")
        print(f"{'='*70}")
        for r in resultados:
            if not r['passed']:
                print(f"\nTest {r['test_num']}: {r['descripcion']}")
                print(f"  Query: '{r['query']}'")
                print(f"  Esperado: {r['expected']}")
                print(f"  Obtenido: {r['obtained']}")
                extra = set(r['obtained']) - set(r['expected'])
                faltante = set(r['expected']) - set(r['obtained'])
                if extra:
                    print(f"  ⚠️ Extra: {list(extra)}")
                if faltante:
                    print(f"  ⚠️ Faltante: {list(faltante)}")
        print(f"{'='*70}\n")

    return resultados


def main():
    """Punto de entrada principal"""
    if len(sys.argv) < 2:
        print("❌ Error: Se requiere una query o --batch")
        print("\nUso:")
        print("  python tools/test_extractor.py \"delantal con cierre al costado\"")
        print("  python tools/test_extractor.py --batch")
        sys.exit(1)

    if sys.argv[1] == '--batch':
        # Ejecutar suite completa
        test_extractor_batch()
    else:
        # Ejecutar query individual
        query = " ".join(sys.argv[1:])
        test_extractor_single(query)


if __name__ == '__main__':
    main()
