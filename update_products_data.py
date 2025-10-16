#!/usr/bin/env python3
"""
Actualizar datos de productos existentes con campos faltantes de SQLite
"""
import asyncio
import asyncpg
import sqlite3

SQLITE_PATH = "clip_admin_backend/instance/clip_comparador_v2.db"
POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def update_products_data():
    """Actualizar productos con datos faltantes de SQLite"""

    print("🔄 ACTUALIZANDO DATOS DE PRODUCTOS")
    print("=" * 50)

    # 1. Conectar a SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # 2. Conectar a PostgreSQL
    pg_conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # 3. Obtener productos de SQLite con campos faltantes
        cursor.execute("SELECT id, brand, stock, color, tags FROM products")
        sqlite_products = cursor.fetchall()

        print(f"📋 Productos a actualizar: {len(sqlite_products)}")

        # 4. Actualizar cada producto en PostgreSQL
        updated_count = 0
        for prod in sqlite_products:
            try:
                await pg_conn.execute("""
                    UPDATE products
                    SET brand = $2, stock = $3, color = $4, tags = $5
                    WHERE id = $1
                """,
                prod['id'],
                prod['brand'] or '',
                prod['stock'] or 0,
                prod['color'] or '',
                prod['tags'] or '')

                updated_count += 1
                if updated_count % 10 == 0:
                    print(f"  ✅ Actualizados: {updated_count}/{len(sqlite_products)}")

            except Exception as e:
                print(f"  ❌ Error actualizando producto {prod['id']}: {e}")

        print(f"\n📊 RESULTADO:")
        print(f"  ✅ Productos actualizados: {updated_count}")

        # 5. Verificar algunos productos actualizados
        print(f"\n🔍 MUESTRA DE PRODUCTOS ACTUALIZADOS:")
        sample_products = await pg_conn.fetch("""
            SELECT name, brand, stock, color
            FROM products
            WHERE brand IS NOT NULL AND brand != ''
            LIMIT 5
        """)

        for prod in sample_products:
            print(f"  - {prod['name']} | {prod['brand']} | Stock: {prod['stock']} | Color: {prod['color'] or 'N/A'}")

        print(f"\n✨ ¡DATOS DE PRODUCTOS ACTUALIZADOS!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        sqlite_conn.close()
        await pg_conn.close()

if __name__ == "__main__":
    success = asyncio.run(update_products_data())
    if success:
        print("\n🎯 PRODUCTOS COMPLETAMENTE SINCRONIZADOS")
    else:
        print("\n💥 Error en la actualización")
