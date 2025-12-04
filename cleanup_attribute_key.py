#!/usr/bin/env python
"""
Limpia un atributo antiguo (por ejemplo, 'variant_0') para un cliente:
- Elimina la fila de ProductAttributeConfig con ese key
- Quita ese key del JSON de atributos en todos los productos del cliente

Uso:
  python cleanup_attribute_key.py --client-id <UUID> --key variant_0
  python cleanup_attribute_key.py --list-integrations

Si no se pasa --client-id, usar --list-integrations para ver opciones.
"""
import argparse
import sys

from clip_admin_backend.wsgi import create_app


def list_integrations():
    from app.models.tiendanube_integration import TiendanubeIntegration
    rows = TiendanubeIntegration.query.all()
    print("Integraciones disponibles:")
    for r in rows:
        print(f"- store_id={r.store_id} | store_name={r.store_name} | client_id={r.client_id} | domain={r.store_domain}")


def cleanup_for_client(client_id: str, key: str):
    from app import db
    from app.models.product_attribute_config import ProductAttributeConfig
    from app.models.product import Product

    removed_configs = 0
    updated_products = 0

    # Eliminar config si existe
    cfg = ProductAttributeConfig.query.filter_by(client_id=client_id, key=key).first()
    if cfg:
        db.session.delete(cfg)
        removed_configs = 1

    # Actualizar productos
    products = Product.query.filter_by(client_id=client_id).all()
    for p in products:
        if not p.attributes or not isinstance(p.attributes, dict):
            continue
        if key in p.attributes:
            p.attributes.pop(key, None)
            updated_products += 1
    db.session.commit()

    return removed_configs, updated_products


def main():
    parser = argparse.ArgumentParser(description="Cleanup de clave de atributo en cliente")
    parser.add_argument("--client-id", dest="client_id", help="UUID del cliente")
    parser.add_argument("--key", dest="key", default="variant_0", help="Clave a eliminar (default: variant_0)")
    parser.add_argument("--list-integrations", action="store_true", help="Lista integraciones para elegir client_id")

    args = parser.parse_args()

    flask_app = create_app()
    with flask_app.app_context():
        if args.list_integrations and not args.client_id:
            list_integrations()
            return 0

        if not args.client_id:
            print("ERROR: Debes pasar --client-id o usar --list-integrations para ver opciones", file=sys.stderr)
            return 2

        key = args.key.strip()
        removed_configs, updated_products = cleanup_for_client(args.client_id, key)
        print({
            'success': True,
            'client_id': args.client_id,
            'key': key,
            'config_removed': removed_configs,
            'products_updated': updated_products
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
