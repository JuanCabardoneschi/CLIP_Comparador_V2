"""
Genera una clave de encriptación Fernet para TOKEN_ENCRYPTION_KEY
Esta clave debe ser configurada como variable de entorno en Railway
"""
from cryptography.fernet import Fernet

# Generar clave
key = Fernet.generate_key()

print("=" * 80)
print("🔐 TOKEN_ENCRYPTION_KEY Generado")
print("=" * 80)
print()
print("Copia esta clave y configúrala como variable de entorno en Railway:")
print()
print(f"TOKEN_ENCRYPTION_KEY={key.decode()}")
print()
print("=" * 80)
print()
print("Instrucciones para Railway:")
print("1. Ve a tu proyecto en Railway")
print("2. Selecciona el servicio clip_admin_backend")
print("3. Ve a Variables → Raw Editor")
print("4. Agrega la variable TOKEN_ENCRYPTION_KEY con el valor de arriba")
print("5. Guarda y redeploy")
print()
print("=" * 80)
