"""
Script para poblar atributos JSONB de productos en Railway
Extrae color de descripción/campo, asigna marca GOODY y tallas aleatorias
"""

import os
import sys
import re
import random
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from flask import Flask
from app import db
from app.models.product import Product
from app.utils.attribute_seeder import seed_industry_attributes

# Configuración de Railway
# Intentar obtener de variables de entorno
RAILWAY_DB_URL = (
    os.getenv('RAILWAY_DATABASE_URL') or
    os.getenv('DATABASE_URL_RAILWAY') or
    "postgresql://postgres:NxkLvMnqgZQHYIPEGFCafvuJNLgXGBcB@ballast.proxy.rlwy.net:54363/railway"
)
DEMO_FASHION_CLIENT_ID = "60231500-ca6f-4c46-a960-2e17298fcdb0"

# Listas de valores posibles
TALLAS_DISPONIBLES = ["XS", "S", "M", "L", "XL", "XXL"]
MARCA_DEFAULT = "GOODY"

# Palabras clave de colores en español
COLORES = [
    "BLANCO", "BLANCA", "WHITE",
    "NEGRO", "NEGRA", "BLACK",
    "AZUL", "BLUE",
    "ROJO", "ROJA", "RED",
    "VERDE", "GREEN",
    "AMARILLO", "AMARILLA", "YELLOW",
    "ROSA", "PINK",
    "GRIS", "GREY", "GRAY",
    "BEIGE", "MARRON", "BROWN",
    "NARANJA", "ORANGE",
    "VIOLETA", "MORADO", "PURPLE",
    "CELESTE", "NAVY",
    "JEAN", "DENIM"
]


def extract_color_from_text(text):
    """
    Extrae color de un texto (nombre, descripción, etc.)
    
    Args:
        text: Texto donde buscar color
        
    Returns:
        str: Color encontrado en MAYÚSCULAS o None
    """
    if not text:
        return None
    
    text_upper = text.upper()
    
    # Buscar coincidencia exacta con colores conocidos
    for color in COLORES:
        if color in text_upper:
            # Normalizar a español
            color_map = {
                "WHITE": "BLANCA",
                "BLACK": "NEGRA",
                "BLUE": "AZUL",
                "RED": "ROJA",
                "GREEN": "VERDE",
                "YELLOW": "AMARILLA",
                "PINK": "ROSA",
                "GREY": "GRIS",
                "GRAY": "GRIS",
                "BROWN": "MARRON",
                "ORANGE": "NARANJA",
                "PURPLE": "MORADO",
                "DENIM": "JEAN"
            }
            return color_map.get(color, color)
    
    return None


def get_random_tallas(count=None):
    """
    Genera lista de tallas aleatorias
    
    Args:
        count: Número de tallas (si None, elige 2 o 3 al azar)
        
    Returns:
        list: Lista de tallas
    """
    if count is None:
        count = random.choice([2, 3])
    
    return random.sample(TALLAS_DISPONIBLES, min(count, len(TALLAS_DISPONIBLES)))


def populate_product_attributes(client_id, dry_run=False):
    """
    Pobla atributos JSONB de todos los productos de un cliente
    
    Args:
        client_id: UUID del cliente
        dry_run: Si True, solo muestra lo que haría sin guardar
        
    Returns:
        tuple: (products_updated, errors)
    """
    products = Product.query.filter_by(client_id=client_id).all()
    
    if not products:
        print(f"❌ No se encontraron productos para cliente {client_id}")
        return 0, 0
    
    print(f"\n{'=' * 80}")
    print(f"📦 PRODUCTOS ENCONTRADOS: {len(products)}")
    print(f"🔧 MODO: {'DRY RUN (sin guardar)' if dry_run else 'PRODUCCIÓN (guardando cambios)'}")
    print(f"{'=' * 80}\n")
    
    updated = 0
    errors = 0
    
    for idx, product in enumerate(products, 1):
        try:
            # 1. Extraer color
            color = None
            
            # Prioridad 1: Campo color directo
            if hasattr(product, 'color') and product.color:
                color = product.color.upper().strip()
            
            # Prioridad 2: Nombre del producto
            if not color:
                color = extract_color_from_text(product.name)
            
            # Prioridad 3: Descripción
            if not color and product.description:
                color = extract_color_from_text(product.description)
            
            # 2. Generar tallas aleatorias
            tallas = get_random_tallas()
            
            # 3. Construir objeto attributes
            attributes = {
                "marca": MARCA_DEFAULT,
                "talla": tallas  # Lista de tallas
            }
            
            # Solo agregar color si se encontró
            if color:
                attributes["color"] = color
            
            # 4. Mostrar cambio
            print(f"\n{idx}. {product.name[:50]}")
            print(f"   SKU: {product.sku}")
            print(f"   📋 Atributos actuales: {product.attributes or '{}'}")
            print(f"   ✨ Atributos nuevos:")
            print(f"      • Color: {color or 'N/A (no detectado)'}")
            print(f"      • Marca: {MARCA_DEFAULT}")
            print(f"      • Tallas: {', '.join(tallas)}")
            
            # 5. Actualizar (si no es dry run)
            if not dry_run:
                product.attributes = attributes
                updated += 1
                print(f"   ✅ Actualizado")
            else:
                print(f"   ⏭️  Omitido (dry run)")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            errors += 1
            continue
    
    # Guardar cambios
    if not dry_run and updated > 0:
        try:
            db.session.commit()
            print(f"\n{'=' * 80}")
            print(f"✅ CAMBIOS GUARDADOS EN BASE DE DATOS")
            print(f"{'=' * 80}\n")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERROR AL GUARDAR: {e}")
            return 0, len(products)
    
    return updated, errors


