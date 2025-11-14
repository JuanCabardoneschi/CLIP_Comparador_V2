import psycopg2, os
host = "ballast.proxy.rlwy.net"
port = 54363
user = "postgres"
password = "xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum"
db = "railway"
conn = psycopg2.connect(host=host, port=port, user=user, password=password, database=db)
cur = conn.cursor()
cur.execute('SELECT id, client_id, api_key, created_at FROM api_keys ORDER BY created_at')
os.makedirs('backups', exist_ok=True)
with open('backups/railway_apikeys_restore.sql', 'w', encoding='utf-8') as f:
    f.write('-- Restaurar API Keys de Railway (PRODUCCION)\n')
    f.write('DELETE FROM api_keys;\n')
    for row in cur.fetchall():
        f.write("INSERT INTO api_keys (id, client_id, api_key, created_at) VALUES ('%s','%s','%s','%s');\n" % (row[0], row[1], row[2], row[3]))
conn.close()
print('OK: backups/railway_apikeys_restore.sql')
