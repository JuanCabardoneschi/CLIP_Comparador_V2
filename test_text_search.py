"""
Script de prueba interactivo para búsqueda textual con CLIP Comparador V2
Búsqueda híbrida que combina:
- Embedding CLIP textual
- Atributos JSONB (color, material, talla)
- Tags semánticos
- Nombre del producto
"""

print("=== CLIP Text Search - Hybrid System ===\n")

import os
import sys
import json
import psycopg2
import torch
import clip
import numpy as np
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('.env.local')
DATABASE_URL = os.getenv('DATABASE_URL')

# Inicializar modelo CLIP
print("Cargando modelo CLIP...")
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/16", device=device)
print(f"✓ Modelo CLIP cargado en {device}\n")

def get_text_embedding(text: str):
    """Genera embedding CLIP para texto"""
    with torch.no_grad():
        text_tokens = clip.tokenize([text]).to(device)
        text_features = model.encode_text(text_tokens)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features.cpu().numpy()[0]

def calculate_attribute_match(query_lower: str, attributes: dict, category: str = None) -> float:
    """
    Calcula boost por matching de atributos JSONB + categoría.
    Ej: "camisa blanca" → boost si:
      - category contiene "camisa"
      - attributes['color'] contiene "blanco"
    """
    score = 0.0

    # Palabras de la query
    query_words = set(query_lower.split())

    # 1. Match de categoría (importante para tipo de producto)
    if category:
        category_lower = category.lower()
        for word in query_words:
            if len(word) > 3 and word in category_lower:
                score += 0.25  # Boost fuerte por match de categoría

    # 2. Match de atributos JSONB
    if attributes:
        for attr_key, attr_value in attributes.items():
            if attr_value and isinstance(attr_value, str):
                attr_value_lower = attr_value.lower()
                # Match exacto
                if attr_value_lower in query_lower:
                    score += 0.3
                # Match parcial (cualquier palabra)
                elif any(word in attr_value_lower for word in query_words):
                    score += 0.15

    return score

def calculate_tag_match(query_lower: str, tags: str) -> float:
    """
    Calcula boost por matching de tags.
    Ej: "camisa formal" → boost si 'formal' en tags
    """
    score = 0.0
    if not tags:
        return score

    tags_lower = tags.lower()
    query_words = set(query_lower.split())

    # Match directo de tags
    for word in query_words:
        if word in tags_lower:
            score += 0.2

    return score

def hybrid_search(query: str, client_id: str = None, top_k: int = 10):
    """
    Búsqueda híbrida combinando:
    - CLIP embedding similarity (50% - similitud visual/semántica base)
    - Attribute matching (40% - atributos JSONB detectados por CLIP)
    - Tag matching (10% - tags semánticos)

    NOTA: El nombre del producto NO influye (es arbitrario).
    Solo importa: categoría, atributos visuales detectados, y tags.
    """
    print(f"📝 Query: '{query}'\n")

    # Generar embedding CLIP del texto
    text_emb = get_text_embedding(query)
    query_lower = query.lower()

    # Conectar a BD
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Consultar productos con embeddings (de imágenes), atributos y tags
    sql = """
        SELECT p.id, p.name, p.sku, p.attributes, p.tags,
               c.name as category_name, i.clip_embedding,
               i.cloudinary_url
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN images i ON p.id = i.product_id AND i.is_primary = true
        WHERE i.clip_embedding IS NOT NULL
    """

    if client_id:
        sql += f" AND p.client_id = '{client_id}'"

    cursor.execute(sql)
    rows = cursor.fetchall()

    print(f"🔍 Analizando {len(rows)} productos...\n")

    # Calcular scores híbridos
    results = []
    for row in rows:
        prod_id, name, sku, attributes, tags, category_name, embedding, image_url = row

        # Parse attributes si es string JSON
        if isinstance(attributes, str):
            try:
                attributes = json.loads(attributes)
            except:
                attributes = {}

        # Parse embedding si es string JSON
        if isinstance(embedding, str):
            try:
                embedding = json.loads(embedding)
            except:
                continue  # Skip si no se puede parsear

        # Score CLIP (base)
        emb = np.array(embedding, dtype=np.float32)
        clip_similarity = float(np.dot(text_emb, emb) / (np.linalg.norm(text_emb) * np.linalg.norm(emb)))

        # Boosts semánticos
        attr_boost = calculate_attribute_match(query_lower, attributes, category_name)
        tag_boost = calculate_tag_match(query_lower, tags)

        # Score final híbrido
        # Ponderaciones: CLIP 50%, Atributos 40%, Tags 10%
        # El nombre del producto NO influye (es arbitrario)
        final_score = (
            clip_similarity * 0.5 +
            attr_boost * 0.4 +
            tag_boost * 0.1
        )

        results.append({
            "product_id": prod_id,
            "name": name,
            "sku": sku,
            "category": category_name,
            "attributes": attributes,
            "tags": tags or "",
            "image_url": image_url,
            "clip_similarity": clip_similarity,
            "attr_boost": attr_boost,
            "tag_boost": tag_boost,
            "final_score": final_score
        })

    # Ordenar por score final
    results.sort(key=lambda x: x["final_score"], reverse=True)

    cursor.close()
    conn.close()

    return results[:top_k]

# Main execution
if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("Ingrese su búsqueda textual: ")

    results = hybrid_search(query, top_k=5)

    print("=" * 80)
    print(f"🎯 Top {len(results)} resultados:")
    print("=" * 80)

    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['name']} (SKU: {r['sku']})")
        print(f"   📂 Categoría: {r['category']}")
        print(f"   🎨 Atributos: {r['attributes']}")
        print(f"   🏷️  Tags: {r['tags']}")
        print(f"   📊 Scores:")
        print(f"      • CLIP similarity: {r['clip_similarity']:.3f}")
        print(f"      • Attribute boost: +{r['attr_boost']:.3f}")
        print(f"      • Tag boost: +{r['tag_boost']:.3f}")
        print(f"      • FINAL SCORE: {r['final_score']:.3f}")
        if r['image_url']:
            print(f"   🖼️  {r['image_url'][:60]}...")

    print("\n" + "=" * 80)
