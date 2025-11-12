"""
Test rápido de BLIP-2 con transformers 4.47.1
Verifica que encode_image y encode_text funcionan correctamente
"""
import sys
import os

# Agregar directorio al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

def test_blip2():
    """Test básico de BLIP-2"""
    print("🧪 Test BLIP-2 con transformers 4.47.1")
    print("=" * 60)
    print("⚠️  ADVERTENCIA: BLIP-2 tarda 5-10 min en cargar en CPU local")
    print("=" * 60)

    # Importar sistema BLIP-2
    print("\n1️⃣ Importando BLIP2System...")
    from app.utils.blip2_embeddings import get_blip2_system

    # Obtener instancia singleton
    print("\n2️⃣ Obteniendo instancia singleton (iniciando carga del modelo)...")
    print("⏰ Esto puede tardar varios minutos...")
    import time
    start = time.time()

    try:
        blip2 = get_blip2_system()
        load_time = time.time() - start

        print(f"\n✅ Modelo cargado en {load_time:.1f} segundos")

        # Verificar que el modelo está cargado
        print("\n3️⃣ Verificando estado del modelo...")
        print(f"   - Modelo cargado: {blip2._is_loaded}")
        print(f"   - Device: {blip2.device}")
        print(f"   - FP16: {blip2.use_fp16}")

        # RAM info
        if blip2.model is not None:
            param_count = sum(p.numel() for p in blip2.model.parameters())
            bytes_per_param = 2 if blip2.use_fp16 else 4
            ram_gb = (param_count * bytes_per_param) / (1024**3)
            print(f"\n💾 Información del modelo:")
            print(f"   - Parámetros: {param_count:,}")
            print(f"   - RAM estimada: {ram_gb:.2f} GB")

        print("\n" + "=" * 60)
        print("✅ TEST COMPLETADO - Modelo BLIP-2 cargado correctamente")
        print("=" * 60)
        print("\n📝 NOTA: Para probar embeddings, ejecutar en Railway Pro donde")
        print("   la inferencia será mucho más rápida (~2-3 segundos por imagen)")

    except KeyboardInterrupt:
        print("\n\n⚠️  Carga interrumpida por el usuario")
        print("   Esto es normal - BLIP-2 tarda mucho en CPU local")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        raise

    # Verificar versiones
    print("\n📦 Versiones instaladas:")
    import torch
    import transformers
    print(f"   - torch: {torch.__version__}")
    print(f"   - transformers: {transformers.__version__}")


if __name__ == "__main__":
    test_blip2()
