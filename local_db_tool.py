"""
Local DB Admin Tool - Punto único para modificaciones de BD en desarrollo local.

Uso (ejemplos):
  - Ver conteos:            python local_db_tool.py counts
  - Ejecutar SQL directo:   python local_db_tool.py sql -e "SELECT * FROM clients LIMIT 5"
  - Ejecutar archivo SQL:   python local_db_tool.py sql -f script.sql --yes
  - Crear tablas training:  python local_db_tool.py create-training-tables --yes

Flags de seguridad:
  --yes  Confirma y hace COMMIT. Sin --yes se hace ROLLBACK (modo seguro).

Conexión: Usa PostgreSQL local. Lee configuración de .env.local
(LOCAL_DATABASE_URL) o usa defaults de desarrollo.
"""
import os
import sys
import argparse
import psycopg2
from dotenv import load_dotenv

# Cargar configuración local
env_local_path = os.path.join(os.path.dirname(__file__), '.env.local')
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)
    print(f"📄 Configuración cargada desde {env_local_path}")
else:
    load_dotenv()
    print("📄 Usando variables de entorno del sistema")


def get_conn():
    """Obtiene conexión a BD local desde DATABASE_URL o LOCAL_DATABASE_URL"""
    db_url = os.getenv('LOCAL_DATABASE_URL') or os.getenv('DATABASE_URL')

    if db_url:
        # Parse DATABASE_URL (formato: postgresql://user:pass@host:port/db)
        from urllib.parse import urlparse, unquote
        parsed = urlparse(db_url)
        return psycopg2.connect(
            host=parsed.hostname or 'localhost',
            port=parsed.port or 5432,
            database=parsed.path[1:],  # Remove leading /
            user=parsed.username,
            password=unquote(parsed.password) if parsed.password else None  # Decode URL-encoded password
        )
    else:
        # Fallback a valores por defecto
        return psycopg2.connect(
            host=os.getenv('LOCAL_DB_HOST', 'localhost'),
            port=int(os.getenv('LOCAL_DB_PORT', '5432')),
            database=os.getenv('LOCAL_DB', 'clip_comparador_v2'),
            user=os.getenv('LOCAL_DB_USER', 'postgres'),
            password=os.getenv('LOCAL_DB_PASSWORD', 'admin')
        )


def get_counts(cur):
    """Conteo básico de imágenes"""
    try:
        cur.execute("SELECT COUNT(*) FROM images")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM images WHERE is_processed = TRUE")
        processed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM images WHERE is_processed = FALSE AND upload_status = 'pending'")
        pending = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM images WHERE upload_status = 'failed'")
        failed = cur.fetchone()[0]
        return dict(total=total, processed=processed, pending=pending, failed=failed)
    except Exception as e:
        print(f"⚠️  Error obteniendo conteos: {e}")
        return dict(total=0, processed=0, pending=0, failed=0)


def cmd_counts(args):
    """Mostrar conteos de imágenes"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            c = get_counts(cur)
            print(f"total={c['total']} procesadas={c['processed']} pendientes={c['pending']} fallidas={c['failed']}")


def cmd_create_training_tables(args):
    """Crear tablas de entrenamiento visual"""
    sql_create = """
-- Tabla: training_events
CREATE TABLE IF NOT EXISTS training_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    category_id UUID REFERENCES categories(id),
    query_image_ref VARCHAR(500),
    topk_results JSON NOT NULL,
    positives JSON NOT NULL,
    negatives JSON NOT NULL,
    variant_key VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla: client_category_variants
CREATE TABLE IF NOT EXISTS client_category_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    category_id UUID NOT NULL REFERENCES categories(id),
    variant_key VARCHAR(64) NOT NULL,
    name VARCHAR(120) NOT NULL,
    centroid_embedding TEXT,
    support_count INTEGER NOT NULL DEFAULT 0,
    prompts JSON NOT NULL DEFAULT '[]'::json,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índice para búsquedas rápidas
CREATE INDEX IF NOT EXISTS ix_client_category_variants_client_category
    ON client_category_variants (client_id, category_id);

-- Constraint única
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_client_category_variant_key'
    ) THEN
        ALTER TABLE client_category_variants
        ADD CONSTRAINT uq_client_category_variant_key
        UNIQUE (client_id, category_id, variant_key);
    END IF;
END $$;
"""

    with get_conn() as conn:
        with conn.cursor() as cur:
            print("🔨 Creando tablas de entrenamiento...")
            try:
                cur.execute(sql_create)

                if args.yes:
                    conn.commit()
                    print("✅ COMMIT realizado. Tablas creadas exitosamente:")
                    print("   - training_events")
                    print("   - client_category_variants")
                    print("   - Índices y constraints aplicados")
                else:
                    conn.rollback()
                    print("🛟 ROLLBACK (usar --yes para confirmar)")
            except Exception as e:
                conn.rollback()
                print(f"❌ Error creando tablas: {e}")
                sys.exit(1)


def cmd_create_calibration_tables(args):
    """Crear tablas del módulo de calibración"""
    sql_create = """
