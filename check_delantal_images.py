#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar las imágenes del producto DELANTAL
"""

import sqlite3
from pathlib import Path

def check_delantal_images():
    """Verificar las imágenes asociadas al producto DELANTAL"""
    print("🔍 VERIFICANDO IMÁGENES DEL DELANTAL...")
    print()

    # Conectar a la base de datos
    db_path = Path("./clip_admin_backend/instance/clip_comparador_v2.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Buscar el producto delantal
        query = """
        SELECT id, name, sku
        FROM products
        WHERE name LIKE '%DELANTAL%'
        """

        cursor.execute(query)
        products = cursor.fetchall()

        print("📦 PRODUCTOS DELANTAL ENCONTRADOS:")
        for product_id, name, sku in products:
            print(f"   ID: {product_id}")
            print(f"   Nombre: {name}")
            print(f"   SKU: {sku}")
            print()

            # Buscar todas las imágenes de este producto
            img_query = """
            SELECT id, filename, is_primary, created_at
            FROM images
            WHERE product_id = ?
            ORDER BY is_primary DESC, created_at ASC
            """

            cursor.execute(img_query, (product_id,))
            images = cursor.fetchall()

            print(f"🖼️ IMÁGENES ASOCIADAS ({len(images)}):")
            for img_id, filename, is_primary, created_at in images:
                primary_text = "PRINCIPAL" if is_primary else "SECUNDARIA"
                print(f"   • {filename}")
                print(f"     ID: {img_id} | Tipo: {primary_text} | Creado: {created_at}")
            print()

            # Verificar si hay nombres de archivo duplicados (mismo archivo físico)
            filenames = [img[1] for img in images]
            unique_filenames = set(filenames)

            if len(filenames) != len(unique_filenames):
                print("⚠️ PROBLEMA DETECTADO: Hay archivos duplicados!")
                from collections import Counter
                filename_counts = Counter(filenames)
                for filename, count in filename_counts.items():
                    if count > 1:
                        print(f"   📁 {filename} aparece {count} veces")
                print()
            else:
                print("✅ No hay archivos duplicados en este producto")
                print()

        # Verificar si hay imágenes con el mismo nombre base pero IDs diferentes
        print("🔍 VERIFICANDO DUPLICADOS GLOBALES...")
        dup_query = """
        SELECT filename, COUNT(*) as count, GROUP_CONCAT(id) as ids
        FROM images
        GROUP BY filename
        HAVING COUNT(*) > 1
        """

        cursor.execute(dup_query)
        duplicates = cursor.fetchall()

        if duplicates:
            print("⚠️ DUPLICADOS GLOBALES ENCONTRADOS:")
            for filename, count, ids in duplicates:
                print(f"   📁 {filename}: {count} registros (IDs: {ids})")
        else:
            print("✅ No hay duplicados globales")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    check_delantal_images()
