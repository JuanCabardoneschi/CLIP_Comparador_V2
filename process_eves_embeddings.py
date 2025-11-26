"""
Script para procesar embeddings de Eve's Store en Railway
"""
import os
import sys

# Agregar path del backend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIP_BACKEND_DIR = os.path.join(BASE_DIR, 'clip_admin_backend')
if CLIP_BACKEND_DIR not in sys.path:
    sys.path.insert(0, CLIP_BACKEND_DIR)

from app import create_app, db
from app.models.client import Client
from app.models.image import Image
from app.blueprints.embeddings import generate_clip_embedding

def process_eves_embeddings():
    """Procesa embeddings pendientes de Eve's Store"""
    app = create_app()

    with app.app_context():
        # Obtener cliente
        client = Client.query.filter_by(name="Eve's Store").first()
        if not client:
            print("❌ Cliente 'Eve's Store' no encontrado")
            return

        print(f"✅ Cliente encontrado: {client.name} ({client.id})")

        # Obtener imágenes pendientes
        pending_images = Image.query.join(Image.product).filter(
            Image.product.has(client_id=client.id),
            Image.is_processed == False,
            Image.cloudinary_url != None
        ).all()

        print(f"📊 Imágenes pendientes: {len(pending_images)}")

        if not pending_images:
            print("✅ No hay imágenes pendientes")
            return

        # Procesar cada imagen
        processed = 0
        failed = 0

        for i, image in enumerate(pending_images, 1):
            try:
                print(f"🔄 [{i}/{len(pending_images)}] Procesando {image.filename}...")

                # Generar embedding
                embedding, metadata = generate_clip_embedding(image.cloudinary_url, image)

                if embedding is not None:
                    # Guardar embedding
                    image.clip_embedding = ','.join(map(str, embedding))
                    image.is_processed = True
                    image.upload_status = 'completed'

                    # Guardar metadata si existe
                    if metadata:
                        image.optimization_method = metadata.get('optimization_method')
                        image.embedding_confidence = metadata.get('confidence_score')

                    db.session.commit()
                    processed += 1
                    print(f"   ✅ Procesado ({metadata.get('optimization_method', 'simple')})")
                else:
                    failed += 1
                    image.upload_status = 'failed'
                    image.error_message = 'No se pudo generar embedding'
                    db.session.commit()
                    print(f"   ❌ Falló")

            except Exception as e:
                failed += 1
                print(f"   ❌ Error: {e}")
                image.upload_status = 'failed'
                image.error_message = str(e)
                db.session.commit()

        print(f"\n📊 Resumen:")
        print(f"   ✅ Procesados: {processed}")
        print(f"   ❌ Fallidos: {failed}")
        print(f"   📈 Total: {len(pending_images)}")

if __name__ == '__main__':
    process_eves_embeddings()
