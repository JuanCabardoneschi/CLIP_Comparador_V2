"""
Script rápido para eliminar completamente el cliente Test Clip
Incluye: productos, categorías, imágenes, embeddings, usuarios, integración, cliente
"""
import sys
import subprocess

# Client ID actual de Test Clip
CLIENT_ID = "67f2a7df-ed0e-4141-8453-cba894137a76"
CLIENT_NAME = "Test Clip"

def run_sql(query, description):
    """Ejecuta query en Railway DB"""
    print(f"\n🔄 {description}...")
    cmd = f'python railway_db_tool.py sql -e "{query}" --yes'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
    return result.returncode == 0

print("="*80)
print(f"🗑️  ELIMINANDO CLIENTE: {CLIENT_NAME} ({CLIENT_ID})")
print("="*80)

# 1. Eliminar imágenes (cascada eliminará embeddings)
run_sql(
    f"DELETE FROM images WHERE product_id IN (SELECT id FROM products WHERE client_id = '{CLIENT_ID}')",
    "Eliminando imágenes y embeddings"
)

# 2. Eliminar productos
run_sql(
    f"DELETE FROM products WHERE client_id = '{CLIENT_ID}'",
    "Eliminando productos"
)

# 3. Eliminar categorías
run_sql(
    f"DELETE FROM categories WHERE client_id = '{CLIENT_ID}'",
    "Eliminando categorías"
)

# 4. Eliminar configuración de atributos
run_sql(
    f"DELETE FROM product_attribute_config WHERE client_id = '{CLIENT_ID}'",
    "Eliminando configuración de atributos"
)

# 5. Eliminar integración Tiendanube
run_sql(
    f"DELETE FROM tiendanube_integrations WHERE client_id = '{CLIENT_ID}'",
    "Eliminando integración Tiendanube"
)

# 6. Eliminar usuarios del cliente
run_sql(
    f"DELETE FROM users WHERE client_id = '{CLIENT_ID}'",
    "Eliminando usuarios"
)

# 7. Eliminar cliente
run_sql(
    f"DELETE FROM clients WHERE id = '{CLIENT_ID}'",
    "Eliminando cliente"
)

# Verificar eliminación
print("\n" + "="*80)
print("✅ VERIFICACIÓN FINAL")
print("="*80)

run_sql(
    f"SELECT COUNT(*) as total FROM clients WHERE id = '{CLIENT_ID}'",
    "Verificando cliente eliminado"
)

run_sql(
    f"SELECT COUNT(*) as total FROM products WHERE client_id = '{CLIENT_ID}'",
    "Verificando productos eliminados"
)

print("\n" + "="*80)
print("✅ ELIMINACIÓN COMPLETADA")
print("="*80)
print(f"\n💡 Ahora puedes reinstalar el plugin en Tiendanube\n")
