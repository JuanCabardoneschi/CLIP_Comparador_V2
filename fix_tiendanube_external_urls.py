import os
import sys
import argparse
import logging
import re

import psycopg2
from psycopg2.extras import RealDictCursor

"""
Script: fix_tiendanube_external_urls.py

Propósito:
- Corregir `products.external_url` mal formadas que contienen el dict de handle
  (p.ej. "/products/{'es': 'remera-azul'}") reemplazando por la ruta correcta
  de Tiendanube: "/productos/remera-azul" y preservando el dominio si existe.

Uso:
- Python:
  python fix_tiendanube_external_urls.py --database-url "postgresql://..." --dry-run
  python fix_tiendanube_external_urls.py --database-url "postgresql://..."

- Si `--database-url` no se pasa, intenta leer `DATABASE_URL` del entorno.

Notas:
- Solo afecta filas donde `external_url` LIKE "%{\"es\":%}" o "%{'es':%}" y donde
  aparece "/products/" o "/product/".
- No borra datos; aplica una actualización precisa de texto.
"""

LOGGER = logging.getLogger("fix_tiendanube_external_urls")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PRODUCTS_TABLE = "products"

# Regex Python para visualización previa (no usado en DB), coincide con ambas comillas
PY_HANDLE_PATTERN = re.compile(r"/(products?|product)/\{['\"]es['\"]:\s*['\"]([^'\"]+)['\"]\}")

# SQL que corrige los patrones con comillas simples
SQL_FIX_SINGLE_QUOTES = r"""
UPDATE products
SET external_url = regexp_replace(
    external_url,
    '/products?/\{''es'':\s*''([^'']+)''\}',
    '/productos/\1'
)
WHERE external_url LIKE '%/product%{''es'':%}';
"""

# SQL que corrige los patrones con comillas dobles
SQL_FIX_DOUBLE_QUOTES = r"""
UPDATE products
SET external_url = regexp_replace(
    external_url,
    '/products?/\{"es":\s*"([^"]+)"\}',
    '/productos/\1'
)
WHERE external_url LIKE '%/product%{"es":%}';
"""

# Opcional: normalizar doble barra o espacios accidentales
SQL_TIDY = r"""
UPDATE products
SET external_url = regexp_replace(regexp_replace(external_url, '/{2,}', '/'), '\\s+', '')
WHERE external_url LIKE '%/productos/%';
"""

# Filtro adicional para limitar a clientes Tiendanube si existe la columna integration_type en clients
# Realizamos por JOIN suponiendo esquema multi-tenant.
SQL_SCOPE_TIENDANUBE = r"""
WITH scoped AS (
    SELECT p.id
    FROM products p
    JOIN clients c ON c.id = p.client_id
    WHERE c.integration_type = 'tiendanube'
)
UPDATE products p
SET external_url = x.fixed
FROM (
    SELECT p.id,
           CASE
             WHEN p.external_url ~ '/product(s)?/\{''es'':\s*''[^'']+''\}' THEN regexp_replace(p.external_url, '/products?/\{''es'':\s*''([^'']+)''\}', '/productos/\1')
             WHEN p.external_url ~ '/product(s)?/\{"es":\s*"[^"]+"\}' THEN regexp_replace(p.external_url, '/products?/\{"es":\s*"([^"]+)"\}', '/productos/\1')
             ELSE p.external_url
           END AS fixed
    FROM products p
    JOIN clients c ON c.id = p.client_id
    WHERE c.integration_type = 'tiendanube'
) AS x
WHERE p.id = x.id AND p.external_url <> x.fixed;
"""


def preview_fix(url: str) -> str:
    """Preview local del reemplazo para una URL dada."""
    return PY_HANDLE_PATTERN.sub(lambda m: f"/productos/{m.group(2)}", url)


def run_fix(conn, dry_run: bool):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Conteo inicial de afectados
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM products p
            JOIN clients c ON c.id = p.client_id
            WHERE c.integration_type = 'tiendanube'
              AND (p.external_url LIKE '%/product%{"es":%}' OR p.external_url LIKE '%/product%{''es'':%}')
            """
        )
        initial = cur.fetchone()["cnt"]
        LOGGER.info(f"Filas con external_url mal formada (estimado): {initial}")

        if dry_run:
            # Muestra ejemplos
            cur.execute(
                """
                SELECT p.id, p.external_url
                FROM products p
                JOIN clients c ON c.id = p.client_id
                WHERE c.integration_type = 'tiendanube'
                  AND (p.external_url LIKE '%/product%{"es":%}' OR p.external_url LIKE '%/product%{''es'':%}')
                ORDER BY p.id
                LIMIT 10
                """
            )
            rows = cur.fetchall()
            for r in rows:
                before = r["external_url"]
                after = preview_fix(before)
                LOGGER.info(f"ID {r['id']}:\n  BEFORE: {before}\n  AFTER : {after}")
            return

        # Aplica fixes directos (simple quotes y double quotes)
        LOGGER.info("Aplicando correcciones (comillas simples)...")
        cur.execute(SQL_FIX_SINGLE_QUOTES)
        LOGGER.info("Aplicando correcciones (comillas dobles)...")
        cur.execute(SQL_FIX_DOUBLE_QUOTES)

        # Limpieza final
        LOGGER.info("Normalizando URLs...")
        cur.execute(SQL_TIDY)

        # Reporte final
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM products p
            JOIN clients c ON c.id = p.client_id
            WHERE c.integration_type = 'tiendanube'
              AND (p.external_url LIKE '%/product%{"es":%}' OR p.external_url LIKE '%/product%{''es'':%}')
            """
        )
        remaining = cur.fetchone()["cnt"]
        LOGGER.info(f"Filas aún con patrón mal formado: {remaining}")

        conn.commit()
        LOGGER.info("Commit realizado.")


def main():
    parser = argparse.ArgumentParser(description="Fix external_url mal formadas para Tiendanube")
    parser.add_argument("--database-url", dest="database_url", help="Cadena de conexión PostgreSQL (postgresql://...)")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="Solo previsualiza cambios sin actualizar DB")
    args = parser.parse_args()

    db_url = args.database_url or os.getenv("DATABASE_URL")
    if not db_url:
        LOGGER.error("Debe proporcionar --database-url o definir la variable de entorno DATABASE_URL")
        sys.exit(1)

    try:
        conn = psycopg2.connect(db_url)
    except Exception as e:
        LOGGER.error(f"No se pudo conectar a la base de datos: {e}")
        sys.exit(1)

    try:
        run_fix(conn, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
