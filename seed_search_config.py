"""
Script para poblar store_search_config con configuraciones default
para todos los clientes existentes
"""
import psycopg2
import os
from dotenv import load_dotenv

# Cargar variables de entorno
env_local_path = '.env.local'
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)
    print(f"📄 Cargando configuración desde {env_local_path}")
else:
    load_dotenv()
    print("📄 Cargando configuración desde .env")

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no encontrado")
    exit(1)

print(f"🔗 Conectando a: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local'}")

def seed_search_config():
    """Crea configuraciones default para clientes sin config"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Conexión establecida\n")
        
        with conn, conn.cursor() as cur:
            # Ver cuántos clientes existen
            cur.execute("SELECT COUNT(*) FROM clients")
            total_clients = cur.fetchone()[0]
            print(f"📊 Total de clientes: {total_clients}")
            
            # Ver cuántos ya tienen configuración
            cur.execute("SELECT COUNT(*) FROM store_search_config")
            existing_configs = cur.fetchone()[0]
            print(f"📊 Configuraciones existentes: {existing_configs}")
            
            # Obtener clientes sin configuración
            cur.execute("""
                SELECT c.id, c.name, c.industry
                FROM clients c
                LEFT JOIN store_search_config ssc ON c.id = ssc.store_id
                WHERE ssc.store_id IS NULL
            """)
            clients_without_config = cur.fetchall()
            
            if not clients_without_config:
                print("\n✅ Todos los clientes ya tienen configuración de búsqueda")
                return
            
            print(f"\n🔧 Clientes sin configuración: {len(clients_without_config)}")
            print("\nCreando configuraciones default...\n")
            
            # Insertar configuraciones default
            for client_id, name, industry in clients_without_config:
                cur.execute("""
                    INSERT INTO store_search_config (
                        store_id, 
                        visual_weight, 
                        metadata_weight, 
                        business_weight,
                        metadata_config
                    ) VALUES (
                        %s, 0.6, 0.3, 0.1,
                        '{"color": {"enabled": true, "weight": 0.3}, "brand": {"enabled": true, "weight": 0.3}, "pattern": {"enabled": false, "weight": 0.2}}'::jsonb
                    )
                """, (client_id,))
                
                print(f"  ✓ {name} (industry: {industry or 'general'})")
            
            conn.commit()
            
            print(f"\n✅ Configuraciones creadas: {len(clients_without_config)}")
            
            # Verificar resultado final
            cur.execute("SELECT COUNT(*) FROM store_search_config")
            final_configs = cur.fetchone()[0]
            print(f"📊 Total de configuraciones: {final_configs}")
            
            # Mostrar ejemplo de configuración
            cur.execute("""
                SELECT 
                    c.name,
                    ssc.visual_weight,
                    ssc.metadata_weight,
                    ssc.business_weight
                FROM store_search_config ssc
                JOIN clients c ON c.id = ssc.store_id
                LIMIT 3
            """)
            examples = cur.fetchall()
            
            print("\n📦 Ejemplos de configuraciones:")
            for name, visual, metadata, business in examples:
                print(f"   {name}:")
                print(f"     Visual: {visual}, Metadata: {metadata}, Business: {business}")
            
    except psycopg2.Error as e:
        print(f"❌ Error de PostgreSQL: {e}")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Conexión cerrada")

if __name__ == "__main__":
    print("=" * 60)
    print("SEED: Configuraciones de búsqueda default")
    print("=" * 60)
    seed_search_config()
    print("\n✨ Seed completado")
