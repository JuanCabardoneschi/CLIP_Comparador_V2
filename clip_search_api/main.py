"""
CLIP Search API - FastAPI Application
API optimizada para búsqueda visual de productos
"""

import os
import time
from typing import List

import uvicorn
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Cargar variables de entorno
load_dotenv()

# Importar módulos
from app.core.clip_engine import CLIPEngine  # Usar versión real con Transformers
from app.core.search_engine import SearchEngine
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.search_response import (
    SearchResponse,
    SearchResult,
    HealthResponse,
    ErrorResponse
)

# Configuración
API_TITLE = os.getenv("API_TITLE", "CLIP Search API")
API_VERSION = os.getenv("API_VERSION", "2.0.0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "clip_admin_backend",
    "instance",
    "clip_comparador_v2.db"
)

# Crear aplicación FastAPI
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description="API de búsqueda visual inteligente basada en CLIP",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

# Inicializar engines globalmente (singleton pattern)
clip_engine = None
search_engine = None


@app.on_event("startup")
async def startup_event():
    """Inicializar engines al startup"""
    global clip_engine, search_engine

    print("🚀 Iniciando CLIP Search API...")

    # Inicializar CLIP engine
    clip_engine = CLIPEngine(model_name="openai/clip-vit-base-patch16", device="cpu")
    print("✅ CLIP Engine inicializado")

    # Inicializar search engine
    search_engine = SearchEngine(clip_engine, DB_PATH)
    print("✅ Search Engine inicializado")

    print("🎯 API lista para recibir requests")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup al shutdown"""
    print("🛑 Cerrando CLIP Search API...")


@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "service": "CLIP Search API",
        "version": API_VERSION,
        "status": "running",
        "endpoints": {
            "search_image": "/api/v2/search/image",
            "search_text": "/api/v2/search/text",
            "health": "/health",
            "docs": "/docs",
        },
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Contar productos indexados (ejemplo con client demo)
        indexed_products = 0
        if search_engine:
            indexed_products = search_engine.get_total_indexed_products("eda53b5a-d006-489d-a2bd-01a659e58652")

        return HealthResponse(
            status="healthy",
            version=API_VERSION,
            clip_model=clip_engine.model_name if clip_engine else "not_loaded",
            indexed_products=indexed_products
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "health_check_failed", "message": str(e)}
        )


@app.post("/api/v2/search/image", response_model=SearchResponse)
async def search_by_image(
    image: UploadFile = File(..., description="Imagen para búsqueda visual"),
    client_info: dict = Depends(verify_api_key),
    limit: int = 10,
    threshold: float = 0.1
):
    """
    Búsqueda visual por imagen

    Args:
        image: Archivo de imagen (JPG, PNG, WEBP)
        limit: Número máximo de resultados (1-20)
        threshold: Umbral mínimo de similitud (0.0-1.0)

    Returns:
        SearchResponse: Resultados de búsqueda
    """
    start_time = time.time()

    try:
        # Validar parámetros
        if limit < 1 or limit > 20:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_parameter", "message": "limit debe estar entre 1 y 20"}
            )

        if threshold < 0.0 or threshold > 1.0:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_parameter", "message": "threshold debe estar entre 0.0 y 1.0"}
            )

        # Validar archivo de imagen
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_file", "message": "El archivo debe ser una imagen"}
            )

        # Verificar tamaño (15MB máximo)
        max_size = 15 * 1024 * 1024  # 15MB
        content = await image.read()
        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"Imagen muy grande. Máximo: {max_size/1024/1024:.1f}MB"
                }
            )

        # Realizar búsqueda
        results = search_engine.search_by_image(
            image_data=content,
            client_id=client_info["client_id"],
            limit=limit,
            similarity_threshold=threshold
        )

        processing_time = time.time() - start_time

        return SearchResponse(
            query_type="image",
            results=[
                SearchResult(
                    product_id=r.product_id,
                    name=r.name,
                    description=r.description,
                    image_url=r.image_url,
                    similarity=r.similarity,
                    price=r.price,
                    sku=r.sku
                ) for r in results
            ],
            total_results=len(results),
            processing_time=processing_time,
            client_id=client_info["client_id"]
        )

    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={
                "error": "search_failed",
                "message": f"Error en búsqueda visual: {str(e)}",
                "processing_time": processing_time
            }
        )


@app.post("/api/v2/search/text", response_model=SearchResponse)
async def search_by_text(
    query: str,
    client_info: dict = Depends(verify_api_key),
    limit: int = 10,
    threshold: float = 0.1
):
    """
    Búsqueda visual por texto descriptivo

    Args:
        query: Texto descriptivo del producto buscado
        limit: Número máximo de resultados (1-20)
        threshold: Umbral mínimo de similitud (0.0-1.0)

    Returns:
        SearchResponse: Resultados de búsqueda
    """
    start_time = time.time()

    try:
        # Validar parámetros
        if not query or len(query.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_parameter", "message": "query debe tener al menos 3 caracteres"}
            )

        if limit < 1 or limit > 20:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_parameter", "message": "limit debe estar entre 1 y 20"}
            )

        if threshold < 0.0 or threshold > 1.0:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_parameter", "message": "threshold debe estar entre 0.0 y 1.0"}
            )

        # Realizar búsqueda
        results = search_engine.search_by_text(
            text=query.strip(),
            client_id=client_info["client_id"],
            limit=limit,
            similarity_threshold=threshold
        )

        processing_time = time.time() - start_time

        return SearchResponse(
            query_type="text",
            results=[
                SearchResult(
                    product_id=r.product_id,
                    name=r.name,
                    description=r.description,
                    image_url=r.image_url,
                    similarity=r.similarity,
                    price=r.price,
                    sku=r.sku
                ) for r in results
            ],
            total_results=len(results),
            processing_time=processing_time,
            client_id=client_info["client_id"]
        )

    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={
                "error": "search_failed",
                "message": f"Error en búsqueda por texto: {str(e)}",
                "processing_time": processing_time
            }
        )


@app.get("/api/v2/client/stats")
async def get_client_stats(client_info: dict = Depends(verify_api_key)):
    """
    Obtener estadísticas del cliente

    Returns:
        dict: Estadísticas del cliente
    """
    try:
        total_products = search_engine.get_total_indexed_products(client_info["client_id"])

        return {
            "client_id": client_info["client_id"],
            "client_name": client_info["client_name"],
            "total_indexed_products": total_products,
            "api_version": API_VERSION,
            "clip_model": clip_engine.model_name
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "stats_failed", "message": str(e)}
        )


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8000))

    print(f"🚀 Iniciando CLIP Search API en puerto {port}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
