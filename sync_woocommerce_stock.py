"""Re-sincroniza solo stock desde WooCommerce para un cliente.

Uso:
  python sync_woocommerce_stock.py --client-id <UUID>
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app
from app.services.woocommerce_sync_service import WooCommerceSyncService


def main():
    parser = argparse.ArgumentParser(description="Sync solo stock desde WooCommerce")
    parser.add_argument("--client-id", required=True, help="UUID del cliente")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        service = WooCommerceSyncService(args.client_id)
        result = service.sync_stock_only()
        print(
          f"✅ Stock sincronizado: updated={result['updated']} missing={result['missing']} total={result['total']}"
        )


if __name__ == "__main__":
    main()
