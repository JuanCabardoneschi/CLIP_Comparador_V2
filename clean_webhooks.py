"""
Script para limpiar webhooks duplicados de Tiendanube
Consulta la base de datos directamente para obtener el token
"""
import subprocess
import json
import requests
import sys

def get_integration_data(client_name="Test Clip"):
    """Obtiene datos de integración desde la base de datos"""
    print(f"🔍 Buscando integración para cliente: {client_name}")

    # Consultar la base de datos usando railway_db_tool
    cmd = [
        'python', 'railway_db_tool.py', 'sql', '-e',
        f"""
        SELECT
            ti.id as integration_id,
            ti.store_id,
            ti.access_token,
            ti.webhook_ids,
            c.name as client_name
        FROM tiendanube_integrations ti
        JOIN clients c ON ti.client_id = c.id
        WHERE c.name = '{client_name}'
        LIMIT 1
        """
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Error consultando base de datos: {result.stderr}")
        return None

    # Parsear el resultado
    lines = result.stdout.strip().split('\n')

    # Buscar la línea con los datos (después de los headers)
    for line in lines:
        if '|' in line and not line.startswith('-') and 'integration_id' not in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                return {
                    'integration_id': parts[0],
                    'store_id': parts[1],
                    'access_token_encrypted': parts[2],
                    'webhook_ids': parts[3],
                    'client_name': parts[4]
                }

    print("❌ No se encontró la integración")
    return None


def decrypt_token(encrypted_token):
    """
    El token está encriptado con Fernet.
    Como estamos usando Railway, necesitamos desencriptarlo con la clave correcta.
    Por ahora, asumimos que el método get_access_token() de la integración ya lo hace.
    """
    # NOTA: El token en la BD está encriptado.
    # Para desencriptarlo necesitamos TOKEN_ENCRYPTION_KEY de Railway.
    # Vamos a usar un enfoque más simple: llamar al endpoint del admin
    return encrypted_token


def clean_webhooks_direct(store_id, access_token):
    """Limpia webhooks usando la API de Tiendanube directamente"""

    headers = {
        'Authentication': f'bearer {access_token}',
        'User-Agent': 'CLIP Comparador V2',
        'Content-Type': 'application/json'
    }

    # Listar todos los webhooks
    print(f"🔍 Listando webhooks para store {store_id}...")
    response = requests.get(
        f'https://api.tiendanube.com/v1/{store_id}/webhooks',
        headers=headers,
        timeout=10,
        verify=False
    )

    if response.status_code != 200:
        print(f"❌ Error listando webhooks: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

    all_webhooks = response.json()
    print(f"📋 Total de webhooks encontrados: {len(all_webhooks)}")
    print()

    # Separar webhooks correctos e incorrectos
    old_webhooks = []
    new_webhooks = []

    for wh in all_webhooks:
        wh_id = wh.get('id')
        url = wh.get('url', '')
        event = wh.get('event')

        print(f"   ID: {wh_id}")
        print(f"   Event: {event}")
        print(f"   URL: {url}")

        if '/api/webhooks/tiendanube/' not in url:
            old_webhooks.append(wh)
            print(f"   ❌ INCORRECTO (sin /api/)")
        else:
            new_webhooks.append(wh)
            print(f"   ✅ CORRECTO")
        print()

    if not old_webhooks:
        print("✅ No hay webhooks incorrectos para eliminar")
        return True

    print(f"🗑️ Se encontraron {len(old_webhooks)} webhooks incorrectos")
    print(f"✅ Se mantendrán {len(new_webhooks)} webhooks correctos")
    print()

    # Pedir confirmación
    confirm = input("¿Desea eliminar los webhooks incorrectos? (s/n): ")
    if confirm.lower() != 's':
        print("❌ Operación cancelada")
        return False

    print()
    print("🗑️ Eliminando webhooks incorrectos...")

    deleted_count = 0
    for wh in old_webhooks:
        wh_id = wh.get('id')
        event = wh.get('event')

        print(f"   Eliminando: {event} (ID: {wh_id})")

        del_response = requests.delete(
            f'https://api.tiendanube.com/v1/{store_id}/webhooks/{wh_id}',
            headers=headers,
            timeout=10,
            verify=False
        )

        if del_response.status_code == 200:
            print(f"   ✅ Eliminado exitosamente")
            deleted_count += 1
        else:
            print(f"   ❌ Error: {del_response.status_code} - {del_response.text}")

    print()
    print(f"🎉 Limpieza completada:")
    print(f"   ✅ Eliminados: {deleted_count}/{len(old_webhooks)}")
    print(f"   ✅ Mantenidos: {len(new_webhooks)}")

    return True


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    client_name = sys.argv[1] if len(sys.argv) > 1 else "Test Clip"

    # Obtener datos de la integración
    data = get_integration_data(client_name)

    if not data:
        print("❌ No se pudo obtener los datos de la integración")
        sys.exit(1)

    print(f"✅ Integración encontrada:")
    print(f"   ID: {data['integration_id']}")
    print(f"   Store ID: {data['store_id']}")
    print(f"   Cliente: {data['client_name']}")
    print()

    # PROBLEMA: El token está encriptado
    # Necesitamos usar el modelo de Flask para desencriptarlo
    # Como alternativa, vamos a usar el token encriptado directamente
    # y ver si Tiendanube lo acepta (probablemente no)

    print("⚠️ PROBLEMA: El token está encriptado en la base de datos")
    print("   Necesitamos usar la aplicación Flask para desencriptarlo")
    print()
    print("💡 SOLUCIÓN: Usar el endpoint del admin que ya creamos")
    print()
    print(f"   Ejecuta desde el navegador (como SUPER_ADMIN):")
    print(f"   POST https://clipcomparadorv2-production.up.railway.app/admin/tiendanube/integrations/{data['integration_id']}/clean-webhooks")
    print()
    print("   O desde curl:")
    print(f"   curl -X POST https://clipcomparadorv2-production.up.railway.app/admin/tiendanube/integrations/{data['integration_id']}/clean-webhooks \\")
    print(f"        -H 'Cookie: session=TU_SESSION_COOKIE'")

