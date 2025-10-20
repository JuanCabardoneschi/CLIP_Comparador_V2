"""
Agrega configuraciones de atributos para los campos migrados automáticamente
que SÍ existen en el JSONB de productos
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

# Atributos que realmente existen en el JSONB de productos
REAL_ATTRIBUTES = [
    {
        'key': 'brand',
        'label': 'Marca',
        'type': 'text',
        'expose_in_search': False,  # Cambiar a True si querés exponerlo
        'field_order': 10
    },
    {
        'key': 'color',
        'label': 'Color',
        'type': 'text',
        'expose_in_search': False,
        'field_order': 11
    },
    {
        'key': 'price',
        'label': 'Precio',
        'type': 'number',
        'expose_in_search': False,
        'field_order': 12
    },
    {
        'key': 'stock',
        'label': 'Stock',
        'type': 'number',
        'expose_in_search': False,
        'field_order': 13
    },
    {
        'key': 'tags',
        'label': 'Etiquetas',
        'type': 'text',
        'expose_in_search': False,
        'field_order': 14
    }
]

def add_real_attributes():
    conn = psycopg2.connect(**RAILWAY_DB)
    try:
        with conn, conn.cursor() as cur:
            # Obtener client_id del demo
            cur.execute("SELECT id FROM clients WHERE slug = 'demo_fashion_store' LIMIT 1")
            row = cur.fetchone()
            if not row:
                print("❌ Cliente demo_fashion_store no encontrado")
                return

            client_id = row[0]
            print(f"✓ Cliente ID: {client_id}")
            print("\n🚀 Agregando configuraciones de atributos reales...\n")

            for attr in REAL_ATTRIBUTES:
                cur.execute(
                    """
                    INSERT INTO product_attribute_config
                        (client_id, key, label, type, required, options, field_order, expose_in_search)
                    VALUES
                        (%s, %s, %s, %s, false, NULL, %s, %s)
                    ON CONFLICT (client_id, key)
                    DO UPDATE SET
                        label = EXCLUDED.label,
                        type = EXCLUDED.type,
                        field_order = EXCLUDED.field_order,
                        expose_in_search = EXCLUDED.expose_in_search
                    """,
                    (client_id, attr['key'], attr['label'], attr['type'],
                     attr['field_order'], attr['expose_in_search'])
                )
                expose_icon = "✅" if attr['expose_in_search'] else "❌"
                print(f"{expose_icon} {attr['key']:15s} -> {attr['label']}")

            print("\n✅ Configuraciones agregadas/actualizadas correctamente")
            print("\nℹ️  Todos están marcados como OCULTOS por defecto")
            print("   Podés cambiarlos a visibles desde el admin: /attributes")

    finally:
        conn.close()

if __name__ == "__main__":
    add_real_attributes()
