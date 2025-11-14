import psycopg2
import uuid
from datetime import datetime

# Conectar a local para obtener los client_ids
local_conn = psycopg2.connect(host='localhost', port=5432, user='postgres', password='Laurana@01', database='clip_comparador_v2')
local_cur = local_conn.cursor()
local_cur.execute(\"\"\"SELECT id, name FROM clients ORDER BY created_at\"\"\")
clients = {name: client_id for client_id, name in local_cur.fetchall()}
print('Clientes en local:')
for name, client_id in clients.items():
    print(f'  {name}: {client_id}')
local_conn.close()

# API Keys de producción (desde demo-store-clean.html)
prod_api_keys = [
    {
        'api_key': 'test-api-key-demo-fashion-store-2024',
        'client_name': 'Goody Store',
        'key_name': 'Demo Fashion Store Key'
    },
    {
        'api_key': 'clip_fe117bcd62de8a1e05a214c5',
        'client_name': 'Eve',
        'key_name': 'Eve Store Key'
    }
]

# Conectar a Railway
railway_conn = psycopg2.connect(
    host='ballast.proxy.rlwy.net',
    port=54363,
    user='postgres',
    password='xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum',
    database='railway'
)
railway_cur = railway_conn.cursor()

# Insertar API keys
print('\nInsertando API keys en Railway:')
for key_data in prod_api_keys:
    client_name = key_data['client_name']
    if client_name not in clients:
        print(f'    Cliente {client_name} no encontrado, saltando...')
        continue
    
    client_id = clients[client_name]
    api_key_id = str(uuid.uuid4())
    
    railway_cur.execute(\"\"\"
        INSERT INTO api_keys (id, client_id, key_name, api_key, is_active, requests_made, rate_limit, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    \"\"\", (
        api_key_id,
        client_id,
        key_data['key_name'],
        key_data['api_key'],
        True,
        0,
        100,
        datetime.now()
    ))
    print(f\"   {key_data['key_name']}: {key_data['api_key']}\")

railway_conn.commit()
railway_conn.close()

print('\n API keys de producción restauradas en Railway!')
