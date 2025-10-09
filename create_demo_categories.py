#!/usr/bin/env python3
"""
Script para crear categorías del cliente demo con traducciones al inglés
"""
import sqlite3
import uuid
from datetime import datetime

def create_demo_categories():
    """Crear categorías para el cliente demo con traducciones al inglés"""

    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print('🏷️ CREANDO CATEGORÍAS PARA CLIENTE DEMO...')
    print()

    # Obtener el client_id del cliente demo
    result = cur.execute('SELECT id FROM clients WHERE slug = "demo_fashion_store"').fetchone()
    if not result:
        print('❌ Cliente demo no encontrado')
        conn.close()
        return

    client_id = result[0]
    print(f'✅ Cliente demo encontrado: {client_id}')
    print()

    # Categorías con traducciones al inglés
    categorias = [
        {
            'name': 'DELANTAL',
            'name_en': 'APRON',
            'description': 'Delantales para protección y uniformes',
            'clip_prompt': 'apron, protective clothing, kitchen apron, work apron',
            'color': '#FF6B6B'
        },
        {
            'name': 'AMBO VESTIR HOMBRE – DAMA',
            'name_en': 'FORMAL SCRUBS MEN - WOMEN',
            'description': 'Ambos de vestir para hombres y mujeres',
            'clip_prompt': 'formal scrubs, medical uniform, professional clothing, healthcare attire',
            'color': '#4ECDC4'
        },
        {
            'name': 'CAMISAS HOMBRE- DAMA',
            'name_en': 'SHIRTS MEN - WOMEN',
            'description': 'Camisas para hombres y mujeres',
            'clip_prompt': 'shirt, dress shirt, formal shirt, business shirt, blouse',
            'color': '#45B7D1'
        },
        {
            'name': 'CASACAS',
            'name_en': 'COATS',
            'description': 'Casacas y abrigos',
            'clip_prompt': 'coat, jacket, outerwear, blazer, formal jacket',
            'color': '#96CEB4'
        },
        {
            'name': 'ZUECOS',
            'name_en': 'CLOGS',
            'description': 'Zuecos y calzado especializado',
            'clip_prompt': 'clogs, medical shoes, comfort shoes, professional footwear',
            'color': '#FECA57'
        },
        {
            'name': 'GORROS – GORRAS',
            'name_en': 'HATS - CAPS',
            'description': 'Gorros, gorras y accesorios para la cabeza',
            'clip_prompt': 'hat, cap, medical cap, surgical cap, beanie, headwear',
            'color': '#FF9FF3'
        },
        {
            'name': 'CARDIGAN HOMBRE – DAMA',
            'name_en': 'CARDIGAN MEN - WOMEN',
            'description': 'Cardigans para hombres y mujeres',
            'clip_prompt': 'cardigan, sweater, knit jacket, button-up sweater',
            'color': '#54A0FF'
        },
        {
            'name': 'BUZOS',
            'name_en': 'SWEATSHIRTS',
            'description': 'Buzos y sudaderas',
            'clip_prompt': 'sweatshirt, hoodie, pullover, casual wear, sportswear',
            'color': '#5F27CD'
        },
        {
            'name': 'ZAPATO DAMA',
            'name_en': 'WOMEN SHOES',
            'description': 'Zapatos para mujeres',
            'clip_prompt': 'women shoes, dress shoes, professional shoes, work shoes, heels',
            'color': '#00D2D3'
        },
        {
            'name': 'CHALECO DAMA- HOMBRE',
            'name_en': 'VEST WOMEN - MEN',
            'description': 'Chalecos para mujeres y hombres',
            'clip_prompt': 'vest, waistcoat, sleeveless jacket, formal vest',
            'color': '#FF6348'
        },
        {
            'name': 'CHAQUETAS',
            'name_en': 'JACKETS',
            'description': 'Chaquetas y prendas de abrigo',
            'clip_prompt': 'jacket, blazer, sport jacket, casual jacket, outerwear',
            'color': '#2ED573'
        },
        {
            'name': 'REMERAS',
            'name_en': 'T-SHIRTS',
            'description': 'Remeras y camisetas',
            'clip_prompt': 't-shirt, tee, casual shirt, cotton shirt, polo shirt',
            'color': '#FFA502'
        }
    ]

    # Insertar categorías
    categorias_creadas = 0
    for categoria in categorias:
        # Verificar si ya existe
        existing = cur.execute(
            'SELECT id FROM categories WHERE client_id = ? AND name = ?',
            (client_id, categoria['name'])
        ).fetchone()

        if not existing:
            category_id = str(uuid.uuid4())
            cur.execute('''
                INSERT INTO categories (
                    id, client_id, name, name_en, description,
                    clip_prompt, color, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                category_id,
                client_id,
                categoria['name'],
                categoria['name_en'],
                categoria['description'],
                categoria['clip_prompt'],
                categoria['color'],
                1,  # is_active
                datetime.now(),
                datetime.now()
            ))
            categorias_creadas += 1
            print(f'✅ {categoria["name"]} → {categoria["name_en"]}')
        else:
            print(f'✅ {categoria["name"]} ya existe')

    conn.commit()

    # Verificar categorías creadas
    print()
    print('📊 RESUMEN:')
    result = cur.execute(
        'SELECT name, name_en, color FROM categories WHERE client_id = ? ORDER BY name',
        (client_id,)
    ).fetchall()

    print(f'Total categorías: {len(result)}')
    print(f'Nuevas creadas: {categorias_creadas}')
    print()
    print('🏷️ CATEGORÍAS EN BASE DE DATOS:')
    for name, name_en, color in result:
        print(f'  • {name} → {name_en} ({color})')

    conn.close()
    print()
    print('🎯 ¡CATEGORÍAS DEMO CREADAS EXITOSAMENTE!')

if __name__ == "__main__":
    create_demo_categories()
