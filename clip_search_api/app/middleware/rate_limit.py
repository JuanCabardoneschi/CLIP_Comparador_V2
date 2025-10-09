"""
Middleware de Rate Limiting para la API de búsqueda
"""

import os
import time
import redis
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware para rate limiting por cliente"""

    def __init__(
        self,
        app,
        calls_per_minute: int = 60,
        calls_per_hour: int = 1000
    ):
        """
        Inicializar middleware de rate limiting

        Args:
            app: Aplicación FastAPI
            calls_per_minute: Llamadas por minuto permitidas
            calls_per_hour: Llamadas por hora permitidas
        """
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.calls_per_hour = calls_per_hour

        # Configurar Redis
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True
        )

    async def dispatch(self, request: Request, call_next):
        """
        Procesar request con rate limiting

        Args:
            request: Request HTTP
            call_next: Siguiente middleware

        Returns:
            Response HTTP
        """
        try:
            # Obtener API Key del header
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                # Si no hay API Key, continuar (será manejado por auth middleware)
                return await call_next(request)

            # Verificar rate limits
            current_time = int(time.time())
            minute_key = f"rate_limit:{api_key}:minute:{current_time // 60}"
            hour_key = f"rate_limit:{api_key}:hour:{current_time // 3600}"

            # Incrementar contadores
            minute_count = self.redis_client.incr(minute_key)
            hour_count = self.redis_client.incr(hour_key)

            # Establecer expiración
            if minute_count == 1:
                self.redis_client.expire(minute_key, 60)
            if hour_count == 1:
                self.redis_client.expire(hour_key, 3600)

            # Verificar límites
            if minute_count > self.calls_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"Límite de {self.calls_per_minute} llamadas por minuto excedido",
                        "retry_after": 60 - (current_time % 60)
                    },
                    headers={
                        "X-RateLimit-Limit-Minute": str(self.calls_per_minute),
                        "X-RateLimit-Remaining-Minute": str(max(0, self.calls_per_minute - minute_count)),
                        "X-RateLimit-Reset-Minute": str(60 - (current_time % 60))
                    }
                )

            if hour_count > self.calls_per_hour:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"Límite de {self.calls_per_hour} llamadas por hora excedido",
                        "retry_after": 3600 - (current_time % 3600)
                    },
                    headers={
                        "X-RateLimit-Limit-Hour": str(self.calls_per_hour),
                        "X-RateLimit-Remaining-Hour": str(max(0, self.calls_per_hour - hour_count)),
                        "X-RateLimit-Reset-Hour": str(3600 - (current_time % 3600))
                    }
                )

            # Procesar request
            response = await call_next(request)

            # Agregar headers de rate limiting
            response.headers["X-RateLimit-Limit-Minute"] = str(self.calls_per_minute)
            response.headers["X-RateLimit-Remaining-Minute"] = str(max(0, self.calls_per_minute - minute_count))
            response.headers["X-RateLimit-Limit-Hour"] = str(self.calls_per_hour)
            response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, self.calls_per_hour - hour_count))

            return response

        except HTTPException:
            raise
        except Exception as e:
            # En caso de error con Redis, continuar sin rate limiting
            return await call_next(request)
