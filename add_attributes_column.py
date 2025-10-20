"""
Script para agregar columna attributes (JSONB) a tabla products en Railway PostgreSQL
"""
import psycopg2

# Credenciales Railway PostgreSQL (mismas que add_sensitivity_columns.py)
DB_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def add_attributes_column():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    try:
        print("🚀 Agregando columna attributes a products si no existe...")
        cursor.execute(
            """
            ALTER TABLE products
            ADD COLUMN IF NOT EXISTS attributes JSONB;
            """
        )
        conn.commit()
        print("✅ Columna attributes verificada/creada correctamente")

        # Confirmar existencia de la columna
        cursor.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'products' AND column_name = 'attributes';
            """
        )
        row = cursor.fetchone()
        if row:
            print(f"📋 Columna encontrada: {row[0]} ({row[1]})")
        else:
            print("⚠️ No se encontró la columna 'attributes' tras intentar crearla")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error agregando columna attributes: {e}")
        import traceback; traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
        print("🔌 Conexión cerrada")

if __name__ == "__main__":
    add_attributes_column()
