"""
Verificar el tipo de datos de clients.id
"""
import psycopg2
import os
from dotenv import load_dotenv

# Cargar variables de entorno
env_local_path = '.env.local'
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)

DATABASE_URL = os.getenv('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL)
try:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'clients' AND column_name = 'id';
        """)
        result = cur.fetchone()
        print(f"clients.id:")
        print(f"  column_name: {result[0]}")
        print(f"  data_type: {result[1]}")
        print(f"  udt_name: {result[2]}")
finally:
    conn.close()
