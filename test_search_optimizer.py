"""
Tests unitarios para SearchOptimizer

Valida:
- Cálculo de metadata_score con diferentes atributos
- Cálculo de business_score con diferentes factores
- Ranking de resultados con ponderación
- Edge cases y validaciones
"""

import pytest
from unittest.mock import Mock
from clip_admin_backend.app.core.search_optimizer import SearchOptimizer, SearchResult
from clip_admin_backend.app.models.store_search_config import StoreSearchConfig


# ========================================
# FIXTURES
# ========================================

@pytest.fixture
def mock_config_balanced():
    """Config balanceada: visual=0.5, metadata=0.3, business=0.2"""
    config = Mock(spec=StoreSearchConfig)
    config.visual_weight = 0.5
    config.metadata_weight = 0.3
    config.business_weight = 0.2
    config.metadata_config = {
        'color_weight': 1.0,
        'brand_weight': 1.0,
        'pattern_weight': 0.8,
        'material_weight': 0.7,
        'style_weight': 0.6
    }
    return config


@pytest.fixture
def mock_config_visual_heavy():
    """Config heavy visual: visual=0.8, metadata=0.15, business=0.05"""
    config = Mock(spec=StoreSearchConfig)
    config.visual_weight = 0.8
    config.metadata_weight = 0.15
    config.business_weight = 0.05
    config.metadata_config = {
        'color_weight': 1.0,
        'brand_weight': 1.0
    }
    return config


@pytest.fixture
def mock_product_basic():
    """Producto básico con atributos mínimos"""
    product = Mock()
    product.id = 'product-001'
    product.name = 'Camisa Blanca'
    product.color = 'BLANCO'
    product.brand = 'Nike'
    product.stock = 10
    product.attributes = None
    return product


@pytest.fixture
def mock_product_no_stock():
    """Producto sin stock"""
    product = Mock()
    product.id = 'product-002'
    product.name = 'Polo Rojo'
    product.color = 'ROJO'
    product.brand = 'Adidas'
    product.stock = 0
    product.attributes = None
    return product


@pytest.fixture
def mock_product_featured():
    """Producto destacado con descuento"""
    product = Mock()
    product.id = 'product-003'
    product.name = 'Chaqueta Premium'
    product.color = 'NEGRO'
    product.brand = 'Puma'
    product.stock = 5
    product.is_featured = True
    product.discount = 20
    product.attributes = None
    return product


@pytest.fixture
def mock_product_jsonb_attrs():
    """Producto con atributos en JSONB"""
    product = Mock()
    product.id = 'product-004'
    product.name = 'Vestido Floral'
    product.stock = 3
    product.attributes = {
        'color': 'AZUL',
        'pattern': 'FLORES',
        'material': 'ALGODON',
        'style': 'CASUAL'
    }
    return product


# ========================================
# TESTS DE INICIALIZACIÓN
# ========================================

def test_optimizer_initialization_valid(mock_config_balanced):
    """Test: Inicialización correcta con config válida"""
    optimizer = SearchOptimizer(mock_config_balanced)

    assert optimizer.visual_weight == 0.5
    assert optimizer.metadata_weight == 0.3
    assert optimizer.business_weight == 0.2
    assert optimizer.metadata_config['color_weight'] == 1.0


def test_optimizer_initialization_invalid_weights():
    """Test: Error si pesos no suman 1.0"""
    config = Mock(spec=StoreSearchConfig)
    config.visual_weight = 0.5
    config.metadata_weight = 0.3
    config.business_weight = 0.3  # SUMA = 1.1
    config.metadata_config = {}

    with pytest.raises(ValueError, match="Pesos no suman 1.0"):
        SearchOptimizer(config)


# ========================================
# TESTS DE METADATA SCORE
# ========================================

def test_metadata_score_all_match(mock_config_balanced, mock_product_basic):
    """Test: Score 1.0 cuando todos los atributos coinciden"""
    optimizer = SearchOptimizer(mock_config_balanced)

    detected = {
        'color': 'BLANCO',
        'brand': 'Nike'
    }

    score = optimizer.calculate_metadata_score(mock_product_basic, detected)

    # Ambos atributos coinciden perfectamente
    assert score == 1.0


