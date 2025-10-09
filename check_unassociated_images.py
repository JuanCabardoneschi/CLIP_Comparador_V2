#!/usr/bin/env python3
"""
Script para revisar imágenes no asociadas a productos
"""
import sqlite3
import os
import re

def check_unassociated_images():
    """Revisar imágenes que no están asociadas a productos"""

    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    images_path = './clip_admin_backend/static/uploads/clients/demo_fashion_store'

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print('🔍 REVISANDO IMÁGENES NO ASOCIADAS A PRODUCTOS...')
    print()

    # Obtener client_id del cliente demo
    result = cur.execute('SELECT id FROM clients WHERE slug = "demo_fashion_store"').fetchone()
    if not result:
        print('❌ Cliente demo no encontrado')
        conn.close()
        return

    client_id = result[0]
    print(f'✅ Cliente demo encontrado: {client_id}')

    # Obtener todas las imágenes asociadas a productos
    result = cur.execute('''
        SELECT filename FROM images
        WHERE client_id = ? AND product_id IS NOT NULL
    ''', (client_id,)).fetchall()

    images_in_db = set(row[0] for row in result)
    print(f'📊 Imágenes asociadas a productos: {len(images_in_db)}')

    # Obtener todas las imágenes del directorio
    if not os.path.exists(images_path):
        print(f'❌ Directorio no encontrado: {images_path}')
        conn.close()
        return

    all_image_files = [f for f in os.listdir(images_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    print(f'📁 Imágenes totales en directorio: {len(all_image_files)}')
    print()

    # Encontrar imágenes no asociadas
    unassociated_images = []
    for image_file in all_image_files:
        if image_file not in images_in_db:
            unassociated_images.append(image_file)

    print(f'🔍 IMÁGENES NO ASOCIADAS: {len(unassociated_images)}')
    print()

    if unassociated_images:
        # Analizar patrones de las imágenes no asociadas
        patterns = {}

        for image_file in unassociated_images:
            # Extraer el nombre limpio
            clean_name = re.sub(r'^[a-f0-9\-]+_', '', image_file)
            clean_name = re.sub(r'\.(jpg|jpeg|png)$', '', clean_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'\s*\(\d+\)\s*$', '', clean_name)

            # Categorizar por patrón
            if 'GOODY' in clean_name and any(x in clean_name for x in ['0', '2025', '-']):
                pattern = 'CÓDIGOS GOODY'
            elif 'DELANTAL' in clean_name.upper():
                pattern = 'DELANTALES'
            elif 'CAMISA' in clean_name.upper():
                pattern = 'CAMISAS'
            elif 'CHAQUETA' in clean_name.upper():
                pattern = 'CHAQUETAS'
            elif 'CASACA' in clean_name.upper():
                pattern = 'CASACAS'
            elif any(keyword in clean_name.upper() for keyword in ['AMBO', 'CARDIGAN', 'CHALECO', 'BUZO', 'ZAPATO', 'ZUECO', 'GORRO', 'GORRA', 'BOINA']):
                pattern = 'OTRAS PRENDAS'
            else:
                pattern = 'NO CLASIFICADO'

            if pattern not in patterns:
                patterns[pattern] = []
            patterns[pattern].append({
                'filename': image_file,
                'clean_name': clean_name
            })

        # Mostrar por categorías
        for pattern, images in patterns.items():
            print(f'📂 {pattern} ({len(images)} imágenes):')
            for img in images[:10]:  # Mostrar solo las primeras 10
                print(f'  • {img["clean_name"][:60]}...')
                print(f'    📁 {img["filename"][:50]}...')
            if len(images) > 10:
                print(f'  ... y {len(images) - 10} más')
            print()

        # Resumen de recomendaciones
        print('💡 RECOMENDACIONES:')

        goody_codes = patterns.get('CÓDIGOS GOODY', [])
        if goody_codes:
            print(f'  🏷️  {len(goody_codes)} imágenes con códigos GOODY pueden ser:')
            print('     - Catálogos o referencias internas')
            print('     - Imágenes de campañas o promocionales')
            print('     - Fotos de productos sin identificar aún')

        other_products = sum(len(images) for pattern, images in patterns.items()
                           if pattern not in ['CÓDIGOS GOODY', 'NO CLASIFICADO'])
        if other_products:
            print(f'  🛍️  {other_products} imágenes de productos específicos pueden ser:')
            print('     - Duplicados con nombres ligeramente diferentes')
            print('     - Variantes del mismo producto')
            print('     - Productos que no se procesaron correctamente')

        unclassified = patterns.get('NO CLASIFICADO', [])
        if unclassified:
            print(f'  ❓ {len(unclassified)} imágenes sin clasificar necesitan revisión manual')

    else:
        print('✅ ¡Todas las imágenes están asociadas a productos!')

    # Verificar integridad inversa: productos sin imágenes
    result = cur.execute('''
        SELECT p.name, p.sku
        FROM products p
        LEFT JOIN images i ON p.id = i.product_id
        WHERE p.client_id = ? AND i.id IS NULL
    ''', (client_id,)).fetchall()

    products_without_images = result

    print()
    print(f'🖼️  PRODUCTOS SIN IMÁGENES: {len(products_without_images)}')
    if products_without_images:
        for name, sku in products_without_images[:5]:
            print(f'  • {sku}: {name[:50]}...')
        if len(products_without_images) > 5:
            print(f'  ... y {len(products_without_images) - 5} más')

    conn.close()
    print()
    print('🎯 ANÁLISIS COMPLETADO')

if __name__ == "__main__":
    check_unassociated_images()
