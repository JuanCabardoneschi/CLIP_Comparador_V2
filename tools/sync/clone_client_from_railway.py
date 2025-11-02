"""
Clona un cliente específico desde Railway a la base de datos local.

Copias incluidas (filtradas por client_id):
- clients (1 fila)
- store_search_config (1 fila con store_id = client_id)
- categories
- products
- images
- product_attribute_config

Modo de uso (PowerShell):
  python tools/sync/clone_client_from_railway.py --slug eve-store --replace
  python tools/sync/clone_client_from_railway.py --name "Eve Store" --replace

Notas:
- Lee DATABASE_URL de .env.local en la raíz del repo (fallback: tools/sync/.env.local)
- Reemplaza en LOCAL todo lo del cliente indicado (DELETE dependientes + INSERT)
- Mantiene los mismos IDs/UUIDs para preservar relaciones y reproducibilidad
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import argparse

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv


# ------------------------------
# Config: .env.local (LOCAL DB)
# ------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent  # .../CLIP_Comparador_V2

ENV_LOCAL_ROOT = REPO_ROOT / ".env.local"
ENV_LOCAL_SYNC = SCRIPT_DIR / ".env.local"  # fallback (coincide con otros scripts)

if ENV_LOCAL_ROOT.exists():
    load_dotenv(ENV_LOCAL_ROOT)
elif ENV_LOCAL_SYNC.exists():
    load_dotenv(ENV_LOCAL_SYNC)
else:
    print("❌ No se encontró .env.local en raíz ni en tools/sync/. Crea uno desde .env.local.example")
    sys.exit(1)

LOCAL_DB_URL = os.getenv("DATABASE_URL")
if not LOCAL_DB_URL:
    print("❌ DATABASE_URL no definido en .env.local")
    sys.exit(1)


# ------------------------------
# Config: Railway (PROD DB)
# ------------------------------
RAILWAY_DB = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}


# ------------------------------
# Helpers SQL
# ------------------------------
TABLES_BY_CLIENT = {
    # tabla : (col_id_cliente, filtro_por_store_id?)
    'store_search_config': ('store_id', True),
    'categories': ('client_id', False),
    'products': ('client_id', False),
    'images': ('client_id', False),
    'product_attribute_config': ('client_id', False),
}


def fetchone_dict(cur) -> Optional[Dict]:
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    cols = [desc[0] for desc in cur.description]
    return {k: v for k, v in zip(cols, row)}


def fetchall_dicts(cur) -> List[Dict]:
    rows = cur.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    cols = [desc[0] for desc in cur.description]
    return [{k: v for k, v in zip(cols, r)} for r in rows]


def get_client_by_slug_or_name(conn, slug: Optional[str], name: Optional[str]) -> Optional[Dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if slug:
            cur.execute("SELECT * FROM clients WHERE slug = %s LIMIT 1", (slug,))
            return fetchone_dict(cur)
        if name:
            cur.execute("SELECT * FROM clients WHERE LOWER(name) = LOWER(%s) LIMIT 1", (name,))
            row = fetchone_dict(cur)
            if row:
                return row
            # búsqueda laxa por contains
            cur.execute("SELECT * FROM clients WHERE LOWER(name) LIKE LOWER(%s) ORDER BY created_at DESC LIMIT 1", (f"%{name}%",))
            return fetchone_dict(cur)
    return None


def fetch_table_rows_for_client(conn, table: str, client_id: str, use_store_id: bool = False) -> Tuple[List[Dict], List[str]]:
    """Devuelve (rows, columns) para una tabla filtrando por client_id/store_id"""
    with conn.cursor() as cur:
        id_col = 'store_id' if use_store_id else 'client_id'
        cur.execute(f"SELECT * FROM {table} WHERE {id_col} = %s", (client_id,))
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        result = []
        for r in rows:
            # convertir a dict conservando columnas
            result.append({c: v for c, v in zip(cols, r)})
        return result, cols


def delete_local_client_tree(conn, client_id: str, client_slug: Optional[str] = None):
    """Borra datos del cliente en LOCAL en orden seguro."""
    with conn.cursor() as cur:
        # Intentar resolver por slug a id en LOCAL, si el id no existiera
        if client_slug:
            cur.execute("SELECT id FROM clients WHERE slug = %s", (client_slug,))
            row = cur.fetchone()
            local_id = row[0] if row else client_id
        else:
            local_id = client_id

        # Dependientes primero
        cur.execute("DELETE FROM images WHERE client_id = %s", (local_id,))
        cur.execute("DELETE FROM products WHERE client_id = %s", (local_id,))
        cur.execute("DELETE FROM categories WHERE client_id = %s", (local_id,))
        cur.execute("DELETE FROM product_attribute_config WHERE client_id = %s", (local_id,))
        cur.execute("DELETE FROM store_search_config WHERE store_id = %s", (local_id,))
        # Finalmente el cliente (si coincide por id)
        cur.execute("DELETE FROM clients WHERE id = %s", (local_id,))


def insert_row(conn, table: str, row: Dict, columns: List[str]):
    """Inserta una fila exacta en LOCAL respetando columnas y valores."""
    # Algunas columnas pueden no existir en LOCAL o tener defaults incompatibles; filtrar por columnas reales
    with conn.cursor() as cur:
        # Detectar columnas reales en LOCAL para la tabla
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """,
            (table,)
        )
        local_cols = [r[0] for r in cur.fetchall()]
        cols = [c for c in columns if c in local_cols]
        if not cols:
            return

        # Adaptar valores JSON (dict/list) para JSON/JSONB
        values = []
        for c in cols:
            v = row.get(c)
            if isinstance(v, (dict, list)):
                v = psycopg2.extras.Json(v)
            values.append(v)
        placeholders = ", ".join(["%s"] * len(cols))
        colnames = ", ".join(cols)
        sql = f"INSERT INTO {table} ({colnames}) VALUES ({placeholders})"
        cur.execute(sql, values)


