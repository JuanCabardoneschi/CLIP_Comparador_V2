"""
SearchOptimizer - Motor de ranking de resultados de búsqueda

Sistema de 3 capas para optimizar resultados de búsqueda visual:
1. Visual Layer: Scores de similitud CLIP (ya existente)
2. Metadata Layer: Matching de atributos (color, marca, patrón, etc.)
3. Business Layer: Métricas de negocio (stock, featured, descuentos)

Uso:
    config = StoreSearchConfig.query.get(store_id)
    optimizer = SearchOptimizer(config)
    ranked_results = optimizer.rank_results(raw_results, detected_attrs)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    Resultado enriquecido de búsqueda con scores de múltiples capas.

    Attributes:
        product_id: UUID del producto
        product: Objeto Product completo (para acceso a atributos)
        visual_score: Score de similitud visual CLIP [0-1]
        metadata_score: Score de matching de atributos [0-1]
        business_score: Score de métricas de negocio [0-1]
        final_score: Score ponderado final [0-1]
        debug_info: Información de debugging (opcional)

    Example:
        >>> result = SearchResult(
        ...     product_id='uuid-123',
        ...     product=product_obj,
        ...     visual_score=0.85,
        ...     metadata_score=0.60,
        ...     business_score=0.40,
        ...     final_score=0.75
        ... )
        >>> print(f"Score final: {result.final_score:.2%}")
        Score final: 75.00%
    """
    product_id: str
    product: Any  # Product object
    visual_score: float
    metadata_score: float
    business_score: float
    final_score: float
    debug_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializar resultado a diccionario.

        Returns:
            Dict con todos los scores y metadata del producto
        """
        return {
            'product_id': self.product_id,
            'visual_score': round(self.visual_score, 4),
            'metadata_score': round(self.metadata_score, 4),
            'business_score': round(self.business_score, 4),
            'final_score': round(self.final_score, 4),
            'debug_info': self.debug_info
        }


class SearchOptimizer:
    """
    Motor de optimización de resultados de búsqueda visual.

    Aplica ponderación configurable de 3 capas:
    - Visual: Similitud CLIP (peso configurable, default 0.6)
    - Metadata: Matching de atributos (peso configurable, default 0.3)
    - Business: Métricas de negocio (peso configurable, default 0.1)

    Attributes:
        config: StoreSearchConfig con pesos y metadata_config
        visual_weight: Peso para similitud visual [0-1]
        metadata_weight: Peso para atributos [0-1]
        business_weight: Peso para métricas negocio [0-1]
        metadata_config: Dict con pesos específicos por atributo

    Example:
        >>> config = StoreSearchConfig.query.get(store_id)
        >>> optimizer = SearchOptimizer(config)
        >>> raw_results = [
        ...     {'product': product1, 'similarity': 0.85},
        ...     {'product': product2, 'similarity': 0.78}
        ... ]
        >>> detected_attrs = {'color': 'BLANCO', 'brand': 'Nike'}
        >>> ranked = optimizer.rank_results(raw_results, detected_attrs)
        >>> print(f"Mejor resultado: {ranked[0].final_score:.2%}")
    """

    def __init__(self, config):
        """
        Inicializar SearchOptimizer con configuración de tienda.

        Args:
            config: StoreSearchConfig con pesos y metadata_config

        Raises:
            ValueError: Si los pesos no suman 1.0 ± 0.01
        """
        self.config = config
        self.visual_weight = config.visual_weight
        self.metadata_weight = config.metadata_weight
        self.business_weight = config.business_weight
        self.metadata_config = config.metadata_config or {}

        # Validar pesos
        total = self.visual_weight + self.metadata_weight + self.business_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Pesos no suman 1.0 (actual: {total}). "
                f"visual={self.visual_weight}, metadata={self.metadata_weight}, "
                f"business={self.business_weight}"
            )

        logger.debug(
            f"SearchOptimizer inicializado: "
            f"v={self.visual_weight}, m={self.metadata_weight}, b={self.business_weight}"
        )

    def _normalize_color_gender(self, color_str: str) -> str:
        """
        Normaliza género en nombres de colores para matching consistente.

        CLIP detecta colores en masculino (NEGRO, BLANCO, ROJO),
        pero en BD pueden estar en femenino (NEGRA, BLANCA, ROJA).

        Args:
            color_str: Color en mayúsculas (ej: "NEGRA", "BLANCO")

        Returns:
            Color normalizado a masculino (ej: "NEGRO", "BLANCO")
        """
        # Mapa de conversión femenino → masculino
        GENDER_MAP = {
            'NEGRA': 'NEGRO',
            'BLANCA': 'BLANCO',
            'ROJA': 'ROJO',
            'AMARILLA': 'AMARILLO',
            'VERDE': 'VERDE',  # Invariante
            'AZUL': 'AZUL',    # Invariante
            'GRIS': 'GRIS',    # Invariante
            'ROSA': 'ROSA',    # Invariante (o ROSADO)
            'NARANJA': 'NARANJA',  # Invariante
            'VIOLETA': 'VIOLETA',  # Invariante
            'MORADA': 'MORADO',
            'CELESTE': 'CELESTE',  # Invariante
            'TURQUESA': 'TURQUESA',  # Invariante
            'BEIGE': 'BEIGE',  # Invariante
            'MARRON': 'MARRON',  # Invariante (o MARRÓN)
            'DORADA': 'DORADO',
            'PLATEADA': 'PLATEADO',
            'BRONCEADA': 'BRONCEADO'
        }

        return GENDER_MAP.get(color_str.upper(), color_str.upper())

    def calculate_metadata_score(
        self,
        product: Any,
        detected_attributes: Dict[str, Any]
    ) -> float:
        """
        Calcular score de matching de atributos del producto.

        Compara atributos detectados en imagen con atributos del producto.
        Cada atributo tiene un peso configurable en metadata_config.

        Atributos soportados:
        - color: Matching exacto de color (peso default: 1.0)
        - brand: Matching exacto de marca (peso default: 1.0)
        - pattern: Matching de patrón/estampado (peso default: 0.8)
        - material: Matching de material (peso default: 0.7)
        - style: Matching de estilo (peso default: 0.6)

        Args:
            product: Objeto Product con atributos
            detected_attributes: Dict con atributos detectados en imagen
                Ej: {'color': 'BLANCO', 'brand': 'Nike', 'pattern': 'liso'}

        Returns:
            Score normalizado [0-1] donde:
            - 0.0 = Sin matching de atributos
            - 1.0 = Todos los atributos coinciden perfectamente

        Example:
            >>> product = Product(color='BLANCO', brand='Nike')
            >>> detected = {'color': 'BLANCO', 'brand': 'Adidas'}
            >>> score = optimizer.calculate_metadata_score(product, detected)
            >>> # Solo color coincide: score = 0.5 (1 de 2 atributos)
        """
        if not detected_attributes:
            logger.debug(f"Producto {product.id}: Sin atributos detectados, metadata_score=0.0")
            return 0.0

        # Obtener pesos de atributos desde config (con defaults)
        weights = {
            'color': self.metadata_config.get('color_weight', 1.0),
            'brand': self.metadata_config.get('brand_weight', 1.0),
            'pattern': self.metadata_config.get('pattern_weight', 0.8),
            'material': self.metadata_config.get('material_weight', 0.7),
            'style': self.metadata_config.get('style_weight', 0.6),
        }

        total_score = 0.0
        total_weight = 0.0
        matches = []

        for attr_name, detected_value in detected_attributes.items():
            # Obtener peso del atributo (si no está en defaults, usar 0.5)
            weight = weights.get(attr_name, 0.5)

            # Obtener valor del producto (priorizar JSONB sobre columnas directas)
            product_value = None

            # 1. Buscar en attributes JSONB primero (más confiable y actualizado)
            if hasattr(product, 'attributes') and product.attributes:
                product_value = product.attributes.get(attr_name)

            # 2. Fallback a atributos directos si no está en JSONB
            if product_value is None and hasattr(product, attr_name):
                product_value = getattr(product, attr_name)

            # Si no hay valor en producto, no contar este atributo
            if product_value is None:
                continue

            # Comparar valores (case-insensitive, strip whitespace)
            detected_str = str(detected_value).strip().upper()
            product_str = str(product_value).strip().upper()

            # Normalizar género para colores (NEGRO/NEGRA, BLANCO/BLANCA, etc.)
            if attr_name.lower() == 'color':
                detected_str = self._normalize_color_gender(detected_str)
                product_str = self._normalize_color_gender(product_str)

            is_match = detected_str == product_str

            if is_match:
                total_score += weight
                matches.append(f"{attr_name}={detected_value}")

            total_weight += weight

        # Normalizar score [0-1]
        normalized_score = (total_score / total_weight) if total_weight > 0 else 0.0

        # Cap a 1.0 por seguridad
        normalized_score = min(normalized_score, 1.0)

        logger.debug(
            f"Producto {product.id}: metadata_score={normalized_score:.3f} "
            f"(matches: {len(matches)}/{len(detected_attributes)} → {', '.join(matches) if matches else 'ninguno'})"
        )

        return normalized_score

    def calculate_business_score(self, product: Any) -> float:
        """
        Calcular score basado en métricas de negocio.

        Factores considerados:
        - Stock disponible (peso: 0.4)
          * stock > 0: contribuye 0.4
          * stock = 0: contribuye 0.0

        - Producto destacado/featured (peso: 0.3) [OPCIONAL]
          * is_featured = True: contribuye 0.3
          * is_featured = False: contribuye 0.0
          * Si campo no existe: no se considera

        - Descuento activo (peso: 0.3) [OPCIONAL]
          * discount > 0: contribuye 0.3
          * discount = 0: contribuye 0.0
          * Si campo no existe: no se considera

        Args:
            product: Objeto Product con atributos de negocio

        Returns:
            Score [0-1] donde:
            - 0.0 = Sin stock, no featured, sin descuento
            - 1.0 = Con stock, featured, con descuento

        Note:
            Si solo existe 'stock' (sin is_featured ni discount),
            el score se normaliza: stock>0 → 1.0, stock=0 → 0.0

        Example:
            >>> product = Product(stock=10, is_featured=True)
            >>> score = optimizer.calculate_business_score(product)
            >>> # stock (0.4) + featured (0.3) = 0.7
        """
        score = 0.0
        max_possible = 0.0
        factors = []

        # Factor 1: Stock (peso 0.4)
        STOCK_WEIGHT = 0.4
        max_possible += STOCK_WEIGHT

        stock = getattr(product, 'stock', 0) or 0
        if stock > 0:
            score += STOCK_WEIGHT
            factors.append(f"stock={stock}")

        # Factor 2: Featured (peso 0.3) - OPCIONAL
        FEATURED_WEIGHT = 0.3
        if hasattr(product, 'is_featured'):
            max_possible += FEATURED_WEIGHT
            if getattr(product, 'is_featured', False):
                score += FEATURED_WEIGHT
                factors.append("featured")

        # Factor 3: Descuento (peso 0.3) - OPCIONAL
        DISCOUNT_WEIGHT = 0.3
        if hasattr(product, 'discount'):
            max_possible += DISCOUNT_WEIGHT
            discount = getattr(product, 'discount', 0) or 0
            if discount > 0:
                score += DISCOUNT_WEIGHT
                factors.append(f"discount={discount}%")

        # Normalizar score [0-1]
        normalized_score = (score / max_possible) if max_possible > 0 else 0.0

        # Cap a 1.0 por seguridad
        normalized_score = min(normalized_score, 1.0)

        logger.debug(
            f"Producto {product.id}: business_score={normalized_score:.3f} "
            f"(factores: {', '.join(factors) if factors else 'ninguno'})"
        )

        return normalized_score

    def rank_results(
        self,
        raw_results: List[Dict[str, Any]],
        detected_attributes: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Rankear y ordenar resultados aplicando ponderación de 3 capas.

        Proceso:
        1. Para cada resultado crudo (product + similarity)
        2. Calcular metadata_score (matching de atributos)
        3. Calcular business_score (métricas de negocio)
        4. Aplicar fórmula ponderada:
           final_score = (visual * w_v) + (metadata * w_m) + (business * w_b)
        5. Crear SearchResult con todos los scores
        6. Ordenar por final_score descendente

        Args:
            raw_results: Lista de dicts con formato:
                [
                    {
                        'product': Product object,
                        'similarity': float [0-1],
                        'score': float [0-1] (alternativo a similarity)
                    },
                    ...
                ]
            detected_attributes: Dict opcional con atributos detectados
                Ej: {'color': 'BLANCO', 'brand': 'Nike'}
                Si es None, metadata_score será 0.0 para todos

        Returns:
            Lista ordenada de SearchResult (mayor a menor final_score)

        Raises:
            ValueError: Si raw_results está vacío o formato inválido

        Example:
            >>> raw_results = [
            ...     {'product': product1, 'similarity': 0.85},
            ...     {'product': product2, 'similarity': 0.78}
            ... ]
            >>> detected = {'color': 'BLANCO'}
            >>> ranked = optimizer.rank_results(raw_results, detected)
            >>> for result in ranked[:3]:
            ...     print(f"{result.product.name}: {result.final_score:.2%}")
            Camisa Blanca: 82.50%
            Polo Blanco: 78.30%
        """
        if not raw_results:
            logger.warning("rank_results llamado con lista vacía")
            return []

        detected_attributes = detected_attributes or {}
        ranked_results = []

        logger.info(
            f"Rankeando {len(raw_results)} resultados con atributos: "
            f"{list(detected_attributes.keys()) if detected_attributes else 'ninguno'}"
        )

        for raw_result in raw_results:
            # Extraer producto y visual score
            product = raw_result.get('product')
            if product is None:
                logger.error(f"Resultado sin producto: {raw_result}")
                continue

            # Visual score puede venir como 'similarity' o 'score'
            visual_score = raw_result.get('similarity') or raw_result.get('score', 0.0)

            # Calcular metadata score
            metadata_score = self.calculate_metadata_score(product, detected_attributes)

            # Calcular business score
            business_score = self.calculate_business_score(product)

            # Aplicar fórmula ponderada
            final_score = (
                (visual_score * self.visual_weight) +
                (metadata_score * self.metadata_weight) +
                (business_score * self.business_weight)
            )

            # Cap final score a 1.0
            final_score = min(final_score, 1.0)

            # Crear SearchResult
            result = SearchResult(
                product_id=str(product.id),
                product=product,
                visual_score=visual_score,
                metadata_score=metadata_score,
                business_score=business_score,
                final_score=final_score,
                debug_info={
                    'visual_contribution': visual_score * self.visual_weight,
                    'metadata_contribution': metadata_score * self.metadata_weight,
                    'business_contribution': business_score * self.business_weight,
                    'weights': {
                        'visual': self.visual_weight,
                        'metadata': self.metadata_weight,
                        'business': self.business_weight
                    }
                }
            )

            ranked_results.append(result)

            logger.debug(
                f"Rankeado {product.name}: "
                f"visual={visual_score:.3f} ({self.visual_weight}), "
                f"metadata={metadata_score:.3f} ({self.metadata_weight}), "
                f"business={business_score:.3f} ({self.business_weight}) "
                f"→ FINAL={final_score:.3f}"
            )

        # Ordenar por final_score descendente
        ranked_results.sort(key=lambda r: r.final_score, reverse=True)

        logger.info(
            f"Ranking completado: {len(ranked_results)} resultados ordenados. "
            f"Top score: {ranked_results[0].final_score:.3f}"
        )

        return ranked_results
