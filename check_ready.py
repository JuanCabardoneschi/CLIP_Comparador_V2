#!/usr/bin/env python3
"""
Verificación final antes de Railway deployment
"""

import os

def check_railway_ready():
    """Verificar que todo esté listo para Railway"""

    print("🚂 VERIFICACIÓN FINAL RAILWAY")
    print("=" * 40)

    # Archivos críticos para Railway
    critical_files = [
        ("Dockerfile", "Docker configuration"),
        ("Procfile", "Process definition"),
        ("railway.toml", "Railway configuration"),
        ("requirements.txt", "Python dependencies"),
        ("clip_admin_backend/app.py", "Flask application"),
        ("RAILWAY_VARS.md", "Variables guide")
    ]

    print("📁 Archivos críticos:")
    all_good = True
    for file_path, description in critical_files:
        if os.path.exists(file_path):
            print(f"   ✅ {description}: {file_path}")
        else:
            print(f"   ❌ {description}: {file_path} - FALTANTE")
            all_good = False

    # Verificar estructura Flask
    print("\n🌶️ Estructura Flask:")
    flask_structure = [
        "clip_admin_backend/app/",
        "clip_admin_backend/app/models/",
        "clip_admin_backend/app/blueprints/",
        "clip_admin_backend/app/templates/",
        "clip_admin_backend/app/static/"
    ]

    for path in flask_structure:
        if os.path.exists(path):
            print(f"   ✅ {path}")
        else:
            print(f"   ❌ {path} - FALTANTE")
            all_good = False

    # Archivos que NO deben estar
    print("\n🗑️ Archivos auxiliares eliminados:")
    unwanted_files = [
        "quick_migrate_to_railway.py",
        "verify_quick.py",
        "cloudinary_migration_mapping.json",
        "railway_migration_data_*.json"
    ]

    for pattern in unwanted_files:
        if '*' in pattern:
            # Check pattern
            import glob
            matches = glob.glob(pattern)
            if matches:
                print(f"   ⚠️ Encontrados: {matches}")
            else:
                print(f"   ✅ {pattern} - eliminado")
        else:
            if not os.path.exists(pattern):
                print(f"   ✅ {pattern} - eliminado")
            else:
                print(f"   ⚠️ {pattern} - aún existe")

    print("\n📋 ESTADO FINAL:")
    if all_good:
        print("🎉 ¡SISTEMA LISTO PARA RAILWAY!")
        print("📝 Revisa RAILWAY_VARS.md para configurar variables")
        print("🚀 Comando siguiente: git push para deployar")
    else:
        print("⚠️ Hay problemas que corregir")

    return all_good

if __name__ == "__main__":
    check_railway_ready()
