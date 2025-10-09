"""
Middleware de autenticación para la API de búsqueda
"""

import os
import sqlite3
from fastapi import HTTPException, Header
from typing import Optional


async def verify_api_key(x_api_key: str = Header(..., description="API Key del cliente")):
    """
    Verificar API Key y devolver información del cliente

    Args:
        x_api_key: API Key en el header X-API-Key

    Returns:
        dict: Información del cliente

    Raises:
        HTTPException: Si la API Key es inválida
    """
    try:
        # Conectar a la base de datos del admin
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "..",
            "clip_admin_backend",
            "instance",
            "clip_comparador_v2.db"
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Buscar la API Key activa
        query = """
            SELECT c.id, c.name, c.domain_allowed
            FROM clients c
            WHERE c.api_key = ? AND c.is_active = 1
        """

        cursor = conn.execute(query, (x_api_key,))
        client = cursor.fetchone()
        conn.close()

        if not client:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "unauthorized",
                    "message": "API Key inválida o inactiva"
                }
            )

        return {
            "client_id": client["id"],
            "client_name": client["name"],
            "domain_allowed": client["domain_allowed"]
        }

    except sqlite3.Error as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "database_error",
                "message": f"Error de base de datos: {str(e)}"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Error interno: {str(e)}"
            }
        )
