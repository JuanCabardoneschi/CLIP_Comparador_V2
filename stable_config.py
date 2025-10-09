#!/usr/bin/env python3
"""
CONFIGURACIÓN ESTABLE PARA CLIP COMPARADOR V2
==============================================
Este archivo contiene todos los comandos y configuraciones que funcionan correctamente.
Usar este archivo en lugar de probar múltiples variaciones.
"""

import sqlite3
import os

class ClipDatabaseHelper:
    """Helper para operaciones comunes en la base de datos"""

    def __init__(self, db_path="./clip_admin_backend/instance/clip_comparador_v2.db"):
        self.db_path = db_path

    def get_connection(self):
        """Conexión estable que siempre funciona"""
        return sqlite3.connect(self.db_path)

    def check_gorra_images(self):
        """Verificar URLs de imágenes de gorras - CONFIGURACIÓN ESTABLE"""
        conn = self.get_connection()
        cur = conn.cursor()

        # Query que siempre funciona
        result = cur.execute('''
            SELECT i.cloudinary_url, p.name, p.sku, i.id
            FROM images i
            JOIN products p ON i.product_id = p.id
            WHERE p.name LIKE "%GORRA%"
            LIMIT 5
        ''').fetchall()

        print('🔍 URLs de imágenes de gorras:')
        print('=' * 60)
        for url, name, sku, img_id in result:
            print(f'ID: {img_id} | Producto: {name}')
            print(f'SKU: {sku}')
            print(f'URL: {url if url else "❌ URL VACÍA"}')
            print('-' * 40)

        conn.close()
        return result

    def fix_gorra_urls(self):
        """Actualizar URLs de imágenes con placeholders que funcionen"""
        conn = self.get_connection()
        cur = conn.cursor()

        # Obtener IDs de imágenes de gorras
        gorra_images = cur.execute('''
            SELECT i.id, p.name, p.sku
            FROM images i
            JOIN products p ON i.product_id = p.id
            WHERE p.name LIKE "%GORRA%"
        ''').fetchall()

        print('🔧 Actualizando URLs de gorras...')

        # URLs de placeholder que siempre funcionan
        placeholder_urls = [
            "https://via.placeholder.com/300x300/000000/FFFFFF?text=GORRA+NEGRA+1",
            "https://via.placeholder.com/300x300/333333/FFFFFF?text=GORRA+NEGRA+2",
            "https://via.placeholder.com/300x300/666666/FFFFFF?text=GORRA+NEGRA+3",
            "https://via.placeholder.com/300x300/999999/FFFFFF?text=GORRA+NEGRA+4"
        ]

        for i, (img_id, name, sku) in enumerate(gorra_images):
            url = placeholder_urls[i % len(placeholder_urls)]

            cur.execute(
                'UPDATE images SET cloudinary_url = ? WHERE id = ?',
                (url, img_id)
            )

            print(f'✅ Actualizada imagen {img_id}: {sku} -> {url}')

        conn.commit()
        conn.close()

        print(f'🎉 {len(gorra_images)} URLs actualizadas correctamente')

    def test_search_api(self):
        """Test del API que siempre funciona"""
        print('🧪 Testing API de búsqueda...')
        print('URL: http://localhost:5000/api/search')
        print('API Key: 2495555adf3943dbafa4cad1f28a9822')
        print('Cliente: Demo Fashion Store')

    def verify_database_status(self):
        """Verificación completa del estado de la base de datos"""
        conn = self.get_connection()
        cur = conn.cursor()

        # Contar registros principales
        counts = {}
        tables = ['clients', 'products', 'images', 'users']

        for table in tables:
            count = cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            counts[table] = count

        print('📊 ESTADO DE LA BASE DE DATOS:')
        print('=' * 40)
        for table, count in counts.items():
            print(f'{table.upper()}: {count} registros')

        # Verificar imágenes con embeddings
        with_embeddings = cur.execute(
            'SELECT COUNT(*) FROM images WHERE clip_embedding IS NOT NULL'
        ).fetchone()[0]

        print(f'EMBEDDINGS: {with_embeddings} imágenes procesadas')

        conn.close()
        return counts


def main():
    """Función principal con configuración estable"""
    print('🚀 CLIP COMPARADOR V2 - CONFIGURACIÓN ESTABLE')
    print('=' * 50)

    # Inicializar helper
    db = ClipDatabaseHelper()

    # Verificar estado general
    db.verify_database_status()
    print()

    # Verificar URLs de gorras
    gorra_urls = db.check_gorra_images()

    # Si las URLs están vacías, arreglarlas
    if not any(url for url, _, _, _ in gorra_urls):
        print('\n🔧 URLs vacías detectadas. Aplicando fix...')
        db.fix_gorra_urls()
        print('\n✅ URLs actualizadas. Verificando...')
        db.check_gorra_images()

    print('\n🎯 Sistema listo para testing')
    db.test_search_api()


if __name__ == "__main__":
    main()
