"""
Script para eliminar el cliente 'Eve's Store' de producción Railway
"""
import os
import psycopg2

def get_conn():
    host = 'ballast.proxy.rlwy.net'
    port = 54363
    database = 'railway'
    user = 'postgres'
    password = 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
    return psycopg2.connect(host=host, port=port, database=database, user=user, password=password)

def main():
    print("🔌 Conectando a Railway PostgreSQL...")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Buscar el cliente Eve's Store
            cur.execute("""
                SELECT id, name, email, created_at
                FROM clients
                WHERE name ILIKE '%eve%store%'
            """)

            clients = cur.fetchall()

            if not clients:
                print("❌ No se encontró el cliente 'Eve's Store'")
                return

            print(f"\n📋 Clientes encontrados:")
            for client in clients:
                client_id, name, email, created_at = client
                print(f"   ID: {client_id}")
                print(f"   Nombre: {name}")
                print(f"   Email: {email}")
                print(f"   Creado: {created_at}")

                # Contar usuarios asociados
                cur.execute("SELECT COUNT(*) FROM users WHERE client_id = %s", (client_id,))
                user_count = cur.fetchone()[0]
                print(f"   Usuarios: {user_count}")

                # Contar categorías
                cur.execute("SELECT COUNT(*) FROM categories WHERE client_id = %s", (client_id,))
                cat_count = cur.fetchone()[0]
                print(f"   Categorías: {cat_count}")

                # Contar productos
                cur.execute("SELECT COUNT(*) FROM products WHERE client_id = %s", (client_id,))
                prod_count = cur.fetchone()[0]
                print(f"   Productos: {prod_count}")

                # Contar imágenes
                cur.execute("SELECT COUNT(*) FROM images WHERE client_id = %s", (client_id,))
                img_count = cur.fetchone()[0]
                print(f"   Imágenes: {img_count}")
                print()

            # Confirmación
            confirm = input("⚠️  ¿Eliminar este cliente y todos sus datos? (escribe 'DELETE' para confirmar): ")

            if confirm != 'DELETE':
                print("❌ Operación cancelada")
                conn.rollback()
                return

            print("\n🗑️  Eliminando datos...")

            for client in clients:
                client_id = client[0]

                # Eliminar en orden correcto (respetando foreign keys)
                print(f"   - Eliminando imágenes del cliente {client_id}...")
                cur.execute("DELETE FROM images WHERE client_id = %s", (client_id,))

                print(f"   - Eliminando productos del cliente {client_id}...")
                cur.execute("DELETE FROM products WHERE client_id = %s", (client_id,))

                print(f"   - Eliminando categorías del cliente {client_id}...")
                cur.execute("DELETE FROM categories WHERE client_id = %s", (client_id,))

                # Intentar eliminar atributos si la tabla existe
                try:
                    print(f"   - Eliminando atributos del cliente {client_id}...")
                    cur.execute("DELETE FROM product_attribute_configs WHERE client_id = %s", (client_id,))
                except psycopg2.errors.UndefinedTable:
                    print(f"   - Tabla product_attribute_configs no existe, omitiendo...")
                    conn.rollback()
                    # Reiniciar transacción
                    cur.execute("BEGIN")

                print(f"   - Eliminando usuarios del cliente {client_id}...")
                cur.execute("DELETE FROM users WHERE client_id = %s", (client_id,))

                print(f"   - Eliminando cliente {client_id}...")
                cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))

            # Commit
            conn.commit()
            print("\n✅ Cliente 'Eve's Store' eliminado exitosamente de producción")
            print("   Todos los datos asociados (usuarios, categorías, productos, imágenes) fueron eliminados")

if __name__ == "__main__":
    main()
