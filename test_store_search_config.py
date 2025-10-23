"""
Tests básicos para el modelo StoreSearchConfig
Ejecutar con: python test_store_search_config.py
"""
import os
import sys

# Añadir path para importar modelos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

import psycopg2
from dotenv import load_dotenv

# Cargar variables de entorno
env_local_path = '.env.local'
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)

DATABASE_URL = os.getenv('DATABASE_URL')

def test_validation():
    """Test de validación de pesos"""
    print("\n" + "="*60)
    print("TEST 1: Validación de pesos")
    print("="*60)
    
    # Importar modelo
    from app.models.store_search_config import StoreSearchConfig
    
    # Test 1: Pesos válidos
    config = StoreSearchConfig(
        store_id='test-uuid-123',
        visual_weight=0.6,
        metadata_weight=0.3,
        business_weight=0.1
    )
    is_valid, error = config.validate_weights()
    assert is_valid, f"Debería ser válido pero falló: {error}"
    print("✓ Test 1.1: Pesos válidos (0.6, 0.3, 0.1) - PASSED")
    
    # Test 2: Suma incorrecta
    config2 = StoreSearchConfig(
        store_id='test-uuid-123',
        visual_weight=0.5,
        metadata_weight=0.3,
        business_weight=0.1
    )
    is_valid, error = config2.validate_weights()
    assert not is_valid, "Debería ser inválido (suma != 1.0)"
    assert "Sum of weights" in error, f"Mensaje de error incorrecto: {error}"
    print(f"✓ Test 1.2: Suma incorrecta (0.9) - PASSED (error: '{error}')")
    
    # Test 3: Peso fuera de rango
    config3 = StoreSearchConfig(
        store_id='test-uuid-123',
        visual_weight=1.5,
        metadata_weight=0.0,
        business_weight=-0.5
    )
    is_valid, error = config3.validate_weights()
    assert not is_valid, "Debería ser inválido (peso > 1.0)"
    print(f"✓ Test 1.3: Peso fuera de rango - PASSED (error: '{error}')")
    
    print("\n✅ Todos los tests de validación pasaron")


def test_presets():
    """Test de presets"""
    print("\n" + "="*60)
    print("TEST 2: Presets de configuración")
    print("="*60)
    
    from app.models.store_search_config import StoreSearchConfig
    
    # Test preset 'visual'
    config = StoreSearchConfig(store_id='test-uuid-123')
    config.apply_preset('visual')
    assert config.visual_weight == 0.8
    assert config.metadata_weight == 0.1
    assert config.business_weight == 0.1
    print("✓ Test 2.1: Preset 'visual' (0.8, 0.1, 0.1) - PASSED")
    
    # Test preset 'metadata'
    config.apply_preset('metadata')
    assert config.visual_weight == 0.3
    assert config.metadata_weight == 0.6
    assert config.business_weight == 0.1
    print("✓ Test 2.2: Preset 'metadata' (0.3, 0.6, 0.1) - PASSED")
    
    # Test preset 'balanced'
    config.apply_preset('balanced')
    assert config.visual_weight == 0.6
    assert config.metadata_weight == 0.3
    assert config.business_weight == 0.1
    print("✓ Test 2.3: Preset 'balanced' (0.6, 0.3, 0.1) - PASSED")
    
    # Test preset inválido
    try:
        config.apply_preset('invalid')
        assert False, "Debería haber lanzado ValueError"
    except ValueError as e:
        assert 'Unknown preset' in str(e)
        print(f"✓ Test 2.4: Preset inválido rechazado - PASSED")
    
    print("\n✅ Todos los tests de presets pasaron")


