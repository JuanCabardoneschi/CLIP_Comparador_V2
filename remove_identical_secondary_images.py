#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para eliminar imágenes secundarias que son idénticas a la principal
"""

import sqlite3
import os
from pathlib import Path

def remove_identical_secondary_images():
    """Eliminar imágenes secundarias que son idénticas a la principal"""
    print("🧹 ELIMINANDO IMÁGENES SECUNDARIAS IDÉNTICAS...")
    print()

    # Conectar a la base de datos
    db_path = Path("./clip_admin_backend/instance/clip_comparador_v2.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    removed_count = 0

    try:
        # Buscar productos con múltiples imágenes
        query = """
        SELECT product_id, COUNT(*) as image_count
        FROM images
        GROUP BY product_id
        HAVING COUNT(*) > 1
        """

        cursor.execute(query)
        products_with_multiple_images = cursor.fetchall()

        print(f"📦 Productos con múltiples imágenes: {len(products_with_multiple_images)}")
        print()

        for product_id, image_count in products_with_multiple_images:
            # Obtener todas las imágenes del producto
            img_query = """
            SELECT id, filename, is_primary
            FROM images
            WHERE product_id = ?
            ORDER BY is_primary DESC, created_at ASC
            """

            cursor.execute(img_query, (product_id,))
            images = cursor.fetchall()

            if len(images) < 2:
                continue

            # Extraer el nombre base del archivo (sin UUID y extensión)
            primary_image = images[0]  # La primera siempre es principal
            primary_filename = primary_image[1]

            # Extraer nombre base del archivo principal
            # Formato: UUID_NOMBRE_ORIGINAL.extension
            if '_' in primary_filename:
                primary_base = '_'.join(primary_filename.split('_')[1:])
            else:
                primary_base = primary_filename

            # Buscar imágenes secundarias con el mismo nombre base
            for img_id, filename, is_primary in images[1:]:  # Saltar la principal
                if '_' in filename:
                    secondary_base = '_'.join(filename.split('_')[1:])
                else:
                    secondary_base = filename

                if primary_base == secondary_base:
                    print("🔍 Imagen duplicada encontrada:")
                    print(f"   Principal: {primary_filename}")
                    print(f"   Secundaria: {filename}")

                    # Eliminar el archivo físico
                    file_path = Path(f"./clip_admin_backend/static/uploads/clients/demo_fashion_store/{filename}")
                    if file_path.exists():
                        try:
                            os.remove(file_path)
                            print(f"   ✅ Archivo eliminado: {filename}")
                        except Exception as e:
                            print(f"   ❌ Error eliminando archivo: {e}")
                    else:
                        print(f"   ⚠️ Archivo no encontrado: {file_path}")

                    # Eliminar el registro de la base de datos
                    try:
                        cursor.execute("DELETE FROM images WHERE id = ?", (img_id,))
                        print("   ✅ Registro eliminado de la base de datos")
                        removed_count += 1
                    except Exception as e:
                        print(f"   ❌ Error eliminando registro: {e}")

                    print()

        # Confirmar cambios
        conn.commit()
        print(f"✅ Proceso completado. {removed_count} imágenes duplicadas eliminadas.")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    remove_identical_secondary_images()
