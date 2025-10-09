#!/usr/bin/env python3
"""
Script para agregar columnas faltantes a la base de datos
"""
import sqlite3
import os

def fix_database():
    """Agregar columnas faltantes"""

    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print('🔧 Agregando columnas faltantes...')

    # Agregar api_settings a clients
    try:
        cur.execute('ALTER TABLE clients ADD COLUMN api_settings TEXT DEFAULT "{}"')
        print('✅ clients.api_settings agregada')
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
            print('✅ clients.api_settings ya existe')
        else:
            print(f'❌ Error api_settings: {e}')

    # Agregar columnas faltantes a images
    columnas_images = [
        ('cloudinary_url', 'TEXT'),
        ('cloudinary_public_id', 'TEXT'),
        ('mime_type', 'TEXT'),
        ('is_primary', 'BOOLEAN DEFAULT 0'),
        ('is_processed', 'BOOLEAN DEFAULT 0'),
        ('clip_embedding', 'TEXT'),
        ('upload_status', 'TEXT DEFAULT "pending"'),
        ('error_message', 'TEXT'),
        ('updated_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP')
    ]

    for col_name, col_type in columnas_images:
        try:
            cur.execute(f'ALTER TABLE images ADD COLUMN {col_name} {col_type}')
            print(f'✅ images.{col_name} agregada')
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f'✅ images.{col_name} ya existe')
            else:
                print(f'❌ Error {col_name}: {e}')

    conn.commit()

    # Verificar estructura final
    print()
    print('📊 ESTRUCTURA FINAL DE CLIENTS:')
    result = cur.execute('PRAGMA table_info(clients)').fetchall()
    for col in result:
        print(f'  - {col[1]} ({col[2]})')

    print()
    print('📊 ESTRUCTURA FINAL DE IMAGES:')
    result = cur.execute('PRAGMA table_info(images)').fetchall()
    for col in result:
        print(f'  - {col[1]} ({col[2]})')

    conn.close()
    print()
    print('🎯 Columnas actualizadas exitosamente!')

if __name__ == "__main__":
    fix_database()
