#!/usr/bin/env python3
"""
Script para inicializar configuración de MODA para cliente TiendaNube existente
- Actualiza vocabulary cache
- Agrega atributos del template fashion
- Valida que alternative_terms se generen con vocabulario de moda
"""

import os
import sys
import json
from datetime import datetime

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app, db
from app.models.client import Client
from app.models.category import Category
from app.models.product_attribute_config import ProductAttributeConfig
from app.utils.industry_templates import get_industry_template
from app.utils.attribute_seeder import seed_attributes

app = create_app()

# Cliente TiendaNube
TIENDANUBE_CLIENT_ID = '747ff760-8eae-46e8-94ca-8ad076370316'

def init_fashion_config():
    """Inicializa configuración de moda para cliente TiendaNube"""

    with app.app_context():
        print("\n" + "="*80)
        print("🔧 INICIALIZANDO CONFIGURACIÓN FASHION PARA CLIENTE TIENDANUBE")
        print("="*80)

        # 1. Verificar cliente
        client = Client.query.get(TIENDANUBE_CLIENT_ID)
        if not client:
            print(f"❌ Cliente {TIENDANUBE_CLIENT_ID} no encontrado")
            return False

        print(f"✅ Cliente encontrado: {client.name} (industry={client.industry})")

        # 2. Actualizar a fashion si no está
        if client.industry != 'fashion':
            print(f"⚠️  Actualizando industry a 'fashion'...")
            client.industry = 'fashion'
            db.session.commit()
            print(f"✅ Actualizado: {client.industry}")

        # 3. Inicializar vocabulary cache
        print("\n📚 Inicializando vocabulary cache...")
        init_vocabulary_cache(client.id)

        # 4. Agregar atributos del template fashion
        print("\n🏷️ Agregando atributos del template fashion...")
        add_fashion_attributes(client.id)

        # 5. Validar categorías existentes
        print("\n✨ Validando categorías existentes...")
        validate_categories(client.id)

        print("\n" + "="*80)
        print("✅ CONFIGURACIÓN FASHION INICIALIZADA")
        print("="*80 + "\n")
        return True


def init_vocabulary_cache(client_id):
    """Inicializa vocabulary cache con vocabulario de moda"""

    # Obtener template de fashion
    template = get_industry_template('fashion')

    # Construir vocabulario base
    fashion_vocab = {
        'color_terms': [
            'rojo', 'azul', 'verde', 'negro', 'blanco', 'gris', 'beige', 'rosa', 'naranja', 'amarillo',
            'violeta', 'marrón', 'dorado', 'plateado', 'bordeaux', 'navy', 'turquesa', 'mint',
            'nude', 'coral', 'salvia', 'mostaza', 'piel', 'crudo'
        ],
        'material_terms': [
            'algodón', 'cuero', 'poliéster', 'lino', 'seda', 'lana', 'sintético', 'mezclilla',
            'nylon', 'rayon', 'spandex', 'viscosa', 'gabardina', 'punto', 'plush', 'algodón orgánico'
        ],
        'size_terms': ['xs', 's', 'm', 'l', 'xl', 'xxl', 'xxxl', 'talla única', 'one size'],
        'category_terms': [
            'remera', 'camiseta', 'remeron', 'buzo', 'campera', 'blazer', 'saco',
            'pantalón', 'jean', 'short', 'falda', 'pollera', 'vestido', 'bombacha',
            'medias', 'calcetines', 'zapatillas', 'zapatos', 'botas', 'sandalias', 'chinelas',
            'cinturón', 'bolso', 'mochila', 'cartera', 'billetera',
            'gorro', 'sombrero', 'bufanda', 'guantes', 'gafas', 'lentes', 'reloj',
            'bikini', 'traje de baño', 'bermuda', 'jogger', 'legging', 'crop top'
        ],
        'brand_terms': [],  # Se llenarían con marcas reales del cliente
        'style_terms': [
            'casual', 'deportivo', 'formal', 'elegante', 'bohemio', 'clásico', 'moderno',
            'vintage', 'retro', 'minimalista', 'oversized', 'fitted', 'slim', 'wide',
            'slim fit', 'regular fit', 'relaxed fit', 'boyfriend', 'skinny', 'bootcut'
        ],
        'color_embeddings': {}  # Se generarán en primer use
    }

    # Guardar en tabla client_vocabulary_cache
    from sqlalchemy import text

    try:
        # Verificar si existe registro
        result = db.session.execute(
            text("SELECT id FROM client_vocabulary_cache WHERE client_id = :cid"),
            {'cid': client_id}
        )
        existing = result.fetchone()

        if existing:
            # Actualizar
            db.session.execute(
                text("""UPDATE client_vocabulary_cache
                        SET vocabulary = :vocab, updated_at = :now
                        WHERE client_id = :cid"""),
                {
                    'vocab': json.dumps(fashion_vocab),
                    'cid': client_id,
                    'now': datetime.utcnow()
                }
            )
            print(f"✅ Vocabulary cache actualizado")
        else:
            # Insertar nuevo
            db.session.execute(
                text("""INSERT INTO client_vocabulary_cache
                        (client_id, vocabulary, updated_at)
                        VALUES (:cid, :vocab, :now)"""),
                {
                    'cid': client_id,
                    'vocab': json.dumps(fashion_vocab),
                    'now': datetime.utcnow()
                }
            )
            print(f"✅ Vocabulary cache creado")

        db.session.commit()
    except Exception as e:
        print(f"⚠️ Error inicializando vocabulary cache: {e}")
        db.session.rollback()


