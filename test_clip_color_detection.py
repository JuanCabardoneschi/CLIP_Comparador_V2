#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba: Detección de color usando CLIP Zero-Shot Classification
Prueba con "musculosa paris" para ver qué color detecta CLIP
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

# Cargar variables de entorno desde .env.local
from dotenv import load_dotenv
load_dotenv('.env.local')

from app import create_app, db
from app.models.product import Product
from app.models.image import Image
from transformers import CLIPProcessor, CLIPModel
import torch
import numpy as np
from PIL import Image as PILImage
import requests
from io import BytesIO

def load_image_from_url(url):
    """Cargar imagen desde URL"""
    response = requests.get(url, timeout=10)
    return PILImage.open(BytesIO(response.content)).convert('RGB')

def detect_color_zeroshot(image, colores):
    """Detectar color usando zero-shot classification"""

    # Cargar modelo CLIP
    print("🔄 Cargando modelo CLIP...")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
    model.eval()

    # Preparar prompts con contexto
    text_prompts = [f"a {color} tank top" for color in colores]

    print(f"🎨 Evaluando contra {len(colores)} colores...")

    # Procesar en batch (imagen + todos los textos)
    inputs = processor(
        text=text_prompts,
        images=image,
        return_tensors="pt",
        padding=True
    )

    # Forward pass
    with torch.no_grad():
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image  # [1, N_colores]
        probs = logits_per_image.softmax(dim=1)  # Convertir a probabilidades

    # Extraer resultados
    resultados = []
    for i, color in enumerate(colores):
        prob = probs[0][i].item()
        resultados.append({
            'color': color,
            'probabilidad': prob,
            'porcentaje': prob * 100
        })

    # Ordenar por probabilidad
    resultados.sort(key=lambda x: x['probabilidad'], reverse=True)

    return resultados

def main():
    app = create_app()

    with app.app_context():
        print("\n" + "="*60)
        print("🧪 TEST: CLIP Zero-Shot Color Detection")
        print("="*60 + "\n")

        # Buscar producto "musculosa paris"
        print("🔍 Buscando producto 'musculosa paris'...")
        product = Product.query.filter(
            Product.name.ilike('%musculosa paris%')
        ).first()

        if not product:
            print("❌ No se encontró el producto 'musculosa paris'")
            return

        print(f"✅ Producto encontrado: {product.name} (ID: {product.id})")

        # Obtener imagen primaria
        primary_image = Image.query.filter_by(
            product_id=product.id,
            is_primary=True
        ).first()

        if not primary_image:
            primary_image = Image.query.filter_by(product_id=product.id).first()

        if not primary_image:
            print("❌ No se encontró imagen para el producto")
            return

        print(f"📸 Imagen: {primary_image.display_url[:80]}...")

        # Cargar imagen
        print("🔄 Descargando imagen...")
        try:
            pil_image = load_image_from_url(primary_image.display_url)
            print(f"✅ Imagen cargada: {pil_image.size}")
        except Exception as e:
            print(f"❌ Error cargando imagen: {e}")
            return

        # Lista de colores a evaluar
        colores = [
            "black", "white", "gray", "red", "blue", "green",
            "yellow", "pink", "purple", "brown", "beige", "orange",
            "navy", "cream", "khaki"
        ]

        # Detectar color
        print("\n" + "-"*60)
        print("🎨 Ejecutando Zero-Shot Color Classification...")
        print("-"*60 + "\n")

        resultados = detect_color_zeroshot(pil_image, colores)

        # Mostrar resultados
        print("\n📊 RESULTADOS (Top 10):\n")
        print(f"{'#':<4} {'Color':<12} {'Probabilidad':<15} {'%':<10} {'Barra'}")
        print("-"*60)

        for i, res in enumerate(resultados[:10], 1):
            color = res['color']
            prob = res['probabilidad']
            pct = res['porcentaje']
            barra = '█' * int(pct / 2)  # Barra visual

            print(f"{i:<4} {color:<12} {prob:<15.4f} {pct:<10.2f} {barra}")

        # Mostrar top 3
        print("\n" + "="*60)
        print("🏆 TOP 3 COLORES DETECTADOS:")
        print("="*60)
        for i, res in enumerate(resultados[:3], 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            print(f"{emoji} {res['color'].upper()}: {res['porcentaje']:.2f}%")

        # Conclusión
        print("\n" + "="*60)
        top_color = resultados[0]
        if top_color['probabilidad'] > 0.15:
            print(f"✅ Color detectado con confianza: {top_color['color'].upper()}")
        else:
            print(f"⚠️ Detección con baja confianza. Top: {top_color['color'].upper()} ({top_color['porcentaje']:.1f}%)")
        print("="*60 + "\n")

if __name__ == '__main__':
    main()
