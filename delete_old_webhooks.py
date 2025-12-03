"""
Script simple para eliminar webhooks viejos de Tiendanube
Usa directamente psycopg2 para evitar problemas de Flask
"""
import psycopg2
import requests
from cryptography.fernet import Fernet
import os

# Railway DB credentials
DB_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"
CLIENT_ID = "6aaeb2f7-d4ba-4ec3-bde7-8e7225fe3f08"

# Encryption key (debe ser la misma que usa el sistema)
ENCRYPTION_KEY = os.environ.get('TOKEN_ENCRYPTION_KEY', '5l5GDKVGr3aNEq-6h7sC7OQUL9cUQFSk8Y1_RJcnXBo=')
cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

print("🔍 Conectando a Railway DB...\n")

# Conectar a DB
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Obtener integración
cur.execute("""
    SELECT store_id, access_token
    FROM tiendanube_integrations
    WHERE client_id = %s
""", (CLIENT_ID,))

row = cur.fetchone()
if not row:
    print(f"❌ No se encontró integración para client_id {CLIENT_ID}")
    exit(1)

store_id = row[0]
encrypted_token = row[1]

# Desencriptar token
try:
    access_token = cipher.decrypt(encrypted_token.encode()).decode()
except:
    print("❌ Error desencriptando token")
    exit(1)

print(f"✅ Store ID: {store_id}")
print("✅ Access token obtenido\n")

# Headers para API de Tiendanube
headers = {
    'Authentication': f'bearer {access_token}',
    'User-Agent': 'CLIP Comparador V2'
}

# Listar TODOS los webhooks
print("📋 Listando webhooks en Tiendanube...\n")
print("="*80)

response = requests.get(
    f'https://api.tiendanube.com/v1/{store_id}/webhooks',
    headers=headers,
    timeout=10,
    verify=False
)

if response.status_code != 200:
    print(f"❌ Error: HTTP {response.status_code}")
    exit(1)

webhooks = response.json()
print(f"\n📊 Total webhooks: {len(webhooks)}\n")

webhooks_to_delete = []
webhooks_ok = []

for wh in webhooks:
    wh_id = wh.get('id')
    event = wh.get('event')
    url = wh.get('url')

    print(f"ID: {wh_id} | Event: {event}")
    print(f"   URL: {url}")

    if '/api/webhooks/tiendanube/' in url:
        print(f"   ✅ CORRECTO\n")
        webhooks_ok.append(wh_id)
    else:
        print(f"   ❌ INCORRECTO - SERÁ ELIMINADO\n")
        webhooks_to_delete.append({'id': wh_id, 'event': event, 'url': url})

print("="*80)
print(f"\n📊 Resumen:")
print(f"   ✅ Correctos: {len(webhooks_ok)}")
print(f"   ❌ Incorrectos: {len(webhooks_to_delete)}\n")

if not webhooks_to_delete:
    print("✅ No hay webhooks incorrectos. Todo OK!")
    exit(0)

# Confirmar eliminación
print(f"⚠️  Se eliminarán {len(webhooks_to_delete)} webhooks incorrectos.")
confirm = input("¿Continuar? (si/no): ")

if confirm.lower() != 'si':
    print("❌ Cancelado")
    exit(0)

print(f"\n🗑️  Eliminando webhooks...\n")

for wh in webhooks_to_delete:
    response = requests.delete(
        f'https://api.tiendanube.com/v1/{store_id}/webhooks/{wh["id"]}',
        headers=headers,
        timeout=10,
        verify=False
    )

    if response.status_code == 200:
        print(f"✅ Eliminado: {wh['event']} (ID: {wh['id']})")
    else:
        print(f"❌ Error eliminando {wh['id']}: HTTP {response.status_code}")

print(f"\n✅ Proceso completado!")
print(f"💡 Ahora Tiendanube solo usará los webhooks con URLs correctas (/api/)")

conn.close()