-- Tabla: training_images (dataset de ground-truth para calibración)
CREATE TABLE IF NOT EXISTS training_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    cloudinary_public_id VARCHAR(255),
    cloudinary_url TEXT NOT NULL,
    expected_categories JSON NOT NULL DEFAULT '[]'::json,
    notes TEXT,
    case_type VARCHAR(50) DEFAULT 'general',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_calibration_result JSON,
    created_by_user_id UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Tabla: calibration_runs (historial de calibraciones ejecutadas)
CREATE TABLE IF NOT EXISTS calibration_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    results JSON NOT NULL,
    applied BOOLEAN NOT NULL DEFAULT FALSE,
    applied_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS ix_training_images_client_id
    ON training_images (client_id);

CREATE INDEX IF NOT EXISTS ix_training_images_is_active
    ON training_images (is_active);

CREATE INDEX IF NOT EXISTS ix_calibration_runs_client_id
    ON calibration_runs (client_id);

CREATE INDEX IF NOT EXISTS ix_calibration_runs_created_at
    ON calibration_runs (created_at DESC);
"""

    with get_conn() as conn:
        with conn.cursor() as cur:
            print("🔨 Creando tablas de calibración...")
            try:
                cur.execute(sql_create)

                if args.yes:
                    conn.commit()
                    print("✅ COMMIT realizado. Tablas creadas exitosamente:")
                    print("   - training_images (dataset de ground-truth)")
                    print("   - calibration_runs (historial de calibraciones)")
                    print("   - Índices aplicados")
                else:
                    conn.rollback()
                    print("🛟 ROLLBACK (usar --yes para confirmar)")
            except Exception as e:
                conn.rollback()
                print(f"❌ Error creando tablas: {e}")
                sys.exit(1)


def cmd_sql(args):
    """Ejecutar SQL arbitrario"""
    if not args.e and not args.f:
        print("❌ Debes especificar -e 'SQL' o -f archivo.sql")
        sys.exit(1)

    query = None
    if args.e:
        query = args.e
    elif args.f:
        if not os.path.exists(args.f):
            print(f"❌ Archivo no encontrado: {args.f}")
            sys.exit(1)
        with open(args.f, 'r', encoding='utf-8') as fh:
            query = fh.read()

    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(query)

                # Si es un SELECT, mostrar resultados
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    print(f"\n{'=' * 80}")
                    print(f"📊 RESULTADOS: {len(rows)} filas")
                    print(f"{'=' * 80}\n")

                    if rows:
                        col_widths = [len(col) for col in columns]
                        for row in rows:
                            for i, val in enumerate(row):
                                col_widths[i] = max(col_widths[i], len(str(val)) if val is not None else 4)

                        col_widths = [min(w, 50) for w in col_widths]

                        header = " | ".join(col.ljust(col_widths[i]) for i, col in enumerate(columns))
                        print(header)
                        print("-" * len(header))

                        for row in rows:
                            row_str = " | ".join(
                                str(val).ljust(col_widths[i])[:col_widths[i]] if val is not None else "NULL".ljust(col_widths[i])
                                for i, val in enumerate(row)
                            )
                            print(row_str)

                        print(f"\n{'=' * 80}\n")
                    else:
                        print("(Sin resultados)\n")

                affected = cur.rowcount

                if not cur.description:
                    if args.yes:
                        conn.commit()
                        print(f"✅ COMMIT realizado. Filas afectadas: {affected}")
                    else:
                        conn.rollback()
                        print(f"🛟 ROLLBACK (usar --yes para confirmar). Filas que se afectarían: {affected}")
                else:
                    if args.yes:
                        conn.commit()
                    print(f"✅ Query ejecutado exitosamente")

            except Exception as e:
                conn.rollback()
                print(f"❌ Error ejecutando SQL: {e}")
                sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(description='Local DB Admin Tool')
    parser.add_argument('--yes', action='store_true', help='Confirmar cambios (COMMIT)')

    subparsers = parser.add_subparsers(dest='command', help='Comando a ejecutar')

    # Comando: counts
    subparsers.add_parser('counts', help='Mostrar conteos de imágenes')

    # Comando: create-training-tables
    subparsers.add_parser('create-training-tables', help='Crear tablas del módulo de entrenamiento')

    # Comando: create-calibration-tables
    subparsers.add_parser('create-calibration-tables', help='Crear tablas del módulo de calibración')

    # Comando: sql
    sql_parser = subparsers.add_parser('sql', help='Ejecutar SQL directo')
    sql_parser.add_argument('-e', type=str, help='SQL inline')
    sql_parser.add_argument('-f', type=str, help='Archivo SQL')

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmd_map = {
        'counts': cmd_counts,
        'create-training-tables': cmd_create_training_tables,
        'create-calibration-tables': cmd_create_calibration_tables,
        'sql': cmd_sql,
    }

    cmd_func = cmd_map.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        print(f"❌ Comando desconocido: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
