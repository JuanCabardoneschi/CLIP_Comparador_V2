"""
Script para sincronizar el estado de imágenes procesadas en la base de datos CLIP Comparador V2.
Marca como procesadas todas las imágenes que tengan embedding generado pero estén marcadas como pendientes.
"""






import importlib.util
import sys
spec = importlib.util.spec_from_file_location("clip_app", "./clip_admin_backend/app.py")
clip_app = importlib.util.module_from_spec(spec)
sys.modules["clip_app"] = clip_app
spec.loader.exec_module(clip_app)

flask_app = clip_app.create_app()
db = clip_app.db
from clip_admin_backend.app.models.image import Image

with flask_app.app_context():
    images = Image.query.filter(
        Image.clip_embedding.isnot(None),
        (Image.is_processed == False) | (Image.upload_status != 'completed')
    ).all()
    print(f"Imágenes a actualizar: {len(images)}")
    for img in images:
        img.is_processed = True
        img.upload_status = 'completed'
    db.session.commit()
    print("Sincronización completada.")
