"""
Railway DB Admin Tool - Punto único para modificaciones de BD en producción.

Uso (ejemplos):
  - Ver conteos:            python railway_db_tool.py counts
  - Arreglar pendientes:   python railway_db_tool.py fix-pending-images --yes
  - Ejecutar SQL directo:  python railway_db_tool.py sql -e "UPDATE ..." --yes
  - Ejecutar archivo SQL:  python railway_db_tool.py sql -f script.sql --yes

Flags de seguridad:
  --yes  Confirma y hace COMMIT. Sin --yes se hace ROLLBACK (modo seguro).

Conexión: Usa Railway (ballast.proxy.rlwy.net:54363). Puedes sobreescribir con
variables de entorno RAILWAY_DB_HOST/PORT/DB/USER/PASSWORD si fuera necesario.
"""
import os
import sys
import argparse
import psycopg2


def get_conn():
    host = os.getenv('RAILWAY_DB_HOST', 'ballast.proxy.rlwy.net')
    port = int(os.getenv('RAILWAY_DB_PORT', '54363'))
    database = os.getenv('RAILWAY_DB', 'railway')
    user = os.getenv('RAILWAY_DB_USER', 'postgres')
    password = os.getenv('RAILWAY_DB_PASSWORD', 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum')
    return psycopg2.connect(host=host, port=port, database=database, user=user, password=password)


def get_counts(cur):
    cur.execute("SELECT COUNT(*) FROM images")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM images WHERE is_processed = TRUE")
    processed = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM images WHERE is_processed = FALSE AND upload_status = 'pending'")
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM images WHERE upload_status = 'failed'")
    failed = cur.fetchone()[0]
    return dict(total=total, processed=processed, pending=pending, failed=failed)


def cmd_counts(args):
    with get_conn() as conn:
        with conn.cursor() as cur:
            c = get_counts(cur)
            print(f"total={c['total']} processed={c['processed']} pending={c['pending']} failed={c['failed']}")


def cmd_fix_pending_images(args):
    sql_fix = (
        """
        UPDATE images
           SET is_processed = TRUE,
               upload_status = 'completed',
               updated_at = NOW()
         WHERE clip_embedding IS NOT NULL
           AND (is_processed = FALSE OR upload_status <> 'completed');
        """
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            before = get_counts(cur)
            print(f"Antes: total={before['total']} procesadas={before['processed']} pendientes={before['pending']} fallidas={before['failed']}")
            cur.execute(sql_fix)
            affected = cur.rowcount
            if args.yes:
                conn.commit()
                print(f"✅ COMMIT realizado. Filas afectadas: {affected}")
            else:
                conn.rollback()
                print(f"🛟 ROLLBACK (usar --yes para confirmar). Filas que se afectarían: {affected}")
            after = get_counts(cur)
            print(f"Después: total={after['total']} procesadas={after['processed']} pendientes={after['pending']} fallidas={after['failed']}")


def cmd_sql(args):
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
            cur.execute(query)
            
            # Si es un SELECT, mostrar resultados
            if cur.description:
                # Obtener nombres de columnas
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                
                print(f"\n{'=' * 80}")
                print(f"📊 RESULTADOS: {len(rows)} filas")
                print(f"{'=' * 80}\n")
                
                if rows:
                    # Calcular ancho máximo por columna
                    col_widths = [len(col) for col in columns]
                    for row in rows:
                        for i, val in enumerate(row):
                            col_widths[i] = max(col_widths[i], len(str(val)) if val is not None else 4)
                    
                    # Limitar ancho máximo a 50 caracteres
                    col_widths = [min(w, 50) for w in col_widths]
                    
                    # Imprimir encabezados
                    header = " | ".join(col.ljust(col_widths[i]) for i, col in enumerate(columns))
                    print(header)
                    print("-" * len(header))
                    
                    # Imprimir filas
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
            
            # Para INSERT/UPDATE/DELETE
            if not cur.description:
                if args.yes:
                    conn.commit()
                    print(f"✅ COMMIT realizado. Filas afectadas: {affected}")
                else:
                    conn.rollback()
                    print(f"🛟 ROLLBACK (usar --yes para confirmar). Filas que se afectarían: {affected}")
            else:
                # Para SELECT, no hacer commit/rollback
                if args.yes:
                    conn.commit()
                print(f"✅ Query ejecutado exitosamente")


def build_parser():
    p = argparse.ArgumentParser(description="Railway DB Admin Tool")
    sub = p.add_subparsers(dest='command', required=True)

    sub_counts = sub.add_parser('counts', help='Muestra conteos básicos de imágenes')
    sub_counts.set_defaults(func=cmd_counts)

    sub_fix = sub.add_parser('fix-pending-images', help='Marca como completadas imágenes con embedding ya generado')
    sub_fix.add_argument('--yes', action='store_true', help='Confirma y realiza COMMIT')
    sub_fix.set_defaults(func=cmd_fix_pending_images)

    sub_sql = sub.add_parser('sql', help='Ejecuta SQL arbitrario')
    sub_sql.add_argument('-e', help='SQL inline a ejecutar')
    sub_sql.add_argument('-f', help='Archivo .sql a ejecutar')
    sub_sql.add_argument('--yes', action='store_true', help='Confirma y realiza COMMIT')
    sub_sql.set_defaults(func=cmd_sql)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
