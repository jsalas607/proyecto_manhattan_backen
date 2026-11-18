"""Caja única por restaurante aunque Cartera la pida varias veces a la vez.
Ejecutar:
    python test_caja.py
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./caja.db"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin"

import httpx  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.core.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.main import app, bootstrap_admin  # noqa: E402
from app.models.cartera import Caja  # noqa: E402


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await bootstrap_admin()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api") as ac:
        r = await ac.post("/auth/login", json={"username": "admin", "password": "admin"})
        H = {"Authorization": f"Bearer {r.json()['access_token']}"}
        rid = (await ac.post("/restaurants", headers=H,
                             json={"title": "Licorera", "paymentMethods": ["efectivo"]})).json()["id"]
        base = f"/restaurants/{rid}"

        # Lo que hace Cartera al abrirse: varias peticiones a la vez sin caja creada
        rs = await asyncio.gather(*(
            [ac.get(f"{base}/caja", headers=H) for _ in range(6)]
            + [ac.get(f"{base}/caja/totales", headers=H) for _ in range(4)]
        ))
        assert all(r.status_code == 200 for r in rs), [r.status_code for r in rs]
        async with AsyncSessionLocal() as db:
            n = await db.scalar(select(func.count()).select_from(Caja).where(Caja.restaurant_id == rid))
        assert n == 1, n
        print("1. 10 peticiones simultáneas → 200 y una sola caja OK")

        r = await ac.get(f"{base}/caja", headers=H)
        assert r.status_code == 200 and r.json()["status"] == "cerrada", r.text
        print("2. la caja nueva arranca cerrada OK")


if __name__ == "__main__":
    asyncio.run(main())
