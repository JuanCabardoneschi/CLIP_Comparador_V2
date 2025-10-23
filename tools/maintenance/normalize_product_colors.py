"""
Normaliza valores de color en JSONB products.attributes->>'color'
- Unifica género: NEGRA→NEGRO, BLANCA→BLANCO, etc.
- Normaliza a UPPERCASE
- Ejecutar solo en producción para limpieza de datos existentes
"""
import psycopg2

RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

# Normalización de género y aliases
NORMALIZE_MAP = {
    'NEGRA': 'NEGRO',
    'BLANCA': 'BLANCO',
    'ROJA': 'ROJO',
    'AMARILLA': 'AMARILLO',
    'MORADA': 'MORADO',
    'DORADA': 'DORADO',
    'PLATEADA': 'PLATEADO',
    'BRONCEADA': 'BRONCEADO',
    'VERDE': 'VERDE',
    'AZUL': 'AZUL',
    'GRIS': 'GRIS',
    'ROSA': 'ROSA',
    'NARANJA': 'NARANJA',
    'VIOLETA': 'VIOLETA',
    'CELESTE': 'CELESTE',
    'BEIGE': 'BEIGE',
    'MARRON': 'MARRON',
    'MARRÓN': 'MARRON',
    'BORDO': 'BORDO',
    # Casos específicos encontrados
    'JEAN': 'AZUL',  # Tela común, normalizar a AZUL
    'RAYA': 'RAYADO',  # Patrón, no color (podría ir a otro atributo)
    'CARAMELO': 'CARAMELO',
    'HABANO': 'MARRON',  # Es un tono de marrón
}


def normalize_color(raw_value):
    """Normaliza un valor de color individual"""
    if not raw_value:
        return None

    # Uppercase y strip
    normalized = str(raw_value).strip().upper()

    # Aplicar mapeo
    return NORMALIZE_MAP.get(normalized, normalized)


def run():
    conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with conn:
            with conn.cursor() as cur:
                # Obtener productos con color
                cur.execute("""
                    SELECT id, name, attributes->>'color' AS color_raw
                    FROM products
                    WHERE attributes ? 'color'
                      AND NULLIF(TRIM(attributes->>'color'), '') IS NOT NULL
                    ORDER BY name
                """)

                products = cur.fetchall()
                print(f"🔍 Productos con color: {len(products)}\n")

                updated = 0
                unchanged = 0

                for product_id, name, color_raw in products:
                    color_normalized = normalize_color(color_raw)

                    if color_normalized != color_raw:
                        cur.execute("""
                            UPDATE products
                            SET attributes = jsonb_set(
                                attributes,
                                '{color}',
                                to_jsonb(%s::text)
                            )
                            WHERE id = %s
                        """, (color_normalized, product_id))

                        print(f"✅ {name[:40]:40s} | '{color_raw}' → '{color_normalized}'")
                        updated += 1
                    else:
                        unchanged += 1

                print(f"\n{'='*70}")
                print(f"📊 RESUMEN")
                print(f"{'='*70}")
                print(f"Total procesados: {len(products)}")
                print(f"✅ Actualizados: {updated}")
                print(f"⏭️  Sin cambios: {unchanged}")
                print(f"{'='*70}")

                if updated > 0:
                    print("\n✅ Cambios aplicados y commiteados")
                else:
                    print("\n⏭️  No se requirieron cambios")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run()
