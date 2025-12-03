"""
Script para corregir productos en Tiendanube:
1. Remover "**Características**" de las descripciones
2. Crear variantes reales basadas en esas características

Uso:
    python fix_tiendanube_products.py --store-id 7019043 --dry-run
    python fix_tiendanube_products.py --store-id 7019043  # Aplicar cambios
"""

import os
import sys
import re
import requests
import argparse
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Cargar variables de entorno
load_dotenv('.env.railway')

class TiendanubeProductFixer:
    def __init__(self, store_id: str, access_token: str, dry_run: bool = True):
        self.store_id = store_id
        self.access_token = access_token
        self.dry_run = dry_run
        self.base_url = f"https://api.tiendanube.com/v1/{store_id}"
        self.headers = {
            'Authentication': f'bearer {access_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'CLIP Comparador (admin@clipcomparador.com)'
        }

    def get_products(self) -> List[Dict]:
        """Obtener todos los productos de la tienda"""
        products = []
        page = 1
        per_page = 50

        while True:
            url = f"{self.base_url}/products"
            params = {'page': page, 'per_page': per_page}

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            page_products = response.json()
            if not page_products:
                break

            products.extend(page_products)
            print(f"📦 Obtenidos {len(page_products)} productos (página {page})")

            if len(page_products) < per_page:
                break

            page += 1

        return products

    def extract_characteristics(self, description: str) -> Optional[Dict[str, str]]:
        """
        Extraer características del formato:
        **Características:**
        - Color: Rojo
        - Talla: M
        """
        if not description or '**Características**' not in description:
            return None

        # Buscar la sección de características
        match = re.search(
            r'\*\*Características\*\*:?\s*\n((?:[-•]\s*\w+:\s*.+\n?)+)',
            description,
            re.IGNORECASE
        )

        if not match:
            return None

        characteristics_text = match.group(1)
        characteristics = {}

        # Extraer cada característica
        for line in characteristics_text.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Remover bullets (-, •, *)
            line = re.sub(r'^[-•*]\s*', '', line)

            # Buscar patrón "Clave: Valor"
            char_match = re.match(r'(\w+):\s*(.+)', line)
            if char_match:
                key = char_match.group(1).strip()
                value = char_match.group(2).strip()
                characteristics[key] = value

        return characteristics if characteristics else None

    def clean_description(self, description: str) -> str:
        """Remover la sección de Características de la descripción"""
        if not description:
            return description

        # Remover todo desde "**Características**" hasta el final o hasta encontrar otro contenido
        cleaned = re.sub(
            r'\n?\*\*Características\*\*:?\s*\n((?:[-•]\s*\w+:\s*.+\n?)+)',
            '',
            description,
            flags=re.IGNORECASE
        )

        return cleaned.strip()

    def get_variant_attribute_name(self, char_key: str) -> str:
        """
        Mapear nombre de característica a atributo de variante Tiendanube.
        Tiendanube soporta cualquier nombre, pero usaremos nombres estándar.
        """
        mapping = {
            'Color': 'Color',
            'Talla': 'Talle',  # En Argentina se usa "Talle"
            'Tamaño': 'Tamaño',
            'Material': 'Material',
            'Estilo': 'Estilo'
        }

        return mapping.get(char_key, char_key)

    def create_variants_from_characteristics(
        self,
        product_id: int,
        characteristics: Dict[str, str],
        current_price: float,
        current_stock: Optional[int] = None
    ) -> List[Dict]:
        """
        Crear variantes basadas en las características extraídas.
        Tiendanube requiere al menos una variante por producto.
        """
        variants = []

        # Si hay características, crear variantes
        if characteristics:
            # Crear una variante con los atributos
            variant = {
                'price': str(current_price),
                'stock_management': True,
                'stock': current_stock if current_stock is not None else 0,
                'values': []
            }

            # Agregar cada característica como atributo de variante
            for key, value in characteristics.items():
                variant_attr_name = self.get_variant_attribute_name(key)
                variant['values'].append({
                    'es': variant_attr_name,  # Nombre del atributo en español
                    'value': value  # Valor del atributo
                })

            variants.append(variant)
        else:
            # Si no hay características, crear variante default
            variant = {
                'price': str(current_price),
                'stock_management': True,
                'stock': current_stock if current_stock is not None else 0
            }
            variants.append(variant)

        return variants

    def update_product(self, product_id: int, updates: Dict) -> bool:
        """Actualizar un producto en Tiendanube"""
        if self.dry_run:
            print(f"  [DRY-RUN] Actualizaría producto {product_id} con:")
            print(f"  {json.dumps(updates, indent=2, ensure_ascii=False)}")
            return True

        url = f"{self.base_url}/products/{product_id}"

        try:
            response = requests.put(url, headers=self.headers, json=updates)
            response.raise_for_status()
            print(f"  ✅ Producto {product_id} actualizado exitosamente")
            return True
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error actualizando producto {product_id}: {e}")
            if hasattr(e.response, 'text'):
                print(f"  Response: {e.response.text}")
            return False

    def process_products(self):
        """Procesar todos los productos"""
        print(f"\n{'='*70}")
        print(f"🔧 Modo: {'DRY-RUN (simulación)' if self.dry_run else 'APLICANDO CAMBIOS'}")
        print(f"🏪 Store ID: {self.store_id}")
        print(f"{'='*70}\n")

        # Obtener productos
        products = self.get_products()
        print(f"\n📊 Total de productos encontrados: {len(products)}\n")

        stats = {
            'total': len(products),
            'with_characteristics': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }

        for i, product in enumerate(products, 1):
            product_id = product['id']
            name = product['name']['es']
            description = product['description']['es'] if product.get('description') else ''

            print(f"\n[{i}/{len(products)}] Procesando: {name} (ID: {product_id})")

            # Verificar si tiene características
            characteristics = self.extract_characteristics(description)

            if not characteristics:
                print(f"  ℹ️  No tiene características para extraer")
                stats['skipped'] += 1
                continue

            stats['with_characteristics'] += 1
            print(f"  📋 Características encontradas: {characteristics}")

            # Preparar actualizaciones
            updates = {}

            # Limpiar descripción
            cleaned_desc = self.clean_description(description)
            if cleaned_desc != description:
                updates['description'] = {'es': cleaned_desc}
                print(f"  🧹 Descripción limpiada (removidos {len(description) - len(cleaned_desc)} caracteres)")

            # Crear variantes
            current_price = float(product['variants'][0]['price']) if product.get('variants') else 0.0
            current_stock = product['variants'][0].get('stock') if product.get('variants') else None

            variants = self.create_variants_from_characteristics(
                product_id,
                characteristics,
                current_price,
                current_stock
            )

            if variants:
                updates['variants'] = variants
                print(f"  🎨 Variantes creadas: {len(variants)}")

            # Aplicar actualizaciones
            if updates:
                if self.update_product(product_id, updates):
                    stats['updated'] += 1
                else:
                    stats['errors'] += 1

        # Mostrar resumen
        print(f"\n{'='*70}")
        print(f"📊 RESUMEN")
        print(f"{'='*70}")
        print(f"Total productos:              {stats['total']}")
        print(f"Con características:          {stats['with_characteristics']}")
        print(f"Actualizados exitosamente:    {stats['updated']}")
        print(f"Errores:                      {stats['errors']}")
        print(f"Sin cambios necesarios:       {stats['skipped']}")
        print(f"{'='*70}\n")


