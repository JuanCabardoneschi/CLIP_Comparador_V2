"""
Search Engine - Motor de búsqueda visual con CLIP
"""

import os
import sqlite3
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from .clip_engine import CLIPEngine


def get_image_display_url(cloudinary_url, filename, client_slug="demo_fashion_store"):
    """
    Replica la lógica de la clase Image para generar URLs de display
    Prioriza Cloudinary sobre rutas locales
    """
    # Si tiene URL de Cloudinary, usarla (preferido)
    if cloudinary_url:
        return cloudinary_url

    # Fallback a URL local si no tiene Cloudinary
    if filename:
        return f"/static/uploads/clients/{client_slug}/{filename}"

    # Placeholder si no hay nada
    return '/static/images/placeholder.svg'


@dataclass
class SearchResult:
    """Resultado de búsqueda"""
    product_id: str
    client_id: str
    name: str
    description: str
    image_url: str
    similarity: float
    price: Optional[float] = None
    sku: Optional[str] = None


class SearchEngine:
    """Motor de búsqueda visual"""

    def __init__(self, clip_engine: CLIPEngine, db_path: str):
        """
        Inicializar motor de búsqueda

        Args:
            clip_engine: Instancia del motor CLIP
            db_path: Ruta a la base de datos
        """
        self.clip_engine = clip_engine
        self.db_path = db_path

    def search_by_image(
        self,
        image_data: bytes,
        client_id: str,
        limit: int = 10,
        similarity_threshold: float = 0.1
    ) -> List[SearchResult]:
        """
        Buscar productos similares por imagen

        Args:
            image_data: Datos binarios de la imagen
            client_id: ID del cliente
            limit: Número máximo de resultados
            similarity_threshold: Umbral mínimo de similitud

        Returns:
            List[SearchResult]: Lista de productos similares
        """
        # Generar embedding de la imagen de consulta
        query_embedding = self.clip_engine.process_image(image_data)

        # Buscar en la base de datos
        results = self._search_in_database(
            query_embedding,
            client_id,
            limit,
            similarity_threshold
        )

        return results

    def search_by_text(
        self,
        text: str,
        client_id: str,
        limit: int = 10,
        similarity_threshold: float = 0.1
    ) -> List[SearchResult]:
        """
        Buscar productos por descripción de texto

        Args:
            text: Texto de consulta
            client_id: ID del cliente
            limit: Número máximo de resultados
            similarity_threshold: Umbral mínimo de similitud

        Returns:
            List[SearchResult]: Lista de productos similares
        """
        # Generar embedding del texto de consulta
        query_embedding = self.clip_engine.process_text(text)

        # Buscar en la base de datos
        results = self._search_in_database(
            query_embedding,
            client_id,
            limit,
            similarity_threshold
        )

        return results

    def _search_in_database(
        self,
        query_embedding: np.ndarray,
        client_id: str,
        limit: int,
        similarity_threshold: float
    ) -> List[SearchResult]:
        """
        Buscar en la base de datos usando embedding

        Args:
            query_embedding: Vector embedding de consulta
            client_id: ID del cliente
            limit: Número máximo de resultados
            similarity_threshold: Umbral mínimo de similitud

        Returns:
            List[SearchResult]: Lista de productos similares
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            # Query para obtener imágenes procesadas del cliente
            query = """
                SELECT
                    i.id as image_id,
                    i.embedding,
                    i.filename,
                    i.cloudinary_url,
                    p.id as product_id,
                    p.name,
                    p.description,
                    p.price,
                    p.sku,
                    p.client_id
                FROM images i
                JOIN products p ON i.product_id = p.id
                WHERE p.client_id = ?
                AND i.is_processed = 1
                AND i.embedding IS NOT NULL
                AND p.is_active = 1
            """

            cursor = conn.execute(query, (client_id,))
            rows = cursor.fetchall()

            results = []

            for row in rows:
                # DEBUG: Imprimir datos de la fila
                print(f"🔍 DEBUG - Row data:")
                print(f"  filename: {row['filename']}")
                print(f"  cloudinary_url: {row['cloudinary_url']}")
                print(f"  product name: {row['name']}")

                # Deserializar embedding almacenado
                stored_embedding = np.array(eval(row['embedding']))

                # Calcular similitud
                similarity = self.clip_engine.calculate_similarity(
                    query_embedding,
                    stored_embedding
                )

                # Filtrar por umbral
                if similarity >= similarity_threshold:
                    # Usar la función helper que replica la lógica de la clase Image
                    image_url = get_image_display_url(row['cloudinary_url'], row['filename'])

                    result = SearchResult(
                        product_id=row['product_id'],
                        client_id=row['client_id'],
                        name=row['name'],
                        description=row['description'] or '',
                        image_url=image_url,
                        similarity=float(similarity),
                        price=float(row['price']) if row['price'] else None,
                        sku=row['sku']
                    )
                    results.append(result)

            # Ordenar por similitud descendente
            results.sort(key=lambda x: x.similarity, reverse=True)

            # Limitar resultados
            results = results[:limit]

            conn.close()

            return results

        except Exception as e:
            raise Exception(f"Error en búsqueda de base de datos: {str(e)}")

    def get_total_indexed_products(self, client_id: str) -> int:
        """
        Obtener número total de productos indexados para un cliente

        Args:
            client_id: ID del cliente

        Returns:
            int: Número de productos indexados
        """
        try:
            conn = sqlite3.connect(self.db_path)

            query = """
                SELECT COUNT(*) as total
                FROM images i
                JOIN products p ON i.product_id = p.id
                WHERE p.client_id = ?
                AND i.is_processed = 1
                AND i.embedding IS NOT NULL
                AND p.is_active = 1
            """

            cursor = conn.execute(query, (client_id,))
            result = cursor.fetchone()

            conn.close()

            return result[0] if result else 0

        except Exception as e:
            raise Exception(f"Error obteniendo total de productos: {str(e)}")
