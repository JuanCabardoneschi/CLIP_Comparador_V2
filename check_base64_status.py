#!/usr/bin/env python3
"""
Verificar estado de base64_data en las imágenes y optimizar rendimiento
"""
import asyncio
import asyncpg

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def check_base64_status():
    """Verificar estado de base64_data en imágenes"""
    
    print("🔍 VERIFICANDO ESTADO DE BASE64 EN IMÁGENES")
    print("=" * 60)
    
    conn = await asyncpg.connect(POSTGRES_URL)
    
    try:
        # 1. Contar imágenes con y sin base64
        print("📊 ESTADO GENERAL:")
        
        total_images = await conn.fetchval("SELECT COUNT(*) FROM images")
        print(f"  Total imágenes: {total_images}")
        
        with_base64 = await conn.fetchval("""
            SELECT COUNT(*) FROM images 
            WHERE base64_data IS NOT NULL AND base64_data != ''
        """)
        print(f"  Con base64_data: {with_base64}")
        
        without_base64 = total_images - with_base64
        print(f"  Sin base64_data: {without_base64}")
        
        percentage = (with_base64 / total_images * 100) if total_images > 0 else 0
        print(f"  Porcentaje completo: {percentage:.1f}%")
        
        # 2. Mostrar ejemplos de imágenes sin base64
        if without_base64 > 0:
            print(f"\n🔍 IMÁGENES SIN BASE64 (primeras 10):")
            missing_base64 = await conn.fetch("""
                SELECT filename, cloudinary_url, product_id
                FROM images 
                WHERE base64_data IS NULL OR base64_data = ''
                LIMIT 10
            """)
            
            for img in missing_base64:
                print(f"  - {img['filename']} | Product: {img['product_id']}")
                print(f"    Cloudinary: {img['cloudinary_url'][:50] if img['cloudinary_url'] else 'NO URL'}...")
        
        # 3. Verificar tamaño promedio de base64
        if with_base64 > 0:
            print(f"\n📏 ANÁLISIS DE TAMAÑO BASE64:")
            avg_size = await conn.fetchval("""
                SELECT AVG(LENGTH(base64_data)) 
                FROM images 
                WHERE base64_data IS NOT NULL AND base64_data != ''
            """)
            print(f"  Tamaño promedio base64: {avg_size:.0f} caracteres")
            
            # Convertir a KB aproximado (base64 es ~33% más grande que binario)
            approx_kb = (avg_size * 0.75) / 1024 if avg_size else 0
            print(f"  Tamaño imagen aproximado: {approx_kb:.1f} KB")
        
        # 4. Verificar embeddings
        print(f"\n🧠 ESTADO DE EMBEDDINGS:")
        with_embeddings = await conn.fetchval("""
            SELECT COUNT(*) FROM images 
            WHERE clip_embedding IS NOT NULL AND clip_embedding != ''
        """)
        print(f"  Con embeddings: {with_embeddings}/{total_images}")
        
        # 5. Diagnóstico de rendimiento
        print(f"\n⚡ DIAGNÓSTICO DE RENDIMIENTO:")
        
        if without_base64 > 0:
            print(f"  ⚠️  PROBLEMA: {without_base64} imágenes sin base64")
            print(f"     Esto causa lentitud porque se descargan de Cloudinary en tiempo real")
        else:
            print(f"  ✅ Todas las imágenes tienen base64 precalculado")
        
        if with_embeddings < total_images:
            missing_embeddings = total_images - with_embeddings
            print(f"  ⚠️  PROBLEMA: {missing_embeddings} imágenes sin embeddings")
        else:
            print(f"  ✅ Todas las imágenes tienen embeddings")
        
        # 6. Recomendaciones
        print(f"\n💡 RECOMENDACIONES:")
        
        if without_base64 > 0:
            print(f"  🔧 Regenerar base64 para {without_base64} imágenes")
            print(f"     Esto mejorará significativamente el tiempo de respuesta")
        
        if with_embeddings < total_images:
            print(f"  🧠 Generar embeddings faltantes")
        
        if without_base64 == 0 and with_embeddings == total_images:
            print(f"  ✅ Sistema optimizado - rendimiento debería ser < 1 segundo")
        
        return {
            'total': total_images,
            'with_base64': with_base64,
            'without_base64': without_base64,
            'with_embeddings': with_embeddings
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await conn.close()

if __name__ == "__main__":
    result = asyncio.run(check_base64_status())
    if result:
        print(f"\n🎯 RESUMEN:")
        print(f"   Base64 completo: {result['with_base64']}/{result['total']}")
        print(f"   Embeddings: {result['with_embeddings']}/{result['total']}")
    else:
        print("\n💥 Error en verificación")