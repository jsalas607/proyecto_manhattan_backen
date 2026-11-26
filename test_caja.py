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
from app.models.cartera import Caja, CajaMontoInicial  # noqa: E402


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

        async def vender(monto, metodo):
            r = await ac.post(f"{base}/ventas", headers=H, json={
                "mesaNumero": 0, "orden": 0, "nombreCliente": "Mostrador", "items": [],
                "pagos": [{"metodo": metodo, "monto": monto}], "total": monto,
            })
            assert r.status_code in (200, 201), r.text

        async def totales():
            r = await ac.get(f"{base}/caja/totales", headers=H,
                             params={"metodos": "efectivo,transferencia"})
            assert r.status_code == 200, r.text
            return {t["name"]: t["total"] for t in r.json()}

        # Venta de la madrugada, del turno anterior (la caja ya estaba cerrada)
        await vender(20000, "efectivo")
        await vender(50000, "transferencia")
        await asyncio.sleep(0.05)

        # Dos toques seguidos en «Abrir caja»
        body = {"montosIniciales": {"efectivo": 100000, "transferencia": 0}}
        rs = await asyncio.gather(*[ac.post(f"{base}/caja/abrir", headers=H, json=body) for _ in range(3)])
        assert all(r.status_code == 200 for r in rs), [r.text for r in rs]
        async with AsyncSessionLocal() as db:
            n = await db.scalar(select(func.count()).select_from(CajaMontoInicial))
        assert n == 2, n
        print("3. tres toques en «Abrir caja» → un monto por método OK")

        t = await totales()
        assert t == {"efectivo": 100000, "transferencia": 0}, t
        r = await ac.get(f"{base}/stats", headers=H)
        assert r.json()["ordenesCreadias"] == 0, r.text
        print("4. las ventas de antes de abrir no se suman a la caja ni a las estadísticas OK")

        await vender(5000, "efectivo")
        t = await totales()
        assert t == {"efectivo": 105000, "transferencia": 0}, t
        st = (await ac.get(f"{base}/stats", headers=H)).json()
        assert st["ordenesCreadias"] == 1 and st["dineroFacturado"] == 5000, st
        print("5. las ventas del turno sí se suman (100.000 + 5.000) OK")

        r = await ac.post(f"{base}/caja/cerrar", headers=H)
        assert r.status_code == 200 and r.json()["status"] == "cerrada", r.text
        async with AsyncSessionLocal() as db:
            n = await db.scalar(select(func.count()).select_from(CajaMontoInicial))
        assert n == 0, n
        print("6. cerrar la caja borra los montos iniciales OK")


if __name__ == "__main__":
    asyncio.run(main())
