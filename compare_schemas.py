"""
Compara esquemas de PostgreSQL local vs Railway.
Genera SQL para igualar Railway con local (local es la verdad).
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

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

def get_tables(conn):
    """Obtiene lista de tablas (excluyendo system tables)"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        return [row['table_name'] for row in cur.fetchall()]

def get_columns(conn, table_name):
    """Obtiene columnas de una tabla con sus tipos"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default,
                ordinal_position
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        return {row['column_name']: row for row in cur.fetchall()}

def get_constraints(conn, table_name):
    """Obtiene constraints de una tabla"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            LEFT JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            LEFT JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.table_name = %s
            ORDER BY tc.constraint_type, tc.constraint_name
        """, (table_name,))
        return cur.fetchall()

def compare_schemas(local_conn, railway_conn):
    """Compara esquemas y genera SQL de migración"""
    
    print("\n" + "="*80)
    print("📊 COMPARACIÓN DE ESQUEMAS: LOCAL (verdad) vs RAILWAY")
    print("="*80 + "\n")
    
    # Obtener tablas
    local_tables = set(get_tables(local_conn))
    railway_tables = set(get_tables(railway_conn))
    
    print(f"📋 Tablas en LOCAL: {len(local_tables)}")
    print(f"📋 Tablas en RAILWAY: {len(railway_tables)}")
    
    # Tablas que faltan en Railway
    missing_tables = local_tables - railway_tables
    if missing_tables:
        print(f"\n⚠️  Tablas que faltan en RAILWAY: {missing_tables}")
    
    # Tablas extra en Railway
    extra_tables = railway_tables - local_tables
    if extra_tables:
        print(f"\n⚠️  Tablas extra en RAILWAY (serán ignoradas): {extra_tables}")
    
    # SQL de migración
    migration_sql = []
    migration_sql.append("-- ============================================================")
    migration_sql.append("-- MIGRACIÓN DE ESQUEMA: Igualar Railway con Local")
    migration_sql.append(f"-- Generado: {__import__('datetime').datetime.now()}")
    migration_sql.append("-- ============================================================\n")
    migration_sql.append("BEGIN;\n")
    
    # Comparar cada tabla común
    common_tables = local_tables & railway_tables
    
    for table_name in sorted(common_tables):
        print(f"\n{'='*80}")
        print(f"📊 Comparando tabla: {table_name}")
        print(f"{'='*80}")
        
        local_cols = get_columns(local_conn, table_name)
        railway_cols = get_columns(railway_conn, table_name)
        
        local_col_names = set(local_cols.keys())
        railway_col_names = set(railway_cols.keys())
        
        # Columnas que faltan en Railway
        missing_cols = local_col_names - railway_col_names
        if missing_cols:
            print(f"  ➕ Columnas a AGREGAR en Railway: {missing_cols}")
            migration_sql.append(f"-- Tabla: {table_name} - Agregar columnas")
            for col in sorted(missing_cols):
                col_info = local_cols[col]
                col_type = col_info['data_type'].upper()
                
                # Ajustar tipo según character_maximum_length
                if col_info['character_maximum_length']:
                    col_type = f"VARCHAR({col_info['character_maximum_length']})"
                elif col_type == 'CHARACTER VARYING':
                    col_type = 'TEXT'
                
                nullable = "" if col_info['is_nullable'] == 'YES' else " NOT NULL"
                default = f" DEFAULT {col_info['column_default']}" if col_info['column_default'] else ""
                
                migration_sql.append(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col} {col_type}{nullable}{default};")
        
        # Columnas extra en Railway
        extra_cols = railway_col_names - local_col_names
        if extra_cols:
            print(f"  ➖ Columnas a ELIMINAR de Railway: {extra_cols}")
            migration_sql.append(f"\n-- Tabla: {table_name} - Eliminar columnas")
            for col in sorted(extra_cols):
                migration_sql.append(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS {col};")
        
        # Columnas comunes - verificar tipos
        common_cols = local_col_names & railway_col_names
        type_diffs = []
        for col in sorted(common_cols):
            local_type = local_cols[col]['data_type']
            railway_type = railway_cols[col]['data_type']
            
            # Normalizar tipos para comparación
            local_normalized = local_type.upper()
            railway_normalized = railway_type.upper()
            
            if local_normalized != railway_normalized:
                type_diffs.append((col, railway_type, local_type))
        
        if type_diffs:
            print(f"  🔄 Columnas con tipos diferentes:")
            migration_sql.append(f"\n-- Tabla: {table_name} - Ajustar tipos")
            for col, railway_type, local_type in type_diffs:
                print(f"     {col}: Railway={railway_type} → Local={local_type}")
                # NOTA: ALTER TYPE puede ser peligroso, comentamos por seguridad
                migration_sql.append(f"-- ALTER TABLE {table_name} ALTER COLUMN {col} TYPE {local_type}; -- REVISAR MANUALMENTE")
        
        if not missing_cols and not extra_cols and not type_diffs:
            print(f"  ✅ Esquema idéntico")
        
        migration_sql.append("")
    
    migration_sql.append("\nCOMMIT;\n")
    migration_sql.append("-- ============================================================")
    migration_sql.append("-- FIN DE MIGRACIÓN DE ESQUEMA")
    migration_sql.append("-- ============================================================")
    
    return "\n".join(migration_sql)

def main():
    print("\n" + "="*80)
    print("🔍 COMPARADOR DE ESQUEMAS: LOCAL vs RAILWAY")
    print("="*80)
    
    # Conectar
    try:
        print("\n📡 Conectando a LOCAL...")
        local_conn = psycopg2.connect(**LOCAL_CONFIG)
        print("✅ Conectado a LOCAL")
        
        print("\n📡 Conectando a RAILWAY...")
        railway_conn = psycopg2.connect(**RAILWAY_CONFIG)
        print("✅ Conectado a RAILWAY")
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return
    
    # Comparar
    migration_sql = compare_schemas(local_conn, railway_conn)
    
    # Guardar SQL
    output_file = "migrations/schema_sync_railway.sql"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(migration_sql)
    
    print("\n" + "="*80)
    print(f"✅ SQL de migración generado: {output_file}")
    print("="*80)
    print("\n📋 Próximos pasos:")
    print(f"   1. Revisar: {output_file}")
    print(f"   2. Aplicar: python railway_db_tool.py sql -f {output_file} --yes")
    print(f"   3. Verificar: python compare_schemas.py")
    print(f"   4. Migrar datos: python migrate_data_to_railway.py")
    
    local_conn.close()
    railway_conn.close()

if __name__ == '__main__':
    main()
