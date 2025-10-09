"""
CLIP Engine - Motor de procesamiento CLIP para búsqueda visual usando Transformers
"""

import io
import os
import torch
import numpy as np
from PIL import Image
from typing import List, Optional, Tuple
import sqlite3
import redis
import json
import hashlib
from transformers import CLIPProcessor, CLIPModel


class CLIPEngine:
    """Motor CLIP para procesar imágenes y generar embeddings usando Transformers"""

    def __init__(self, model_name: str = "openai/clip-vit-base-patch16", device: str = "cpu"):
        """
        Inicializar el motor CLIP

        Args:
            model_name: Modelo CLIP a usar (default: openai/clip-vit-base-patch16)
            device: Dispositivo de procesamiento (cpu/cuda)
        """
        self.device = device
        self.model_name = model_name

        # Cargar modelo CLIP con Transformers
        print(f"🔄 Cargando modelo CLIP {model_name} en {device}...")
        self.model = CLIPModel.from_pretrained(model_name)
        self.processor = CLIPProcessor.from_pretrained(model_name)

        # Configurar dispositivo
        self.model.eval()
        if device == "cuda" and torch.cuda.is_available():
            self.model = self.model.cuda()
            print(f"✅ Modelo CLIP cargado en GPU")
        else:
            print(f"✅ Modelo CLIP cargado en CPU")

        # Configurar Redis para cache
        try:
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                decode_responses=True
            )
            # Test conexión
            self.redis_client.ping()
            print("✅ Redis conectado para cache de embeddings")
        except Exception:
            print("⚠️ Redis no disponible, usando solo memoria")
            self.redis_client = None

    def process_image(self, image_data: bytes) -> np.ndarray:
        """
        Procesar imagen y generar embedding CLIP

        Args:
            image_data: Datos binarios de la imagen

        Returns:
            np.ndarray: Vector embedding de la imagen
        """
        try:
            # Crear hash para cache
            image_hash = hashlib.md5(image_data).hexdigest()
            cache_key = f"clip_embedding:{image_hash}"

            # Verificar cache
            if self.redis_client:
                cached_embedding = self.redis_client.get(cache_key)
                if cached_embedding:
                    return np.array(json.loads(cached_embedding))

            # Procesar imagen
            image = Image.open(io.BytesIO(image_data)).convert('RGB')

            # Usar el processor de Transformers
            inputs = self.processor(images=image, return_tensors="pt")

            # Mover al dispositivo correcto
            if self.device == "cuda" and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Generar embedding
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)
                embedding = image_features.cpu().numpy().flatten()

            # Normalizar embedding
            embedding = embedding / np.linalg.norm(embedding)

            # Guardar en cache (24 horas)
            if self.redis_client:
                self.redis_client.setex(
                    cache_key,
                    86400,  # 24 horas
                    json.dumps(embedding.tolist())
                )

            return embedding

        except Exception as e:
            raise Exception(f"Error procesando imagen: {str(e)}")

    def process_text(self, text: str) -> np.ndarray:
        """
        Procesar texto y generar embedding CLIP

        Args:
            text: Texto a procesar

        Returns:
            np.ndarray: Vector embedding del texto
        """
        try:
            # Crear hash para cache
            text_hash = hashlib.md5(text.encode()).hexdigest()
            cache_key = f"clip_text_embedding:{text_hash}"

            # Verificar cache
            if self.redis_client:
                cached_embedding = self.redis_client.get(cache_key)
                if cached_embedding:
                    return np.array(json.loads(cached_embedding))

            # Procesar texto con Transformers
            inputs = self.processor(text=[text], return_tensors="pt", padding=True)

            # Mover al dispositivo correcto
            if self.device == "cuda" and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Generar embedding
            with torch.no_grad():
                text_features = self.model.get_text_features(**inputs)
                embedding = text_features.cpu().numpy().flatten()

            # Normalizar embedding
            embedding = embedding / np.linalg.norm(embedding)

            # Guardar en cache (24 horas)
            if self.redis_client:
                self.redis_client.setex(
                    cache_key,
                    86400,  # 24 horas
                    json.dumps(embedding.tolist())
                )

            return embedding

        except Exception as e:
            raise Exception(f"Error procesando texto: {str(e)}")

    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calcular similitud coseno entre dos embeddings

        Args:
            embedding1: Primer vector embedding
            embedding2: Segundo vector embedding

        Returns:
            float: Similitud coseno (0-1)
        """
        return float(np.dot(embedding1, embedding2))
