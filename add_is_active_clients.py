import asyncio
import asyncpg

async def add_is_active_to_clients():
    conn = await asyncpg.connect('postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway')
    try:
        await conn.execute('ALTER TABLE clients ADD COLUMN is_active BOOLEAN DEFAULT true')
        print('✅ is_active agregado a clients')

        # Actualizar con datos de SQLite
        await conn.execute("UPDATE clients SET is_active = true WHERE is_active IS NULL")
        print('✅ Datos actualizados')
    except Exception as e:
        print(f'⚠️ is_active ya existe o error: {e}')
    finally:
        await conn.close()

asyncio.run(add_is_active_to_clients())
