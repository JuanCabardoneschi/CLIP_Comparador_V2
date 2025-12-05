#!/usr/bin/env python3
"""Verificar valores del atributo color en Railway."""

import psycopg2
import json

# Conectar a Railway
conn = psycopg2.connect(
    'postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway'
)
cur = conn.cursor()

# Query
cur.execute("""
    SELECT options
    FROM product_attribute_config
    WHERE client_id = '747ff760-8eae-46e8-94ca-8ad076370316'
    AND key = 'color'
""")

result = cur.fetchone()
if result:
    options = result[0]
    values = options.get('values', [])
    print(f"📋 Total de colores: {len(values)}")
    print(f"\n🎨 Lista de colores:")
    for i, color in enumerate(values, 1):
        print(f"  {i}. {color}")

    # Verificar si Verde está
    if 'Verde' in values:
        print(f"\n✅ 'Verde' SÍ está en la lista (posición {values.index('Verde') + 1})")
    else:
        print(f"\n❌ 'Verde' NO está en la lista")
else:
    print("❌ No se encontró configuración de color")

conn.close()
