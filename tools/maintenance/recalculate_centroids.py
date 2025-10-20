import os
import sys
import importlib.util
import traceback

# Base del proyecto
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
APP_DIR = os.path.join(ROOT, 'clip_admin_backend')

print(f"📁 ROOT: {ROOT}")
print(f"📁 APP_DIR: {APP_DIR}")

# Asegurar que podemos importar app.py de clip_admin_backend
sys.path.insert(0, APP_DIR)

app_py = os.path.join(APP_DIR, 'app.py')
print(f"🔄 Cargando Flask app desde: {app_py}")

try:
    spec = importlib.util.spec_from_file_location('clip_admin_backend_app', app_py)
    app_module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(app_module)

    flask_app = app_module.create_app()
    print("✅ Flask app creada")

    # Importar modelos luego de crear app
    from app.models.category import Category

    with flask_app.app_context():
        print("🚀 Recalculando centroides para todas las categorías activas (force=True)...")
        stats = Category.recalculate_all_centroids(force=True)
        print("📊 Resultado:")
        print(stats)
        print("✅ Recalculo de centroides completado")

except Exception as e:
    print(f"❌ Error: {e}")
    traceback.print_exc()
    sys.exit(1)
