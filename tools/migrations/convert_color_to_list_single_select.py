"""
Convierte el atributo 'color' a tipo 'list' (single select) por cliente y
puebla las opciones con:
- Todos los colores usados en products.attributes->>'color' (uppercased)
- + Colores básicos de indumentaria

Uso:
  python tools/migrations/convert_color_to_list_single_select.py
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

BASIC_COLORS = [
    'NEGRO','BLANCO','GRIS','AZUL','ROJO','VERDE','AMARILLO','MARRON','BEIGE',
    'CELESTE','ROSA','NARANJA','VIOLETA','BORDO','DORADO','PLATEADO'
]

UPSERT_SQL = """
INSERT INTO product_attribute_config
  (client_id, key, label, type, required, options, field_order, expose_in_search)
VALUES
  (%s, 'color', 'Color', 'list', false, %s::jsonb, 11, false)
ON CONFLICT (client_id, key)
DO UPDATE SET
  label = EXCLUDED.label,
  type = 'list',
  options = EXCLUDED.options,
  field_order = EXCLUDED.field_order,
  expose_in_search = EXCLUDED.expose_in_search
"""

FETCH_CLIENTS_SQL = """
SELECT id, name FROM clients ORDER BY name
"""

FETCH_COLORS_SQL = """
SELECT DISTINCT UPPER(TRIM(p.attributes->>'color')) AS color
FROM products p
WHERE p.client_id = %s
  AND p.attributes ? 'color'
  AND NULLIF(TRIM(p.attributes->>'color'), '') IS NOT NULL
ORDER BY color
"""


def run():
    conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(FETCH_CLIENTS_SQL)
            clients = cur.fetchall()
            print(f"🧾 Clientes: {len(clients)}")

            for c in clients:
                client_id = c['id']
                client_name = c['name']

                # Obtener colores usados por el cliente
                cur.execute(FETCH_COLORS_SQL, (client_id,))
                rows = cur.fetchall()
                used_colors = [r['color'] for r in rows if r['color']]

                # Mezclar con básicos
                all_colors = list(dict.fromkeys(used_colors + BASIC_COLORS))  # único y preserva orden

                # Construir JSON array
                import json
                options_json = json.dumps(all_colors, ensure_ascii=False)

                cur.execute(UPSERT_SQL, (client_id, options_json))
                print(f"✅ {client_name}: {len(all_colors)} opciones de color actualizadas")

        print("\n✅ Conversión completada")
    finally:
        conn.close()


if __name__ == '__main__':
    run()