def add_fashion_attributes(client_id):
    """Agrega atributos del template fashion al cliente"""

    template = get_industry_template('fashion')
    existing_keys = set()

    # Obtener claves existentes
    existing = ProductAttributeConfig.query.filter_by(client_id=client_id).all()
    existing_keys = {attr.key for attr in existing}

    print(f"  Atributos existentes: {existing_keys}")

    order = len(existing)

    # Agregar atributos faltantes
    for attr_key, attr_config in template.items():
        if attr_key in existing_keys:
            print(f"  ⏭️  '{attr_key}' ya existe, omitiendo")
            continue

        try:
            attr = ProductAttributeConfig(
                client_id=client_id,
                key=attr_key,
                label=attr_config.get('label', attr_key.title()),
                type=attr_config.get('type', 'text'),
                required=attr_config.get('required', False),
                options=attr_config.get('options'),
                field_order=order,
                expose_in_search=attr_config.get('expose_in_search', False),
                description=attr_config.get('description', '')
            )
            db.session.add(attr)
            order += 1
            print(f"  ➕ Agregado: '{attr_key}' ({attr_config.get('type')})")
        except Exception as e:
            print(f"  ❌ Error agregando '{attr_key}': {e}")

    try:
        db.session.commit()
        print(f"✅ Atributos committeados")
    except Exception as e:
        print(f"❌ Error committeando atributos: {e}")
        db.session.rollback()


def validate_categories(client_id):
    """Valida que las categorías tengan alternative_terms y prompts correctos"""

    categories = Category.query.filter_by(client_id=client_id).all()

    print(f"  Total de categorías: {len(categories)}")

    missing_terms = []
    missing_prompts = []

    for cat in categories:
        if not cat.alternative_terms:
            missing_terms.append(cat.name)
        if not cat.clip_prompt:
            missing_prompts.append(cat.name)

    if missing_terms:
        print(f"  ⚠️  Sin alternative_terms ({len(missing_terms)}): {', '.join(missing_terms[:3])}...")
    else:
        print(f"  ✅ Todas las categorías tienen alternative_terms")

    if missing_prompts:
        print(f"  ⚠️  Sin clip_prompt ({len(missing_prompts)}): {', '.join(missing_prompts[:3])}...")
    else:
        print(f"  ✅ Todas las categorías tienen clip_prompt")

    # Mostrar muestra
    if categories:
        cat = categories[0]
        print(f"\n  Ejemplo de categoría:")
        print(f"    • Nombre: {cat.name}")
        print(f"    • Nombre EN: {cat.name_en}")
        print(f"    • Alternative terms: {cat.alternative_terms}")
        print(f"    • CLIP prompt: {cat.clip_prompt[:100]}...")


if __name__ == '__main__':
    success = init_fashion_config()
    sys.exit(0 if success else 1)