def test_database_operations():
    """Test de operaciones con la base de datos"""
    print("\n" + "="*60)
    print("TEST 3: Operaciones con base de datos")
    print("="*60)
    
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn, conn.cursor() as cur:
            # Test 1: Verificar que la tabla existe
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'store_search_config'
                );
            """)
            exists = cur.fetchone()[0]
            assert exists, "La tabla store_search_config no existe"
            print("✓ Test 3.1: Tabla store_search_config existe - PASSED")
            
            # Test 2: Verificar columnas
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'store_search_config'
                ORDER BY ordinal_position;
            """)
            columns = [row[0] for row in cur.fetchall()]
            expected_columns = [
                'store_id', 'visual_weight', 'metadata_weight', 
                'business_weight', 'metadata_config', 
                'created_at', 'updated_at'
            ]
            assert columns == expected_columns, f"Columnas incorrectas: {columns}"
            print(f"✓ Test 3.2: Todas las columnas presentes - PASSED")
            
            # Test 3: Verificar foreign key
            cur.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'store_search_config' 
                AND constraint_type = 'FOREIGN KEY';
            """)
            fk_exists = cur.fetchone() is not None
            assert fk_exists, "Foreign key no existe"
            print("✓ Test 3.3: Foreign key a clients configurada - PASSED")
            
            # Test 4: Verificar que hay al menos una configuración
            cur.execute("SELECT COUNT(*) FROM store_search_config")
            count = cur.fetchone()[0]
            assert count > 0, "No hay configuraciones en la tabla"
            print(f"✓ Test 3.4: Configuraciones existentes ({count}) - PASSED")
            
            # Test 5: Verificar datos de ejemplo
            cur.execute("""
                SELECT store_id, visual_weight, metadata_weight, business_weight
                FROM store_search_config
                LIMIT 1
            """)
            row = cur.fetchone()
            assert row is not None, "No se pudo leer configuración"
            store_id, visual, metadata, business = row
            
            # Verificar que los pesos suman aproximadamente 1.0
            total = visual + metadata + business
            assert abs(total - 1.0) < 0.01, f"Suma de pesos incorrecta: {total}"
            print(f"✓ Test 3.5: Datos válidos (suma={total:.2f}) - PASSED")
            
    finally:
        conn.close()
    
    print("\n✅ Todos los tests de base de datos pasaron")


def test_helper_methods():
    """Test de métodos helper"""
    print("\n" + "="*60)
    print("TEST 4: Métodos helper")
    print("="*60)
    
    from app.models.store_search_config import StoreSearchConfig
    
    # Test get_enabled_metadata_attributes
    config = StoreSearchConfig(
        store_id='test-uuid-123',
        metadata_config={
            'color': {'enabled': True, 'weight': 0.3},
            'brand': {'enabled': True, 'weight': 0.3},
            'pattern': {'enabled': False, 'weight': 0.2}
        }
    )
    
    enabled = config.get_enabled_metadata_attributes()
    assert 'color' in enabled, "color debería estar habilitado"
    assert 'brand' in enabled, "brand debería estar habilitado"
    assert 'pattern' not in enabled, "pattern no debería estar habilitado"
    print(f"✓ Test 4.1: get_enabled_metadata_attributes() - PASSED (enabled: {enabled})")
    
    # Test update_weights
    config = StoreSearchConfig(store_id='test-uuid-123')
    success, error = config.update_weights(visual=0.7, metadata=0.2)
    assert success, f"update_weights falló: {error}"
    assert config.visual_weight == 0.7
    assert config.metadata_weight == 0.2
    assert config.business_weight == 0.1  # No modificado
    print("✓ Test 4.2: update_weights() parcial - PASSED")
    
    # Test to_dict
    config = StoreSearchConfig(store_id='test-uuid-123')
    data = config.to_dict()
    assert 'store_id' in data
    assert 'visual_weight' in data
    assert 'metadata_config' in data
    print(f"✓ Test 4.3: to_dict() - PASSED (keys: {list(data.keys())})")
    
    print("\n✅ Todos los tests de métodos helper pasaron")


if __name__ == "__main__":
    print("╔" + "="*58 + "╗")
    print("║" + " " * 10 + "TESTS: StoreSearchConfig Model" + " " * 18 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        test_validation()
        test_presets()
        test_database_operations()
        test_helper_methods()
        
        print("\n" + "="*60)
        print("✅ TODOS LOS TESTS PASARON")
        print("="*60)
        print("\n📊 Resumen:")
        print("  - Validación de pesos: ✓")
        print("  - Presets de configuración: ✓")
        print("  - Operaciones de base de datos: ✓")
        print("  - Métodos helper: ✓")
        print("\n✨ Modelo StoreSearchConfig funcionando correctamente")
        
    except AssertionError as e:
        print(f"\n❌ TEST FALLÓ: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
