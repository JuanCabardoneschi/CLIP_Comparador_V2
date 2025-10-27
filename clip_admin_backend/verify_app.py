#!/usr/bin/env python3
"""
Script de verificación para validar que la app se puede importar correctamente
Se ejecuta antes de Gunicorn en Railway para diagnosticar errores de importación
"""

import sys
import traceback

print("=" * 60)
print("🔍 Verificando que la app se puede importar...")
print("=" * 60)

try:
    # Intentar importar el módulo wsgi
    print("\n1️⃣ Importando módulo wsgi...")
    import wsgi as wsgi_module
    print("   ✅ Módulo wsgi importado correctamente")

    # Verificar que existe el atributo 'app'
    print("\n2️⃣ Verificando que existe el atributo 'app'...")
    if hasattr(wsgi_module, 'app'):
        print("   ✅ Atributo 'app' encontrado")
        app_instance = wsgi_module.app
        print(f"   ✅ Tipo: {type(app_instance)}")
        print(f"   ✅ Nombre: {app_instance.name}")
    else:
        print("   ❌ ERROR: No se encontró el atributo 'app' en el módulo")
        print(f"   📋 Atributos disponibles: {[attr for attr in dir(wsgi_module) if not attr.startswith('_')]}")
        sys.exit(1)

    # Verificar que existe create_app
    print("\n3️⃣ Verificando función create_app...")
    if hasattr(wsgi_module, 'create_app'):
        print("   ✅ Función 'create_app' encontrada")
    else:
        print("   ⚠️  ADVERTENCIA: No se encontró la función 'create_app'")

    print("\n" + "=" * 60)
    print("✅ VERIFICACIÓN COMPLETA - La app está lista para Gunicorn")
    print("=" * 60)
    sys.exit(0)

except Exception as e:
    print("\n" + "=" * 60)
    print("❌ ERROR AL IMPORTAR LA APP")
    print("=" * 60)
    print(f"\n🔴 Error: {e}")
    print("\n📋 Traceback completo:")
    traceback.print_exc()
    print("\n" + "=" * 60)
    sys.exit(1)
