"""
Railway Migration - Seed product_attribute_config desde templates por industria

Uso:
  # Dry-run (no guarda)
  python railway_seed_industry_attributes.py --client-id <UUID> --industry <industry>

  # Aplicar cambios (COMMIT)
  python railway_seed_industry_attributes.py --client-id <UUID> --industry <industry> --yes

  # Listar industrias disponibles
  python railway_seed_industry_attributes.py --list-industries

Nota: Usa los templates hardcoded de clip_admin_backend/app/utils/industry_templates.py
"""
import os
import sys
import argparse
import json
import psycopg2
from psycopg2.extras import Json


# --- Carga de templates hardcoded (sin levantar Flask) ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIP_BACKEND_DIR = os.path.join(SCRIPT_DIR, 'clip_admin_backend')
if CLIP_BACKEND_DIR not in sys.path:
    sys.path.insert(0, CLIP_BACKEND_DIR)

try:
    from app.utils.industry_templates import (
        get_industry_template,
        get_available_industries,
    )
except Exception as e:
    print(f"❌ No se pudieron cargar los templates: {e}")
    print("   Verifica que exista clip_admin_backend/app/utils/industry_templates.py")
    sys.exit(1)


def get_conn():
    """Conectar a Railway PostgreSQL usando credenciales del proyecto"""
    host = os.getenv('RAILWAY_DB_HOST', 'ballast.proxy.rlwy.net')
    port = int(os.getenv('RAILWAY_DB_PORT', '54363'))
    database = os.getenv('RAILWAY_DB', 'railway')
    user = os.getenv('RAILWAY_DB_USER', 'postgres')
    password = os.getenv('RAILWAY_DB_PASSWORD', 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum')

    print(f"🔌 Conectando a Railway PostgreSQL...")
    print(f"   Host: {host}:{port}")
    print(f"   Database: {database}")
    print(f"   User: {user}")

    return psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        connect_timeout=10,
    )


def check_client_exists(cur, client_id: str) -> bool:
    cur.execute("SELECT 1 FROM clients WHERE id = %s", (client_id,))
    return cur.fetchone() is not None


def get_existing_keys(cur, client_id: str):
    cur.execute(
        "SELECT key FROM product_attribute_config WHERE client_id = %s",
        (client_id,),
    )
    return {row[0] for row in cur.fetchall()}


def seed_attributes(cur, client_id: str, industry: str):
    template = get_industry_template(industry)
    existing = get_existing_keys(cur, client_id)

    created = []
    skipped = []

    for order, (key, cfg) in enumerate(template.items(), start=1):
        if key in existing:
            skipped.append(key)
            continue

        cur.execute(
            """
            INSERT INTO product_attribute_config
                (client_id, key, label, type, required, options, field_order, expose_in_search)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                client_id,
                key,
                cfg.get('label', key.capitalize()),
                cfg.get('type', 'text'),
                bool(cfg.get('required', False)),
                Json(cfg.get('options')) if cfg.get('options') is not None else None,
                order,
                bool(cfg.get('expose_in_search', True)),
            ),
        )
        created.append(key)

    return created, skipped


def build_parser():
    p = argparse.ArgumentParser(description="Seed de atributos por industria (Railway)")
    p.add_argument('--client-id', help='UUID del cliente')
    p.add_argument('--industry', help="Industria: 'fashion', 'automotive', 'home', 'electronics', 'generic'")
    p.add_argument('--list-industries', action='store_true', help='Lista industrias disponibles y sale')
    p.add_argument('--yes', action='store_true', help='Confirma y realiza COMMIT (por defecto ROLLBACK)')
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_industries:
        print("Industrias disponibles:")
        for code, label in get_available_industries():
            print(f" - {code}: {label}")
        return

    if not args.client_id or not args.industry:
        print("❌ Debes especificar --client-id y --industry (o usar --list-industries)")
        sys.exit(1)

    dry_run = not args.yes
    if dry_run:
        print("🛟 MODO SEGURO: Se hará ROLLBACK al final (usa --yes para confirmar cambios)")
    else:
        print("✅ MODO COMMIT: Los cambios serán permanentes")

    try:
        with get_conn() as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
                # Validar cliente
                if not check_client_exists(cur, args.client_id):
                    print(f"❌ Cliente no encontrado: {args.client_id}")
                    sys.exit(1)

                print(f"🔧 Sembrando atributos para client_id={args.client_id} industry={args.industry}...")
                created, skipped = seed_attributes(cur, args.client_id, args.industry)

                print(f"   ➕ A crear: {len(created)}  {created}")
                print(f"   ↩️  Ya existen: {len(skipped)}  {skipped}")

                if dry_run:
                    conn.rollback()
                    print("🛟 ROLLBACK ejecutado (modo seguro)")
                    print("   Para aplicar cambios, ejecuta con --yes")
                else:
                    conn.commit()
                    print("✅ COMMIT ejecutado - Atributos creados")
    except psycopg2.Error as e:
        print(f"\n❌ ERROR de PostgreSQL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
