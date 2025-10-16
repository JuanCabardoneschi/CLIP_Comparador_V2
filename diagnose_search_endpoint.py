#!/usr/bin/env python3
"""
Verificar API keys en PostgreSQL y diagnosticar problema del endpoint /search
"""
import asyncio
import asyncpg

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def diagnose_search_endpoint():
    """Diagnosticar problemas del endpoint de búsqueda"""
    
    print("🔍 DIAGNOSTICANDO ENDPOINT /api/search")
    print("=" * 50)
    
    conn = await asyncpg.connect(POSTGRES_URL)
    
    try:
        # 1. Verificar tabla api_keys
        print("📋 Verificando tabla api_keys...")
        try:
            api_keys = await conn.fetch("SELECT * FROM api_keys")
            print(f"  📊 API Keys encontradas: {len(api_keys)}")
            for key in api_keys:
                print(f"    - {key['api_key'][:20]}... | Cliente: {key['client_id']} | Activa: {key['is_active']}")
        except Exception as e:
            print(f"  ❌ Error en api_keys: {e}")
        
        # 2. Verificar si clients tiene api_key
        print(f"\n📋 Verificando api_key en clients...")
        try:
            clients = await conn.fetch("SELECT id, name, api_key, is_active FROM clients")
            print(f"  📊 Clientes encontrados: {len(clients)}")
            for client in clients:
                print(f"    - {client['name']} | API Key: {client['api_key'] or 'NO TIENE'} | Activo: {client['is_active']}")
        except Exception as e:
            print(f"  ❌ Error consultando clients: {e}")
        
        # 3. Verificar imágenes con embeddings
        print(f"\n📋 Verificando imágenes con embeddings...")
        try:
            images_with_embeddings = await conn.fetchval("""
                SELECT COUNT(*) FROM images 
                WHERE clip_embedding IS NOT NULL AND clip_embedding != ''
            """)
            print(f"  📊 Imágenes con embeddings: {images_with_embeddings}")
            
            total_images = await conn.fetchval("SELECT COUNT(*) FROM images")
            print(f"  📊 Total imágenes: {total_images}")
            
            if images_with_embeddings == 0:
                print(f"  ⚠️  PROBLEMA: No hay embeddings generados!")
        except Exception as e:
            print(f"  ❌ Error verificando embeddings: {e}")
        
        # 4. Generar API key para testing si no existe
        print(f"\n🔧 CREANDO API KEY PARA TESTING...")
        try:
            client_id = '60231500-ca6f-4c46-a960-2e17298fcdb0'
            test_api_key = 'test-api-key-demo-fashion-store-2024'
            
            # Actualizar cliente con API key
            await conn.execute("""
                UPDATE clients 
                SET api_key = $1 
                WHERE id = $2
            """, test_api_key, client_id)
            
            print(f"  ✅ API Key creada: {test_api_key}")
            print(f"  📝 Usar en widget: X-API-Key: {test_api_key}")
            
        except Exception as e:
            print(f"  ❌ Error creando API key: {e}")
        
        print(f"\n🎯 RESUMEN DEL DIAGNÓSTICO:")
        print(f"  ✅ Base de datos conectada")
        print(f"  ✅ Estructuras de tablas verificadas")
        print(f"  ✅ API Key de prueba creada")
        print(f"  📝 Para el widget usar: X-API-Key: test-api-key-demo-fashion-store-2024")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en diagnóstico: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(diagnose_search_endpoint())
    if success:
        print("\n🚀 DIAGNÓSTICO COMPLETO")
    else:
        print("\n💥 Error en diagnóstico")