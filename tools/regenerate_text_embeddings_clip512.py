#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Regenera embeddings de TEXTO en la tabla `embeddings` usando CLIP ViT-B/16 (512D).

- Corrige inconsistencias de dimensión (p.ej., 384D → 512D)
- Permite filtrar por tipo (`--types vocabulary,color,category`) o por claves específicas (`--keys vocab:estampado,color:negro`)
- Por defecto procesa SOLO filas con dimensión distinta a 512 cuando la opción `--only-wrong-dim` está activa (default)

Uso:
  python tools/regenerate_text_embeddings_clip512.py --types vocabulary,color --only-wrong-dim
  python tools/regenerate_text_embeddings_clip512.py --keys vocab:estampado,color:negro
  python tools/regenerate_text_embeddings_clip512.py --all   # Regenera todo sin filtrar
"""
import os
import sys
import json
import argparse
from typing import List, Optional

# Preparar path para importar la app
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'clip_admin_backend'))

from app import create_app, db  # type: ignore
from app.models.embedding import Embedding  # type: ignore
from app.blueprints.embeddings import get_clip_model  # type: ignore

import numpy as np
import torch


def _text_to_embedding_512(text: str) -> List[float]:
    """Genera embedding de texto con CLIP (ViT-B/16) retornando 512 floats normalizados.
    """
    model, processor = get_clip_model()
    model.eval()
    with torch.no_grad():
        inputs = processor(text=[text], return_tensors="pt", padding=True)
        outputs = model.get_text_features(**inputs)  # [1, 512]
        emb = outputs[0].cpu().numpy().astype(np.float32)
        # Normalizar a norma 1
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb.tolist()


def _key_to_text(key: str) -> str:
    """Convierte una clave de embeddings (p.ej. 'vocab:estampado') a texto base."""
    if not key:
        return ""
    if ':' in key:
        return key.split(':', 1)[1].replace('_', ' ').strip()
    return key.replace('_', ' ').strip()


def _dim_of_json_vector(js: str) -> Optional[int]:
    try:
        arr = json.loads(js)
        return len(arr) if isinstance(arr, list) else None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--types', help='Tipos a procesar, coma-separados (vocabulary,color,category)', default='')
    parser.add_argument('--keys', help='Claves específicas coma-separadas (p.ej. "vocab:estampado,color:negro")', default='')
    parser.add_argument('--all', action='store_true', help='Procesar todos los registros (ignora filtros)')
    parser.add_argument('--only-wrong-dim', action='store_true', default=True, help='Solo corregir filas con dimensión != 512')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        q = Embedding.query

        if not args.all:
            type_list = [t.strip() for t in args.types.split(',') if t.strip()] if args.types else []
            key_list = [k.strip() for k in args.keys.split(',') if k.strip()] if args.keys else []

            if type_list:
                q = q.filter(Embedding.type.in_(type_list))
            if key_list:
                q = q.filter(Embedding.key.in_(key_list))

        rows: List[Embedding] = q.all()
        if not rows:
            print("⚠️ No se encontraron filas para procesar (ver filtros)")
            return

        print(f"📊 Filas a evaluar: {len(rows)}")
        updated = 0
        skipped = 0

        for row in rows:
            try:
                current_dim = _dim_of_json_vector(row.embedding)
                if args.only_wrong_dim and current_dim == 512:
                    skipped += 1
                    continue

                text = _key_to_text(row.key)
                if not text:
                    print(f"   ⚠️ Saltando '{row.key}': texto vacío")
                    skipped += 1
                    continue

                new_emb = _text_to_embedding_512(text)
                row.embedding = json.dumps(new_emb)
                db.session.add(row)
                updated += 1

                if updated % 25 == 0:
                    db.session.commit()
                    print(f"   💾 Commit intermedio: {updated} filas actualizadas")

            except Exception as e:
                print(f"   ❌ Error procesando '{row.key}': {e}")

        db.session.commit()
        print("\n✅ Proceso completado")
        print(f"   - Actualizadas: {updated}")
        print(f"   - Omitidas: {skipped}")
        print(f"   - Total examinadas: {len(rows)}")


if __name__ == '__main__':
    main()
