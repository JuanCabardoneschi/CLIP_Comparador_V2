#!/usr/bin/env python3
"""
Script para eliminar registros duplicados de imágenes en la base de datos
"""
import sqlite3

def remove_duplicate_image_records():
    """Eliminar registros duplicados de imágenes manteniendo solo uno por filename"""

    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print('🧹 ELIMINANDO REGISTROS DUPLICADOS DE IMÁGENES...')
    print()

    # Obtener client_id del cliente demo
    result = cur.execute('SELECT id FROM clients WHERE slug = "demo_fashion_store"').fetchone()
    if not result:
        print('❌ Cliente demo no encontrado')
        conn.close()
        return

    client_id = result[0]
    print(f'✅ Cliente demo encontrado: {client_id}')

    # Buscar imágenes duplicadas por filename
    result = cur.execute('''
        SELECT filename, COUNT(*) as count, GROUP_CONCAT(id) as ids
        FROM images
        WHERE client_id = ?
        GROUP BY filename
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    ''', (client_id,)).fetchall()

    duplicates_found = result
    print(f'🔍 Imágenes con registros duplicados: {len(duplicates_found)}')

    if not duplicates_found:
        print('✅ ¡No se encontraron duplicados!')
        conn.close()
        return

    print()
    total_duplicates_removed = 0

    for filename, count, ids_str in duplicates_found:
        ids = ids_str.split(',')
        print(f'📁 {filename[:50]}... ({count} registros)')

        # Obtener detalles de todos los registros duplicados
        detailed_records = []
        for record_id in ids:
            detail = cur.execute('''
                SELECT id, product_id, is_primary, created_at
                FROM images
                WHERE id = ?
            ''', (record_id,)).fetchone()
            if detail:
                detailed_records.append(detail)

        # Decidir cuál mantener basado en prioridad:
        # 1. El que tiene product_id (está asociado)
        # 2. El que es is_primary = 1
        # 3. El más antiguo (created_at menor)

        keep_record = None
        records_to_delete = []

        # Ordenar por prioridad
        detailed_records.sort(key=lambda x: (
            0 if x[1] is not None else 1,  # product_id no nulo primero
            0 if x[2] == 1 else 1,         # is_primary = 1 primero
            x[3] if x[3] else '9999'       # created_at más antiguo
        ))

        keep_record = detailed_records[0]
        records_to_delete = detailed_records[1:]

        print(f'   ✅ Mantener: ID {keep_record[0]} (product_id: {keep_record[1]}, primary: {keep_record[2]})')

        # Eliminar los registros duplicados
        for record in records_to_delete:
            try:
                cur.execute('DELETE FROM images WHERE id = ?', (record[0],))
                print(f'   🗑️  Eliminado: ID {record[0]} (product_id: {record[1]}, primary: {record[2]})')
                total_duplicates_removed += 1
            except Exception as e:
                print(f'   ❌ Error eliminando ID {record[0]}: {e}')

        print()

    conn.commit()

    # Verificar resultado final
    print(f'📊 RESUMEN:')
    print(f'  🗑️  Registros duplicados eliminados: {total_duplicates_removed}')

    # Contar imágenes totales restantes
    result = cur.execute('SELECT COUNT(*) FROM images WHERE client_id = ?', (client_id,)).fetchone()
    total_images = result[0] if result else 0
    print(f'  📸 Imágenes totales restantes: {total_images}')

    # Verificar que no queden duplicados
    result = cur.execute('''
        SELECT COUNT(*)
        FROM (
            SELECT filename, COUNT(*) as count
            FROM images
            WHERE client_id = ?
            GROUP BY filename
            HAVING COUNT(*) > 1
        )
    ''', (client_id,)).fetchone()

    remaining_duplicates = result[0] if result else 0

    if remaining_duplicates == 0:
        print(f'  ✅ ¡No quedan duplicados!')
    else:
        print(f'  ⚠️  Aún quedan {remaining_duplicates} archivos con duplicados')

    # Mostrar estadísticas de productos con imágenes
    print()
    print('📈 ESTADÍSTICAS FINALES:')

    result = cur.execute('''
        SELECT
            COUNT(DISTINCT p.id) as products_with_images,
            COUNT(i.id) as total_images,
            COUNT(CASE WHEN i.is_primary = 1 THEN 1 END) as primary_images,
            COUNT(CASE WHEN i.is_primary = 0 THEN 1 END) as secondary_images
        FROM products p
        JOIN images i ON p.id = i.product_id
        WHERE p.client_id = ?
    ''', (client_id,)).fetchone()

    if result:
        products_with_images, total_imgs, primary_imgs, secondary_imgs = result
        print(f'  📦 Productos con imágenes: {products_with_images}')
        print(f'  📸 Imágenes totales: {total_imgs}')
        print(f'  🎯 Imágenes primarias: {primary_imgs}')
        print(f'  📷 Imágenes secundarias: {secondary_imgs}')

    conn.close()
    print()
    print('🎯 ¡LIMPIEZA DE DUPLICADOS COMPLETADA!')

if __name__ == "__main__":
    remove_duplicate_image_records()
