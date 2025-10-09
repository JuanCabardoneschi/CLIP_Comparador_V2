#!/usr/bin/env python3
"""
Script para verificar URLs de imágenes
"""
import sqlite3

def check_image_urls():
    conn = sqlite3.connect('./clip_admin_backend/instance/clip_comparador_v2.db')
    cur = conn.cursor()

    # Verificar URLs de imágenes de gorras
    result = cur.execute('''
        SELECT i.cloudinary_url, p.name, p.sku
        FROM images i
        JOIN products p ON i.product_id = p.id
        WHERE p.name LIKE "%GORRA%"
        LIMIT 5
    ''').fetchall()

    print('URLs de imágenes de gorras:')
    print('=' * 60)
    for url, name, sku in result:
        print(f'Producto: {name}')
        print(f'SKU: {sku}')
        print(f'URL: {url[:100] if url else "URL vacía"}...')
        print('-' * 40)

    conn.close()

if __name__ == "__main__":
    check_image_urls()
