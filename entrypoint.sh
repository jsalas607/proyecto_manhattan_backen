#!/usr/bin/env bash
set -e

echo "Esperando a PostgreSQL..."
# Espera simple basada en reintentos de alembic/python
python - <<'PYEOF'
import asyncio
import sys
import asyncpg
import os
import re

url = os.environ.get("DATABASE_URL", "")
# Convertir SQLAlchemy URL -> asyncpg URL
dsn = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)

async def wait():
    for intento in range(30):
        try:
            conn = await asyncpg.connect(dsn)
            await conn.close()
            print("PostgreSQL disponible.")
            return
        except Exception as e:
            print(f"  intento {intento + 1}/30: {e}")
            await asyncio.sleep(2)
    print("No se pudo conectar a PostgreSQL.", file=sys.stderr)
    sys.exit(1)

asyncio.run(wait())
PYEOF

echo "Aplicando migraciones..."
alembic upgrade head

echo "Arrancando API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
