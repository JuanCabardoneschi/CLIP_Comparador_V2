"""
CLIP Engine Mock - Versión simplificada para testing sin PyTorch
"""

import hashlib
import json
import numpy as np
import redis
from typing import Optional


class CLIPEngine:
    """Motor CLIP mock para testing sin dependencias pesadas"""

    def __init__(self, model_name: str = "ViT-B/16", device: str = "cpu"):
        """Inicializar motor mock"""
        self.device = device
        self.model_name = model_name

        print(f"🔄 Inicializando CLIP Engine Mock {model_name}...")

        # Redis opcional para cache
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True
            )
            # Test conexión
            self.redis_client.ping()
            print("✅ Redis conectado")
        except:
            print("⚠️ Redis no disponible, usando cache en memoria")
            self.redis_client = None
            self._memory_cache = {}

        print(f"✅ CLIP Engine Mock {model_name} listo")

    def process_image(self, image_data: bytes) -> np.ndarray:
        """
        Procesar imagen mock - genera embedding aleatorio consistente
        """
        try:
            # Crear hash para consistencia
            image_hash = hashlib.md5(image_data).hexdigest()
            cache_key = f"clip_mock_embedding:{image_hash}"

            # Verificar cache
            if self.redis_client:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return np.array(json.loads(cached))
            elif cache_key in self._memory_cache:
                return self._memory_cache[cache_key]

            # Generar embedding mock basado en hash (consistente)
            np.random.seed(int(image_hash[:8], 16) % (2**32))
            embedding = np.random.normal(0, 1, 512)  # Vector 512D
            embedding = embedding / np.linalg.norm(embedding)  # Normalizar

            # Guardar en cache
            if self.redis_client:
                self.redis_client.setex(cache_key, 3600, json.dumps(embedding.tolist()))
            else:
                self._memory_cache[cache_key] = embedding

            return embedding

        except Exception as e:
            raise Exception(f"Error procesando imagen mock: {str(e)}")

    def process_text(self, text: str) -> np.ndarray:
        """
        Procesar texto mock - genera embedding basado en texto
        """
        try:
            # Hash del texto
            text_hash = hashlib.md5(text.encode()).hexdigest()
            cache_key = f"clip_mock_text:{text_hash}"

            # Verificar cache
            if self.redis_client:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return np.array(json.loads(cached))
            elif cache_key in self._memory_cache:
                return self._memory_cache[cache_key]

            # Generar embedding mock basado en texto
            np.random.seed(int(text_hash[:8], 16) % (2**32))
            embedding = np.random.normal(0, 1, 512)

            # Añadir sesgo basado en palabras clave
            text_lower = text.lower()
            if 'azul' in text_lower:
                embedding[0] += 0.5
            if 'rojo' in text_lower:
                embedding[1] += 0.5
            if 'camiseta' in text_lower:
                embedding[2] += 0.5
            if 'polo' in text_lower:
                embedding[3] += 0.5

            embedding = embedding / np.linalg.norm(embedding)

            # Guardar en cache
            if self.redis_client:
                self.redis_client.setex(cache_key, 3600, json.dumps(embedding.tolist()))
            else:
                self._memory_cache[cache_key] = embedding

            return embedding

        except Exception as e:
            raise Exception(f"Error procesando texto mock: {str(e)}")

    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calcular similitud coseno"""
        return float(np.dot(embedding1, embedding2))
