#!/usr/bin/env python3
"""
Script para crear productos automáticamente desde las imágenes de Goody
basándose en el patrón de nombres identificado
"""
import sqlite3
import uuid
import os
import re
from datetime import datetime

def extract_product_info_from_filename(filename):
    """Extraer información del producto desde el nombre del archivo"""
    # Remover el UUID y la extensión
    clean_name = re.sub(r'^[a-f0-9\-]+_', '', filename)
    clean_name = re.sub(r'\.(jpg|jpeg|png)$', '', clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\s*\(\d+\)\s*$', '', clean_name)  # Remover (número) del final

    # Mapeo de categorías basado en palabras clave
    category_mapping = {
        'DELANTAL': 'DELANTAL',
        'AMBO': 'AMBO VESTIR HOMBRE – DAMA',
        'CAMISA': 'CAMISAS HOMBRE- DAMA',
        'CASACA': 'CASACAS',
        'ZUECO': 'ZUECOS',
        'GORRO': 'GORROS – GORRAS',
        'GORRA': 'GORROS – GORRAS',
        'BOINA': 'GORROS – GORRAS',
        'CARDIGAN': 'CARDIGAN HOMBRE – DAMA',
        'BUZO': 'BUZOS',
        'ZAPATO': 'ZAPATO DAMA',
        'CHALECO': 'CHALECO DAMA- HOMBRE',
        'CHAQUETA': 'CHAQUETAS'
    }

    # Encontrar categoría
    category = None
    for keyword, cat_name in category_mapping.items():
        if keyword in clean_name.upper():
            category = cat_name
            break

    # Si no encuentra categoría específica, usar patrón general
    if not category:
        if 'GOODY' in clean_name and any(x in clean_name for x in ['0', '2025']):
            # Archivos tipo "GOODY - JUNI0 2025-0238" o "GOODY-0331"
            return None  # Saltar estos archivos por ahora

    # Extraer color
    colors = ['BLANCO', 'BLANCA', 'NEGRO', 'NEGRA', 'AZUL', 'VERDE', 'HABANO', 'TOSTADO',
              'AMARILLO', 'CARAMELO', 'JEAN', 'RAYA']
    detected_color = None
    for color in colors:
        if color in clean_name.upper():
            detected_color = color
            break

    # Generar SKU basado en categoría
    sku_prefixes = {
        'DELANTAL': 'DEL',
        'AMBO VESTIR HOMBRE – DAMA': 'AMB',
        'CAMISAS HOMBRE- DAMA': 'CAM',
        'CASACAS': 'CAS',
        'ZUECOS': 'ZUE',
        'GORROS – GORRAS': 'GOR',
        'CARDIGAN HOMBRE – DAMA': 'CAR',
        'BUZOS': 'BUZ',
        'ZAPATO DAMA': 'ZAP',
        'CHALECO DAMA- HOMBRE': 'CHA',
        'CHAQUETAS': 'CHQ'
    }

    sku_prefix = sku_prefixes.get(category, 'GOD')

    return {
        'name': clean_name,
        'category': category,
        'color': detected_color,
        'sku_prefix': sku_prefix,
        'filename': filename
    }

def create_products_from_images():
    """Crear productos automáticamente desde las imágenes"""

    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    images_path = './clip_admin_backend/static/uploads/clients/demo_fashion_store'

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print('🏭 CREANDO PRODUCTOS DESDE IMÁGENES DE GOODY...')
    print()

    # Obtener client_id del cliente demo
    result = cur.execute('SELECT id FROM clients WHERE slug = "demo_fashion_store"').fetchone()
    if not result:
        print('❌ Cliente demo no encontrado')
        conn.close()
        return

    client_id = result[0]
    print(f'✅ Cliente demo encontrado: {client_id}')

    # Obtener mapeo de categorías por nombre
    categories = {}
    result = cur.execute('SELECT id, name FROM categories WHERE client_id = ?', (client_id,)).fetchall()
    for cat_id, cat_name in result:
        categories[cat_name] = cat_id

    print(f'✅ {len(categories)} categorías disponibles')
    print()

    # Obtener lista de imágenes
    if not os.path.exists(images_path):
        print(f'❌ Directorio de imágenes no encontrado: {images_path}')
        conn.close()
        return

    image_files = [f for f in os.listdir(images_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    print(f'📁 Encontradas {len(image_files)} imágenes')
    print()

    # Contadores
    productos_creados = 0
    productos_saltados = 0
    errores = 0

    # Contadores para SKUs
    sku_counters = {}

    # Procesar cada imagen
    for image_file in image_files:
        try:
            # Extraer información del producto
            product_info = extract_product_info_from_filename(image_file)

            if not product_info or not product_info.get('category'):
                productos_saltados += 1
                print(f'⏭️  Saltado: {image_file[:50]}... (no se pudo categorizar)')
                continue

            category_id = categories.get(product_info['category'])
            if not category_id:
                productos_saltados += 1
                print(f'⏭️  Saltado: {image_file[:50]}... (categoría no encontrada)')
                continue

            # Verificar si ya existe un producto con esta imagen
            existing = cur.execute(
                'SELECT id FROM products WHERE client_id = ? AND name = ?',
                (client_id, product_info['name'])
            ).fetchone()

            if existing:
                productos_saltados += 1
                print(f'⏭️  Ya existe: {product_info["name"][:50]}...')
                continue

            # Generar SKU único
            prefix = product_info['sku_prefix']
            if prefix not in sku_counters:
                sku_counters[prefix] = 1
            else:
                sku_counters[prefix] += 1

            sku = f'GOD-{prefix}-{sku_counters[prefix]:03d}'

            # Crear producto
            product_id = str(uuid.uuid4())

            # Generar descripción automática
            description = f"Producto {product_info['name']} de la línea GOODY."
            if product_info['color']:
                description += f" Color: {product_info['color']}."
            description += f" Categoría: {product_info['category']}."

            # Precio demo (random entre 25 y 150)
            import random
            price = round(random.uniform(25.0, 150.0), 2)

            cur.execute('''
                INSERT INTO products (
                    id, client_id, category_id, name, description, sku,
                    price, stock, brand, color, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product_id,
                client_id,
                category_id,
                product_info['name'],
                description,
                sku,
                price,
                random.randint(10, 100),  # Stock aleatorio
                'GOODY',
                product_info['color'],
                1,  # is_active
                datetime.now(),
                datetime.now()
            ))

            # Crear registro de imagen asociada
            image_id = str(uuid.uuid4())
            image_url = f'/static/uploads/clients/demo_fashion_store/{image_file}'

            cur.execute('''
                INSERT INTO images (
                    id, client_id, product_id, filename, cloudinary_url,
                    is_primary, is_processed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                image_id,
                client_id,
                product_id,
                image_file,
                image_url,
                1,  # is_primary
                1,  # is_processed
                datetime.now(),
                datetime.now()
            ))

            productos_creados += 1
            print(f'✅ {sku}: {product_info["name"][:50]}... → {product_info["category"]}')

        except Exception as e:
            errores += 1
            print(f'❌ Error con {image_file[:30]}...: {str(e)}')

    conn.commit()

    # Resumen final
    print()
    print('📊 RESUMEN DE CREACIÓN:')
    print(f'  ✅ Productos creados: {productos_creados}')
    print(f'  ⏭️  Productos saltados: {productos_saltados}')
    print(f'  ❌ Errores: {errores}')

    # Mostrar distribución por categoría
    print()
    print('📈 DISTRIBUCIÓN POR CATEGORÍA:')
    result = cur.execute('''
        SELECT c.name, COUNT(p.id) as total
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id AND p.client_id = ?
        WHERE c.client_id = ?
        GROUP BY c.id, c.name
        ORDER BY total DESC
    ''', (client_id, client_id)).fetchall()

    for cat_name, total in result:
        print(f'  • {cat_name}: {total} productos')

    conn.close()
    print()
    print('🎯 ¡PRODUCTOS CREADOS EXITOSAMENTE!')
    print('💡 Ahora puedes ver los productos en el panel de administración')

if __name__ == "__main__":
    create_products_from_images()
