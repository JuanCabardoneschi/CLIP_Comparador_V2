"""
Test Simple de SearchOptimizer - Sin dependencias externas

Ejecutar: python test_search_optimizer_simple.py
"""

import sys
import os

# Configurar path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app.core.search_optimizer import SearchOptimizer, SearchResult


# ========================================
# MOCK OBJECTS
# ========================================

class MockConfig:
    """Mock de StoreSearchConfig"""
    def __init__(self, visual=0.6, metadata=0.3, business=0.1):
        self.visual_weight = visual
        self.metadata_weight = metadata
        self.business_weight = business
        self.metadata_config = {
            'color_weight': 1.0,
            'brand_weight': 1.0,
            'pattern_weight': 0.8,
            'material_weight': 0.7,
            'style_weight': 0.6
        }


class MockProduct:
    """Mock de Product"""
    def __init__(self, id, name, color=None, brand=None, stock=0, **kwargs):
        self.id = id
        self.name = name
        self.color = color
        self.brand = brand
        self.stock = stock
        self.attributes = kwargs.get('attributes')

        # Atributos opcionales
        for key, value in kwargs.items():
            if key != 'attributes':
                setattr(self, key, value)


# ========================================
# HELPER FUNCTIONS
# ========================================

def assert_equal(actual, expected, msg=""):
    """Assert simple"""
    if actual != expected:
        raise AssertionError(f"{msg}\n  Expected: {expected}\n  Actual: {actual}")


def assert_true(condition, msg=""):
    """Assert booleano"""
    if not condition:
        raise AssertionError(f"{msg}\n  Condition was False")


def assert_close(actual, expected, tolerance=0.01, msg=""):
    """Assert para floats con tolerancia"""
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{msg}\n  Expected: {expected} ± {tolerance}\n  Actual: {actual}")


def run_test(test_func):
    """Ejecutar test y reportar resultado"""
    try:
        test_func()
        print(f"✅ {test_func.__name__}")
        return True
    except AssertionError as e:
        print(f"❌ {test_func.__name__}")
        print(f"   {str(e)}")
        return False
    except Exception as e:
        print(f"💥 {test_func.__name__}")
        print(f"   ERROR: {str(e)}")
        return False


# ========================================
# TESTS
# ========================================

def test_optimizer_initialization():
    """Test 1: Inicialización correcta"""
    config = MockConfig(visual=0.5, metadata=0.3, business=0.2)
    optimizer = SearchOptimizer(config)

    assert_equal(optimizer.visual_weight, 0.5, "Visual weight incorrecto")
    assert_equal(optimizer.metadata_weight, 0.3, "Metadata weight incorrecto")
    assert_equal(optimizer.business_weight, 0.2, "Business weight incorrecto")


def test_invalid_weights():
    """Test 2: Error si pesos no suman 1.0"""
    config = MockConfig(visual=0.5, metadata=0.3, business=0.3)  # Suma 1.1

    try:
        SearchOptimizer(config)
        raise AssertionError("Debería haber lanzado ValueError")
    except ValueError as e:
        if "Pesos no suman 1.0" not in str(e):
            raise AssertionError(f"Error message incorrecto: {e}")


def test_metadata_score_full_match():
    """Test 3: Score 1.0 con todos los atributos matching"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', color='BLANCO', brand='Nike')
    detected = {'color': 'BLANCO', 'brand': 'Nike'}

    score = optimizer.calculate_metadata_score(product, detected)
    assert_equal(score, 1.0, "Score debería ser 1.0 con match perfecto")


def test_metadata_score_partial_match():
    """Test 4: Score 0.5 con 50% de atributos matching"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', color='BLANCO', brand='Nike')
    detected = {'color': 'BLANCO', 'brand': 'Adidas'}  # Solo color match

    score = optimizer.calculate_metadata_score(product, detected)
    assert_equal(score, 0.5, "Score debería ser 0.5 con 1 de 2 matches")


