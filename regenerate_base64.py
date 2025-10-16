#!/usr/bin/env python3
"""
Regenerar base64_data para todas las imágenes y optimizar rendimiento
"""
import asyncio
import asyncpg
import aiohttp
import base64
from io import BytesIO
from PIL import Image
import time

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def optimize_image_for_base64(image_data, max_size=512):
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

async def download_and_convert_image(session, image_record):
    """Descargar imagen de Cloudinary y convertir a base64 optimizado"""
    
    image_id = image_record['id']
    filename = image_record['filename']
    cloudinary_url = image_record['cloudinary_url']
    
    print(f"  📥 Procesando: {filename[:50]}...")
    
    try:
        # Descargar imagen
        async with session.get(cloudinary_url) as response:
            if response.status == 200:
                image_data = await response.read()
                
                # Optimizar imagen
                optimized_data = await optimize_image_for_base64(image_data)
                
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
                print(f"    ❌ Error HTTP {response.status}")
                return {'image_id': image_id, 'success': False, 'error': f'HTTP {response.status}'}
                
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return {'image_id': image_id, 'success': False, 'error': str(e)}

async def regenerate_all_base64():
    """Regenerar base64_data para todas las imágenes"""
    
    print("🚀 INICIANDO REGENERACIÓN DE BASE64")
    print("=" * 60)
    
    conn = await asyncpg.connect(POSTGRES_URL)
    
    try:
        # 1. Obtener todas las imágenes sin base64
        print("📋 Obteniendo lista de imágenes...")
        
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
            return
        
        # 2. Procesar en lotes para evitar sobrecarga
        print(f"\n🔄 Procesando imágenes...")
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        # Crear sesión HTTP reutilizable
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            
            # Procesar en lotes de 5
            batch_size = 5
            
            for i in range(0, total_images, batch_size):
                batch = images[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (total_images + batch_size - 1) // batch_size
                
                print(f"\n📦 Lote {batch_num}/{total_batches} ({len(batch)} imágenes):")
                
                # Procesar lote en paralelo
                tasks = [download_and_convert_image(session, img) for img in batch]
                results = await asyncio.gather(*tasks)
                
                # Guardar resultados exitosos
                updates = []
                for result in results:
                    if result['success']:
                        updates.append((result['base64_data'], result['image_id']))
                        successful += 1
                    else:
                        failed += 1
                        print(f"    ❌ Falló imagen ID: {result['image_id']}")
                
                # Actualizar en lote
                if updates:
                    await conn.executemany("""
                        UPDATE images 
                        SET base64_data = $1, updated_at = NOW()
                        WHERE id = $2
                    """, updates)
                    print(f"    💾 Guardadas: {len(updates)} imágenes")
                
                # Progreso
                processed = min(i + batch_size, total_images)
                elapsed = time.time() - start_time
                progress = (processed / total_images) * 100
                
                print(f"    📊 Progreso: {processed}/{total_images} ({progress:.1f}%) - {elapsed:.1f}s transcurridos")
                
                # Pausa breve entre lotes
                if batch_num < total_batches:
                    await asyncio.sleep(1)
        
        # 3. Resumen final
        total_time = time.time() - start_time
        
        print(f"\n🎯 REGENERACIÓN COMPLETADA")
        print(f"=" * 60)
        print(f"✅ Exitosas: {successful}")
        print(f"❌ Fallidas: {failed}")
        print(f"⏱️  Tiempo total: {total_time:.1f} segundos")
        print(f"⚡ Promedio: {total_time/total_images:.2f}s por imagen")
        
        # 4. Verificar resultado final
        print(f"\n🔍 VERIFICACIÓN FINAL:")
        
        total_with_base64 = await conn.fetchval("""
            SELECT COUNT(*) FROM images 
            WHERE base64_data IS NOT NULL AND base64_data != ''
        """)
        
        total_images_db = await conn.fetchval("SELECT COUNT(*) FROM images")
        
        percentage = (total_with_base64 / total_images_db * 100) if total_images_db > 0 else 0
        
        print(f"   Imágenes con base64: {total_with_base64}/{total_images_db} ({percentage:.1f}%)")
        
        if percentage == 100:
            print(f"\n🎉 ¡OPTIMIZACIÓN COMPLETA!")
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
    print("🔧 OPTIMIZADOR DE RENDIMIENTO CLIP")
    print("   Regenerando base64 para todas las imágenes...")
    print()
    
    result = asyncio.run(regenerate_all_base64())
    
    if result:
        print(f"\n✅ Proceso completado:")
        print(f"   - {result['successful']} imágenes optimizadas")
        print(f"   - {result['failed']} errores")
        print(f"   - {result['total_time']:.1f} segundos total")
        print(f"   - {result['final_percentage']:.1f}% base64 completo")
        
        if result['final_percentage'] == 100:
            print(f"\n🚀 ¡SISTEMA OPTIMIZADO! Tiempo de respuesta mejorado significativamente")
    else:
        print("\n💥 Error en optimización")