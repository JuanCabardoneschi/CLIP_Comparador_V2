"""
Script de diagnóstico para verificar configuración de atributos en Railway
"""
import psycopg2
import psycopg2.extras

RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def diagnose():
    conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            print("🔍 DIAGNÓSTICO DE ATRIBUTOS EN RAILWAY\n")
            print("=" * 60)

            # 1. Verificar tabla existe
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'product_attribute_config'
                );
            """)
            exists = cur.fetchone()['exists']
            print(f"✓ Tabla product_attribute_config existe: {exists}")

            if not exists:
                print("❌ La tabla no existe en Railway!")
                return

            # 2. Contar total de configuraciones
            cur.execute("SELECT COUNT(*) as total FROM product_attribute_config")
            total = cur.fetchone()['total']
            print(f"✓ Total de configuraciones: {total}")

            # 3. Listar todas las configuraciones con cliente
            print("\n📋 CONFIGURACIONES POR CLIENTE:")
            print("-" * 60)
            cur.execute("""
                SELECT c.slug as client_slug,
                       pac.key, pac.label, pac.type,
                       pac.expose_in_search, pac.field_order
                FROM product_attribute_config pac
                JOIN clients c ON c.id = pac.client_id
                ORDER BY c.slug, pac.field_order, pac.key
            """)
            configs = cur.fetchall()

            current_client = None
            for cfg in configs:
                if cfg['client_slug'] != current_client:
                    current_client = cfg['client_slug']
                    print(f"\n🏢 Cliente: {current_client}")

                expose_icon = "✅" if cfg['expose_in_search'] else "❌"
                print(f"  {expose_icon} {cfg['key']:20s} | {cfg['label']:25s} | {cfg['type']:10s}")

            # 4. Verificar cuántos están expuestos por cliente
            print("\n📊 RESUMEN DE EXPOSICIÓN:")
            print("-" * 60)
            cur.execute("""
                SELECT c.slug, c.id,
                       COUNT(*) as total,
                       SUM(CASE WHEN expose_in_search THEN 1 ELSE 0 END) as expuestos
                FROM product_attribute_config pac
                JOIN clients c ON c.id = pac.client_id
                GROUP BY c.slug, c.id
            """)
            summary = cur.fetchall()

            for row in summary:
                print(f"Cliente {row['slug']}:")
                print(f"  - Total atributos: {row['total']}")
                print(f"  - Expuestos: {row['expuestos']}")
                print(f"  - Ocultos: {row['total'] - row['expuestos']}")
                print(f"  - Client ID: {row['id']}")

                # 5. Verificar productos con atributos para este cliente
                cur.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN attributes IS NOT NULL THEN 1 ELSE 0 END) as con_attrs
                    FROM products
                    WHERE client_id = %s
                """, (row['id'],))
                prod_stats = cur.fetchone()
                print(f"  - Productos totales: {prod_stats['total']}")
                print(f"  - Con atributos JSONB: {prod_stats['con_attrs']}")

                # Ejemplo de producto con atributos
                if prod_stats['con_attrs'] > 0:
                    cur.execute("""
                        SELECT name, attributes
                        FROM products
                        WHERE client_id = %s AND attributes IS NOT NULL
                        LIMIT 1
                    """, (row['id'],))
                    example = cur.fetchone()
                    if example:
                        print(f"\n  📦 Ejemplo producto: {example['name']}")
                        if example['attributes']:
                            print(f"     Atributos en JSONB: {list(example['attributes'].keys())}")

            print("\n" + "=" * 60)
            print("✅ Diagnóstico completado")

    finally:
        conn.close()

if __name__ == "__main__":
    diagnose()
