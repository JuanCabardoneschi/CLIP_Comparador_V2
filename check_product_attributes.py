"""
Script para verificar atributos de productos
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('.env.local')
DATABASE_URL = os.getenv('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

print("\n📋 CONSULTANDO ATRIBUTOS DE PRODUCTOS DELANTAL\n")

cursor.execute("""
    SELECT name, attributes, tags
    FROM products
    WHERE name LIKE '%DELANTAL%HABANO%'
       OR name LIKE '%Caramelo%'
       OR name LIKE '%Amarillo%'
       OR name LIKE '%NEGRO%TOSTADO%'
    LIMIT 10
""")

for row in cursor.fetchall():
    name, attributes, tags = row
    print(f"Producto: {name}")
    print(f"  Atributos: {attributes}")
    print(f"  Tags: {tags}")
    print()

cursor.close()
conn.close()
