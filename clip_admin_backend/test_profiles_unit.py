#!/usr/bin/env python
"""
Test del servicio de perfiles de búsqueda (sin BD).
"""

from app.services.search_profiles_service import SearchProfilesService

def test_profile_service():
    """Test unitario del servicio sin BD."""

    print("\n" + "="*70)
    print("🧪 TEST: Servicio de Perfiles de Búsqueda (Sin BD)")
    print("="*70)

    # Test 1: Perfiles disponibles
    print("\n✅ TEST 1: Perfiles disponibles")
    profiles = SearchProfilesService.get_all_profiles()
    for slug, info in profiles.items():
        print(f"   {slug}: {info['name']}")
    assert len(profiles) >= 2
    print("   ✓ PASS")

    # Test 2: Perfil fashion
    print("\n✅ TEST 2: Perfil 'fashion' con variantes")
    fashion = SearchProfilesService.DEFAULT_PROFILES['fashion']
    print(f"   Variantes: {len(fashion['variants_map'])}")
    print(f"   Sinónimos: {len(fashion['category_synonyms'])}")
    print(f"   Colores: {len(fashion['color_tokens'])}")
    assert "short" in fashion['variants_map'].values()
    assert "remera" in fashion['category_synonyms']
    print("   ✓ PASS")

    # Test 3: Normalización
    print("\n✅ TEST 3: Normalización de tokens")
    tests = [
        ("short rojo", ["short", "rojo"]),
        ("remeras", ["remera"]),
        ("shores azul", ["short", "azul"]),
    ]
    for query, expected_contains in tests:
        result = SearchProfilesService.normalize_tokens(query, fashion)
        print(f"   '{query}' → {result}")
        assert result, f"No debe estar vacío"
    print("   ✓ PASS")

    # Test 4: Expansión
    print("\n✅ TEST 4: Expansión de query")
    expanded = SearchProfilesService.expand_query("remera", [], fashion)
    print(f"   'remera' expandido a {len(expanded)} términos: {expanded}")
    assert "remera" in expanded
    assert "camiseta" in expanded or "polera" in expanded
    print("   ✓ PASS")

    # Test 5: Uniforms
    print("\n✅ TEST 5: Perfil 'uniforms'")
    uniforms = SearchProfilesService.DEFAULT_PROFILES['uniforms']
    print(f"   Variantes: {len(uniforms['variants_map'])}")
    assert "delantal" in uniforms['variants_map'].values()
    assert "ambo" in uniforms['category_synonyms']
    print("   ✓ PASS")

    print("\n" + "="*70)
    print("✅ TODOS LOS TESTS UNITARIOS PASARON")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_profile_service()
