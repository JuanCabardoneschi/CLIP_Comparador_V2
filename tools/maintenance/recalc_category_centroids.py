import os
import sys
from datetime import datetime

# Ensure we can import the app factory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'clip_admin_backend'))

import importlib.util

# Load clip_admin_backend/app.py as a module to get create_app
APP_FILE = os.path.join(PROJECT_ROOT, 'clip_admin_backend', 'app.py')
spec = importlib.util.spec_from_file_location("clip_backend_app", APP_FILE)
clip_backend_app = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(clip_backend_app)
create_app = clip_backend_app.create_app

from app import db
from app.models.category import Category

TARGET_NAMES = [
    'shores tiro alto',
    'shores tiro bajo',
]


def main():
    app = create_app()
    with app.app_context():
        print("\n=== Recalculando centroides ===")
        for name in TARGET_NAMES:
            cat = Category.query.filter(Category.name == name).first()
            if not cat:
                print(f"⚠️  Categoría no encontrada: {name}")
                continue
            before_count = cat.centroid_image_count or 0
            print(f"→ {cat.name} (id={cat.id}) | imágenes previas usadas: {before_count}")
            ok = cat.update_centroid_embedding(force_recalculate=True)
            if ok:
                try:
                    db.session.commit()
                    print(f"✅ Guardado: {cat.name} | imágenes usadas: {cat.centroid_image_count} | fecha: {cat.centroid_updated_at}")
                except Exception as e:
                    db.session.rollback()
                    print(f"❌ Error guardando {cat.name}: {e}")
            else:
                print(f"❌ No se pudo recalcular: {cat.name}")


if __name__ == '__main__':
    main()
