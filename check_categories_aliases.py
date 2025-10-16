#!/usr/bin/env python3
"""
Verificar el estado actual de categorías y sus alias en Railway PostgreSQL
"""
import asyncio
import asyncpg

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def check_categories_aliases():
    """Verificar categorías y sus configuraciones de alias para CLIP"""
    
    print("🏷️  VERIFICANDO CATEGORÍAS Y ALIAS PARA CLIP")
    print("=" * 60)
    
    conn = await asyncpg.connect(POSTGRES_URL)
    
    try:
        # 1. Primero obtener el ID real del cliente
        print("🔍 Buscando cliente...")
        
        client = await conn.fetchrow("""
            SELECT id, name FROM clients 
            WHERE name ILIKE '%demo%' OR name ILIKE '%fashion%' OR name ILIKE '%goody%'
            LIMIT 1
        """)
        
        if not client:
            print("❌ No se encontró el cliente")
            return
        
        client_id = client['id']
        client_name = client['name']
        print(f"   Cliente encontrado: {client_name} (ID: {client_id})")
        
        # 2. Obtener todas las categorías del cliente
        print(f"\n📋 CATEGORÍAS EXISTENTES:")
        
        categories = await conn.fetch("""
            SELECT id, name, name_en, alternative_terms, clip_prompt, 
                   visual_features, confidence_threshold, is_active, client_id
            FROM categories 
            WHERE client_id = $1
            ORDER BY name
        """, client_id)
        
        total_categories = len(categories)
        print(f"   Total categorías: {total_categories}")
        
        if total_categories == 0:
            print("❌ No se encontraron categorías para el cliente")
            return
        
        print(f"\n🔍 DETALLE DE CATEGORÍAS Y ALIAS:")
        print("-" * 60)
        
        for i, cat in enumerate(categories, 1):
            print(f"\n{i}. {cat['name']} (ID: {str(cat['id'])[:8]}...)")
            print(f"   📝 Español: {cat['name']}")
            print(f"   🌍 Inglés: {cat['name_en'] or 'NO CONFIGURADO'}")
            print(f"   🔗 Términos alternativos: {cat['alternative_terms'] or 'NINGUNO'}")
            print(f"   🤖 CLIP prompt: {cat['clip_prompt'] or 'NO CONFIGURADO'}")
            print(f"   👁️  Características visuales: {cat['visual_features'] or 'NO CONFIGURADO'}")
            print(f"   🎯 Umbral confianza: {cat['confidence_threshold']}")
            print(f"   ✅ Activa: {cat['is_active']}")
        
        # 2. Verificar productos por categoría
        print(f"\n📊 PRODUCTOS POR CATEGORÍA:")
        print("-" * 60)
        
        for cat in categories:
            product_count = await conn.fetchval("""
                SELECT COUNT(*) FROM products 
                WHERE category_id = $1
            """, cat['id'])
            
            image_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT i.id) FROM images i
                JOIN products p ON i.product_id = p.id
                WHERE p.category_id = $1
            """, cat['id'])
            
            print(f"   {cat['name']}: {product_count} productos, {image_count} imágenes")
        
        # 3. Diagnóstico de configuración CLIP
        print(f"\n🤖 DIAGNÓSTICO CONFIGURACIÓN CLIP:")
        print("-" * 60)
        
        sin_name_en = sum(1 for cat in categories if not cat['name_en'])
        sin_clip_prompt = sum(1 for cat in categories if not cat['clip_prompt'])
        sin_alternative_terms = sum(1 for cat in categories if not cat['alternative_terms'])
        
        print(f"   ⚠️  Sin name_en: {sin_name_en}/{total_categories}")
        print(f"   ⚠️  Sin clip_prompt: {sin_clip_prompt}/{total_categories}")
        print(f"   ⚠️  Sin términos alternativos: {sin_alternative_terms}/{total_categories}")
        
        # 4. Recomendaciones
        print(f"\n💡 RECOMENDACIONES:")
        print("-" * 60)
        
        if sin_name_en > 0:
            print(f"   🔧 Configurar name_en para {sin_name_en} categorías")
            print(f"      Ejemplo: 'GORRAS' → name_en: 'caps, hats, baseball caps'")
        
        if sin_clip_prompt > 0:
            print(f"   🔧 Configurar clip_prompt para {sin_clip_prompt} categorías")
            print(f"      Ejemplo: 'a photo of a baseball cap or hat worn on the head'")
        
        if sin_alternative_terms > 0:
            print(f"   🔧 Configurar alternative_terms para {sin_alternative_terms} categorías")
            print(f"      Ejemplo: 'gorro,boina,sombrero,gorra deportiva'")
        
        print(f"\n🎯 PRÓXIMOS PASOS:")
        print(f"   1. Configurar alias faltantes en admin panel")
        print(f"   2. Implementar detección de categoría con CLIP")
        print(f"   3. Búsqueda filtrada por categoría detectada")
        
        return {
            'total_categories': total_categories,
            'sin_name_en': sin_name_en,
            'sin_clip_prompt': sin_clip_prompt,
            'categories': categories
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await conn.close()

if __name__ == "__main__":
    result = asyncio.run(check_categories_aliases())
    if result:
        print(f"\n✅ Verificación completada:")
        print(f"   - {result['total_categories']} categorías encontradas")
        print(f"   - {result['sin_name_en']} sin name_en")
        print(f"   - {result['sin_clip_prompt']} sin clip_prompt")
    else:
        print("\n💥 Error en verificación")