def test_metadata_score_no_match():
    """Test 5: Score 0.0 sin matches"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', color='BLANCO', brand='Nike')
    detected = {'color': 'NEGRO', 'brand': 'Adidas'}  # Ninguno match

    score = optimizer.calculate_metadata_score(product, detected)
    assert_equal(score, 0.0, "Score debería ser 0.0 sin matches")


def test_metadata_score_case_insensitive():
    """Test 6: Matching case-insensitive"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', color='BLANCO', brand='Nike')
    detected = {'color': 'blanco', 'brand': 'nike'}  # Lowercase

    score = optimizer.calculate_metadata_score(product, detected)
    assert_equal(score, 1.0, "Matching debería ser case-insensitive")


def test_metadata_score_empty_detected():
    """Test 7: Score 0.0 sin atributos detectados"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', color='BLANCO')

    score = optimizer.calculate_metadata_score(product, {})
    assert_equal(score, 0.0, "Score debería ser 0.0 sin atributos detectados")


def test_metadata_score_jsonb_attributes():
    """Test 8: Matching con atributos JSONB"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct(
        'p1', 'Vestido',
        attributes={
            'color': 'AZUL',
            'pattern': 'FLORES'
        }
    )
    detected = {'color': 'AZUL', 'pattern': 'FLORES'}

    score = optimizer.calculate_metadata_score(product, detected)
    assert_equal(score, 1.0, "Debería hacer match con atributos JSONB")


def test_business_score_with_stock():
    """Test 9: Score 1.0 con stock disponible"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', stock=10)

    score = optimizer.calculate_business_score(product)
    assert_equal(score, 1.0, "Score debería ser 1.0 con stock")


def test_business_score_no_stock():
    """Test 10: Score 0.0 sin stock"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', stock=0)

    score = optimizer.calculate_business_score(product)
    assert_equal(score, 0.0, "Score debería ser 0.0 sin stock")


def test_business_score_with_featured():
    """Test 11: Score con is_featured"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', stock=5, is_featured=True)

    score = optimizer.calculate_business_score(product)
    assert_equal(score, 1.0, "Score debería ser 1.0 con stock + featured")


def test_business_score_with_discount():
    """Test 12: Score con descuento"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', stock=5, discount=20)

    score = optimizer.calculate_business_score(product)
    assert_equal(score, 1.0, "Score debería ser 1.0 con stock + descuento")


def test_rank_results_basic():
    """Test 13: Ranking básico de 2 productos"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    p1 = MockProduct('p1', 'Camisa Blanca', color='BLANCO', stock=10)
    p2 = MockProduct('p2', 'Polo Rojo', color='ROJO', stock=5)

    raw_results = [
        {'product': p1, 'similarity': 0.8},
        {'product': p2, 'similarity': 0.9}
    ]

    detected = {'color': 'BLANCO'}

    ranked = optimizer.rank_results(raw_results, detected)

    assert_equal(len(ranked), 2, "Debería haber 2 resultados")
    assert_true(ranked[0].final_score >= ranked[1].final_score,
                "Resultados deberían estar ordenados descendentemente")


def test_rank_results_metadata_boosts_score():
    """Test 14: Metadata matching aumenta score final"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', color='BLANCO', brand='Nike', stock=10)

    raw_results = [
        {'product': product, 'similarity': 0.7}
    ]

    detected = {'color': 'BLANCO', 'brand': 'Nike'}

    ranked = optimizer.rank_results(raw_results, detected)

    result = ranked[0]

    # visual: 0.7 * 0.6 = 0.42
    # metadata: 1.0 * 0.3 = 0.30
    # business: 1.0 * 0.1 = 0.10
    # total = 0.82
    expected = 0.82
    assert_close(result.final_score, expected, 0.01,
                 f"Final score debería ser ~{expected}")


def test_rank_results_empty_list():
    """Test 15: Lista vacía retorna lista vacía"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    ranked = optimizer.rank_results([], {})
    assert_equal(len(ranked), 0, "Lista vacía debería retornar lista vacía")


def test_rank_results_sorts_correctly():
    """Test 16: Ordenamiento correcto por final_score"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    # Crear 5 productos con diferentes scores
    products = []
    for i in range(5):
        p = MockProduct(f'p{i}', f'Producto {i}',
                       color='BLANCO' if i % 2 == 0 else 'NEGRO',
                       stock=10)
        products.append(p)

    raw_results = [
        {'product': p, 'similarity': 0.5 + (i * 0.1)}
        for i, p in enumerate(products)
    ]

    detected = {'color': 'BLANCO'}

    ranked = optimizer.rank_results(raw_results, detected)

    # Verificar que están ordenados
    for i in range(len(ranked) - 1):
        assert_true(ranked[i].final_score >= ranked[i+1].final_score,
                   f"Resultado {i} debería tener score >= resultado {i+1}")


