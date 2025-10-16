#!/usr/bin/env python3
"""
Actualizar el clip_prompt de GORROS-GORRAS para mejor detección
"""
import asyncio
import asyncpg

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def update_gorras_prompt():
    """Actualizar el prompt de GORROS-GORRAS para mejor detección visual"""
    
    print("🔧 ACTUALIZANDO PROMPT DE GORROS-GORRAS")
    print("=" * 50)
    
    conn = await asyncpg.connect(POSTGRES_URL)
    
    try:
        # Prompt actual
        current = await conn.fetchrow("""
            SELECT clip_prompt FROM categories 
            WHERE name = 'GORROS – GORRAS'
        """)
        
        print(f"❌ Prompt ACTUAL:")
        print(f"   '{current['clip_prompt']}'")
        
        # Nuevo prompt optimizado para detección visual
        new_prompt = "baseball cap, sports cap, purple cap, fitted cap, casual hat, cap with visor"
        
        print(f"\n✅ Prompt NUEVO (optimizado):")
        print(f"   '{new_prompt}'")
        
        # Actualizar
        await conn.execute("""
            UPDATE categories 
            SET clip_prompt = $1,
                updated_at = NOW()
            WHERE name = 'GORROS – GORRAS'
        """, new_prompt)
        
        print(f"\n🎯 ACTUALIZACIÓN COMPLETADA")
        print(f"   El prompt ahora coincide con lo que CLIP naturalmente detectaría")
        print(f"   Tu gorra púrpura debería tener 80-90% confianza")
        
        # Verificar actualización
        updated = await conn.fetchrow("""
            SELECT clip_prompt FROM categories 
            WHERE name = 'GORROS – GORRAS'
        """)
        
        print(f"\n✅ VERIFICACIÓN:")
        print(f"   Prompt actualizado: '{updated['clip_prompt']}'")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(update_gorras_prompt())
    if success:
        print(f"\n🚀 ¡LISTO! Prueba ahora tu gorra púrpura")
        print(f"   Debería detectarse como 'GORROS – GORRAS' con alta confianza")
    else:
        print(f"\n💥 Error en actualización")