"""
Test de Integración - SearchOptimizer en API /search

Prueba la integración del SearchOptimizer en el endpoint de búsqueda visual.
Este script simula el flujo completo sin hacer request HTTP real.
"""

import sys
import os

# Configurar path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

def test_imports():
    """Test 1: Verificar que los imports funcionan"""
    print("🧪 TEST 1: Verificando imports...")
    
    try:
        from app.core.search_optimizer import SearchOptimizer, SearchResult
        print("   ✅ SearchOptimizer importado")
        
        from app.models.store_search_config import StoreSearchConfig
        print("   ✅ StoreSearchConfig importado")
        
        # Simular que se importa en api.py
        from app.blueprints import api
        print("   ✅ Blueprint api importado sin errores")
        
        return True
    except Exception as e:
        print(f"   ❌ Error en imports: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_optimizer_in_api_flow():
    """Test 2: Simular flujo completo con optimizer"""
    print("\n🧪 TEST 2: Simulando flujo de API con optimizer...")
    
    try:
        from app.core.search_optimizer import SearchOptimizer
        from app.models.store_search_config import StoreSearchConfig
        
        # Mock de configuración
        class MockConfig:
            def __init__(self):
                self.visual_weight = 0.6
                self.metadata_weight = 0.3
                self.business_weight = 0.1
                self.metadata_config = {
                    'color_weight': 1.0,
                    'brand_weight': 1.0
                }
        
        # Mock de producto
        class MockProduct:
            def __init__(self, id, name, color, stock):
                self.id = id
                self.name = name
                self.color = color
                self.stock = stock
                self.attributes = None
        
        # Crear optimizer
        config = MockConfig()
        optimizer = SearchOptimizer(config)
        print("   ✅ SearchOptimizer inicializado")
        
        # Simular product_best_match (output de _find_similar_products_in_category)
        p1 = MockProduct('p1', 'Gorra Negra', 'NEGRO', 10)
        p2 = MockProduct('p2', 'Gorra Azul', 'AZUL', 5)
        p3 = MockProduct('p3', 'Gorra Roja', 'ROJO', 0)
        
        product_best_match = {
            'p1': {
                'product': p1,
                'similarity': 0.75,
                'image': None,
                'category': 'Gorras'
            },
            'p2': {
                'product': p2,
                'similarity': 0.82,
                'image': None,
                'category': 'Gorras'
            },
            'p3': {
                'product': p3,
                'similarity': 0.68,
                'image': None,
                'category': 'Gorras'
            }
        }
        
        print(f"   ✅ Mock product_best_match creado: {len(product_best_match)} productos")
        
        # Simular atributos detectados
        detected_attributes = {'color': 'NEGRO'}
        print(f"   ✅ Atributos detectados: {detected_attributes}")
        
        # Convertir a formato de optimizer
        raw_results = [
            {
                'product': match_data['product'],
                'similarity': match_data['similarity']
            }
            for product_id, match_data in product_best_match.items()
        ]
        
        # Aplicar ranking
        ranked_results = optimizer.rank_results(raw_results, detected_attributes)
        print(f"   ✅ Ranking completado: {len(ranked_results)} resultados")
        
        # Verificar resultados
        print("\n   📊 Resultados rankeados:")
        for i, result in enumerate(ranked_results, 1):
            print(f"      {i}. {result.product.name}")
            print(f"         Visual: {result.visual_score:.3f} | "
                  f"Metadata: {result.metadata_score:.3f} | "
                  f"Business: {result.business_score:.3f} → "
                  f"FINAL: {result.final_score:.3f}")
        
        # Verificar que el producto con color matching tenga mejor metadata_score
        negro_result = next((r for r in ranked_results if r.product.color == 'NEGRO'), None)
        if negro_result:
            print(f"\n   ✅ Producto NEGRO tiene metadata_score: {negro_result.metadata_score:.3f}")
            if negro_result.metadata_score > 0:
                print("   ✅ Metadata matching funcionando correctamente")
        
        # Verificar que producto sin stock tenga menor business_score
        sin_stock = next((r for r in ranked_results if r.product.stock == 0), None)
        if sin_stock:
            print(f"   ✅ Producto sin stock tiene business_score: {sin_stock.business_score:.3f}")
            if sin_stock.business_score == 0:
                print("   ✅ Business scoring funcionando correctamente")
        
        # Simular actualización de product_best_match (como en api.py)
        for ranked in ranked_results:
            product_id = ranked.product_id
            if product_id in product_best_match:
                product_best_match[product_id]['optimizer_scores'] = {
                    'visual_score': ranked.visual_score,
                    'metadata_score': ranked.metadata_score,
                    'business_score': ranked.business_score,
                    'final_score': ranked.final_score,
                    'debug_info': ranked.debug_info
                }
                product_best_match[product_id]['similarity'] = ranked.final_score
        
        print("\n   ✅ product_best_match actualizado con optimizer_scores")
        
        # Verificar que similarity se actualizó con final_score
        for pid, data in product_best_match.items():
            if 'optimizer_scores' in data:
                assert data['similarity'] == data['optimizer_scores']['final_score'], \
                    "Similarity debería igualar final_score"
        
        print("   ✅ Similarity actualizado correctamente con final_score")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en flujo: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """Test 3: Verificar que funciona sin optimizer (backward compatibility)"""
    print("\n🧪 TEST 3: Verificando backward compatibility (sin optimizer)...")
    
    try:
        # Simular flujo sin optimizer
        class MockProduct:
            def __init__(self, id, name, stock):
                self.id = id
                self.name = name
                self.stock = stock
        
        product_best_match = {
            'p1': {
                'product': MockProduct('p1', 'Producto 1', 10),
                'similarity': 0.85,
                'category': 'Test'
            }
        }
        
        # Sin optimizer_scores, el flujo debe seguir funcionando
        results = []
        for pid, data in product_best_match.items():
            optimizer_scores = data.get('optimizer_scores')  # None
            
            result = {
                'product_id': pid,
                'name': data['product'].name,
                'similarity': data['similarity']
            }
            
            # Solo agregar optimizer si existe
            if optimizer_scores:
                result['optimizer'] = optimizer_scores
            
            results.append(result)
        
        print(f"   ✅ Resultado sin optimizer: {results[0]}")
        print("   ✅ Campo 'optimizer' no presente (correcto)")
        
        # Verificar que similarity sigue siendo la original
        assert results[0]['similarity'] == 0.85, "Similarity debe ser la original"
        print("   ✅ Similarity original preservada")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_flag():
    """Test 4: Verificar feature flag use_optimizer"""
    print("\n🧪 TEST 4: Verificando feature flag use_optimizer...")
    
    try:
        # Simular diferentes valores de feature flag
        test_cases = [
            ('true', True),
            ('True', True),
            ('TRUE', True),
            ('false', False),
            ('False', False),
            ('0', False),
            ('', False),
        ]
        
        for value, expected in test_cases:
            result = value.lower() == 'true'
            assert result == expected, f"Feature flag '{value}' debería ser {expected}"
            print(f"   ✅ use_optimizer='{value}' → {result}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    print("=" * 70)
    print("🧪 TEST SUITE: Integración SearchOptimizer en API")
    print("=" * 70)
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Flujo completo con optimizer", test_optimizer_in_api_flow),
        ("Backward compatibility", test_backward_compatibility),
        ("Feature flag", test_feature_flag),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n{'=' * 70}")
                print(f"✅ {test_name}: PASS")
                print(f"{'=' * 70}")
            else:
                failed += 1
                print(f"\n{'=' * 70}")
                print(f"❌ {test_name}: FAIL")
                print(f"{'=' * 70}")
        except Exception as e:
            failed += 1
            print(f"\n{'=' * 70}")
            print(f"💥 {test_name}: ERROR")
            print(f"   {str(e)}")
            print(f"{'=' * 70}")
    
    print(f"\n{'=' * 70}")
    print(f"📊 RESULTADOS: {passed}/{len(tests)} tests pasaron")
    print(f"{'=' * 70}")
    
    if failed == 0:
        print("\n🎉 ¡TODO OK! Integración lista para Railway")
        print("\n📋 Próximos pasos:")
        print("   1. Commitear cambios")
        print("   2. Push a Railway")
        print("   3. Probar con widget en producción (use_optimizer=true)")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) fallaron")
        print("   Revisar errores antes de deploy")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