def test_metadata_score_partial_match(mock_config_balanced, mock_product_basic):
    """Test: Score parcial cuando solo algunos atributos coinciden"""
    optimizer = SearchOptimizer(mock_config_balanced)

    detected = {
        'color': 'BLANCO',  # Match
        'brand': 'Adidas'   # No match
    }

    score = optimizer.calculate_metadata_score(mock_product_basic, detected)

    # Solo color coincide: 1.0 / 2.0 = 0.5
    assert score == 0.5


def test_metadata_score_no_match(mock_config_balanced, mock_product_basic):
    """Test: Score 0.0 cuando ningún atributo coincide"""
    optimizer = SearchOptimizer(mock_config_balanced)

    detected = {
        'color': 'NEGRO',    # No match
        'brand': 'Adidas'    # No match
    }

    score = optimizer.calculate_metadata_score(mock_product_basic, detected)

    assert score == 0.0


def test_metadata_score_case_insensitive(mock_config_balanced, mock_product_basic):
    """Test: Matching case-insensitive"""
    optimizer = SearchOptimizer(mock_config_balanced)

    detected = {
        'color': 'blanco',  # Lowercase debe hacer match con BLANCO
        'brand': 'nike'     # Lowercase debe hacer match con Nike
    }

    score = optimizer.calculate_metadata_score(mock_product_basic, detected)

    assert score == 1.0


def test_metadata_score_empty_detected(mock_config_balanced, mock_product_basic):
    """Test: Score 0.0 si no hay atributos detectados"""
    optimizer = SearchOptimizer(mock_config_balanced)

    score = optimizer.calculate_metadata_score(mock_product_basic, {})

    assert score == 0.0


def test_metadata_score_jsonb_attributes(mock_config_balanced, mock_product_jsonb_attrs):
    """Test: Matching funciona con atributos en JSONB"""
    optimizer = SearchOptimizer(mock_config_balanced)

    detected = {
        'color': 'AZUL',
        'pattern': 'FLORES',
        'material': 'ALGODON'
    }

    score = optimizer.calculate_metadata_score(mock_product_jsonb_attrs, detected)

    # Todos coinciden (3/3)
    assert score == 1.0


def test_metadata_score_weighted_attributes(mock_config_balanced):
    """Test: Atributos con diferentes pesos"""
    optimizer = SearchOptimizer(mock_config_balanced)

    # Producto con pattern y style
    product = Mock()
    product.id = 'test'
    product.attributes = {
        'pattern': 'RAYAS',
        'style': 'FORMAL'
    }

    detected = {
        'pattern': 'RAYAS',  # weight=0.8, match
        'style': 'CASUAL'    # weight=0.6, no match
    }

    score = optimizer.calculate_metadata_score(product, detected)

    # Solo pattern coincide: 0.8 / (0.8 + 0.6) = 0.571
    assert abs(score - 0.571) < 0.01


# ========================================
# TESTS DE BUSINESS SCORE
# ========================================

def test_business_score_with_stock_only(mock_config_balanced, mock_product_basic):
    """Test: Score 1.0 cuando solo hay stock (sin is_featured/discount)"""
    optimizer = SearchOptimizer(mock_config_balanced)

    score = optimizer.calculate_business_score(mock_product_basic)

    # Stock > 0, sin otros factores → normalizado a 1.0
    assert score == 1.0


def test_business_score_no_stock(mock_config_balanced, mock_product_no_stock):
    """Test: Score 0.0 cuando no hay stock"""
    optimizer = SearchOptimizer(mock_config_balanced)

    score = optimizer.calculate_business_score(mock_product_no_stock)

    assert score == 0.0


def test_business_score_featured_with_discount(mock_config_balanced, mock_product_featured):
    """Test: Score máximo con todos los factores activos"""
    optimizer = SearchOptimizer(mock_config_balanced)

    score = optimizer.calculate_business_score(mock_product_featured)

    # stock (0.4) + is_featured (0.3) + discount (0.3) = 1.0
    assert score == 1.0


def test_business_score_featured_no_stock(mock_config_balanced):
    """Test: Featured pero sin stock"""
    optimizer = SearchOptimizer(mock_config_balanced)

    product = Mock()
    product.id = 'test'
    product.stock = 0
    product.is_featured = True
    product.discount = 20

    score = optimizer.calculate_business_score(product)

    # Solo is_featured (0.3) + discount (0.3) = 0.6 de 1.0 = 0.6
    assert abs(score - 0.6) < 0.01


