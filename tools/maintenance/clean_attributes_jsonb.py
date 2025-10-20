"""
Limpia el campo attributes de todos los productos en Railway
para eliminar la migración legacy y empezar limpio
"""
import psycopg2

RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def clean_attributes_jsonb():
    conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with conn, conn.cursor() as cur:
            # Ver cuántos productos tienen atributos
            cur.execute("SELECT COUNT(*) FROM products WHERE attributes IS NOT NULL")
            count = cur.fetchone()[0]
            print(f"📊 Productos con atributos JSONB: {count}")

            if count == 0:
                print("✓ Ya está limpio")
                return

            # Mostrar ejemplo de lo que se va a limpiar
            cur.execute("""
                SELECT name, attributes
                FROM products
                WHERE attributes IS NOT NULL
                LIMIT 3
            """)
            examples = cur.fetchall()

            print("\n📦 Ejemplos de atributos que se limpiarán:")
            for name, attrs in examples:
                print(f"   {name}: {list(attrs.keys()) if attrs else 'N/A'}")

            print(f"\n⚠️  ¿Limpiar el campo attributes de {count} productos?")
            print("   Esto NO borra los productos, solo vacía el JSONB attributes")
            print("   Los campos normales (price, stock, brand, etc.) se mantienen")

            # Limpiar
            cur.execute("UPDATE products SET attributes = NULL WHERE attributes IS NOT NULL")
            conn.commit()

            print(f"\n✅ Campo attributes limpiado en {count} productos")
            print("✓ Ahora podés usar attributes solo para campos dinámicos personalizados")

    finally:
        conn.close()

if __name__ == "__main__":
    clean_attributes_jsonb()
