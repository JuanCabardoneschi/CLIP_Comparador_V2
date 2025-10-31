"""
Analiza por qué diferentes delantales tienen diferentes similitudes CLIP
con la query 'delantal marrón'
"""
import os
import psycopg2
import torch
import clip
import numpy as np
from dotenv import load_dotenv
import json

load_dotenv('.env.local')
DATABASE_URL = os.getenv('DATABASE_URL')

device = "cpu"
model, _ = clip.load('ViT-B/16', device=device)

# Conectar a BD
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Query de prueba
query_text = "delantal marrón"
print(f"Query: '{query_text}'\n")

# Generar embedding de la query
with torch.no_grad():
    text_tokens = clip.tokenize([query_text]).to(device)
    query_embedding = model.encode_text(text_tokens)
    query_embedding = query_embedding / query_embedding.norm(dim=-1, keepdim=True)
    query_embedding = query_embedding.cpu().numpy()[0]

# Obtener delantales específicos
cursor.execute("""
    SELECT p.id, p.name, p.sku, p.attributes, i.clip_embedding
    FROM products p
    JOIN categories c ON p.category_id = c.id
    LEFT JOIN images i ON p.id = i.product_id
    WHERE c.name = 'DELANTAL'
    AND i.clip_embedding IS NOT NULL
    AND (p.name LIKE '%Amarillo%' OR p.name LIKE '%Marrón%' OR p.name LIKE '%Negro%')
    ORDER BY p.name
""")

products = cursor.fetchall()

print("=== Análisis de Similitudes CLIP ===\n")

# Casos de interés
target_products = [
    "Delantal Amarillo Mostaza",
    "Delantal Marrón Chocolate",
    "Delantal Negro",
]

for product_id, name, sku, attributes, embedding_json in products:
    # Parsear embedding
    if isinstance(embedding_json, str):
        embedding = np.array(json.loads(embedding_json))
    else:
        embedding = np.array(embedding_json)

    # Normalizar
    embedding = embedding / np.linalg.norm(embedding)

    # Calcular similitud
    similarity = float(np.dot(query_embedding, embedding))

    # Parsear atributos
    if isinstance(attributes, str):
        attrs = json.loads(attributes)
    else:
        attrs = attributes

    color = attrs.get('color', 'N/A')

    print(f"Producto: {name}")
    print(f"  SKU: {sku}")
    print(f"  Color detectado: {color}")
    print(f"  CLIP Similarity: {similarity:.4f}")
    print(f"  Embedding norm: {np.linalg.norm(embedding):.4f}")

    # Analizar componentes del embedding
    print(f"  Embedding stats:")
    print(f"    - Mean: {embedding.mean():.6f}")
    print(f"    - Std: {embedding.std():.6f}")
    print(f"    - Min: {embedding.min():.6f}")
    print(f"    - Max: {embedding.max():.6f}")
    print()

cursor.close()
conn.close()

print("\n=== Conclusión ===")
print("La similitud CLIP depende de:")
print("1. Composición visual de la imagen (ángulo, iluminación, fondo)")
print("2. Características visuales del color en la imagen específica")
print("3. Otros elementos visuales (diseño, forma, textura)")
print("\nNo solo del color nominal del producto.")
