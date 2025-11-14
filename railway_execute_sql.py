"""
Ejecutar archivo SQL en Railway PostgreSQL
Uso: python railway_execute_sql.py migrations/railway_schema_update_13nov2025.sql
"""
import sys
import psycopg2

RAILWAY_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'btjTLhgRVQGljdqRBJoJpHjQikqbxcTp'
}

def execute_sql_file(filepath):
    """Ejecutar archivo SQL en Railway"""
    print(f"📁 Leyendo archivo: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    print(f"📄 Contenido: {len(sql_content)} caracteres")
    print("🔌 Conectando a Railway...")

    conn = psycopg2.connect(**RAILWAY_CONFIG)
    conn.autocommit = False  # Usar transacción manual
    cur = conn.cursor()

    try:
        print("⚙️ Ejecutando SQL...")
        cur.execute(sql_content)
        conn.commit()
        print("✅ Migración completada exitosamente")

        # Mostrar notices (RAISE NOTICE)
        for notice in conn.notices:
            print(f"  ℹ️ {notice.strip()}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error durante migración: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Uso: python railway_execute_sql.py <archivo.sql>")
        sys.exit(1)

    execute_sql_file(sys.argv[1])