# ========================================
# TESTS DE RANK_RESULTS
# ========================================

def test_rank_results_basic(mock_config_balanced, mock_product_basic, mock_product_no_stock):
    """Test: Ranking básico de 2 productos"""
    optimizer = SearchOptimizer(mock_config_balanced)

    raw_results = [
        {'product': mock_product_basic, 'similarity': 0.8},
        {'product': mock_product_no_stock, 'similarity': 0.9}
    ]

    detected = {'color': 'BLANCO'}

    ranked = optimizer.rank_results(raw_results, detected)

    assert len(ranked) == 2
    # Verificar que están ordenados descendentemente
    assert ranked[0].final_score >= ranked[1].final_score


def test_rank_results_visual_heavy_config(mock_config_visual_heavy, mock_product_basic):
    """Test: Config visual-heavy prioriza similitud visual"""
    optimizer = SearchOptimizer(mock_config_visual_heavy)

    raw_results = [
        {'product': mock_product_basic, 'similarity': 0.95}
    ]

    detected = {}  # Sin metadata

    ranked = optimizer.rank_results(raw_results, detected)

    result = ranked[0]
    # Con peso visual 0.8, final_score ≈ 0.95 * 0.8 = 0.76
    assert abs(result.final_score - 0.76) < 0.05


def test_rank_results_metadata_boosts_score(mock_config_balanced, mock_product_basic):
    """Test: Metadata matching aumenta score final"""
    optimizer = SearchOptimizer(mock_config_balanced)

    raw_results = [
        {'product': mock_product_basic, 'similarity': 0.7}
    ]

    detected = {'color': 'BLANCO', 'brand': 'Nike'}

    ranked = optimizer.rank_results(raw_results, detected)

    result = ranked[0]

    # visual: 0.7 * 0.5 = 0.35
    # metadata: 1.0 * 0.3 = 0.30 (todos coinciden)
    # business: 1.0 * 0.2 = 0.20 (tiene stock)
    # final = 0.85
    assert abs(result.final_score - 0.85) < 0.01


def test_rank_results_empty_list(mock_config_balanced):
    """Test: Lista vacía retorna lista vacía"""
    optimizer = SearchOptimizer(mock_config_balanced)

    ranked = optimizer.rank_results([], {})

    assert ranked == []


def test_rank_results_sorts_correctly(mock_config_balanced):
    """Test: Resultados se ordenan correctamente por final_score"""
    optimizer = SearchOptimizer(mock_config_balanced)

    # Producto 1: Alta visual, sin metadata match
    product1 = Mock()
    product1.id = 'p1'
    product1.name = 'Producto 1'
    product1.color = 'NEGRO'
    product1.stock = 10
    product1.attributes = None

    # Producto 2: Baja visual, con metadata match
    product2 = Mock()
    product2.id = 'p2'
    product2.name = 'Producto 2'
    product2.color = 'BLANCO'
    product2.stock = 5
    product2.attributes = None

    raw_results = [
        {'product': product1, 'similarity': 0.9},  # Alta visual, no match
        {'product': product2, 'similarity': 0.6}   # Baja visual, match
    ]

    detected = {'color': 'BLANCO'}

    ranked = optimizer.rank_results(raw_results, detected)

    # Verificar orden descendente
    for i in range(len(ranked) - 1):
        assert ranked[i].final_score >= ranked[i+1].final_score


def test_rank_results_all_score_components_present(mock_config_balanced, mock_product_basic):
    """Test: SearchResult contiene todos los componentes de score"""
    optimizer = SearchOptimizer(mock_config_balanced)

    raw_results = [
        {'product': mock_product_basic, 'similarity': 0.8}
    ]

    ranked = optimizer.rank_results(raw_results, {})

    result = ranked[0]

    assert hasattr(result, 'visual_score')
    assert hasattr(result, 'metadata_score')
    assert hasattr(result, 'business_score')
    assert hasattr(result, 'final_score')
    assert hasattr(result, 'product_id')
    assert hasattr(result, 'product')
    assert hasattr(result, 'debug_info')


