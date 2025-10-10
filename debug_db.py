#!/usr/bin/env python3
"""
Script para debuggear la base de datos SQLite y verificar URLs de Cloudinary
"""

import sqlite3
import os

# Ruta a la base de datos
db_path = os.path.join("clip_admin_backend", "instance", "clip_comparador_v2.db")

print(f"🔍 Verificando base de datos: {db_path}")
print(f"🔍 ¿Archivo existe? {os.path.exists(db_path)}")

if not os.path.exists(db_path):
    print("❌ Base de datos no encontrada!")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Verificar estructura de tabla images
    print("\n🔍 Estructura de tabla 'images':")
    cursor = conn.execute("PRAGMA table_info(images)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col['name']}: {col['type']}")

    # Verificar si existe columna cloudinary_url
    has_cloudinary = any(col['name'] == 'cloudinary_url' for col in columns)
    print(f"\n🔍 ¿Columna 'cloudinary_url' existe? {has_cloudinary}")

    if has_cloudinary:
        # Verificar datos reales
        print("\n🔍 Primeras 5 imágenes con sus URLs:")
        cursor = conn.execute("""
            SELECT filename, cloudinary_url, is_processed
            FROM images
            LIMIT 5
        """)
        rows = cursor.fetchall()

        for row in rows:
            print(f"  📁 {row['filename']}")
            print(f"     cloudinary_url: {row['cloudinary_url']}")
            print(f"     is_processed: {row['is_processed']}")
            print()

    conn.close()
    print("✅ Verificación completa")

except Exception as e:
    print(f"❌ Error: {e}")
