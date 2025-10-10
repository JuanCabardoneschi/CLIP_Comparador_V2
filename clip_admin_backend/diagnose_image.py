#!/usr/bin/env python3
"""
Diagnóstico completo: ¿De dónde viene la imagen que se ve?
"""

import os
import sqlite3

# Ruta a la base de datos
db_path = os.path.join("instance", "clip_comparador_v2.db")

print(f"🔍 DIAGNÓSTICO COMPLETO DE IMAGEN")
print(f"📁 Base de datos: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Buscar el producto DELANTAL PECHERA INESITA
    cursor = conn.execute("""
        SELECT id, name FROM products 
        WHERE name LIKE '%DELANTAL PECHERA INESITA%'
    """)
    products = cursor.fetchall()
    
    if not products:
        print("❌ Producto no encontrado")
        conn.close()
        exit(1)
    
    product_id = products[0]['id']
    product_name = products[0]['name']
    print(f"✅ Producto: {product_name}")
    
    # Buscar TODAS las imágenes de este producto
    cursor = conn.execute("""
        SELECT id, filename, original_filename, cloudinary_url, cloudinary_public_id, 
               base64_data, upload_status, is_processed, file_size, created_at
        FROM images 
        WHERE product_id = ?
        ORDER BY created_at DESC
    """, (product_id,))
    
    images = cursor.fetchall()
    
    print(f"\n📊 TOTAL IMÁGENES: {len(images)}")
    
    if not images:
        print("❌ No hay imágenes registradas en BD")
        conn.close()
        exit(0)
    
    for i, img in enumerate(images, 1):
        print(f"\n📷 IMAGEN {i}:")
        print(f"  🆔 ID: {img['id']}")
        print(f"  📄 Filename: {img['filename']}")
        print(f"  📄 Original: {img['original_filename']}")
        print(f"  🌐 Cloudinary URL: {'✅ SÍ' if img['cloudinary_url'] else '❌ NO'}")
        print(f"  🏷️ Cloudinary ID: {'✅ SÍ' if img['cloudinary_public_id'] else '❌ NO'}")
        print(f"  💾 Base64 data: {'✅ SÍ' if img['base64_data'] else '❌ NO'}")
        print(f"  📊 Upload status: {img['upload_status']}")
        print(f"  🧠 Is processed: {img['is_processed']}")
        print(f"  📏 File size: {img['file_size']} bytes")
        print(f"  🕐 Created: {img['created_at']}")
        
        # Verificar si existe archivo local
        client_folder = "demo_fashion_store"  # Asumiendo cliente por defecto
        local_path = os.path.join("static", "uploads", "clients", client_folder, img['filename'])
        full_local_path = os.path.join(os.path.dirname(__file__), local_path)
        
        print(f"  📁 Ruta local: {local_path}")
        print(f"  📁 Archivo local existe: {'✅ SÍ' if os.path.exists(full_local_path) else '❌ NO'}")
        
        if os.path.exists(full_local_path):
            file_size = os.path.getsize(full_local_path)
            print(f"  📏 Tamaño archivo local: {file_size} bytes")
        
        # Mostrar URLs de Cloudinary si existen
        if img['cloudinary_url']:
            print(f"  🌐 URL completa: {img['cloudinary_url'][:80]}...")
        
        print(f"  {'='*50}")
    
    conn.close()
    print("\n🎯 CONCLUSIÓN:")
    print("Si la imagen se ve pero no está en Cloudinary:")
    print("1. ✅ Archivo local existe → Se sirve desde static/")
    print("2. ❌ Upload a Cloudinary falló → Revisar logs Flask")
    print("3. ❌ Base64 no se generó → Proceso incompleto")
    
except Exception as e:
    print(f"❌ Error: {e}")
    if 'conn' in locals():
        conn.close()