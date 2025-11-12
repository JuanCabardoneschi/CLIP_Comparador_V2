import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar .env.local desde la raíz del repo
ROOT = Path(__file__).resolve().parents[2]
ENV_LOCAL = ROOT / '.env.local'
if ENV_LOCAL.exists():
    load_dotenv(ENV_LOCAL)
else:
    load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print('❌ DATABASE_URL no definido. Revisa .env.local')
    sys.exit(1)

print(f'🔗 Conectando a DB: {DATABASE_URL.split("@")[1] if "@" in DATABASE_URL else DATABASE_URL}')
engine = create_engine(DATABASE_URL, future=True)

DDL = [
    """
    ALTER TABLE images
      ADD COLUMN IF NOT EXISTS crop_x INTEGER,
      ADD COLUMN IF NOT EXISTS crop_y INTEGER,
      ADD COLUMN IF NOT EXISTS crop_w INTEGER,
      ADD COLUMN IF NOT EXISTS crop_h INTEGER,
      ADD COLUMN IF NOT EXISTS is_crop_manual BOOLEAN,
      ADD COLUMN IF NOT EXISTS refined BOOLEAN;
    """,
    "CREATE INDEX IF NOT EXISTS ix_images_is_crop_manual ON images(is_crop_manual);",
    "CREATE INDEX IF NOT EXISTS ix_images_refined ON images(refined);",
]

try:
    with engine.begin() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))
    print('✅ Columnas/índices de crop aplicados correctamente.')
except Exception as e:
    print(f'💥 Error aplicando DDL: {e}')
    sys.exit(2)
