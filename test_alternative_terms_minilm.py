#!/usr/bin/env python3
"""
TEST: Generador automático de alternative_terms usando MiniLM.
Versión actualizada con filtrado por grupos de categorías.
"""

import sys
import os
import importlib.util

print("=" * 80)
print("🧪 TEST: Generador de Alternative Terms con MiniLM + Filtrado por Grupos")
print("=" * 80)

# Importar el servicio directamente sin inicializar Flask
service_path = os.path.join(
    os.path.dirname(__file__),
    'clip_admin_backend',
    'app',
    'services',
    'alternative_terms_generator.py'
)

spec = importlib.util.spec_from_file_location("alt_terms_gen", service_path)
alt_terms_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alt_terms_module)

generate_alternative_terms = alt_terms_module.generate_alternative_terms
detect_category_group = alt_terms_module.detect_category_group


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
        print(f"{'='*80}")
        print(f"📝 Generando alternative_terms para: '{category_name}'")
        print(f"{'='*80}")

        # Detectar grupo
        group = detect_category_group(category_name)
        if group:
            print(f"  🎯 Grupo detectado: '{group}'")
        else:
            print(f"  ⚠️ Grupo no detectado → usando vocabulario completo")

        alternative_terms = generate_alternative_terms(category_name)

        print(f"\n  ✅ RESULTADO:")
        print(f"     {alternative_terms if alternative_terms else '(vacío)'}")
        print(f"{'='*80}\n")

        results.append({
            'category': category_name,
            'alternative_terms': alternative_terms,
            'group': group
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

    for r in results:
        print(f"\n  📂 {r['category']} (grupo: {r['group'] or 'desconocido'})")
        print(f"     → {r['alternative_terms']}")

    # Comparar con valores manuales de Eve's Store
    print("\n" + "="*80)
    print("🔍 COMPARACIÓN CON VALORES MANUALES (Eve's Store)")
    print("="*80)

    manual_values = {
        "remera musculosas": "remera sin mangas, camiseta sin mangas",
        "top": "remera corta, camisa corta",
        "shores tiro alto": "short tiro alto",
        "shores tiro bajo": "short tiro bajo",
        "bikinis": "traje de baño",
    }

    for r in results:
        cat = r['category']
        if cat in manual_values:
            manual = set(t.strip() for t in manual_values[cat].split(','))
            auto = set(t.strip() for t in (r['alternative_terms'] or '').split(',') if t.strip())

            overlap = manual & auto
            missing = manual - auto
            extra = auto - manual

            print(f"\n  {cat}:")
            print(f"    Manual:      {', '.join(manual)}")
            print(f"    Auto-gen:    {', '.join(auto) if auto else '(vacío)'}")
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
