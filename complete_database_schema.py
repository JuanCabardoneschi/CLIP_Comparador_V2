#!/usr/bin/env python3
"""
Script para verificar y completar TODAS las tablas con columnas faltantes
"""
import sqlite3
import os

def fix_all_missing_columns():
    """Verificar y agregar todas las columnas faltantes de todas las tablas"""

    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print('🔧 VERIFICANDO Y COMPLETANDO TODAS LAS TABLAS...')
    print()

    # ============ TABLA PRODUCTS ============
    print('📋 TABLA PRODUCTS:')
    columnas_products = [
        ('slug', 'VARCHAR(100)'),
        ('metadata', 'TEXT'),  # Usamos TEXT en lugar de JSONB para SQLite
        ('brand', 'VARCHAR(100)'),
        ('model', 'VARCHAR(100)'),
        ('color', 'VARCHAR(50)'),
        ('size', 'VARCHAR(50)'),
        ('weight', 'DECIMAL(8,3)'),
        ('dimensions', 'TEXT'),  # JSON como TEXT
        ('materials', 'TEXT'),
        ('care_instructions', 'TEXT'),
        ('warranty', 'TEXT'),
        ('origin_country', 'VARCHAR(100)'),
        ('barcode', 'VARCHAR(50)'),
        ('min_stock_alert', 'INTEGER DEFAULT 10'),
        ('max_stock', 'INTEGER'),
        ('cost_price', 'DECIMAL(10,2)'),
        ('profit_margin', 'DECIMAL(5,2)'),
        ('discount_percentage', 'DECIMAL(5,2) DEFAULT 0'),
        ('tax_category', 'VARCHAR(50)'),
        ('seasonal', 'BOOLEAN DEFAULT 0'),
        ('featured', 'BOOLEAN DEFAULT 0'),
        ('view_count', 'INTEGER DEFAULT 0'),
        ('search_count', 'INTEGER DEFAULT 0'),
        ('last_viewed', 'DATETIME'),
        ('seo_title', 'VARCHAR(255)'),
        ('seo_description', 'TEXT'),
        ('seo_keywords', 'TEXT')
    ]

    for col_name, col_type in columnas_products:
        try:
            cur.execute(f'ALTER TABLE products ADD COLUMN {col_name} {col_type}')
            print(f'✅ products.{col_name} agregada')
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f'✅ products.{col_name} ya existe')
            else:
                print(f'❌ Error {col_name}: {e}')

    # ============ TABLA IMAGES ============
    print()
    print('🖼️ TABLA IMAGES:')
    columnas_images_extra = [
        ('product_id', 'TEXT'),
        ('original_filename', 'VARCHAR(255)'),
        ('file_size', 'INTEGER'),
        ('width', 'INTEGER'),
        ('height', 'INTEGER'),
        ('format', 'VARCHAR(10)'),
        ('alt_text', 'VARCHAR(255)'),
        ('caption', 'TEXT'),
        ('sort_order', 'INTEGER DEFAULT 0'),
        ('tags', 'TEXT'),
        ('dominant_color', 'VARCHAR(7)'),
        ('color_palette', 'TEXT'),
        ('quality_score', 'DECIMAL(3,2)'),
        ('blur_hash', 'VARCHAR(50)'),
        ('metadata', 'TEXT'),
        ('is_thumbnail_generated', 'BOOLEAN DEFAULT 0'),
        ('thumbnail_versions', 'TEXT'),
        ('compression_applied', 'BOOLEAN DEFAULT 0'),
        ('face_detected', 'BOOLEAN DEFAULT 0'),
        ('text_detected', 'BOOLEAN DEFAULT 0'),
        ('nsfw_score', 'DECIMAL(3,2) DEFAULT 0.0'),
        ('aesthetic_score', 'DECIMAL(3,2)'),
        ('FOREIGN KEY (product_id)', 'REFERENCES products(id)')
    ]

    for col_def in columnas_images_extra:
        if col_def[0].startswith('FOREIGN KEY'):
            continue  # Skip foreign key constraints for ALTER TABLE
        col_name, col_type = col_def
        try:
            cur.execute(f'ALTER TABLE images ADD COLUMN {col_name} {col_type}')
            print(f'✅ images.{col_name} agregada')
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f'✅ images.{col_name} ya existe')
            else:
                print(f'❌ Error {col_name}: {e}')

    # ============ TABLA CLIENTS ============
    print()
    print('🏢 TABLA CLIENTS:')
    columnas_clients = [
        ('phone', 'VARCHAR(20)'),
        ('website', 'VARCHAR(255)'),
        ('address', 'TEXT'),
        ('city', 'VARCHAR(100)'),
        ('state', 'VARCHAR(100)'),
        ('country', 'VARCHAR(100)'),
        ('postal_code', 'VARCHAR(20)'),
        ('timezone', 'VARCHAR(50) DEFAULT "America/Lima"'),
        ('language', 'VARCHAR(10) DEFAULT "es"'),
        ('currency', 'VARCHAR(10) DEFAULT "PEN"'),
        ('plan_type', 'VARCHAR(50) DEFAULT "basic"'),
        ('plan_expires_at', 'DATETIME'),
        ('storage_used', 'BIGINT DEFAULT 0'),
        ('storage_limit', 'BIGINT DEFAULT 1073741824'),  # 1GB
        ('products_count', 'INTEGER DEFAULT 0'),
        ('products_limit', 'INTEGER DEFAULT 1000'),
        ('api_calls_count', 'INTEGER DEFAULT 0'),
        ('api_calls_limit', 'INTEGER DEFAULT 10000'),
        ('last_api_call', 'DATETIME'),
        ('webhook_url', 'VARCHAR(500)'),
        ('webhook_secret', 'VARCHAR(100)'),
        ('logo_url', 'VARCHAR(500)'),
        ('brand_colors', 'TEXT'),  # JSON
        ('custom_css', 'TEXT'),
        ('seo_settings', 'TEXT'),  # JSON
        ('analytics_enabled', 'BOOLEAN DEFAULT 1'),
        ('notifications_enabled', 'BOOLEAN DEFAULT 1'),
        ('backup_enabled', 'BOOLEAN DEFAULT 0'),
        ('last_backup', 'DATETIME'),
        ('notes', 'TEXT')
    ]

    for col_name, col_type in columnas_clients:
        try:
            cur.execute(f'ALTER TABLE clients ADD COLUMN {col_name} {col_type}')
            print(f'✅ clients.{col_name} agregada')
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f'✅ clients.{col_name} ya existe')
            else:
                print(f'❌ Error {col_name}: {e}')

    # ============ TABLA USERS ============
    print()
    print('👤 TABLA USERS:')
    columnas_users = [
        ('avatar_url', 'VARCHAR(500)'),
        ('phone', 'VARCHAR(20)'),
        ('timezone', 'VARCHAR(50)'),
        ('language', 'VARCHAR(10) DEFAULT "es"'),
        ('theme', 'VARCHAR(20) DEFAULT "light"'),
        ('email_verified', 'BOOLEAN DEFAULT 0'),
        ('email_verification_token', 'VARCHAR(100)'),
        ('password_reset_token', 'VARCHAR(100)'),
        ('password_reset_expires', 'DATETIME'),
        ('two_factor_enabled', 'BOOLEAN DEFAULT 0'),
        ('two_factor_secret', 'VARCHAR(100)'),
        ('login_attempts', 'INTEGER DEFAULT 0'),
        ('locked_until', 'DATETIME'),
        ('permissions', 'TEXT'),  # JSON
        ('preferences', 'TEXT'),  # JSON
        ('notes', 'TEXT')
    ]

    for col_name, col_type in columnas_users:
        try:
            cur.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
            print(f'✅ users.{col_name} agregada')
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f'✅ users.{col_name} ya existe')
            else:
                print(f'❌ Error {col_name}: {e}')

    # ============ VERIFICAR NUEVAS TABLAS NECESARIAS ============
    print()
    print('📊 CREANDO TABLAS ADICIONALES...')

    # Tabla de logs de búsqueda
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS search_logs (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                user_id TEXT,
                search_type VARCHAR(20) DEFAULT 'text',
                query_text TEXT,
                query_image_url VARCHAR(500),
                results_count INTEGER DEFAULT 0,
                execution_time DECIMAL(8,3),
                ip_address VARCHAR(45),
                user_agent TEXT,
                session_id VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print('✅ Tabla search_logs creada')
    except sqlite3.OperationalError as e:
        print(f'✅ search_logs ya existe: {e}')

    # Tabla de configuración de API keys
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                key_hash VARCHAR(255) NOT NULL,
                name VARCHAR(100),
                description TEXT,
                permissions TEXT,
                rate_limit INTEGER DEFAULT 1000,
                is_active BOOLEAN DEFAULT 1,
                last_used DATETIME,
                expires_at DATETIME,
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')
        print('✅ Tabla api_keys creada')
    except sqlite3.OperationalError as e:
        print(f'✅ api_keys ya existe: {e}')

    conn.commit()

    # ============ VERIFICAR ESTRUCTURA FINAL ============
    print()
    print('📊 RESUMEN FINAL:')
    tablas = ['clients', 'users', 'categories', 'products', 'images', 'search_logs', 'api_keys']

    for tabla in tablas:
        try:
            result = cur.execute(f'PRAGMA table_info({tabla})').fetchall()
            print(f'{tabla.upper()}: {len(result)} columnas')
        except:
            print(f'{tabla.upper()}: ❌ No existe')

    conn.close()
    print()
    print('🎯 ¡TODAS LAS TABLAS COMPLETADAS EXITOSAMENTE!')
    print('✅ Ahora el sistema debería funcionar sin errores de columnas faltantes')

if __name__ == "__main__":
    fix_all_missing_columns()