def test_search_result_components():
    """Test 17: SearchResult tiene todos los componentes"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', stock=5)
    raw_results = [{'product': product, 'similarity': 0.8}]

    ranked = optimizer.rank_results(raw_results, {})
    result = ranked[0]

    assert_true(hasattr(result, 'visual_score'), "Falta visual_score")
    assert_true(hasattr(result, 'metadata_score'), "Falta metadata_score")
    assert_true(hasattr(result, 'business_score'), "Falta business_score")
    assert_true(hasattr(result, 'final_score'), "Falta final_score")
    assert_true(hasattr(result, 'product_id'), "Falta product_id")
    assert_true(hasattr(result, 'debug_info'), "Falta debug_info")


def test_search_result_to_dict():
    """Test 18: SearchResult.to_dict() funciona"""
    product = MockProduct('p1', 'Camisa', stock=5)

    result = SearchResult(
        product_id='p1',
        product=product,
        visual_score=0.85,
        metadata_score=0.60,
        business_score=0.40,
        final_score=0.75
    )

    data = result.to_dict()

    assert_equal(data['product_id'], 'p1', "product_id incorrecto")
    assert_equal(data['visual_score'], 0.85, "visual_score incorrecto")
    assert_equal(data['metadata_score'], 0.6, "metadata_score incorrecto")
    assert_equal(data['final_score'], 0.75, "final_score incorrecto")


def test_rank_with_score_field():
    """Test 19: Acepta 'score' en lugar de 'similarity'"""
    config = MockConfig()
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', stock=5)
    raw_results = [{'product': product, 'score': 0.75}]  # Usa 'score'

    ranked = optimizer.rank_results(raw_results, {})

    assert_equal(len(ranked), 1, "Debería procesar resultado con 'score'")
    assert_equal(ranked[0].visual_score, 0.75, "Debería usar 'score' como visual_score")


def test_visual_heavy_config():
    """Test 20: Config visual-heavy prioriza visual"""
    config = MockConfig(visual=0.8, metadata=0.15, business=0.05)
    optimizer = SearchOptimizer(config)

    product = MockProduct('p1', 'Camisa', stock=10)
    raw_results = [{'product': product, 'similarity': 0.9}]

    ranked = optimizer.rank_results(raw_results, {})

    # visual: 0.9 * 0.8 = 0.72
    # metadata: 0 * 0.15 = 0
    # business: 1.0 * 0.05 = 0.05
    # total = 0.77
    expected = 0.77
    assert_close(ranked[0].final_score, expected, 0.01,
                f"Score debería ser ~{expected} con config visual-heavy")


# ========================================
# RUNNER
# ========================================

def main():
    print("=" * 60)
    print("🧪 TEST SUITE: SearchOptimizer")
    print("=" * 60)
    print()

    tests = [
        test_optimizer_initialization,
        test_invalid_weights,
        test_metadata_score_full_match,
        test_metadata_score_partial_match,
        test_metadata_score_no_match,
        test_metadata_score_case_insensitive,
        test_metadata_score_empty_detected,
        test_metadata_score_jsonb_attributes,
        test_business_score_with_stock,
        test_business_score_no_stock,
        test_business_score_with_featured,
        test_business_score_with_discount,
        test_rank_results_basic,
        test_rank_results_metadata_boosts_score,
        test_rank_results_empty_list,
        test_rank_results_sorts_correctly,
        test_search_result_components,
        test_search_result_to_dict,
        test_rank_with_score_field,
        test_visual_heavy_config,
    ]

    passed = 0
    failed = 0

    for test in tests:
        if run_test(test):
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 60)
    print(f"📊 RESULTADOS: {passed}/{len(tests)} tests pasaron")
    print("=" * 60)

    if failed == 0:
        print("🎉 ¡TODO OK! Todos los tests pasaron")
        return 0
    else:
        print(f"⚠️  {failed} test(s) fallaron")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
