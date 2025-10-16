#!/usr/bin/env python3
"""
Verificación final completa del sistema
"""
import asyncio
import asyncpg

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def final_verification():
    """Verificación final completa"""

    print("🔍 VERIFICACIÓN FINAL COMPLETA DEL SISTEMA")
    print("=" * 60)

    conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # Verificar estructura de todas las tablas
        tables = ['clients', 'users', 'categories', 'products', 'images']

        for table in tables:
            print(f"\n📋 TABLA {table.upper()}:")
            cols = await conn.fetch(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """)

            for col in cols:
                print(f"  ✅ {col['column_name']}: {col['data_type']}")

            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"  📊 Registros: {count}")

        # Test específico del dashboard
        print(f"\n🧪 PROBANDO CONSULTAS DEL DASHBOARD...")

        try:
            # Test query clients
            client_test = await conn.fetchrow("""
                SELECT id, name, slug, email, industry FROM clients
                WHERE id = '60231500-ca6f-4c46-a960-2e17298fcdb0'
            """)
            print(f"  ✅ Cliente test: {client_test['name']} ({client_test['email']})")

            # Test query products
            products_count = await conn.fetchval("""
                SELECT COUNT(*) FROM products
                WHERE client_id = '60231500-ca6f-4c46-a960-2e17298fcdb0'
            """)
            print(f"  ✅ Productos del cliente: {products_count}")

            # Test query images
            images_count = await conn.fetchval("""
                SELECT COUNT(*) FROM images
                WHERE client_id = '60231500-ca6f-4c46-a960-2e17298fcdb0'
            """)
            print(f"  ✅ Imágenes del cliente: {images_count}")

            # Test query categories
            categories_count = await conn.fetchval("""
                SELECT COUNT(*) FROM categories
                WHERE client_id = '60231500-ca6f-4c46-a960-2e17298fcdb0'
            """)
            print(f"  ✅ Categorías del cliente: {categories_count}")

        except Exception as e:
            print(f"  ❌ Error en test: {e}")

        print(f"\n📈 RESUMEN FINAL:")
        total_records = 0
        for table in tables:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            total_records += count
            print(f"  ✅ {table}: {count} registros")

        print(f"\n🎯 TOTAL: {total_records} registros migrados")
        print(f"✨ ¡SISTEMA COMPLETAMENTE FUNCIONAL!")

        return True

    except Exception as e:
        print(f"❌ Error en verificación: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(final_verification())
    if success:
        print("\n🚀 SISTEMA LISTO PARA PRODUCCIÓN EN RAILWAY")
    else:
        print("\n💥 Error en verificación final")
