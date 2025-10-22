"""
Script para verificar el estado de embeddings en la BD de producción
"""
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('.env.local')

# Configurar path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app
from app.models import db, Product, Category, Client

def check_embeddings():
    """Verifica estado de embeddings para Eve's Store"""

    app = create_app()

    with app.app_context():
        # Buscar cliente Eve's Store
        client = Client.query.filter(Client.name.ilike('%eve%store%')).first()

        if not client:
            print("❌ No se encontró el cliente Eve's Store")
            return

        print(f"✅ Cliente encontrado: {client.name} (ID: {client.id})")
        print(f"   API Key: {client.api_key}")
        print()

        # Obtener categorías
        categories = Category.query.filter_by(client_id=client.id).all()

        print(f"📋 Categorías: {len(categories)}")
        for cat in categories:
            print(f"   - {cat.name} (slug: {cat.slug}, activa: {cat.is_active})")

            # Contar productos
            products = Product.query.filter_by(category_id=cat.id).all()
            print(f"     Productos: {len(products)}")

            for prod in products:
                has_embedding = prod.image_embedding is not None
                print(f"       • {prod.name} (SKU: {prod.sku})")
                print(f"         - Tiene embedding: {'✅ SÍ' if has_embedding else '❌ NO'}")
                print(f"         - Imagen principal: {prod.get_primary_image()}")

            # Verificar centroide
            centroid = cat.get_centroid_embedding(auto_calculate=False)
            print(f"     Centroide: {'✅ CALCULADO' if centroid is not None else '❌ NO CALCULADO'}")
            print()

if __name__ == '__main__':
    check_embeddings()
