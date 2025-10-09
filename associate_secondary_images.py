#!/usr/bin/env python3
"""
Script para asociar imágenes duplicadas como imágenes secundarias de productos existentes
"""
import sqlite3
import uuid
import os
import re
from datetime import datetime
from difflib import SequenceMatcher

def similarity(a, b):
    """Calcular similitud entre dos strings"""
    return SequenceMatcher(None, a, b).ratio()

def normalize_product_name(name):
    """Normalizar nombre de producto para comparación"""
    # Remover UUID y extensión
    clean = re.sub(r'^[a-f0-9\-]+_', '', name)
    clean = re.sub(r'\.(jpg|jpeg|png)$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(\d+\)\s*$', '', clean)  # Remover (número)
    clean = re.sub(r'\.+$', '', clean)  # Remover puntos finales
    return clean.upper().strip()

def associate_secondary_images():
    """Asociar imágenes no asociadas como imágenes secundarias"""

    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    images_path = './clip_admin_backend/static/uploads/clients/demo_fashion_store'

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print('🖼️  ASOCIANDO IMÁGENES SECUNDARIAS...')
    print()

    # Obtener client_id del cliente demo
    result = cur.execute('SELECT id FROM clients WHERE slug = "demo_fashion_store"').fetchone()
    if not result:
        print('❌ Cliente demo no encontrado')
        conn.close()
        return

    client_id = result[0]
    print(f'✅ Cliente demo encontrado: {client_id}')

    # Obtener productos existentes con sus imágenes primarias
    result = cur.execute('''
        SELECT p.id, p.name, p.sku, i.filename as primary_image
        FROM products p
        LEFT JOIN images i ON p.id = i.product_id AND i.is_primary = 1
        WHERE p.client_id = ?
        ORDER BY p.name
    ''', (client_id,)).fetchall()

    existing_products = {}
    for product_id, product_name, sku, primary_image in result:
        normalized_name = normalize_product_name(product_name)
        existing_products[product_id] = {
            'name': product_name,
            'normalized_name': normalized_name,
            'sku': sku,
            'primary_image': primary_image
        }

    print(f'📦 Productos existentes: {len(existing_products)}')

    # Obtener imágenes no asociadas
    result = cur.execute('''
        SELECT filename FROM images
        WHERE client_id = ? AND product_id IS NULL
    ''', (client_id,)).fetchall()

    unassociated_images = [row[0] for row in result]

    # Obtener todas las imágenes del directorio
    all_image_files = [f for f in os.listdir(images_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    # Encontrar imágenes que están en el directorio pero no en la DB
    images_in_db = set()
    all_images_result = cur.execute('SELECT filename FROM images WHERE client_id = ?', (client_id,)).fetchall()
    for row in all_images_result:
        images_in_db.add(row[0])

    unassociated_from_directory = []
    for image_file in all_image_files:
        if image_file not in images_in_db:
            unassociated_from_directory.append(image_file)

    all_unassociated = list(set(unassociated_images + unassociated_from_directory))

    print(f'🔍 Imágenes no asociadas: {len(all_unassociated)}')
    print()

    # Intentar asociar cada imagen no asociada
    associations_made = 0
    new_images_added = 0
    skipped_images = 0

    for image_file in all_unassociated:
        # Normalizar nombre de la imagen
        normalized_image_name = normalize_product_name(image_file)

        # Buscar el producto más similar
        best_match = None
        best_similarity = 0.0
        best_product_id = None

        for product_id, product_data in existing_products.items():
            similarity_score = similarity(normalized_image_name, product_data['normalized_name'])

            if similarity_score > best_similarity and similarity_score >= 0.7:  # Umbral de similitud
                best_similarity = similarity_score
                best_match = product_data
                best_product_id = product_id

        if best_match and best_similarity >= 0.7:
            try:
                # Verificar si la imagen ya existe en la DB
                existing_image = cur.execute(
                    'SELECT id FROM images WHERE client_id = ? AND filename = ?',
                    (client_id, image_file)
                ).fetchone()

                if existing_image:
                    # Actualizar para asociar con el producto
                    cur.execute('''
                        UPDATE images
                        SET product_id = ?, is_primary = 0, updated_at = ?
                        WHERE id = ?
                    ''', (best_product_id, datetime.now(), existing_image[0]))
                    associations_made += 1
                    action = "asociada"
                else:
                    # Crear nueva entrada de imagen
                    image_id = str(uuid.uuid4())
                    image_url = f'/static/uploads/clients/demo_fashion_store/{image_file}'

                    cur.execute('''
                        INSERT INTO images (
                            id, client_id, product_id, filename, cloudinary_url,
                            is_primary, is_processed, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        image_id, client_id, best_product_id, image_file, image_url,
                        0,  # is_primary = False (imagen secundaria)
                        1,  # is_processed
                        datetime.now(), datetime.now()
                    ))
                    new_images_added += 1
                    action = "agregada"

                print(f'✅ {action}: {image_file[:50]}...')
                print(f'   📦 → {best_match["sku"]}: {best_match["name"][:40]}... (similitud: {best_similarity:.2f})')
                print()

            except Exception as e:
                print(f'❌ Error con {image_file[:30]}...: {str(e)}')
                skipped_images += 1
        else:
            # Clasificar por qué no se pudo asociar
            if 'GOODY' in normalized_image_name and any(x in normalized_image_name for x in ['0', '2025', '-']):
                reason = "código de catálogo"
            elif len(normalized_image_name) < 10:
                reason = "nombre muy corto"
            else:
                reason = f"sin coincidencia (mejor: {best_similarity:.2f})"

            print(f'⏭️  Saltada: {image_file[:50]}... ({reason})')
            skipped_images += 1

    conn.commit()

    # Resumen final
    print()
    print('📊 RESUMEN DE ASOCIACIONES:')
    print(f'  ✅ Imágenes asociadas a productos existentes: {associations_made}')
    print(f'  ➕ Nuevas imágenes agregadas: {new_images_added}')
    print(f'  ⏭️  Imágenes saltadas: {skipped_images}')
    print(f'  📝 Total procesadas: {len(all_unassociated)}')

    # Mostrar estadísticas de productos con múltiples imágenes
    print()
    print('📈 PRODUCTOS CON MÚLTIPLES IMÁGENES:')
    result = cur.execute('''
        SELECT p.sku, p.name, COUNT(i.id) as image_count
        FROM products p
        JOIN images i ON p.id = i.product_id
        WHERE p.client_id = ?
        GROUP BY p.id, p.sku, p.name
        HAVING image_count > 1
        ORDER BY image_count DESC
    ''', (client_id,)).fetchall()

    for sku, name, count in result[:10]:
        print(f'  📸 {sku}: {name[:40]}... ({count} imágenes)')

    if len(result) > 10:
        print(f'  ... y {len(result) - 10} productos más con múltiples imágenes')

    conn.close()
    print()
    print('🎯 ¡ASOCIACIÓN DE IMÁGENES SECUNDARIAS COMPLETADA!')
    print('💡 Puedes revisar manualmente los productos en el panel de administración')

if __name__ == "__main__":
    associate_secondary_images()
