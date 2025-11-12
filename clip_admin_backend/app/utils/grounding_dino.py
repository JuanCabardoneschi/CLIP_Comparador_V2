"""Utilidad Grounding DINO (modo prueba)
=========================================

Detección zero-shot de prendas usando Grounding DINO.
Se usa un wrapper (groundingdino-py). Carga lazy y cachea el modelo.

Nota: Esta versión es experimental y sólo busca mejorar la región a clasificar
por CLIP (recorte más relevante). No reemplaza la lógica multi-crop todavía.
"""
from __future__ import annotations

import threading
from typing import List, Optional, Tuple, Dict

from PIL import Image

try:
    # Import dentro de try para no romper si dependencia no instalada aún
    from groundingdino import Model  # type: ignore
except Exception:  # pragma: no cover - fallback si no está instalado
    Model = None  # type: ignore

_model_lock = threading.Lock()
_grounding_model: Optional[Model] = None

DEFAULT_MODEL_NAME = "groundingdino-swin-tiny"  # modelo liviano para pruebas


def _load_model() -> Optional[Model]:
    """Carga lazy del modelo grounding DINO.

    Returns:
        Instancia del modelo o None si no disponible.
    """
    global _grounding_model
    if _grounding_model is not None:
        return _grounding_model

    if Model is None:
        print("⚠️ groundingdino-py no instalado todavía. Ejecuta: pip install groundingdino-py")
        return None

    with _model_lock:
        if _grounding_model is None:
            try:
                print(f"🔄 Cargando Grounding DINO ({DEFAULT_MODEL_NAME})...")
                _grounding_model = Model(model_name=DEFAULT_MODEL_NAME)
                print("✅ Grounding DINO cargado correctamente")
            except Exception as e:
                print(f"❌ Error cargando modelo Grounding DINO: {e}")
                _grounding_model = None
    return _grounding_model


def detect_and_crop(image: Image, category_names: List[str],
                    box_threshold: float = 0.30,
                    text_threshold: float = 0.25) -> Tuple[Image, Dict]:
    """Detectar prenda y devolver imagen recortada + metadata.

    Args:
        image: PIL Image original.
        category_names: Lista de categorías activas (se usarán como prompt concatenado).
        box_threshold: Umbral de box.
        text_threshold: Umbral de texto.

    Returns:
        (cropped_image, metadata) donde metadata contiene:
            {
              'label': str | None,
              'score': float,
              'box': [x1,y1,x2,y2] | None,
              'used_grounding': bool,
              'error': str | None
            }
    """
    model = _load_model()
    if model is None:
        return image, {
            'label': None,
            'score': 0.0,
            'box': None,
            'used_grounding': False,
            'error': 'Modelo no disponible'
        }

    # Construir prompt concatenado (groundingdino espera frase separada por comas/puntos)
    prompt = ". ".join([name.lower() for name in category_names])

    try:
        detections = model.predict_with_caption(
            image=image,
            caption=prompt,
            box_threshold=box_threshold,
            text_threshold=text_threshold
        )
        # detections es lista de dicts: {'box': [x1,y1,x2,y2], 'label': '...', 'score': 0.78}
        if not detections:
            return image, {
                'label': None,
                'score': 0.0,
                'box': None,
                'used_grounding': True,
                'error': 'Sin detecciones'
            }
        # Elegir mejor score
        best = max(detections, key=lambda d: d.get('score', 0))
        box = best['box']
        x1, y1, x2, y2 = box
        # Padding 8%
        pad_x = int((x2 - x1) * 0.08)
        pad_y = int((y2 - y1) * 0.08)
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(image.width, x2 + pad_x)
        y2 = min(image.height, y2 + pad_y)
        cropped = image.crop((x1, y1, x2, y2))
        return cropped, {
            'label': best.get('label'),
            'score': float(best.get('score', 0.0)),
            'box': [int(x1), int(y1), int(x2), int(y2)],
            'used_grounding': True,
            'error': None
        }
    except Exception as e:  # pragma: no cover - errores runtime externos
        return image, {
            'label': None,
            'score': 0.0,
            'box': None,
            'used_grounding': True,
            'error': str(e)
        }

__all__ = ["detect_and_crop"]
