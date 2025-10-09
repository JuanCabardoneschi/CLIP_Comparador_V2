#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para identificar imágenes huérfanas (sin producto asociado)
"""

import sqlite3
import os
from pathlib import Path

def find_orphaned_images():
    """Encontrar imágenes que no están asociadas a ningún producto"""
    print("🔍 BUSCANDO IMÁGENES HUÉRFANAS...")
    print()

    # Ruta del directorio de imágenes
    images_dir = Path("./clip_admin_backend/static/uploads/clients/demo_fashion_store")

    # Obtener todos los archivos de imagen del directorio
    if not images_dir.exists():
        print(f"❌ El directorio no existe: {images_dir}")
        return

    # Listar todos los archivos de imagen
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
        image_files.extend(images_dir.glob(ext))

    print(f"📁 Total de archivos en el directorio: {len(image_files)}")

    # Conectar a la base de datos
    db_path = Path("./clip_admin_backend/instance/clip_comparador_v2.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Obtener todas las imágenes registradas en la base de datos
        query = "SELECT filename FROM images"
        cursor.execute(query)
        db_images = {row[0] for row in cursor.fetchall()}

        print(f"🗄️ Total de imágenes en la base de datos: {len(db_images)}")
        print()

        # Encontrar archivos huérfanos (en directorio pero no en BD)
        orphaned_files = []
        for image_file in image_files:
            filename = image_file.name
            if filename not in db_images:
                orphaned_files.append(filename)

        # Encontrar registros huérfanos (en BD pero no en directorio)
        missing_files = []
        for db_image in db_images:
            image_path = images_dir / db_image
            if not image_path.exists():
                missing_files.append(db_image)

        # Mostrar resultados
        print("📊 RESULTADOS DEL ANÁLISIS:")
        print(f"   • Archivos en directorio: {len(image_files)}")
        print(f"   • Registros en base de datos: {len(db_images)}")
        print(f"   • Archivos huérfanos (sin producto): {len(orphaned_files)}")
        print(f"   • Registros sin archivo físico: {len(missing_files)}")
        print()

        if orphaned_files:
            print("🗂️ ARCHIVOS HUÉRFANOS (en directorio pero sin producto asociado):")
            for i, filename in enumerate(sorted(orphaned_files), 1):
                # Extraer el nombre base sin UUID
                if '_' in filename:
                    base_name = '_'.join(filename.split('_')[1:])
                else:
                    base_name = filename
                print(f"   {i:2d}. {filename}")
                print(f"       → {base_name}")
            print()
        else:
            print("✅ No hay archivos huérfanos")
            print()

        if missing_files:
            print("⚠️ REGISTROS SIN ARCHIVO FÍSICO:")
            for i, filename in enumerate(sorted(missing_files), 1):
                print(f"   {i:2d}. {filename}")
            print()
        else:
            print("✅ Todos los registros tienen su archivo físico")
            print()

        # Mostrar estadísticas por producto
        product_query = """
        SELECT p.name, COUNT(i.id) as image_count
        FROM products p
        LEFT JOIN images i ON p.id = i.product_id
        GROUP BY p.id, p.name
        ORDER BY image_count DESC, p.name
        """

        cursor.execute(product_query)
        product_stats = cursor.fetchall()

        print("📈 ESTADÍSTICAS POR PRODUCTO:")
        products_with_images = 0
        products_without_images = 0

        for product_name, image_count in product_stats:
            if image_count > 0:
                products_with_images += 1
                print(f"   ✅ {product_name}: {image_count} imagen(es)")
            else:
                products_without_images += 1
                print(f"   ❌ {product_name}: Sin imágenes")

        print()
        print("📊 RESUMEN:")
        print(f"   • Productos con imágenes: {products_with_images}")
        print(f"   • Productos sin imágenes: {products_without_images}")
        print(f"   • Total de productos: {len(product_stats)}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    find_orphaned_images()
