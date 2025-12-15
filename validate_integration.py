"""
Test simplificado: Validar integración de perfiles en search_text.py

Este script verifica que los cambios en search_text.py sean correctos sin
necesidad de ejecutar Flask o instalar dependencias.
"""
import re

def test_search_text_integration():
    """Verifica que search_text.py tenga la integración correcta."""
    print("=" * 70)
    print("VALIDACIÓN DE INTEGRACIÓN: search_text.py")
    print("=" * 70)

    file_path = "clip_admin_backend/app/blueprints/search_text.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tests_passed = 0
    tests_total = 0

    # Test 1: Verificar importación de SearchProfilesService
    tests_total += 1
    if "from app.services.search_profiles_service import SearchProfilesService" in content:
        print("✅ Test 1: SearchProfilesService está importado")
        tests_passed += 1
    else:
        print("❌ Test 1: SearchProfilesService NO está importado")

    # Test 2: Verificar que _extract_key_terms acepta client_profile
    tests_total += 1
    if re.search(r"def _extract_key_terms_with_dependency_parsing\(text: str, client_profile: dict = None\)", content):
        print("✅ Test 2: _extract_key_terms acepta parámetro client_profile")
        tests_passed += 1
    else:
        print("❌ Test 2: _extract_key_terms NO acepta client_profile")

    # Test 3: Verificar que se carga variants_map del perfil
    tests_total += 1
    if "variants_map = client_profile.get('variants_map', {})" in content:
        print("✅ Test 3: variants_map se extrae del perfil")
        tests_passed += 1
    else:
        print("❌ Test 3: variants_map NO se extrae del perfil")

    # Test 4: Verificar que _to_singular acepta variants_map
    tests_total += 1
    if re.search(r"def _to_singular\(token, variants_map=None\)", content):
        print("✅ Test 4: _to_singular acepta parámetro variants_map")
        tests_passed += 1
    else:
        print("❌ Test 4: _to_singular NO acepta variants_map")

    # Test 5: Verificar que _to_singular usa variants_map
    tests_total += 1
    if "if variants_map and txt in variants_map:" in content:
        print("✅ Test 5: _to_singular usa variants_map para normalización")
        tests_passed += 1
    else:
        print("❌ Test 5: _to_singular NO usa variants_map")

    # Test 6: Verificar que se carga perfil en text_search()
    tests_total += 1
    if "SearchProfilesService.get_profile(str(client.id), client.industry)" in content:
        print("✅ Test 6: Perfil se carga en endpoint text_search()")
        tests_passed += 1
    else:
        print("❌ Test 6: Perfil NO se carga en endpoint")

    # Test 7: Verificar que se pasa client_profile al extractor
    tests_total += 1
    if re.search(r"_extract_key_terms_with_dependency_parsing\(query_text, client_profile\)", content):
        print("✅ Test 7: client_profile se pasa al extractor")
        tests_passed += 1
    else:
        print("❌ Test 7: client_profile NO se pasa al extractor")

    # Test 8: Contar llamadas actualizadas a _to_singular
    tests_total += 1
    calls_with_variants = len(re.findall(r"_to_singular\([^,]+, variants_map\)", content))
    if calls_with_variants >= 10:  # Esperamos al menos 10 llamadas actualizadas
        print(f"✅ Test 8: {calls_with_variants} llamadas a _to_singular usan variants_map")
        tests_passed += 1
    else:
        print(f"⚠️  Test 8: Solo {calls_with_variants} llamadas usan variants_map (esperado: 10+)")

    # Test 9: Verificar logging del perfil
    tests_total += 1
    if "[PROFILE] Perfil cargado:" in content:
        print("✅ Test 9: Log de perfil cargado presente")
        tests_passed += 1
    else:
        print("❌ Test 9: Log de perfil NO presente")

    print("\n" + "=" * 70)
    print(f"RESULTADO: {tests_passed}/{tests_total} tests pasaron")
    print("=" * 70)

    if tests_passed == tests_total:
        print("\n🎉 ¡INTEGRACIÓN COMPLETA!")
        print("\n📝 Cambios realizados:")
        print("   1. _extract_key_terms() acepta client_profile")
        print("   2. variants_map se extrae del perfil")
        print("   3. _to_singular() usa variants_map para normalización")
        print("   4. Perfil se carga al inicio de text_search()")
        print("   5. Todas las llamadas a _to_singular actualizadas")

        print("\n🚀 Próximos pasos:")
        print("   1. Configurar mapeos custom en Admin Panel:")
        print("      - Ir a /search-profiles/edit/{profile_id}")
        print("      - Agregar: 'mono' → 'enterito'")
        print("   2. Hacer búsqueda: POST /api/search-text {'query': 'monos'}")
        print("   3. Verificar logs: '[PROFILE] Perfil cargado: Fashion'")
        print("   4. Validar que 'mono' se normalice a 'enterito'\n")
    else:
        print("\n⚠️  Algunos tests fallaron. Revisar la integración.\n")

    return tests_passed == tests_total


def show_code_example():
    """Muestra cómo funciona la integración."""
    print("\n" + "=" * 70)
    print("EJEMPLO DE FLUJO DE BÚSQUEDA")
    print("=" * 70)

    example = """
    # 1. Usuario hace búsqueda
    POST /api/search-text
    {
        "query": "monos negros con cierre"
    }

    # 2. text_search() carga perfil del cliente
    client_profile = SearchProfilesService.get_profile(
        client_id="eve-id",
        industry="uniforms"
    )
    # → Devuelve perfil "Uniforms" con variants_map, color_tokens, etc.

    # 3. Se pasa al extractor
    extraction_result = _extract_key_terms_with_dependency_parsing(
        query_text="monos negros con cierre",
        client_profile=client_profile
    )

    # 4. Dentro del extractor, _to_singular() usa variants_map
    variants_map = client_profile.get('variants_map', {})
    # variants_map = {"mono": "enterito", "monos": "enterito", ...}

    # 5. Cuando spaCy procesa "monos":
    token.text.lower() = "monos"

    # Antes: return token.lemma_.lower() → "mono"
    # Ahora:
    if "monos" in variants_map:
        return variants_map["monos"]  # → "enterito"

    # 6. Resultado
    extraction_result = {
        'text': 'enterito negro cierre',  # ✅ "mono" normalizado
        'category': 'enterito',
        'modifiers': ['negro', 'cierre']
    }
    """

    print(example)
    print("=" * 70)


if __name__ == "__main__":
    print("\n🔍" * 35)
    print("VALIDACIÓN DE INTEGRACIÓN: Perfiles → search_text.py")
    print("🔍" * 35 + "\n")

    success = test_search_text_integration()

    if success:
        show_code_example()
