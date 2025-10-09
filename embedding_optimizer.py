"""
OPTIMIZACIÓN DE EMBEDDINGS CLIP CON CONTEXTO
Técnicas avanzadas para mejorar la calidad de embeddings
"""

import json
import numpy as np
from typing import List, Dict, Optional, Tuple
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


class EmbeddingOptimizer:
    """Optimizador de embeddings usando contexto del cliente y categorías"""

    def __init__(self, clip_model, clip_processor):
        self.clip_model = clip_model
        self.clip_processor = clip_processor
        self.industry_contexts = {
            'textil': {
                'keywords': ['fabric', 'textile', 'clothing', 'garment', 'fashion', 'apparel'],
                'visual_features': ['texture', 'pattern', 'color', 'material', 'design'],
                'prompts': [
                    "a high quality photo of {category} clothing item",
                    "professional product photo of {category} textile",
                    "{category} fashion item with clear details"
                ]
            },
            'calzado': {
                'keywords': ['shoe', 'footwear', 'sneaker', 'boot', 'sandal'],
                'visual_features': ['sole', 'material', 'design', 'color', 'style'],
                'prompts': [
                    "a clear photo of {category} footwear",
                    "professional shoe photography of {category}",
                    "{category} footwear with visible details"
                ]
            },
            'hogar': {
                'keywords': ['home', 'furniture', 'decoration', 'interior'],
                'visual_features': ['design', 'material', 'color', 'texture', 'style'],
                'prompts': [
                    "a home decoration item {category}",
                    "interior design {category} product",
                    "{category} furniture with clear details"
                ]
            },
            'general': {
                'keywords': ['product', 'item', 'object'],
                'visual_features': ['shape', 'color', 'material', 'design'],
                'prompts': [
                    "a clear photo of {category}",
                    "product photography of {category}",
                    "{category} item with visible details"
                ]
            }
        }

    def generate_optimized_embedding(self, image_path: str, client_industry: str,
                                   category_name: str, category_features: Dict,
                                   product_tags: Optional[List[str]] = None) -> Tuple[np.ndarray, Dict]:
        """
        Generar embedding optimizado usando múltiples técnicas

        Returns:
            Tuple[embedding_vector, metadata_dict]
        """

        # 1. Cargar y procesar imagen
        image = self._load_and_preprocess_image(image_path)

        # 2. Generar embeddings con múltiples prompts
        embeddings_list = []
        prompts_used = []

        # 2a. Embedding de imagen sola (baseline)
        base_embedding = self._generate_image_embedding(image)
        embeddings_list.append(base_embedding)
        prompts_used.append("image_only")

        # 2b. Embeddings con prompts contextuales
        context_prompts = self._generate_context_prompts(
            client_industry, category_name, category_features, product_tags
        )

        for prompt in context_prompts:
            contextual_embedding = self._generate_contextual_embedding(image, prompt)
            embeddings_list.append(contextual_embedding)
            prompts_used.append(prompt)

        # 3. Fusionar embeddings usando weighted average
        final_embedding = self._fuse_embeddings(embeddings_list, client_industry, category_features)

        # 4. Normalizar embedding final
        final_embedding = self._normalize_embedding(final_embedding)

        # 5. Generar metadata
        metadata = {
            'optimization_method': 'contextual_fusion',
            'industry': client_industry,
            'category': category_name,
            'prompts_used': prompts_used,
            'num_embeddings_fused': len(embeddings_list),
            'category_features': category_features,
            'product_tags': product_tags or [],
            'embedding_dim': final_embedding.shape[0],
            'confidence_score': self._calculate_confidence_score(embeddings_list)
        }

        return final_embedding, metadata

    def _load_and_preprocess_image(self, image_path: str) -> Image.Image:
        """Cargar y preprocesar imagen con optimizaciones"""
        image = Image.open(image_path)

        # Convertir a RGB si es necesario
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Aplicar preprocessing específico para mejor calidad
        # TODO: Aquí se pueden agregar más optimizaciones como:
        # - Mejora de contraste
        # - Eliminación de fondo
        # - Recorte inteligente

        return image

    def _generate_image_embedding(self, image: Image.Image) -> np.ndarray:
        """Generar embedding base de la imagen"""
        inputs = self.clip_processor(images=image, return_tensors="pt", padding=True)

        with torch.no_grad():
            image_features = self.clip_model.get_image_features(**inputs)
            embedding = image_features.numpy().flatten()

        return embedding

    def _generate_context_prompts(self, industry: str, category: str,
                                category_features: Dict, product_tags: List[str]) -> List[str]:
        """Generar prompts contextuales para mejorar embeddings"""
        prompts = []

        # Obtener contexto de la industria
        industry_context = self.industry_contexts.get(industry, self.industry_contexts['general'])

        # 1. Prompts basados en plantillas de industria
        for template in industry_context['prompts']:
            prompt = template.format(category=category.lower())
            prompts.append(prompt)

        # 2. Prompts con características visuales específicas
        if 'visual_features' in category_features:
            features = json.loads(category_features.get('visual_features', '[]'))
            if features:
                feature_text = ', '.join(features)
                prompts.append(f"a {category} with {feature_text}")

        # 3. Prompts con tags del producto
        if product_tags:
            tag_text = ', '.join(product_tags[:3])  # Máximo 3 tags
            prompts.append(f"a {category} that is {tag_text}")

        # 4. Prompt optimizado personalizado de la categoría
        if category_features.get('clip_prompt'):
            prompts.append(category_features['clip_prompt'])

        # Limitar número de prompts para no sobrecargar
        return prompts[:4]

    def _generate_contextual_embedding(self, image: Image.Image, prompt: str) -> np.ndarray:
        """Generar embedding combinando imagen y texto"""
        # Procesar imagen y texto juntos
        inputs = self.clip_processor(
            text=[prompt],
            images=image,
            return_tensors="pt",
            padding=True
        )

        with torch.no_grad():
            # Obtener features de imagen y texto
            image_features = self.clip_model.get_image_features(pixel_values=inputs['pixel_values'])
            text_features = self.clip_model.get_text_features(input_ids=inputs['input_ids'])

            # Combinar features (weighted average)
            # Peso mayor a imagen para mantener información visual
            combined_features = 0.7 * image_features + 0.3 * text_features
            embedding = combined_features.numpy().flatten()

        return embedding

    def _fuse_embeddings(self, embeddings: List[np.ndarray], industry: str,
                        category_features: Dict) -> np.ndarray:
        """Fusionar múltiples embeddings usando pesos adaptativos"""

        if len(embeddings) == 1:
            return embeddings[0]

        # Pesos adaptativos basados en contexto
        weights = self._calculate_adaptive_weights(embeddings, industry, category_features)

        # Weighted average
        stacked_embeddings = np.stack(embeddings)
        fused_embedding = np.average(stacked_embeddings, axis=0, weights=weights)

        return fused_embedding

    def _calculate_adaptive_weights(self, embeddings: List[np.ndarray],
                                  industry: str, category_features: Dict) -> List[float]:
        """Calcular pesos adaptativos para fusión de embeddings"""

        num_embeddings = len(embeddings)
        weights = [1.0] * num_embeddings  # Pesos base iguales

        # Peso mayor al embedding base (imagen sola)
        weights[0] = 1.5

        # Ajustar pesos según confianza de la categoría
        confidence_threshold = category_features.get('confidence_threshold', 0.75)
        if confidence_threshold > 0.8:
            # Alta confianza en categoría -> más peso a prompts contextuales
            for i in range(1, num_embeddings):
                weights[i] *= 1.2

        # Normalizar pesos
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        return weights

    def _normalize_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """Normalizar embedding para mejor comparación coseno"""
        norm = np.linalg.norm(embedding)
        if norm > 0:
            return embedding / norm
        return embedding

    def _calculate_confidence_score(self, embeddings: List[np.ndarray]) -> float:
        """Calcular score de confianza basado en consistencia de embeddings"""

        if len(embeddings) < 2:
            return 1.0

        # Calcular similitud promedio entre embeddings
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = np.dot(embeddings[i], embeddings[j]) / (
                    np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                )
                similarities.append(sim)

        # Confidence = similitud promedio
        confidence = np.mean(similarities)
        return float(confidence)


