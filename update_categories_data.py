#!/usr/bin/env python3
"""
Actualizar datos de categories con información de SQLite
"""
import asyncio
import asyncpg
import sqlite3

SQLITE_PATH = "clip_admin_backend/instance/clip_comparador_v2.db"
POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def update_categories_data():
    """Actualizar categories con datos de SQLite"""

    print("🔄 ACTUALIZANDO DATOS DE CATEGORIES")
    print("=" * 50)

    # Conectar a SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # Conectar a PostgreSQL
    pg_conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # Obtener categories de SQLite
        cursor.execute("""
            SELECT id, name_en, alternative_terms, clip_prompt, visual_features,
                   confidence_threshold, color FROM categories
        """)
        sqlite_categories = cursor.fetchall()

        print(f"📋 Categories a actualizar: {len(sqlite_categories)}")

        # Actualizar cada categoría en PostgreSQL
        updated_count = 0
        for cat in sqlite_categories:
            try:
                await pg_conn.execute("""
                    UPDATE categories
                    SET name_en = $2, alternative_terms = $3, clip_prompt = $4,
                        visual_features = $5, confidence_threshold = $6, color = $7
                    WHERE id = $1
                """,
                cat['id'],
                cat['name_en'] or '',
                cat['alternative_terms'] or '',
                cat['clip_prompt'] or '',
                cat['visual_features'] or '',
                float(cat['confidence_threshold']) if cat['confidence_threshold'] else 0.5,
                cat['color'] or '')

                updated_count += 1

            except Exception as e:
                print(f"  ❌ Error actualizando categoría {cat['id']}: {e}")

        print(f"\n📊 RESULTADO:")
        print(f"  ✅ Categories actualizadas: {updated_count}")

        print(f"\n✨ ¡DATOS DE CATEGORIES ACTUALIZADOS!")
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
    success = asyncio.run(update_categories_data())
    if success:
        print("\n🎯 CATEGORIES COMPLETAMENTE SINCRONIZADAS")
    else:
        print("\n💥 Error en la actualización")
