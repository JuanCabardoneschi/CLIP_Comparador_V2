import psycopg2
from dotenv import load_dotenv
import os

load_dotenv('.env.local')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute("UPDATE products SET attributes = '{}'::jsonb WHERE name LIKE '%GORRA%CUP%NEGRA%'")
conn.commit()

print(f'Limpiado: {cur.rowcount} productos')

cur.close()
conn.close()
