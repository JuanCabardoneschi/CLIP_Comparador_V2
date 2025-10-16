import sqlite3

# Conectar a SQLite
conn = sqlite3.connect('clip_admin_backend/instance/clip_comparador_v2.db')
cursor = conn.cursor()

print("ESTRUCTURA REAL DE SQLITE:")
print("=" * 40)

tables = ['clients', 'users', 'categories', 'products', 'images']

for table in tables:
    try:
        cursor.execute(f'PRAGMA table_info({table})')
        cols = cursor.fetchall()
        print(f"\nTabla {table}:")
        for col in cols:
            null_constraint = "NOT NULL" if col[3] else "NULL"
            print(f"  {col[1]}: {col[2]} {null_constraint}")
    except Exception as e:
        print(f"  Error: {e}")

conn.close()
