"""Verifica productos específicos en WooCommerce vs BD local.

Uso:
  python verify_woocommerce_product_ids.py --client-id <UUID> --ids 8171 8184 8191
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app
from app.services.woocommerce_sync_service import WooCommerceSyncService


def main():
    parser = argparse.ArgumentParser(description="Verificar productos WooCommerce por ID")
    parser.add_argument("--client-id", required=True, help="UUID del cliente")
    parser.add_argument("--ids", nargs='+', required=True, help="IDs externos de WooCommerce")
    args = parser.parse_args()

    product_ids = [int(x) for x in args.ids]

    app = create_app()
    with app.app_context():
        service = WooCommerceSyncService(args.client_id)
        result = service.verify_products_by_ids(product_ids)
        for item in result['items']:
            print(item)


if __name__ == "__main__":
    main()
