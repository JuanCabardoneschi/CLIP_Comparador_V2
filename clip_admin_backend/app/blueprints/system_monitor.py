"""
Blueprint de Monitoreo del Sistema
Endpoints para verificar uso de memoria y recursos
"""

import psutil
import os
import gc
from flask import Blueprint, jsonify
from flask_login import login_required
from app.utils.permissions import requires_role

bp = Blueprint("system_monitor", __name__, url_prefix="/system")


@bp.route("/memory", methods=["GET"])
@login_required
@requires_role('SUPER_ADMIN')
def memory_status():
    """Obtener estado de memoria del sistema (solo superadmin)"""

    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()

    # Obtener información del sistema
    virtual_memory = psutil.virtual_memory()

    # Verificar si CLIP está cargado
    from app.blueprints.embeddings import _clip_model, _clip_processor
    clip_loaded = _clip_model is not None

    return jsonify({
        "success": True,
        "process": {
            "pid": os.getpid(),
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),  # Resident Set Size
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2),  # Virtual Memory Size
            "percent": round(process.memory_percent(), 2)
        },
        "system": {
            "total_mb": round(virtual_memory.total / 1024 / 1024, 2),
            "available_mb": round(virtual_memory.available / 1024 / 1024, 2),
            "used_mb": round(virtual_memory.used / 1024 / 1024, 2),
            "percent": virtual_memory.percent
        },
        "models": {
            "clip_loaded": clip_loaded
        }
    })


@bp.route("/gc", methods=["POST"])
@login_required
@requires_role('SUPER_ADMIN')
def force_garbage_collection():
    """Forzar garbage collection (solo superadmin)"""

    process = psutil.Process(os.getpid())
    memory_before = process.memory_info().rss / 1024 / 1024

    # Forzar 3 ciclos de GC
    collected = []
    for i in range(3):
        collected.append(gc.collect())

    memory_after = process.memory_info().rss / 1024 / 1024
    freed_mb = memory_before - memory_after

    return jsonify({
        "success": True,
        "message": "Garbage collection ejecutado",
        "memory_before_mb": round(memory_before, 2),
        "memory_after_mb": round(memory_after, 2),
        "freed_mb": round(freed_mb, 2),
        "objects_collected": collected
    })


@bp.route("/clip-unload", methods=["POST"])
@login_required
@requires_role('SUPER_ADMIN')
def unload_clip_model():
    """Descargar modelo CLIP manualmente (solo superadmin)"""

    from app.blueprints.embeddings import _clip_model, _clip_processor, _clip_lock
    import torch

    with _clip_lock:
        if _clip_model is None:
            return jsonify({
                "success": False,
                "message": "Modelo CLIP no está cargado"
            })

        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024

        # Descargar modelo
        import app.blueprints.embeddings as emb_module
        emb_module._clip_model = None
        emb_module._clip_processor = None
        emb_module._clip_current_model_name = None

        # Limpiar GPU si está disponible
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Forzar GC
        gc.collect()
        gc.collect()

        memory_after = process.memory_info().rss / 1024 / 1024
        freed_mb = memory_before - memory_after

        return jsonify({
            "success": True,
            "message": "Modelo CLIP descargado manualmente",
            "memory_before_mb": round(memory_before, 2),
            "memory_after_mb": round(memory_after, 2),
            "freed_mb": round(freed_mb, 2)
        })
