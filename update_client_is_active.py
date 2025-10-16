import asyncio
import asyncpg
import sqlite3

async def update_client_is_active():
    # Obtener datos de SQLite
    sqlite_conn = sqlite3.connect('clip_admin_backend/instance/clip_comparador_v2.db')
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, is_active FROM clients")
    client_data = cursor.fetchone()
    sqlite_conn.close()

    # Actualizar PostgreSQL
    pg_conn = await asyncpg.connect('postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway')
    try:
        is_active_value = bool(client_data['is_active']) if client_data['is_active'] is not None else True
        await pg_conn.execute("UPDATE clients SET is_active = $1 WHERE id = $2",
                            is_active_value, client_data['id'])
        print(f'✅ Cliente {client_data["id"]} actualizado: is_active = {is_active_value}')
    finally:
        await pg_conn.close()

asyncio.run(update_client_is_active())
