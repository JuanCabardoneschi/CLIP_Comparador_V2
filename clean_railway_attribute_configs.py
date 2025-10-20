"""
Limpia todas las configuraciones de atributos en Railway
para que funcione igual que en desarrollo (sin configs)
"""
import psycopg2

RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def clean_configs():
    conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with conn, conn.cursor() as cur:
            # Ver cuántas hay antes
            cur.execute("SELECT COUNT(*) FROM product_attribute_config")
            count_before = cur.fetchone()[0]
            print(f"📊 Configuraciones actuales: {count_before}")

            if count_before == 0:
                print("✓ Ya está limpio, no hay configuraciones")
                return

            # Listar las que vamos a eliminar
            cur.execute("""
                SELECT pac.key, pac.label, c.slug
                FROM product_attribute_config pac
                JOIN clients c ON c.id = pac.client_id
            """)
            configs = cur.fetchall()

            print("\n🗑️  Eliminando configuraciones:")
            for cfg in configs:
                print(f"   - {cfg[0]} ({cfg[1]}) del cliente {cfg[2]}")

            # Eliminar todas
            cur.execute("DELETE FROM product_attribute_config")
            conn.commit()

            # Verificar
            cur.execute("SELECT COUNT(*) FROM product_attribute_config")
            count_after = cur.fetchone()[0]

            print(f"\n✅ Eliminadas {count_before} configuraciones")
            print(f"✓ Configuraciones restantes: {count_after}")
            print("\n🎯 Ahora Railway funcionará igual que desarrollo:")
            print("   - Sin configuraciones = expone TODOS los atributos del JSONB")
            print("   - Mostrará: brand, color, price, stock, tags, etc.")

    finally:
        conn.close()

if __name__ == "__main__":
    clean_configs()
