"""
Test Suite - Verificar funcionalidad post-migración Railway

Ejecuta pruebas críticas para verificar que el sistema sigue funcionando
después de aplicar migración FASE 1 en Railway.
"""
import os
import sys
import requests
import psycopg2
from datetime import datetime


# URLs de Railway
RAILWAY_BASE_URL = "https://clip-comparador-v2-production.up.railway.app"
API_ENDPOINT = f"{RAILWAY_BASE_URL}/api/search"


def get_railway_conn():
    """Conectar a Railway PostgreSQL"""
    host = os.getenv('RAILWAY_DB_HOST', 'ballast.proxy.rlwy.net')
    port = int(os.getenv('RAILWAY_DB_PORT', '54363'))
    database = os.getenv('RAILWAY_DB', 'railway')
    user = os.getenv('RAILWAY_DB_USER', 'postgres')
    password = os.getenv('RAILWAY_DB_PASSWORD', 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum')

    return psycopg2.connect(
        host=host, port=port, database=database,
        user=user, password=password, connect_timeout=10
    )


def test_health_check():
    """Test 1: Health Check - Homepage carga sin error 500"""
    print("\n🧪 TEST 1: Health Check")
    print("-" * 60)

    try:
        response = requests.get(RAILWAY_BASE_URL, timeout=10)

        if response.status_code == 200:
            print(f"   ✅ Status: {response.status_code} OK")
            print(f"   ✅ Response time: {response.elapsed.total_seconds():.2f}s")
            return True
        else:
            print(f"   ❌ Status: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def test_database_table():
    """Test 2: Verificar tabla store_search_config en Railway"""
    print("\n🧪 TEST 2: Database - Tabla store_search_config")
    print("-" * 60)

    try:
        with get_railway_conn() as conn:
            with conn.cursor() as cur:
                # Verificar que tabla existe
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'store_search_config'
                    );
                """)
                exists = cur.fetchone()[0]

                if not exists:
                    print("   ❌ Tabla NO existe")
                    return False

                print("   ✅ Tabla existe")

                # Contar registros
                cur.execute("SELECT COUNT(*) FROM store_search_config;")
                count = cur.fetchone()[0]
                print(f"   ✅ Registros: {count}")

                # Verificar estructura (columnas)
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'store_search_config'
                    ORDER BY ordinal_position;
                """)
                columns = cur.fetchall()
                print(f"   ✅ Columnas: {len(columns)}")
                for col_name, col_type in columns:
                    print(f"      - {col_name}: {col_type}")

                # Verificar foreign key
                cur.execute("""
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name = 'store_search_config'
                    AND constraint_type = 'FOREIGN KEY';
                """)
                fk = cur.fetchone()
                if fk:
                    print(f"   ✅ Foreign key: {fk[0]}")
                else:
                    print("   ⚠️ No foreign key constraint found")

                return True

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def test_model_import():
    """Test 3: Verificar que modelo StoreSearchConfig se importa sin errores"""
    print("\n🧪 TEST 3: Model Import - StoreSearchConfig")
    print("-" * 60)

    try:
        # Cambiar al directorio del backend para imports
        backend_dir = os.path.join(os.path.dirname(__file__), 'clip_admin_backend')
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        # Intentar importar el modelo
        from app.models import StoreSearchConfig

        print("   ✅ Import exitoso: StoreSearchConfig")
        print(f"   ✅ Tabla: {StoreSearchConfig.__tablename__}")
        print(f"   ✅ Columnas: {len(StoreSearchConfig.__table__.columns)}")

        # Verificar atributos clave
        attrs = ['store_id', 'visual_weight', 'metadata_weight', 'business_weight', 'metadata_config']
        for attr in attrs:
            if hasattr(StoreSearchConfig, attr):
                print(f"   ✅ Atributo: {attr}")
            else:
                print(f"   ❌ Atributo faltante: {attr}")
                return False

        return True

    except Exception as e:
        print(f"   ❌ ERROR al importar: {e}")
        return False


def test_api_key_validation():
    """Test 4: API Key validation (debe rechazar keys inválidas)"""
    print("\n🧪 TEST 4: API Security - Key Validation")
    print("-" * 60)

    try:
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": "INVALID_KEY_12345"
        }

        payload = {
            "category": "test",
            "image_url": "https://example.com/test.jpg"
        }

        response = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=10)

        if response.status_code == 401:
            print(f"   ✅ Status: {response.status_code} Unauthorized (correcto)")
            print("   ✅ API Key validation funciona")
            return True
        else:
            print(f"   ⚠️ Status inesperado: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def test_client_configs():
    """Test 5: Verificar que cada cliente tiene su configuración"""
    print("\n🧪 TEST 5: Client Configurations")
    print("-" * 60)

    try:
        with get_railway_conn() as conn:
            with conn.cursor() as cur:
                # Verificar que cada cliente tiene config
                cur.execute("""
                    SELECT
                        c.name,
                        CASE WHEN ssc.store_id IS NOT NULL THEN 'YES' ELSE 'NO' END as has_config,
                        ssc.visual_weight,
                        ssc.metadata_weight,
                        ssc.business_weight
                    FROM clients c
                    LEFT JOIN store_search_config ssc ON c.id = ssc.store_id
                    ORDER BY c.name;
                """)

                rows = cur.fetchall()

                all_ok = True
                for name, has_config, visual, metadata, business in rows:
                    if has_config == 'YES':
                        print(f"   ✅ {name}: v={visual}, m={metadata}, b={business}")
                    else:
                        print(f"   ❌ {name}: NO CONFIG")
                        all_ok = False

                return all_ok

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def main():
    print("=" * 60)
    print("🚀 RAILWAY POST-MIGRATION TEST SUITE")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {RAILWAY_BASE_URL}")
    print("=" * 60)

    results = {
        "Health Check": test_health_check(),
        "Database Table": test_database_table(),
        "Model Import": test_model_import(),
        "API Security": test_api_key_validation(),
        "Client Configs": test_client_configs(),
    }

    print("\n" + "=" * 60)
    print("📊 RESULTADOS FINALES")
    print("=" * 60)

    passed = 0
    failed = 0

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print("=" * 60)
    print(f"Total: {passed}/{len(results)} pruebas pasadas")

    if failed == 0:
        print("\n🎉 ¡TODO OK! Sistema funcionando correctamente")
        print("✅ Listo para continuar con FASE 2")
        return 0
    else:
        print(f"\n⚠️ {failed} prueba(s) fallaron")
        print("🔍 Revisar logs de Railway para más detalles")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
