"""
Sincronizar atributos de productos de local a Railway
"""
import psycopg2
import json
from psycopg2.extras import Json
from urllib.parse import urlparse, unquote

# Local
local_conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='clip_comparador_v2',
    user='postgres',
    password='Laurana@01'
)

# Railway
railway_conn = psycopg2.connect(
    host='ballast.proxy.rlwy.net',
    port=54363,
    database='railway',
    user='postgres',
    password='xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
)

print("📥 Leyendo atributos de local...")
cur_local = local_conn.cursor()
cur_local.execute("""
    SELECT client_id, key, label, type, required, options, field_order, expose_in_search
    FROM product_attribute_config
    ORDER BY field_order
""")
attributes = cur_local.fetchall()
local_conn.close()

print(f"✅ Encontrados {len(attributes)} atributos en local")

if attributes:
    print("\n📤 Copiando a Railway...")
    cur_railway = railway_conn.cursor()

    # Limpiar tabla en Railway
    cur_railway.execute("DELETE FROM product_attribute_config")
    print(f"🗑️  Limpiada tabla en Railway")

    # Insertar atributos
    for attr in attributes:
        # Convertir dict a Json para psycopg2
        client_id, key, label, type_, required, options, field_order, expose_in_search = attr
        cur_railway.execute("""
            INSERT INTO product_attribute_config
            (client_id, key, label, type, required, options, field_order, expose_in_search)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (client_id, key, label, type_, required, Json(options) if options else None, field_order, expose_in_search))
        print(f"   ✓ {label} ({key})")

    railway_conn.commit()
    railway_conn.close()

    print(f"\n✅ {len(attributes)} atributos copiados exitosamente a Railway")
else:
    print("❌ No hay atributos en local para copiar")
