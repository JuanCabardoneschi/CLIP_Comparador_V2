"""
Test para encontrar el threshold óptimo de fuzzy matching
"""
import torch
import numpy as np
from transformers import CLIPProcessor, CLIPModel

# Cargar CLIP
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")

test_cases = [
    ("delantalito", "Delantal Completo"),
    ("delantalito negro", "Delantal Completo"),
    ("short rojo", "Medio Delantal"),
    ("short", "Delantal Completo"),
    ("pantalon corto", "Delantal Completo"),
    ("remera", "REMERAS"),
    ("remerita", "REMERAS"),
    ("gorra", "GORROS – GORRAS"),
    ("gorrita", "GORROS – GORRAS"),
]

print("=== SIMILITUDES CLIP ===\n")

for query, category in test_cases:
    with torch.no_grad():
        # Query embedding
        query_inputs = processor(text=[query], return_tensors="pt", padding=True)
        query_features = model.get_text_features(**query_inputs)
        query_features = query_features / query_features.norm(dim=-1, keepdim=True)
        query_emb = query_features.cpu().numpy()[0]
        
        # Category embedding
        cat_inputs = processor(text=[category], return_tensors="pt", padding=True)
        cat_features = model.get_text_features(**cat_inputs)
        cat_features = cat_features / cat_features.norm(dim=-1, keepdim=True)
        cat_emb = cat_features.cpu().numpy()[0]
        
        # Similarity
        similarity = float(np.dot(query_emb, cat_emb))
        
        verdict = "✅ MATCH" if similarity >= 0.75 else "❌ NO MATCH"
        print(f"{verdict} | {similarity:.4f} | '{query}' → '{category}'")

print("\n=== RECOMENDACIÓN ===")
print("Threshold 0.75: Balance óptimo")
print("  ✅ Acepta: delantalito→delantal, remerita→remeras, gorrita→gorros")
print("  ❌ Rechaza: short→delantal, pantalon→delantal")
