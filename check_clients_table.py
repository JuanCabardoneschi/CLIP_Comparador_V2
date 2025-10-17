"""
Script para verificar estructura de tabla clients en Railway PostgreSQL
"""
import psycopg2
from psycopg2 import sql

# Credenciales Railway PostgreSQL
DB_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def connect_to_railway():
    """Conectar a Railway PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Conectado a Railway PostgreSQL")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a Railway: {e}")
        return None

def get_table_structure(conn, table_name):
    """Obtener estructura de una tabla"""
    cursor = conn.cursor()

    query = """
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """

    cursor.execute(query, (table_name,))
    columns = cursor.fetchall()

    print(f"\n📊 Estructura de tabla '{table_name}':")
    print("-" * 100)
    print(f"{'COLUMNA':<30} {'TIPO':<20} {'NULL':<10} {'DEFAULT':<20}")
    print("-" * 100)

    for col in columns:
        col_name = col[0]
        data_type = col[1]
        max_length = f"({col[2]})" if col[2] else ""
        nullable = "YES" if col[3] == 'YES' else "NO"
        default = str(col[4])[:20] if col[4] else "-"

        print(f"{col_name:<30} {data_type}{max_length:<20} {nullable:<10} {default:<20}")

    cursor.close()
    return columns

def get_sample_data(conn, table_name, limit=3):
    """Obtener datos de ejemplo"""
    cursor = conn.cursor()

    query = sql.SQL("SELECT * FROM {} LIMIT %s").format(sql.Identifier(table_name))
    cursor.execute(query, (limit,))

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    print(f"\n📋 Datos de ejemplo (primeros {limit} registros):")
    print("-" * 100)

    for row in rows:
        print("\nRegistro:")
        for col, val in zip(columns, row):
            print(f"  {col}: {val}")

    cursor.close()

def main():
    print("🚀 Conectando a Railway PostgreSQL...")
    print("=" * 100)

    conn = connect_to_railway()

    if conn:
        try:
            # Ver estructura de tabla clients
            columns = get_table_structure(conn, 'clients')

            # Ver datos de ejemplo
            get_sample_data(conn, 'clients', limit=2)

            print("\n" + "=" * 100)
            print("✅ Análisis completado")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()
            print("\n🔌 Conexión cerrada")
    else:
        print("❌ No se pudo conectar a la base de datos")
        print("\n💡 Por favor proporciona la URL externa de Railway PostgreSQL")

if __name__ == "__main__":
    main()