def main():
    parser = argparse.ArgumentParser(description="Clonar cliente desde Railway a LOCAL")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug", type=str, help="Slug del cliente en Railway (recomendado)")
    g.add_argument("--name", type=str, help="Nombre (o parte) del cliente en Railway")
    parser.add_argument("--replace", action="store_true", help="Reemplazar datos locales de ese cliente")
    args = parser.parse_args()

    # Conexiones
    print("🔌 Conectando a Railway...")
    rw_conn = psycopg2.connect(**RAILWAY_DB)
    print("🔌 Conectando a LOCAL...")
    local_conn = psycopg2.connect(LOCAL_DB_URL)

    try:
        # 1) Resolver cliente en Railway
        client = get_client_by_slug_or_name(rw_conn, args.slug, args.name)
        if not client:
            print("❌ Cliente no encontrado en Railway (verifica --slug o --name)")
            sys.exit(2)

        client_id = client["id"]
        client_slug = client.get("slug")
        print(f"📌 Cliente: {client.get('name')} | slug={client_slug} | id={client_id}")

        # 2) Fetch de tablas en Railway
        with rw_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # clients (1 fila)
            cur.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
            client_row = fetchone_dict(cur)

        all_rows: Dict[str, Tuple[List[Dict], List[str]]] = {}
        for table, (client_col, use_store) in TABLES_BY_CLIENT.items():
            rows, cols = fetch_table_rows_for_client(rw_conn, table, client_id, use_store_id=use_store)
            all_rows[table] = (rows, cols)
            print(f"   • {table:<24s} {len(rows)} filas")

        # 3) Reemplazo en LOCAL (opcional)
        with local_conn:
            with local_conn.cursor() as cur:
                if args.replace:
                    print("🗑️  Limpiando datos previos del cliente en LOCAL...")
                    delete_local_client_tree(local_conn, client_id, client_slug)

                # Insertar clients primero
                print("➕ Insertando clients...")
                insert_row(local_conn, 'clients', client_row, list(client_row.keys()))

                # Insertar secuencia de tablas dependientes
                order = ['store_search_config', 'categories', 'products', 'images', 'product_attribute_config']
                for table in order:
                    rows, cols = all_rows.get(table, ([], []))
                    if not rows:
                        continue
                    print(f"➕ Insertando {table} ({len(rows)})...")
                    for r in rows:
                        insert_row(local_conn, table, r, cols)

        print("\n✅ Clonado completado.")
        print("   Ahora la base LOCAL contiene al cliente y sus datos exactamente como en Railway.")

    finally:
        try:
            rw_conn.close()
        except Exception:
            pass
        try:
            local_conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
