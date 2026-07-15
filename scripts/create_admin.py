"""Crea (o actualiza) un usuario administrador — dueño de restaurante.

No hay endpoint para crear admins a propósito (seguridad): este script se
ejecuta directamente contra la BD. Es idempotente: si el usuario ya existe,
le actualiza la contraseña y se asegura de que sea admin.

Uso (dentro del contenedor de la API, sin reconstruir la imagen):

    docker exec -i manhattan_api python - <<'PY' maria 092303
    ... (contenido de este archivo) ...
    PY

o, si el archivo ya está en la imagen:

    docker exec -it manhattan_api python scripts/create_admin.py maria 092303
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.organization import User


async def main(username: str, password: str, nombre: str = "") -> None:
    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()

        if existing is not None:
            existing.password_hash = hash_password(password)
            existing.is_admin = True
            action = "actualizado"
        else:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    is_admin=True,
                    name=nombre or username,
                    title="Administrador",
                )
            )
            action = "creado"

        await db.commit()
        print(f"OK: admin '{username}' {action}.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("uso: python create_admin.py <username> <password> [nombre]")
        raise SystemExit(1)
    asyncio.run(
        main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    )