def get_access_token_from_db(store_id: str) -> Optional[str]:
    """Obtener access token desencriptado de la base de datos Railway"""
    # Importar Fernet para desencriptar
    from cryptography.fernet import Fernet

    # Credenciales Railway (hardcoded para este script one-off)
    db_config = {
        'host': 'ballast.proxy.rlwy.net',
        'port': 54363,
        'database': 'railway',
        'user': 'postgres',
        'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
    }

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Obtener token encriptado y clave de encriptación
        cur.execute(
            "SELECT access_token FROM tiendanube_integrations WHERE store_id = %s AND is_active = TRUE",
            (store_id,)
        )

        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            print(f"❌ No se encontró integración activa para store_id {store_id}")
            return None

        encrypted_token = result['access_token']

        # Obtener clave de encriptación del ambiente (o generar una por defecto)
        encryption_key = os.environ.get('TOKEN_ENCRYPTION_KEY')
        if not encryption_key:
            print("⚠️  TOKEN_ENCRYPTION_KEY no encontrada, intentando con el token directo...")
            return encrypted_token  # Intentar sin desencriptar

        # Desencriptar
        cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        decrypted_token = cipher.decrypt(encrypted_token.encode()).decode()

        print(f"✅ Token obtenido y desencriptado exitosamente")
        return decrypted_token

    except Exception as e:
        print(f"❌ Error consultando base de datos: {e}")
        import traceback
        traceback.print_exc()
        return None
def main():
    parser = argparse.ArgumentParser(
        description='Corregir productos en Tiendanube: limpiar descripciones y crear variantes'
    )
    parser.add_argument(
        '--store-id',
        type=str,
        required=True,
        help='ID de la tienda en Tiendanube'
    )
    parser.add_argument(
        '--access-token',
        type=str,
        help='Access token (opcional, se obtendrá de la BD si no se provee)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Modo simulación (no aplica cambios)'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Aplicar cambios reales (desactiva dry-run)'
    )

    args = parser.parse_args()

    # Determinar si aplicar cambios
    dry_run = not args.apply

    # Obtener access token
    access_token = args.access_token
    if not access_token:
        print("🔍 Obteniendo access token de la base de datos...")
        access_token = get_access_token_from_db(args.store_id)
        if not access_token:
            sys.exit(1)

    # Crear fixer y procesar
    fixer = TiendanubeProductFixer(args.store_id, access_token, dry_run)

    try:
        fixer.process_products()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
