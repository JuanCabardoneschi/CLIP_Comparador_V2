#!/usr/bin/env python3
"""
Script para agregar columnas faltantes a la tabla categories
"""
import sqlite3
import os

def fix_categories_table():
    """Agregar columnas faltantes a categories"""

    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print('🔧 Agregando columnas faltantes a CATEGORIES...')

    # Columnas faltantes en categories según el error
    columnas_categories = [
        ('name_en', 'TEXT'),
        ('alternative_terms', 'TEXT'),
        ('clip_prompt', 'TEXT'),
        ('visual_features', 'TEXT'),
        ('confidence_threshold', 'REAL DEFAULT 0.8'),
        ('color', 'TEXT DEFAULT "#007bff"'),
        ('updated_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP')
    ]

    for col_name, col_type in columnas_categories:
        try:
            cur.execute(f'ALTER TABLE categories ADD COLUMN {col_name} {col_type}')
            print(f'✅ categories.{col_name} agregada')
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f'✅ categories.{col_name} ya existe')
            else:
                print(f'❌ Error {col_name}: {e}')

    conn.commit()

    # Verificar estructura final
    print()
    print('📊 ESTRUCTURA FINAL DE CATEGORIES:')
    result = cur.execute('PRAGMA table_info(categories)').fetchall()
    for col in result:
        print(f'  - {col[1]} ({col[2]})')

    conn.close()
    print()
    print('🎯 Tabla categories actualizada exitosamente!')

if __name__ == "__main__":
    fix_categories_table()