def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Poblar atributos JSONB de productos en Railway'
    )
    parser.add_argument(
        '--client-id',
        default=DEMO_FASHION_CLIENT_ID,
        help='UUID del cliente (default: Demo Fashion Store)'
    )
    parser.add_argument(
        '--seed-config',
        action='store_true',
        help='Hacer seed de configuración de atributos antes de poblar'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Modo prueba: muestra cambios sin guardar'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Confirmar automáticamente (no pedir confirmación)'
    )
    
    args = parser.parse_args()
    
    # Validar que tengamos URL de Railway
    print(f"🔗 Conectando a: {RAILWAY_DB_URL[:50]}...")
    
    if not RAILWAY_DB_URL or 'localhost' in RAILWAY_DB_URL:
        print("⚠️  ADVERTENCIA: Usando base de datos local o URL no configurada")
        print("   Para Railway, configura RAILWAY_DATABASE_URL en .env")
        if not args.yes:
            response = input("\n¿Continuar de todos modos? (yes/no): ")
            if response.lower() != 'yes':
                sys.exit(0)
    
    # Crear app con Railway DB
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = RAILWAY_DB_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    with app.app_context():
        print("\n" + "=" * 80)
        print("🚂 RAILWAY - POBLACIÓN DE ATRIBUTOS DE PRODUCTOS")
        print("=" * 80)
        print(f"Cliente: {args.client_id}")
        print(f"Seed config: {'Sí' if args.seed_config else 'No'}")
        print(f"Dry run: {'Sí (solo mostrar)' if args.dry_run else 'No (guardar cambios)'}")
        print("=" * 80 + "\n")
        
        # 1. Seed de configuración (si se solicita)
        if args.seed_config:
            print("📋 PASO 1: Seed de configuración de atributos (fashion)")
            print("-" * 80)
            
            try:
                result = seed_industry_attributes(
                    client_id=args.client_id,
                    industry='fashion',
                    commit=not args.dry_run,
                    dry_run=args.dry_run
                )
                
                if result['success']:
                    print(f"✅ Seed exitoso: {result['created']} atributos creados")
                else:
                    print(f"⚠️  {result['message']}")
            except Exception as e:
                print(f"❌ Error en seed: {e}")
                if not args.yes:
                    sys.exit(1)
            
            print()
        
        # 2. Confirmar acción (si no es dry_run ni --yes)
        if not args.dry_run and not args.yes:
            response = input("⚠️  ¿Confirmar actualización de productos en Railway? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Operación cancelada")
                sys.exit(0)
        
        # 3. Poblar atributos
        print("📦 PASO 2: Población de atributos de productos")
        print("-" * 80)
        
        updated, errors = populate_product_attributes(
            client_id=args.client_id,
            dry_run=args.dry_run
        )
        
        # 4. Resumen final
        print("\n" + "=" * 80)
        print("📊 RESUMEN FINAL")
        print("=" * 80)
        print(f"✅ Productos actualizados: {updated}")
        print(f"❌ Errores: {errors}")
        
        if args.dry_run:
            print("\n⚠️  MODO DRY RUN: No se guardaron cambios")
            print("   Ejecuta sin --dry-run para aplicar cambios")
        else:
            print(f"\n✅ Cambios aplicados en Railway")
        
        print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