def test_rank_results_debug_info(mock_config_balanced, mock_product_basic):
    """Test: debug_info contiene contribuciones de cada capa"""
    optimizer = SearchOptimizer(mock_config_balanced)

    raw_results = [
        {'product': mock_product_basic, 'similarity': 0.8}
    ]

    ranked = optimizer.rank_results(raw_results, {})

    debug = ranked[0].debug_info

    assert 'visual_contribution' in debug
    assert 'metadata_contribution' in debug
    assert 'business_contribution' in debug
    assert 'weights' in debug
    assert debug['weights']['visual'] == 0.5


def test_search_result_to_dict(mock_product_basic):
    """Test: SearchResult.to_dict() serializa correctamente"""
    result = SearchResult(
        product_id='p1',
        product=mock_product_basic,
        visual_score=0.85,
        metadata_score=0.60,
        business_score=0.40,
        final_score=0.75,
        debug_info={'test': 'value'}
    )

    data = result.to_dict()

    assert data['product_id'] == 'p1'
    assert data['visual_score'] == 0.85
    assert data['metadata_score'] == 0.6
    assert data['business_score'] == 0.4
    assert data['final_score'] == 0.75
    assert data['debug_info']['test'] == 'value'


# ========================================
# TESTS DE EDGE CASES
# ========================================

def test_rank_results_with_score_instead_of_similarity(mock_config_balanced, mock_product_basic):
    """Test: Acepta 'score' como alternativa a 'similarity'"""
    optimizer = SearchOptimizer(mock_config_balanced)

    raw_results = [
        {'product': mock_product_basic, 'score': 0.75}  # Usa 'score' en lugar de 'similarity'
    ]

    ranked = optimizer.rank_results(raw_results, {})

    assert len(ranked) == 1
    assert ranked[0].visual_score == 0.75


def test_metadata_score_product_missing_attribute(mock_config_balanced):
    """Test: Atributo detectado pero producto no lo tiene"""
    optimizer = SearchOptimizer(mock_config_balanced)

    product = Mock()
    product.id = 'test'
    product.color = 'BLANCO'
    product.attributes = None

    detected = {
        'color': 'BLANCO',  # Match
        'brand': 'Nike'     # Producto no tiene 'brand'
    }

    score = optimizer.calculate_metadata_score(product, detected)

    # Solo cuenta color (1/1) = 1.0
    assert score == 1.0


def test_business_score_none_stock(mock_config_balanced):
    """Test: stock=None tratado como 0"""
    optimizer = SearchOptimizer(mock_config_balanced)

    product = Mock()
    product.id = 'test'
    product.stock = None

    score = optimizer.calculate_business_score(product)

    assert score == 0.0


def test_rank_results_product_none_skipped(mock_config_balanced, mock_product_basic):
    """Test: Resultados con product=None se omiten"""
    optimizer = SearchOptimizer(mock_config_balanced)

    raw_results = [
        {'product': mock_product_basic, 'similarity': 0.8},
        {'product': None, 'similarity': 0.9},  # Inválido
    ]

    ranked = optimizer.rank_results(raw_results, {})

    # Solo debe procesar el resultado válido
    assert len(ranked) == 1


# ========================================
# TESTS DE PERFORMANCE (opcional)
# ========================================

def test_rank_results_performance_100_products(mock_config_balanced):
    """Test: Performance con 100+ productos"""
    optimizer = SearchOptimizer(mock_config_balanced)

    # Crear 100 productos mock
    products = []
    for i in range(100):
        product = Mock()
        product.id = f'product-{i:03d}'
        product.name = f'Producto {i}'
        product.color = 'BLANCO' if i % 2 == 0 else 'NEGRO'
        product.stock = i % 10
        product.attributes = None
        products.append(product)

    raw_results = [
        {'product': p, 'similarity': 0.5 + (i * 0.005)}
        for i, p in enumerate(products)
    ]

    detected = {'color': 'BLANCO'}

    import time
    start = time.time()
    ranked = optimizer.rank_results(raw_results, detected)
    elapsed = time.time() - start

    assert len(ranked) == 100
    # Debe completar en menos de 1 segundo
    assert elapsed < 1.0
    print(f"✅ Performance: 100 productos rankeados en {elapsed:.3f}s")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
