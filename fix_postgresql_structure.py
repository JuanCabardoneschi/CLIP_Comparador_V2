#!/usr/bin/env python3
"""
Corrige la tabla PostgreSQL para que coincida EXACTAMENTE con SQLite
"""
import asyncio
import asyncpg

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def fix_postgresql_to_match_sqlite():
    """Corrige PostgreSQL para que coincida EXACTAMENTE con SQLite"""

    print("🔧 CORRIGIENDO POSTGRESQL PARA COINCIDIR CON SQLITE")
    print("=" * 50)

    conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # 1. Renombrar original_url de vuelta a original_filename
        print("📝 Renombrando original_url -> original_filename...")
        try:
            await conn.execute("ALTER TABLE images RENAME COLUMN original_url TO original_filename")
            print("  ✅ original_filename restaurado")
        except Exception as e:
            print(f"  ⚠️ Ya existe o error: {e}")

        # 2. Agregar format si no existe (está en la migración)
        print("📝 Verificando campo format...")
        cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'images'")
        existing_cols = [col['column_name'] for col in cols]

        if 'format' not in existing_cols:
            await conn.execute("ALTER TABLE images ADD COLUMN format VARCHAR(50)")
            print("  ✅ format agregado")
        else:
            print("  ✅ format ya existe")

        # 3. Verificar estructura final
        print(f"\n📋 ESTRUCTURA FINAL DE POSTGRESQL:")
        final_cols = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'images'
            ORDER BY ordinal_position
        """)

        for col in final_cols:
            print(f"  ✅ {col['column_name']}: {col['data_type']}")

        # 4. Contar registros
        count = await conn.fetchval("SELECT COUNT(*) FROM images")
        print(f"\n📊 Total imágenes: {count}")

        print(f"\n✨ ¡POSTGRESQL CORREGIDO PARA COINCIDIR CON SQLITE!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(fix_postgresql_to_match_sqlite())
    if success:
        print("\n🎯 POSTGRESQL AHORA COINCIDE CON SQLITE")
    else:
        print("\n💥 Error en la corrección")
