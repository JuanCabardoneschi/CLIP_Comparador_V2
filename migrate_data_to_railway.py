"""
Migración de datos de PostgreSQL local a Railway.
Copia tabla por tabla, preservando las API keys de Railway.

Orden de tablas respetando foreign keys:
1. clients
2. categories
3. products
4. images
5. api_keys (preservar las de Railway - NO copiar)
"""
import psycopg2
import psycopg2.extras
import sys
import json
from datetime import datetime

# Configuración LOCAL
LOCAL_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'Laurana@01',
    'database': 'clip_comparador_v2'
}

# Configuración RAILWAY
RAILWAY_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum',
    'database': 'railway'
}

# Orden de tablas a migrar (respetando FK)
TABLES_ORDER = [
    'clients',
    'categories', 
    'products',
    'images'
    # api_keys NO se migra - se preservan las de Railway
]

def get_table_columns(cursor, table_name):
    """Obtiene columnas de una tabla"""
    cursor.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """)
    return [row[0] for row in cursor.fetchall()]

def migrate_table(local_conn, railway_conn, table_name):
    """Migra una tabla completa de local a railway"""
    print(f"\n{'='*60}")
    print(f"Migrando tabla: {table_name}")
    print(f"{'='*60}")
    
    local_cur = local_conn.cursor()
    railway_cur = railway_conn.cursor()
    
    try:
        # 1. Obtener columnas de la tabla en local
        columns = get_table_columns(local_cur, table_name)
        if not columns:
            print(f"⚠️  Tabla {table_name} no encontrada en local, saltando...")
            return
        
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        
        # 2. Contar filas en local
        local_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_rows = local_cur.fetchone()[0]
        print(f"📊 Filas en local: {total_rows}")
        
        if total_rows == 0:
            print(f"⚠️  No hay datos para migrar en {table_name}")
            return
        
        # 3. Desactivar temporalmente constraints FK en Railway
        railway_cur.execute(f"ALTER TABLE {table_name} DISABLE TRIGGER ALL")
        
        # 4. TRUNCATE tabla en Railway
        print(f"🗑️  Limpiando tabla en Railway...")
        railway_cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
        railway_conn.commit()
        
        # 5. Leer datos de local
        print(f"📥 Leyendo datos de local...")
        local_cur.execute(f"SELECT {columns_str} FROM {table_name}")
        
        # 6. Insertar en Railway por lotes
        batch_size = 100
        inserted = 0
        batch = []
        
        print(f"📤 Copiando a Railway...")
        for row in local_cur:
            # Convertir dict/list a JSON string para JSONB
            processed_row = []
            for val in row:
                if isinstance(val, (dict, list)):
                    processed_row.append(psycopg2.extras.Json(val))
                else:
                    processed_row.append(val)
            
            batch.append(tuple(processed_row))
            
            if len(batch) >= batch_size:
                insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                railway_cur.executemany(insert_query, batch)
                railway_conn.commit()
                inserted += len(batch)
                print(f"   ✓ {inserted}/{total_rows} filas copiadas...", end='\r')
                batch = []
        
        # Insertar lote final
        if batch:
            insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            railway_cur.executemany(insert_query, batch)
            railway_conn.commit()
            inserted += len(batch)
        
        # 7. Reactivar constraints
        railway_cur.execute(f"ALTER TABLE {table_name} ENABLE TRIGGER ALL")
        railway_conn.commit()
        
        # 8. Verificar conteo en Railway
        railway_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        railway_count = railway_cur.fetchone()[0]
        
        print(f"\n✅ Tabla {table_name} migrada:")
        print(f"   Local: {total_rows} filas")
        print(f"   Railway: {railway_count} filas")
        
        if total_rows != railway_count:
            print(f"⚠️  ADVERTENCIA: Conteos no coinciden!")
            return False
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error migrando {table_name}: {e}")
        railway_conn.rollback()
        return False
    finally:
        local_cur.close()
        railway_cur.close()

def verify_api_keys(railway_conn):
    """Verifica que las API keys de Railway se mantienen intactas"""
    print(f"\n{'='*60}")
    print("Verificando API Keys de Railway (deben estar intactas)")
    print(f"{'='*60}")
    
    cur = railway_conn.cursor()
    cur.execute("SELECT COUNT(*), LEFT(api_key, 10) || '...' FROM api_keys GROUP BY api_key")
    results = cur.fetchall()
    
    if not results:
        print("⚠️  WARNING: No hay API keys en Railway!")
        return False
    
    print(f"✅ API Keys encontradas: {len(results)}")
    for count, key_preview in results:
        print(f"   {key_preview} (usado {count} vez/veces)")
    
    cur.close()
    return True

def main():
    print("\n" + "="*60)
    print("🚀 MIGRACIÓN DE DATOS LOCAL → RAILWAY")
    print("="*60)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nTablas a migrar: {', '.join(TABLES_ORDER)}")
    print("⚠️  API Keys de Railway NO se tocarán (se preservan)")
    print("\n" + "="*60)
    
    # Conectar a ambas bases
    try:
        print("\n📡 Conectando a LOCAL...")
        local_conn = psycopg2.connect(**LOCAL_CONFIG)
        print("✅ Conectado a LOCAL")
        
        print("\n📡 Conectando a RAILWAY...")
        railway_conn = psycopg2.connect(**RAILWAY_CONFIG)
        print("✅ Conectado a RAILWAY")
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        sys.exit(1)
    
    # Migrar cada tabla
    success_count = 0
    failed_tables = []
    
    for table in TABLES_ORDER:
        if migrate_table(local_conn, railway_conn, table):
            success_count += 1
        else:
            failed_tables.append(table)
    
    # Verificar API keys
    print("\n")
    if not verify_api_keys(railway_conn):
        print("⚠️  WARNING: Problema con API keys, revisa manualmente")
    
    # Resumen final
    print("\n" + "="*60)
    print("📊 RESUMEN DE MIGRACIÓN")
    print("="*60)
    print(f"✅ Tablas migradas exitosamente: {success_count}/{len(TABLES_ORDER)}")
    
    if failed_tables:
        print(f"❌ Tablas con errores: {', '.join(failed_tables)}")
    
    print(f"\nFin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Cerrar conexiones
    local_conn.close()
    railway_conn.close()
    
    if failed_tables:
        sys.exit(1)
    else:
        print("\n✅ Migración completada exitosamente!")
        print("\n📋 Próximos pasos:")
        print("   1. Verificar conteos con: python railway_db_tool.py counts")
        print("   2. Ejecutar smoke tests de API")
        print("   3. Deploy código a Railway: git push railway main")

if __name__ == '__main__':
    main()
