#!/usr/bin/env python3
"""
Script para agregar API keys a los clientes existentes
"""

import uuid
import sqlite3
import os

def main():
    # Conectar a la base de datos
    db_path = './clip_admin_backend/instance/clip_comparador_v2.db'
    if not os.path.exists(db_path):
        print(f"Error: No se encontró la base de datos en {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Agregar columna api_key si no existe
    try:
        cur.execute('ALTER TABLE clients ADD COLUMN api_key TEXT')
        print('✓ Columna api_key agregada a la tabla clients')
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
            print('✓ Columna api_key ya existe')
        else:
            print(f'Error agregando columna: {e}')
            return

    # Generar API keys para clientes sin api_key
    cur.execute('SELECT id, name FROM clients WHERE api_key IS NULL OR api_key = ""')
    clients_without_key = cur.fetchall()

    for client_id, client_name in clients_without_key:
        api_key = str(uuid.uuid4()).replace('-', '')
        cur.execute('UPDATE clients SET api_key = ? WHERE id = ?', (api_key, client_id))
        print(f'✓ API Key generada para {client_name}: {api_key}')

    conn.commit()

    # Mostrar todas las API keys
    cur.execute('SELECT id, name, api_key FROM clients ORDER BY name')
    clients = cur.fetchall()

    print('\n=== API KEYS DE TODOS LOS CLIENTES ===')
    for client_id, name, api_key in clients:
        print(f'{name}: {api_key}')

    conn.close()
    print('\n✓ Base de datos actualizada con éxito!')

if __name__ == '__main__':
    main()
