"""
Utilidad para sembrar atributos por industria desde templates hardcoded.
No modifica esquema ni datos existentes: solo crea los que faltan.
"""
from typing import Dict, Any, List, Tuple

from app import db
from app.models.product_attribute_config import ProductAttributeConfig
from app.utils.industry_templates import get_industry_template


def seed_industry_attributes(client_id: str, industry: str, commit: bool = True, dry_run: bool = False) -> Dict[str, Any]:
    """
    Crea atributos mínimos para un cliente a partir del template de industria.

    - Solo crea los atributos que no existen (match por (client_id, key)).
    - Usa campos existentes del modelo (no requiere nuevas columnas).

    Args:
        client_id: UUID del cliente (str)
        industry: código de industria (e.g., 'fashion', 'automotive', 'home', 'electronics', 'generic')
        commit: si True, hace db.session.commit() al final
        dry_run: si True, no escribe en BD; solo calcula qué se crearía

    Returns:
        dict con resumen: {created_count, skipped_count, created_keys, skipped_keys}
    """
    template: Dict[str, Dict[str, Any]] = get_industry_template(industry)

    created_keys: List[str] = []
    skipped_keys: List[str] = []

    for order, (key, cfg) in enumerate(template.items(), start=1):
        # ¿Ya existe este atributo para el cliente?
        exists = ProductAttributeConfig.query.filter_by(client_id=client_id, key=key).first()
        if exists:
            skipped_keys.append(key)
            continue

        # Construir el nuevo atributo usando solo columnas existentes
        new_attr = ProductAttributeConfig(
            client_id=client_id,
            key=key,
            label=cfg.get('label', key.capitalize()),
            type=cfg.get('type', 'text'),
            required=cfg.get('required', False),
            options=cfg.get('options'),
            field_order=order,
            expose_in_search=cfg.get('expose_in_search', True),
        )

        if not dry_run:
            db.session.add(new_attr)
        created_keys.append(key)

    if commit and not dry_run and created_keys:
        db.session.commit()

    return {
        'industry': industry,
        'created_count': len(created_keys),
        'skipped_count': len(skipped_keys),
        'created_keys': created_keys,
        'skipped_keys': skipped_keys,
    }
