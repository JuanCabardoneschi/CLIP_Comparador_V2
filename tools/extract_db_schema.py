import argparse
import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse, unquote
import psycopg2

# Permitir imports relativos desde la raíz del repo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def load_env_local():
    env_path = os.path.join(ROOT, '.env.local')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass


def get_conn_for_target(target: str):
    if target == 'local':
        # Cargar .env.local si existe (sin imprimir nada)
        load_env_local()
        db_url = os.getenv('LOCAL_DATABASE_URL') or os.getenv('DATABASE_URL')
        if db_url:
            parsed = urlparse(db_url)
            return psycopg2.connect(
                host=parsed.hostname or 'localhost',
                port=parsed.port or 5432,
                database=(parsed.path[1:] if parsed.path.startswith('/') else parsed.path),
                user=parsed.username,
                password=unquote(parsed.password) if parsed.password else None,
            )
        # Fallback a defaults de desarrollo
        return psycopg2.connect(
            host=os.getenv('LOCAL_DB_HOST', 'localhost'),
            port=int(os.getenv('LOCAL_DB_PORT', '5432')),
            database=os.getenv('LOCAL_DB', 'clip_comparador_v2'),
            user=os.getenv('LOCAL_DB_USER', 'postgres'),
            password=os.getenv('LOCAL_DB_PASSWORD', 'admin'),
        )
    elif target == 'railway':
        from railway_db_tool import get_conn  # Usa credenciales definidas allí
        return get_conn()
    else:
        raise ValueError("target debe ser 'local' o 'railway'")


def fetch_schema(cur):
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [r[0] for r in cur.fetchall()]

    schema = {}
    for t in tables:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (t,),
        )
        cols = []
        for name, dtype, nullable, default in cur.fetchall():
            cols.append({
                'name': name,
                'type': dtype,
                'nullable': (nullable == 'YES'),
                'default': default,
            })
        schema[t] = cols
    return schema


def main():
    parser = argparse.ArgumentParser(description='Extrae esquema (tablas y columnas) a JSON')
    parser.add_argument('--target', required=True, choices=['local', 'railway'], help="Origen de conexión: local o railway")
    parser.add_argument('--out', default=None, help='Ruta del archivo de salida (opcional)')
    args = parser.parse_args()

    os.makedirs(os.path.join(ROOT, 'logs'), exist_ok=True)

    with get_conn_for_target(args.target) as conn:
        with conn.cursor() as cur:
            schema = fetch_schema(cur)

    payload = {
        'target': args.target,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'schema': schema,
    }

    if args.out:
        out_path = args.out
    else:
        out_path = os.path.join(ROOT, 'logs', f'schema_{args.target}.json')

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Esquema ({args.target}) guardado en: {out_path}")


if __name__ == '__main__':
    main()
