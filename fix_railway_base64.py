#!/usr/bin/env python3
"""
Regenerar base64_data para todas las imágenes (versión simple sin aiohttp)
"""
import asyncio
import asyncpg
import requests
import base64
from io import BytesIO
from PIL import Image
import time

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

def optimize_image_for_base64(image_data, max_size=512):
    """Optimizar imagen para base64 manteniendo calidad visual"""
    try:
        # Abrir imagen
        img = Image.open(BytesIO(image_data))
        
        # Convertir a RGB si es necesario
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Redimensionar manteniendo aspect ratio
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        
        # Guardar optimizada
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85, optimize=True)
        
        return buffer.getvalue()
    except Exception as e:
        print(f"    ⚠️ Error optimizando imagen: {e}")
        return image_data

def download_and_convert_image(image_record):
    """Descargar imagen de Cloudinary y convertir a base64 optimizado"""
    
    image_id = image_record['id']
    filename = image_record['filename']
    cloudinary_url = image_record['cloudinary_url']
    
    print(f"  📥 Procesando: {filename[:50]}...")
    
    try:
        # Descargar imagen
        response = requests.get(cloudinary_url, timeout=30)
        
        if response.status_code == 200:
            image_data = response.content
            
            # Optimizar imagen
            optimized_data = optimize_image_for_base64(image_data)
            
            # Convertir a base64
            base64_string = base64.b64encode(optimized_data).decode('utf-8')
            base64_data = f"data:image/jpeg;base64,{base64_string}"
            
            size_kb = len(optimized_data) / 1024
            print(f"    ✅ Optimizada: {size_kb:.1f} KB")
            
            return {
                'image_id': image_id,
                'base64_data': base64_data,
                'success': True
            }
        else:
            print(f"    ❌ Error HTTP {response.status_code}")
            return {'image_id': image_id, 'success': False, 'error': f'HTTP {response.status_code}'}
            
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return {'image_id': image_id, 'success': False, 'error': str(e)}

async def regenerate_all_base64():
    """Regenerar base64_data para todas las imágenes en PostgreSQL Railway"""
    
    print("🚀 REGENERANDO BASE64 EN POSTGRESQL RAILWAY")
    print("=" * 60)
    
    conn = await asyncpg.connect(POSTGRES_URL)
    
    try:
        # 1. Obtener todas las imágenes sin base64
        print("📋 Obteniendo lista de imágenes desde Railway...")
        
        images = await conn.fetch("""
            SELECT id, filename, cloudinary_url
            FROM images 
            WHERE (base64_data IS NULL OR base64_data = '') 
            AND cloudinary_url IS NOT NULL
            ORDER BY filename
        """)
        
        total_images = len(images)
        print(f"   Total a procesar: {total_images}")
        
        if total_images == 0:
            print("✅ Todas las imágenes ya tienen base64")
            return {'successful': 0, 'failed': 0, 'total_time': 0, 'final_percentage': 100}
        
        # 2. Procesar una por una (versión simple)
        print(f"\n🔄 Procesando imágenes en PostgreSQL Railway...")
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        for i, image_record in enumerate(images, 1):
            print(f"\n📦 Imagen {i}/{total_images}:")
            
            # Procesar imagen
            result = download_and_convert_image(image_record)
            
            if result['success']:
                # Guardar en PostgreSQL Railway
                await conn.execute("""
                    UPDATE images 
                    SET base64_data = $1, updated_at = NOW()
                    WHERE id = $2
                """, result['base64_data'], result['image_id'])
                
                successful += 1
                print(f"    💾 Guardada en Railway PostgreSQL")
            else:
                failed += 1
                print(f"    ❌ Error: {result.get('error', 'Desconocido')}")
            
            # Progreso cada 10 imágenes
            if i % 10 == 0 or i == total_images:
                elapsed = time.time() - start_time
                progress = (i / total_images) * 100
                avg_time = elapsed / i
                estimated_remaining = (total_images - i) * avg_time
                
                print(f"    📊 Progreso: {i}/{total_images} ({progress:.1f}%)")
                print(f"    ⏱️  Tiempo: {elapsed:.1f}s transcurridos, ~{estimated_remaining:.1f}s restantes")
        
        # 3. Resumen final
        total_time = time.time() - start_time
        
        print(f"\n🎯 REGENERACIÓN EN RAILWAY COMPLETADA")
        print(f"=" * 60)
        print(f"✅ Exitosas: {successful}")
        print(f"❌ Fallidas: {failed}")
        print(f"⏱️  Tiempo total: {total_time:.1f} segundos")
        print(f"⚡ Promedio: {total_time/total_images:.2f}s por imagen")
        
        # 4. Verificar resultado final en Railway
        print(f"\n🔍 VERIFICACIÓN FINAL EN RAILWAY:")
        
        total_with_base64 = await conn.fetchval("""
            SELECT COUNT(*) FROM images 
            WHERE base64_data IS NOT NULL AND base64_data != ''
        """)
        
        total_images_db = await conn.fetchval("SELECT COUNT(*) FROM images")
        
        percentage = (total_with_base64 / total_images_db * 100) if total_images_db > 0 else 0
        
        print(f"   Imágenes con base64: {total_with_base64}/{total_images_db} ({percentage:.1f}%)")
        
        if percentage == 100:
            print(f"\n🎉 ¡RAILWAY POSTGRESQL OPTIMIZADO!")
            print(f"   El tiempo de respuesta ahora debería ser < 1 segundo")
        else:
            print(f"\n⚠️  Aún faltan {total_images_db - total_with_base64} imágenes")
        
        return {
            'successful': successful,
            'failed': failed,
            'total_time': total_time,
            'final_percentage': percentage
        }
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await conn.close()

if __name__ == "__main__":
    print("🔧 OPTIMIZADOR DE RENDIMIENTO - RAILWAY POSTGRESQL")
    print("   Regenerando base64 para todas las imágenes en Railway...")
    print()
    
    result = asyncio.run(regenerate_all_base64())
    
    if result:
        print(f"\n✅ Proceso completado en Railway PostgreSQL:")
        print(f"   - {result['successful']} imágenes optimizadas")
        print(f"   - {result['failed']} errores")
        print(f"   - {result['total_time']:.1f} segundos total")
        print(f"   - {result['final_percentage']:.1f}% base64 completo")
        
        if result['final_percentage'] == 100:
            print(f"\n🚀 ¡RAILWAY POSTGRESQL OPTIMIZADO!")
            print(f"   El tiempo de respuesta de la API mejoró significativamente")
    else:
        print("\n💥 Error en optimización de Railway")