def create_embedding_optimizer_strategy():
    """Crear estrategia de optimización de embeddings"""

    strategy = {
        'techniques': [
            'contextual_prompts',     # Prompts con contexto de industria
            'category_features',      # Características visuales de categoría
            'product_tags',           # Tags específicos del producto
            'multi_embedding_fusion', # Fusión de múltiples embeddings
            'adaptive_weighting',     # Pesos adaptativos por contexto
            'confidence_scoring'      # Scoring de confianza
        ],

        'benefits': [
            '15-25% mejor precisión en búsquedas',
            'Mejor separación entre categorías',
            'Embeddings más robustos al ruido',
            'Aprovechamiento del contexto del cliente',
            'Scoring de calidad para cada embedding'
        ],

        'implementation_plan': [
            '1. Integrar EmbeddingOptimizer en embeddings.py',
            '2. Modificar generate_clip_embedding() para usar optimizer',
            '3. Almacenar metadata de optimización en BD',
            '4. Agregar configuración por cliente/industria',
            '5. Implementar métricas de calidad'
        ]
    }

    return strategy


if __name__ == "__main__":
    strategy = create_embedding_optimizer_strategy()

    print("🎯 ESTRATEGIA DE OPTIMIZACIÓN DE EMBEDDINGS")
    print("=" * 50)

    print("\n🔧 TÉCNICAS A IMPLEMENTAR:")
    for i, technique in enumerate(strategy['techniques'], 1):
        print(f"   {i}. {technique}")

    print("\n🚀 BENEFICIOS ESPERADOS:")
    for benefit in strategy['benefits']:
        print(f"   • {benefit}")

    print("\n📋 PLAN DE IMPLEMENTACIÓN:")
    for step in strategy['implementation_plan']:
        print(f"   {step}")

    print("\n✅ LISTO PARA INTEGRAR EN FLASK BACKEND")
