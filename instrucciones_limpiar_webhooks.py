"""
Instrucciones para limpiar webhooks duplicados de Tiendanube
"""

print("""
═══════════════════════════════════════════════════════════════════
  LIMPIAR WEBHOOKS DUPLICADOS DE TIENDANUBE
═══════════════════════════════════════════════════════════════════

Se ha creado un endpoint en el sistema para limpiar webhooks duplicados.

OPCIÓN 1: Desde el navegador (MÁS FÁCIL)
──────────────────────────────────────────────────────────────────

1. Ingresá a Railway con tu usuario SUPER_ADMIN:
   https://clipcomparadorv2-production.up.railway.app/admin/tiendanube/integrations

2. Abrí la integración de "Test Clip"

3. En la consola del navegador (F12), ejecutá:

   fetch(window.location.origin + '/admin/tiendanube/integrations/<INTEGRATION_ID>/clean-webhooks', {
     method: 'POST',
     headers: {
       'Content-Type': 'application/json'
     },
     credentials: 'include'
   })
   .then(r => r.json())
   .then(data => console.log(data))

   Reemplazá <INTEGRATION_ID> con el ID que ves en la URL


OPCIÓN 2: Desde Python (con sesión autenticada)
──────────────────────────────────────────────────────────────────

1. Primero, obtené el integration_id:
""")

import subprocess
result = subprocess.run(
    ['python', 'railway_db_tool.py', 'sql', '-e',
     "SELECT id FROM tiendanube_integrations JOIN clients ON client_id = clients.id WHERE clients.name = 'Test Clip'"],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)

if result.returncode == 0:
    lines = result.stdout.strip().split('\n')
    for line in lines:
        if '|' in line and 'id' not in line and not line.startswith('-'):
            integration_id = line.strip().strip('|').strip()
            print(f"   Integration ID: {integration_id}")
            print()
            print(f"""
2. Luego, desde Python con sesión autenticada:

   import requests

   # Primero hacé login para obtener la cookie de sesión
   session = requests.Session()

   login_response = session.post(
       'https://clipcomparadorv2-production.up.railway.app/login',
       data={{'username': 'TU_USERNAME', 'password': 'TU_PASSWORD'}},
       verify=False
   )

   # Llamar al endpoint de limpieza
   clean_response = session.post(
       'https://clipcomparadorv2-production.up.railway.app/admin/tiendanube/integrations/{integration_id}/clean-webhooks',
       verify=False
   )

   print(clean_response.json())


OPCIÓN 3: Esperar a que Railway termine el deploy y llamar directamente
──────────────────────────────────────────────────────────────────

El endpoint ya está commitado y Railway lo está deployando.
Una vez que termine, podés llamarlo desde cualquiera de las opciones anteriores.

═══════════════════════════════════════════════════════════════════
""")
            break
else:
    print("   ❌ Error obteniendo Integration ID")
    print("   Revisá manualmente en Railway")
