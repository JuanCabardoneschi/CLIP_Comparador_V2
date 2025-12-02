"""
Helper para obtener un nuevo token de Tiendanube via OAuth
"""

import webbrowser
import time

CLIENT_ID = "8616"
REDIRECT_URI = "https://clipcomparadorv2-production.up.railway.app/oauth/callback"

# URL de autorización
auth_url = f"https://www.tiendanube.com/apps/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read_content,write_content,write_products,write_scripts"

print("=" * 70)
print("🔑 OBTENER TOKEN DE TIENDANUBE")
print("=" * 70)
print()
print("1️⃣  Se va a abrir tu navegador con la página de autorización de Tiendanube")
print("2️⃣  Autorizá la aplicación")
print("3️⃣  Copiá el JSON completo que aparece en la página")
print("4️⃣  El access_token es el valor que necesitás pegar en .env.local")
print()
input("Presioná ENTER para continuar...")

webbrowser.open(auth_url)

print()
print("✅ Navegador abierto")
print()
print("📋 Después de autorizar, copiá el 'access_token' del JSON y pegalo en:")
print("   .env.local → TIENDANUBE_ACCESS_TOKEN=TU_TOKEN_AQUI")
print()
