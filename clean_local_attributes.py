"""
Limpia el campo attributes de todos los productos en desarrollo local
"""
import os
from dotenv import load_dotenv
import psycopg2

# Cargar .env.local
script_dir = os.path.dirname(os.path.abspath(__file__))
env_local_path = os.path.join(script_dir, '.env.local')
load_dotenv(env_local_path)

LOCAL_DB_URL = os.getenv('DATABASE_URL')
if not LOCAL_DB_URL:
    raise SystemExit("❌ DATABASE_URL no definido en .env.local")

def clean_local_attributes():
    conn = psycopg2.connect(LOCAL_DB_URL)
    try:
        with conn, conn.cursor() as cur:
            # Ver cuántos productos tienen atributos
            cur.execute("SELECT COUNT(*) FROM products WHERE attributes IS NOT NULL")
            count = cur.fetchone()[0]
            print(f"📊 Productos con atributos JSONB en LOCAL: {count}")

            if count == 0:
                print("✓ Ya está limpio")
                return

            # Limpiar
            cur.execute("UPDATE products SET attributes = NULL WHERE attributes IS NOT NULL")
            conn.commit()

            print(f"✅ Campo attributes limpiado en {count} productos (LOCAL)")

    finally:
        conn.close()

if __name__ == "__main__":
    clean_local_attributes()
