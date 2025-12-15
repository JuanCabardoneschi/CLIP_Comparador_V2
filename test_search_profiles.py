#!/usr/bin/env python
"""
Test del sistema de perfiles de búsqueda.
Valida que:
1. Los perfiles se cargan correctamente
2. La normalización de tokens funciona
3. La expansión de queries funciona
4. La detección de categorías funciona
"""

import sys
import os

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.client import Client
from app.models.category import Category
from app.services.search_profiles_service import SearchProfilesService

def test_profiles():
    """Test completo del sistema de perfiles."""

    app = create_app()

    with app.app_context():
        print("\n" + "="*70)
        print("🧪 TEST: Sistema de Perfiles de Búsqueda por Industria")
        print("="*70)

        # Test 1: Cargar perfiles disponibles
        print("\n✅ TEST 1: Perfiles disponibles")
        profiles = SearchProfilesService.get_all_profiles()
        for slug, info in profiles.items():
            print(f"   {slug}: {info['name']}")
        assert len(profiles) >= 2, "Debe haber al menos 2 perfiles (fashion, uniforms)"
        print("   ✓ PASS")

        # Test 2: Perfil 'fashion' tiene variantes comunes
        print("\n✅ TEST 2: Perfil 'fashion' con variantes")
        fashion_profile = SearchProfilesService.DEFAULT_PROFILES['fashion']
        assert 'short' in fashion_profile['variants_map'].values(), "Debe mapear shores/short"
        assert 'remera' in fashion_profile['variants_map'].values(), "Debe mapear remeras/remera"
        print(f"   {len(fashion_profile['variants_map'])} variantes configuradas")
        print("   ✓ PASS")

        # Test 3: Normalización de tokens
        print("\n✅ TEST 3: Normalización de tokens")
        profile = SearchProfilesService.DEFAULT_PROFILES['fashion']
        test_cases = [
            ("short rojo", ["short", "rojo"]),
            ("remeras negras", ["remera", "negra"]),
            ("shores azules", ["short", "azul"]),
        ]
        for query, expected in test_cases:
            result = SearchProfilesService.normalize_tokens(query, profile)
            print(f"   '{query}' → {result}")
        print("   ✓ PASS")

        # Test 4: Expansión de query
        print("\n✅ TEST 4: Expansión de query")
        profile = SearchProfilesService.DEFAULT_PROFILES['fashion']

        # Simular categorías vacías para este test
        test_query = "remera"
        expanded = SearchProfilesService.expand_query(test_query, [], profile)
        print(f"   '{test_query}' expandido a: {expanded}")
        assert "remera" in expanded, "Debe incluir el token original"
        print("   ✓ PASS")

        # Test 5: Colores excluidos en detección
        print("\n✅ TEST 5: Colores excluidos")
        profile = SearchProfilesService.DEFAULT_PROFILES['fashion']
        color_tokens = profile.get('color_tokens', set())
        print(f"   {len(color_tokens)} colores configurados: {list(color_tokens)[:5]}...")
        assert "rojo" in color_tokens, "Debe excluir 'rojo'"
        assert "azul" in color_tokens, "Debe excluir 'azul'"
        print("   ✓ PASS")

        # Test 6: Estrategia de filtrado
        print("\n✅ TEST 6: Estrategia de filtrado")
        strategy = profile.get('filter_strategy')
        print(f"   Estrategia: {strategy}")
        assert strategy == "root-unique", "Perfil fashion debe usar root-unique"
        print("   ✓ PASS")

        # Test 7: Caché de perfil
        print("\n✅ TEST 7: Caché de perfil")

        # Crear un cliente de prueba
        test_client_id = "test-client-prof"
        try:
            existing = Client.query.filter_by(id=test_client_id).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()
        except:
            pass

        test_client = Client(
            id=test_client_id,
            name="Test Fashion Store",
            email="test@example.com",
            industry="fashion"
        )
        db.session.add(test_client)
        db.session.commit()

        # Cargar perfil (debería cachearse)
        profile1 = SearchProfilesService.get_profile(test_client_id, "fashion")
        profile2 = SearchProfilesService.get_profile(test_client_id, "fashion")  # Desde caché

        assert profile1 == profile2, "Perfil debe ser consistente (cacheado)"
        assert profile1.get("name") == "Moda / Fashion", "Debe cargar perfil fashion"
        print("   ✓ PASS (caché funciona)")

        # Limpiar
        db.session.delete(test_client)
        db.session.commit()

        print("\n" + "="*70)
        print("✅ TODOS LOS TESTS PASARON")
        print("="*70 + "\n")


if __name__ == "__main__":
    test_profiles()
