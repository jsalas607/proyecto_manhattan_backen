"""Prueba de humo end-to-end contra SQLite en memoria (sin Docker).

No forma parte del runtime; valida el flujo principal de la API.
Ejecutar: .\.venv\Scripts\python.exe smoke_test.py
"""
import asyncio
import os

# IMPORTANTE: configurar antes de importar la app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./smoke.db"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin"

import httpx  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app, bootstrap_admin  # noqa: E402


async def main() -> None:
    # crea el esquema (equivale a la migración baseline create_all)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await bootstrap_admin()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api") as ac:
        ok = 0

        # 1) login admin
        r = await ac.post("/auth/login", json={"username": "admin", "password": "admin"})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        H = {"Authorization": f"Bearer {token}"}
        print("1. login admin OK")
        ok += 1

        # 2) crear restaurante
        r = await ac.post(
            "/restaurants",
            headers=H,
            json={"title": "Sucursal Centro", "paymentMethods": ["efectivo", "nequi"]},
        )
        assert r.status_code == 201, r.text
        rid = r.json()["id"]
        assert r.json()["paymentMethods"] == ["efectivo", "nequi"]
        print(f"2. restaurante creado {rid} OK")
        ok += 1

        # 3) categoria + producto
        r = await ac.post(f"/restaurants/{rid}/categorias", headers=H, json={"nombre": "Principales"})
        assert r.status_code == 201, r.text
        cat = r.json()["id"]
        r = await ac.post(
            f"/restaurants/{rid}/productos",
            headers=H,
            json={
                "nombre": "Bandeja Paisa",
                "precio": 18000,
                "categoriaId": cat,
                "ingredientes": [
                    {"nombre": "Proteína", "obligatorio": False, "opciones": [{"nombre": "Pollo"}]}
                ],
            },
        )
        assert r.status_code == 201, r.text
        prod = r.json()
        assert prod["ingredientes"][0]["opciones"][0]["nombre"] == "Pollo"
        print("3. categoria + producto compuesto OK")
        ok += 1

        # 4) mesa + pedido
        r = await ac.post(f"/restaurants/{rid}/mesas", headers=H, json={"numero": 3, "nombre": "Carlos"})
        assert r.status_code == 201, r.text
        mesa = r.json()
        assert mesa["orden"] == 1
        r = await ac.put(
            f"/restaurants/{rid}/pedidos/{mesa['id']}",
            headers=H,
            json={
                "mesaNumero": 3,
                "orden": 1,
                "items": [
                    {
                        "productoId": prod["id"],
                        "productoNombre": "Bandeja Paisa",
                        "categoriaId": cat,
                        "cantidad": 2,
                        "config": "Proteína: Pollo",
                    }
                ],
            },
        )
        assert r.status_code == 200, r.text
        print("4. mesa + pedido OK")
        ok += 1

        # 5) marcar item listo -> mesas atendidas
        r = await ac.patch(
            f"/restaurants/{rid}/pedidos/{mesa['id']}/items/0/listo", headers=H, json={"listo": True}
        )
        assert r.status_code == 200, r.text
        r = await ac.get(f"/restaurants/{rid}/pedidos/mesas-atendidas", headers=H)
        assert mesa["id"] in r.json(), r.text
        print("5. item listo + mesa atendida OK")
        ok += 1

        # 6) registrar venta + stats
        r = await ac.post(
            f"/restaurants/{rid}/ventas",
            headers=H,
            json={
                "mesaNumero": 3,
                "orden": 1,
                "nombreCliente": "Carlos",
                "items": [
                    {"productoId": prod["id"], "productoNombre": "Bandeja Paisa", "categoriaId": cat,
                     "cantidad": 2, "config": ""}
                ],
                "pagos": [{"metodo": "efectivo", "monto": 36000}],
                "total": 36000,
            },
        )
        assert r.status_code == 201, r.text
        r = await ac.get(f"/restaurants/{rid}/stats", headers=H)
        st = r.json()
        assert st["ordenesCreadias"] == 1 and st["dineroFacturado"] == 36000, st
        print("6. venta + stats OK")
        ok += 1

        # 7) inventario: item + conteo + propagación
        r = await ac.post(
            f"/restaurants/{rid}/inventory/items", headers=H, json={"name": "Arroz", "unidad": "kg"}
        )
        assert r.status_code == 201, r.text
        item_id = r.json()["id"]
        from datetime import date
        hoy = date.today().isoformat()
        r = await ac.put(
            f"/restaurants/{rid}/inventory/{item_id}/real",
            headers=H,
            json={"date": hoy, "invReal": 50},
        )
        assert r.status_code == 200 and r.json()["isCounted"] is True, r.text
        print("7. inventario + conteo OK")
        ok += 1

        # 8) caja: abrir + totales
        r = await ac.post(
            f"/restaurants/{rid}/caja/abrir", headers=H, json={"montosIniciales": {"efectivo": 100000}}
        )
        assert r.status_code == 200 and r.json()["status"] == "abierta", r.text
        r = await ac.get(f"/restaurants/{rid}/caja/totales?metodos=efectivo,nequi", headers=H)
        tot = {x["name"]: x["total"] for x in r.json()}
        # efectivo = 100000 inicial + 36000 venta de hoy
        assert tot["efectivo"] == 136000, tot
        print("8. caja abierta + totales (incluye ventas del día) OK")
        ok += 1

        # 9) permisos: usuario sin acceso -> 403
        # (el registro público ya no existe: el admin crea la cuenta en OTRO
        # restaurante vía /empleados/nuevo-usuario; sin membership en `rid`)
        r = await ac.post(
            "/restaurants", headers=H, json={"title": "Otro", "paymentMethods": []}
        )
        rid2 = r.json()["id"]
        r = await ac.post(
            f"/restaurants/{rid2}/empleados/nuevo-usuario",
            headers=H,
            json={"username": "mesero1", "password": "x", "nombre": "Mesero"},
        )
        assert r.status_code == 201, r.text
        r = await ac.post("/auth/login", json={"username": "mesero1", "password": "x"})
        H2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await ac.get(f"/restaurants/{rid}/stats", headers=H2)
        assert r.status_code == 403, f"esperaba 403, fue {r.status_code}"
        print("9. permisos: usuario sin membership recibe 403 OK")
        ok += 1

        print(f"\n==> TODOS LOS CHECKS PASARON ({ok}/9)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
