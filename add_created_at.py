import asyncio
import asyncpg

async def add_created_at():
    conn = await asyncpg.connect('postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway')
    try:
        await conn.execute('ALTER TABLE images ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        print('✅ created_at agregado')
    except Exception as e:
        print(f'⚠️ created_at ya existe o error: {e}')
    finally:
        await conn.close()

asyncio.run(add_created_at())
