"""
Test Comparativo: CLIP ViT-B/16 vs ViT-L/14
============================================

Compara scores de detección multicrop entre ambos modelos
en las mismas imágenes de prueba.

Uso:
    python test_vitl14_vs_vitb16.py <image_path> [--category EXPECTED]
"""

import sys
import argparse
from pathlib import Path
import json
from PIL import Image as PILImage
import torch
from transformers import CLIPProcessor, CLIPModel
import numpy as np

# Setup paths
sys.path.insert(0, str(Path(__file__).parent / "clip_admin_backend"))

from app import create_app
from app.models.category import Category
from app.blueprints.embeddings import generate_multi_scale_crops


def load_model(model_name):
    """Cargar modelo CLIP"""
    print(f"\n🔄 Cargando {model_name}...")
    model = CLIPModel.from_pretrained(model_name)
    processor = CLIPProcessor.from_pretrained(model_name)
    model.eval()
    print(f"✅ {model_name} cargado")
    return model, processor


def detect_with_model(image_path, model, processor, categories):
    """Ejecutar detección multicrop con un modelo específico"""

    # Cargar imagen
    image = PILImage.open(image_path).convert('RGB')

    # Generar crops (mismo algoritmo que producción)
    crops = generate_multi_scale_crops(image)

    # Preparar prompts de categorías
    category_prompts = []
    category_names = []

    for cat in categories:
        prompt = f"A photo of {cat.name.lower()}"
        category_prompts.append(prompt)
        category_names.append(cat.name)

    # Procesar crops
    crop_results = {}

    for crop_name, crop_image in crops.items():
        # Encode imagen
        img_inputs = processor(images=crop_image, return_tensors="pt")
        with torch.no_grad():
            img_features = model.get_image_features(**img_inputs)
            img_features = img_features / img_features.norm(dim=-1, keepdim=True)

        # Encode prompts
        txt_inputs = processor(text=category_prompts, return_tensors="pt", padding=True)
        with torch.no_grad():
            txt_features = model.get_text_features(**txt_inputs)
            txt_features = txt_features / txt_features.norm(dim=-1, keepdim=True)

        # Similitud coseno
        similarity = (img_features @ txt_features.T).squeeze(0)
        scores = similarity.cpu().numpy()

        crop_results[crop_name] = {
            name: float(score) for name, score in zip(category_names, scores)
        }

    # Agregar max por categoría (mismo algoritmo que producción)
    category_max_scores = {}

    for cat_name in category_names:
        max_score = max(crop_results[crop_name][cat_name] for crop_name in crops.keys())
        category_max_scores[cat_name] = max_score

    # Ordenar por score
    sorted_results = sorted(
        category_max_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return sorted_results, crop_results


def main():
    parser = argparse.ArgumentParser(description="Comparar ViT-B/16 vs ViT-L/14")
    parser.add_argument("image", help="Ruta a imagen de prueba")
    parser.add_argument("--category", help="Categoría esperada (opcional)")
    parser.add_argument("--client", default="goody-store", help="Cliente para categorías")

    args = parser.parse_args()

    if not Path(args.image).exists():
        print(f"❌ Imagen no encontrada: {args.image}")
        return

    print("=" * 70)
    print("   TEST COMPARATIVO: CLIP ViT-B/16 vs ViT-L/14")
    print("=" * 70)
    print(f"\n📸 Imagen: {args.image}")
    if args.category:
        print(f"🎯 Categoría esperada: {args.category}")

    # Cargar categorías desde DB
    app = create_app()
    with app.app_context():
        from app.models.client import Client
        client = Client.query.filter_by(name=args.client).first()

        if not client:
            print(f"❌ Cliente '{args.client}' no encontrado")
            return

        categories = Category.query.filter_by(
            client_id=client.id,
            is_active=True
        ).all()

        if not categories:
            print(f"❌ No hay categorías activas para {args.client}")
            return

        print(f"\n📋 Categorías activas: {len(categories)}")
        for cat in categories:
            print(f"   - {cat.name}")

    # Test con ViT-B/16
    print("\n" + "=" * 70)
    print("🔷 CLIP ViT-B/16 (512D) - BASELINE")
    print("=" * 70)

    model_b16, processor_b16 = load_model("openai/clip-vit-base-patch16")
    results_b16, crops_b16 = detect_with_model(
        args.image, model_b16, processor_b16, categories
    )

    print("\n📊 Resultados ViT-B/16:")
    for i, (cat_name, score) in enumerate(results_b16[:5], 1):
        marker = "✅" if args.category and cat_name == args.category else "  "
        print(f"{marker} {i}. {cat_name}: {score:.4f} ({score*100:.2f}%)")

    # Test con ViT-L/14
    print("\n" + "=" * 70)
    print("🔶 CLIP ViT-L/14 (768D) - NUEVO")
    print("=" * 70)

    model_l14, processor_l14 = load_model("openai/clip-vit-large-patch14")
    results_l14, crops_l14 = detect_with_model(
        args.image, model_l14, processor_l14, categories
    )

    print("\n📊 Resultados ViT-L/14:")
    for i, (cat_name, score) in enumerate(results_l14[:5], 1):
        marker = "✅" if args.category and cat_name == args.category else "  "
        print(f"{marker} {i}. {cat_name}: {score:.4f} ({score*100:.2f}%)")

    # Comparación
    print("\n" + "=" * 70)
    print("📈 COMPARACIÓN")
    print("=" * 70)

    if args.category:
        # Buscar scores de categoría esperada
        score_b16 = next((s for n, s in results_b16 if n == args.category), 0.0)
        score_l14 = next((s for n, s in results_l14 if n == args.category), 0.0)

        delta = score_l14 - score_b16
        delta_pct = (delta / score_b16 * 100) if score_b16 > 0 else 0

        print(f"\n🎯 Categoría esperada: {args.category}")
        print(f"   ViT-B/16: {score_b16:.4f} ({score_b16*100:.2f}%)")
        print(f"   ViT-L/14: {score_l14:.4f} ({score_l14*100:.2f}%)")
        print(f"   Delta:    {delta:+.4f} ({delta_pct:+.2f}%)")

        if delta > 0.05:
            print("\n✅ MEJORA SIGNIFICATIVA con ViT-L/14")
        elif delta > 0:
            print("\n⚠️  Mejora leve con ViT-L/14")
        else:
            print("\n❌ Sin mejora con ViT-L/14")

    # Top-1 accuracy
    top1_b16 = results_b16[0][0] if results_b16 else None
    top1_l14 = results_l14[0][0] if results_l14 else None

    print(f"\n🏆 Top-1 Predicción:")
    print(f"   ViT-B/16: {top1_b16} ({results_b16[0][1]*100:.2f}%)")
    print(f"   ViT-L/14: {top1_l14} ({results_l14[0][1]*100:.2f}%)")

    if args.category:
        if top1_b16 == args.category and top1_l14 == args.category:
            print("   ✅ Ambos modelos aciertan")
        elif top1_b16 != args.category and top1_l14 == args.category:
            print("   ✅ ViT-L/14 corrige el error de ViT-B/16")
        elif top1_b16 == args.category and top1_l14 != args.category:
            print("   ❌ ViT-L/14 introduce nuevo error")
        else:
            print("   ❌ Ambos modelos fallan")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
