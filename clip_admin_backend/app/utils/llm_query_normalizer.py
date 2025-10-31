"""
Normalizador semántico de queries usando Sentence Transformers (MiniLM)
Extrae color, tipo y contexto de la consulta del usuario para enriquecer la búsqueda CLIP.
"""
from sentence_transformers import SentenceTransformer
import re

# Modelo liviano multilingüe
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

# Listas simples para demo, pueden expandirse
COLORES = [
    'negro', 'blanco', 'azul', 'rojo', 'verde', 'amarillo', 'marron', 'gris', 'beige', 'rosa', 'morado',
    'celeste', 'mostaza', 'turquesa', 'petróleo', 'naranja', 'violeta', 'lila', 'dorado', 'plateado'
]
TIPOS = [
    'delantal', 'camisa', 'pantalon', 'remera', 'vestido', 'chaqueta', 'abrigo', 'chaleco', 'blusa', 'falda',
    'pechera', 'guardapolvo', 'buzo', 'short', 'top', 'uniforme', 'traje', 'saco', 'sueter', 'campera'
]

# Contextos comunes
CONTEXTOS = [
    'cocina', 'trabajo', 'industrial', 'escolar', 'hospital', 'limpieza', 'oficina', 'deportivo', 'invierno', 'verano',
    'resistente', 'impermeable', 'unisex', 'femenino', 'masculino', 'niños', 'adultos', 'profesional', 'casual'
]

def normalize_query(query: str) -> dict:
    """
    Extrae color, tipo y contexto de la consulta usando reglas y embeddings.
    Devuelve dict: {'tipo': ..., 'color': ..., 'contexto': ...}
    """
    query_lower = query.lower()
    model = get_model()
    # Embedding (no usado en demo, pero disponible para mejoras)
    emb = model.encode(query_lower)

    # Color: busca el primero que aparece
    color = next((c for c in COLORES if c in query_lower), None)
    # Tipo: busca el primero que aparece
    tipo = next((t for t in TIPOS if t in query_lower), None)
    # Contexto: busca todos los que aparecen
    contexto = [ctx for ctx in CONTEXTOS if ctx in query_lower]

    return {
        'tipo': tipo,
        'color': color,
        'contexto': contexto,
        'query': query,
        'embedding': emb.tolist()  # Por si se quiere usar para CLIP o logging
    }

if __name__ == "__main__":
    # Prueba rápida
    ejemplos = [
        "delantal amarillo para cocina resistente a manchas",
        "camisa azul marino de invierno",
        "guardapolvo blanco escolar unisex",
        "vestido rosa casual verano",
        "pantalon negro industrial impermeable"
    ]
    for q in ejemplos:
        print(f"Query: {q}")
        print(normalize_query(q))
        print()
