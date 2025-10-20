"""
Script para agregar columnas de sensibilidad a tabla clients en Railway PostgreSQL
"""
import psycopg2

# Credenciales Railway PostgreSQL
DB_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def add_sensitivity_columns():
    """Agregar columnas de sensibilidad a la tabla clients"""

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        print("🚀 Agregando columnas de sensibilidad...")
        print("=" * 80)

        # 1. Agregar columna category_confidence_threshold
        print("\n1️⃣ Agregando 'category_confidence_threshold'...")
        cursor.execute("""
            ALTER TABLE clients
            ADD COLUMN IF NOT EXISTS category_confidence_threshold INTEGER
            DEFAULT 70
            CHECK (category_confidence_threshold >= 1 AND category_confidence_threshold <= 100);
        """)
        print("   ✅ Columna agregada con valor default 70 (70%)")

        # 2. Agregar columna product_similarity_threshold
        print("\n2️⃣ Agregando 'product_similarity_threshold'...")
        cursor.execute("""
            ALTER TABLE clients
            ADD COLUMN IF NOT EXISTS product_similarity_threshold INTEGER
            DEFAULT 30
            CHECK (product_similarity_threshold >= 1 AND product_similarity_threshold <= 100);
        """)
        print("   ✅ Columna agregada con valor default 30 (30%)")

        # 3. Commit cambios
        conn.commit()
        print("\n✅ Cambios guardados en la base de datos")

        # 4. Verificar columnas agregadas
        print("\n📊 Verificando columnas agregadas...")
        cursor.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'clients'
            AND column_name IN ('category_confidence_threshold', 'product_similarity_threshold')
            ORDER BY column_name;
        """)

        columns = cursor.fetchall()
        print("-" * 80)
        for col in columns:
            print(f"  ✓ {col[0]}: {col[1]} (default: {col[2]})")

        # 5. Ver datos del cliente demo
        print("\n📋 Datos del cliente Demo Fashion Store:")
        print("-" * 80)
        cursor.execute("""
            SELECT
                name,
                category_confidence_threshold,
                product_similarity_threshold
            FROM clients
            WHERE slug = 'demo_fashion_store';
        """)

        client = cursor.fetchone()
        if client:
            print(f"  Cliente: {client[0]}")
            print(f"  Confianza Categoría: {client[1]}%")
            print(f"  Similitud Productos: {client[2]}%")

        print("\n" + "=" * 80)
        print("✅ Migración completada exitosamente!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
        print("\n🔌 Conexión cerrada")

if __name__ == "__main__":
    add_sensitivity_columns()
