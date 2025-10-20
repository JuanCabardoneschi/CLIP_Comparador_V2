"""
Backup seguro de la base de datos local usando pg_dump y .env.local
- Lee DATABASE_URL de .env.local (sin imprimirla)
- Exporta PGPASSWORD y ejecuta pg_dump con -Fc
- Guarda salida en backups/local_<timestamp>.dump
"""
import os
import sys
import subprocess
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
ENV_LOCAL = ROOT / ".env.local"


def main():
    if not ENV_LOCAL.exists():
        print("❌ .env.local no encontrado. Copia .env.local.example a .env.local y completa credenciales.")
        sys.exit(1)

    load_dotenv(ENV_LOCAL)
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL no está definido en .env.local")
        sys.exit(1)

    # Parsear URI: postgresql://usuario:password@host:puerto/base
    parsed = urlparse(db_url)
    if parsed.scheme not in ("postgresql", "postgres"):
        print("❌ DATABASE_URL no es PostgreSQL")
        sys.exit(1)

    username = parsed.username or "postgres"
    password = parsed.password or ""
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    database = parsed.path.lstrip("/")

    backups_dir = ROOT / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = backups_dir / f"local_{ts}.dump"

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    cmd = [
        "pg_dump",
        "-h", host,
        "-p", port,
        "-U", username,
        "-d", database,
        "-Fc",
        "-f", str(out_file),
    ]

    print("🚀 Ejecutando backup local con pg_dump...")
    try:
        subprocess.run(cmd, check=True, env=env)
        print(f"✅ Backup generado: {out_file}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al ejecutar pg_dump (exit {e.returncode})")
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
