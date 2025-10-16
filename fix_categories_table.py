#!/usr/bin/env python3
"""
Corregir tabla categories con campos faltantes
"""
import asyncio
import asyncpg

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def fix_categories_table():
    """Agregar campos faltantes en categories"""

    print("🔧 CORRIGIENDO TABLA CATEGORIES")
    print("=" * 50)

    conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # Verificar campos actuales
        cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'categories'")
        existing_cols = [col['column_name'] for col in cols]
        print(f"Campos actuales: {', '.join(existing_cols)}")

        # Agregar campos faltantes de SQLite
        fields_to_add = [
            ("name_en", "VARCHAR(255)"),
            ("alternative_terms", "TEXT"),
            ("clip_prompt", "TEXT"),
            ("visual_features", "TEXT"),
            ("confidence_threshold", "DECIMAL(3,2) DEFAULT 0.5"),
            ("color", "VARCHAR(50)")
        ]

        print(f"\n🔨 Agregando campos faltantes...")
        for field_name, field_type in fields_to_add:
            if field_name not in existing_cols:
                try:
                    await conn.execute(f"ALTER TABLE categories ADD COLUMN {field_name} {field_type}")
                    print(f"  ✅ Agregado: {field_name} {field_type}")
                except Exception as e:
                    print(f"  ❌ Error agregando {field_name}: {e}")
            else:
                print(f"  ⏭️  Ya existe: {field_name}")

        print(f"\n✨ ¡TABLA CATEGORIES CORREGIDA!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(fix_categories_table())
    if success:
        print("\n🎯 CATEGORIES SINCRONIZADA CON SQLITE")
    else:
        print("\n💥 Error en la corrección")
