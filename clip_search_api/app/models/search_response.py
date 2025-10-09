"""
Modelos de respuesta para la API de búsqueda
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class SearchResult(BaseModel):
    """Resultado individual de búsqueda"""
    product_id: str = Field(..., description="ID único del producto")
    name: str = Field(..., description="Nombre del producto")
    description: str = Field(default="", description="Descripción del producto")
    image_url: str = Field(..., description="URL de la imagen del producto")
    similarity: float = Field(..., ge=0, le=1, description="Similitud (0-1)")
    price: Optional[float] = Field(None, description="Precio del producto")
    sku: Optional[str] = Field(None, description="SKU del producto")


class SearchResponse(BaseModel):
    """Respuesta completa de búsqueda"""
    query_type: str = Field(..., description="Tipo de consulta (image/text)")
    results: List[SearchResult] = Field(default=[], description="Resultados de búsqueda")
    total_results: int = Field(..., description="Número total de resultados")
    processing_time: float = Field(..., description="Tiempo de procesamiento en segundos")
    client_id: str = Field(..., description="ID del cliente")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de la consulta")


class HealthResponse(BaseModel):
    """Respuesta de health check"""
    status: str = Field(..., description="Estado del servicio")
    version: str = Field(..., description="Versión de la API")
    clip_model: str = Field(..., description="Modelo CLIP utilizado")
    indexed_products: int = Field(..., description="Productos indexados")


class ErrorResponse(BaseModel):
    """Respuesta de error"""
    error: str = Field(..., description="Tipo de error")
    message: str = Field(..., description="Mensaje de error")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp del error")
