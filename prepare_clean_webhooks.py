"""
Script para limpiar webhooks duplicados usando Flask shell context
"""
import os
import sys

# Cambiar al directorio del backend
os.chdir('clip_admin_backend')
sys.path.insert(0, os.getcwd())

# Cargar variables de entorno de Railway
os.environ['FLASK_ENV'] = 'production'

# Script que se ejecutará en el contexto de Flask
flask_script = """
import requests
from app.models.tiendanube_integration import TiendanubeIntegration

# Buscar la integración
integration = TiendanubeIntegration.query.join(
    TiendanubeIntegration.client
).filter_by(name='Test Clip').first()

if not integration:
    print('❌ No se encontró la integración')
    exit(1)

print(f'✅ Integración encontrada: {integration.id}')
print(f'   Store ID: {integration.store_id}')
print()

# Obtener el token desencriptado
access_token = integration.get_access_token()

headers = {
    'Authentication': f'bearer {access_token}',
    'User-Agent': 'CLIP Comparador V2',
    'Content-Type': 'application/json'
}

# Listar webhooks
print('🔍 Listando webhooks...')
response = requests.get(
    f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks',
    headers=headers,
    timeout=10,
    verify=False
)

if response.status_code != 200:
    print(f'❌ Error: {response.status_code}')
    print(response.text)
    exit(1)

webhooks = response.json()
print(f'📋 Total: {len(webhooks)}')
print()

# Separar
old_whs = []
new_whs = []

for wh in webhooks:
    url = wh.get('url', '')
    event = wh.get('event')
    wh_id = wh.get('id')

    print(f'ID: {wh_id}')
    print(f'Event: {event}')
    print(f'URL: {url}')

    if '/api/webhooks/tiendanube/' not in url:
        old_whs.append(wh)
        print('❌ INCORRECTO')
    else:
        new_whs.append(wh)
        print('✅ CORRECTO')
    print()

if not old_whs:
    print('✅ No hay webhooks para eliminar')
    exit(0)

print(f'🗑️ Webhooks a eliminar: {len(old_whs)}')
print(f'✅ Webhooks a mantener: {len(new_whs)}')
print()

# Confirmar
confirm = input('¿Eliminar webhooks incorrectos? (s/n): ')
if confirm.lower() != 's':
    print('❌ Cancelado')
    exit(0)

# Eliminar
deleted = 0
for wh in old_whs:
    wh_id = wh['id']
    event = wh['event']

    print(f'Eliminando: {event} (ID: {wh_id})')

    del_resp = requests.delete(
        f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks/{wh_id}',
        headers=headers,
        timeout=10,
        verify=False
    )

    if del_resp.status_code == 200:
        print('✅ Eliminado')
        deleted += 1
    else:
        print(f'❌ Error: {del_resp.status_code}')

print()
print(f'🎉 Completado: {deleted}/{len(old_whs)} eliminados')
"""

# Guardar el script en un archivo temporal
with open('_clean_webhooks_shell.py', 'w', encoding='utf-8') as f:
    f.write(flask_script)

print("Script creado: _clean_webhooks_shell.py")
print()
print("Para ejecutar:")
print("  cd clip_admin_backend")
print("  flask shell < _clean_webhooks_shell.py")
