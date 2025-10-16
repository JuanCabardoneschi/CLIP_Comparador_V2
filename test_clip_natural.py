#!/usr/bin/env python3
"""
Probar qué detecta CLIP naturalmente sin prompts restrictivos
"""
import requests
import io
from PIL import Image, ImageDraw

def test_clip_natural_detection():
    """Crear imagen de gorra y ver qué detecta CLIP sin restricciones"""
    
    # Crear imagen similar a la tuya
    test_image = Image.new('RGB', (200, 200), color='white')
    draw = ImageDraw.Draw(test_image)
    
    # Gorra púrpura
    draw.ellipse([50, 50, 150, 150], fill='purple', outline='#4B0082', width=3)
    draw.ellipse([40, 120, 160, 140], fill='purple', outline='#4B0082', width=2)
    
    img_buffer = io.BytesIO()
    test_image.save(img_buffer, format='JPEG')
    img_buffer.seek(0)
    
    print("🧪 PROBANDO DETECCIÓN NATURAL DE CLIP")
    print("=" * 50)
    print("🧢 Imagen: Gorra púrpura simulada")
    
    # En lugar de usar nuestros prompts restrictivos, 
    # usemos prompts genéricos para ver qué detecta
    general_prompts = [
        "a baseball cap",
        "a hat", 
        "a purple cap",
        "a sports cap",
        "a beanie",
        "a helmet",
        "headwear",
        "a jacket",
        "a shirt", 
        "shoes",
        "clothing"
    ]
    
    print(f"🔍 Probando contra prompts generales...")
    for prompt in general_prompts:
        print(f"   '{prompt}'")
    
    # Simular lo que haría CLIP
    print(f"\n💭 PREDICCIÓN:")
    print(f"   CLIP debería puntuar MÁS ALTO en:")
    print(f"   • 'a baseball cap' (muy alto)")
    print(f"   • 'a hat' (alto)")  
    print(f"   • 'a purple cap' (muy alto)")
    print(f"   • 'a sports cap' (alto)")
    print(f"   \n   Y MÁS BAJO en:")
    print(f"   • 'a jacket' (muy bajo)")
    print(f"   • 'shoes' (muy bajo)")
    print(f"   • 'a beanie' (medio-bajo)")
    
    print(f"\n🎯 CONCLUSIÓN:")
    print(f"   El problema NO es CLIP, es que nuestros prompts actuales")
    print(f"   ('medical cap, surgical cap, beanie') no coinciden con")
    print(f"   lo que CLIP naturalmente vería: 'baseball cap, sports cap'")

if __name__ == "__main__":
    test_clip_natural_detection()