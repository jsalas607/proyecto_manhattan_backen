"""Jerarquía dentro de un dueño: los gerentes no ven ni tocan a otros gerentes.

- Dueño (is_admin, quien paga): ve y gestiona a TODOS.
- Gerente: empleado con rol que incluye `administrar_restaurante`. Solo ve/gestiona
  empleados normales; no ve a otros gerentes ni a sí mismo (por tanto no puede
  auto-eliminarse).

Ejecutar: python test_jerarquia.py
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./jer.db"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin"

import httpx  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app, bootstrap_admin  # noqa: E402

PERM_GERENTE = ["administrar_restaurante", "crear_empleado", "invitar_empleado"]


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await bootstrap_admin()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api") as ac:
        async def login(u, p):
            r = await ac.post("/auth/login", json={"username": u, "password": p})
            assert r.status_code == 200, r.text
            return {"Authorization": f"Bearer {r.json()['access_token']}"}

        # superadmin crea al dueño (quien paga)
        S = await login("admin", "admin")
        r = await ac.post("/admin/users", headers=S,
                          json={"username": "maria", "password": "123", "nombre": "María",
                                "isAdmin": True})
        assert r.status_code == 201, r.text
        D = await login("maria", "123")  # dueño

        # el dueño crea su restaurante y los roles
        rid = (await ac.post("/restaurants", headers=D,
                             json={"title": "Rest", "paymentMethods": []})).json()["id"]
        rol_ger = (await ac.post(f"/restaurants/{rid}/roles", headers=D,
                                 json={"nombre": "gerente", "permisos": PERM_GERENTE})).json()["id"]
        rol_mes = (await ac.post(f"/restaurants/{rid}/roles", headers=D,
                                 json={"nombre": "mesero", "permisos": ["crear_mesa"]})).json()["id"]
        print("1. dueño creó restaurante + roles (gerente / mesero) OK")

        async def nuevo(username, rol):
            r = await ac.post(f"/restaurants/{rid}/empleados/nuevo-usuario", headers=D,
                              json={"username": username, "password": "x",
                                    "nombre": username, "rolId": rol})
            assert r.status_code == 201, r.text
            return r.json()

        ger1 = await nuevo("ger1", rol_ger)
        ger2 = await nuevo("ger2", rol_ger)
        mesero1 = await nuevo("mesero1", rol_mes)
        print("2. dueño creó ger1, ger2 (gerentes) y mesero1 OK")

        G1 = await login("ger1", "x")

        # El dueño ve a los 3
        vistos_d = {e["nombre"] for e in (await ac.get(f"/restaurants/{rid}/empleados", headers=D)).json()}
        assert vistos_d == {"ger1", "ger2", "mesero1"}, vistos_d
        print("3. el dueño ve a TODOS (ger1, ger2, mesero1) OK")

        # ger1 solo ve a mesero1 (ni a ger2 ni a sí mismo)
        vistos_g = {e["nombre"] for e in (await ac.get(f"/restaurants/{rid}/empleados", headers=G1)).json()}
        assert vistos_g == {"mesero1"}, vistos_g
        print("4. ger1 solo ve a mesero1 (no ve a ger2 ni a sí mismo) OK")

        # ger1 no puede quitar a otro gerente ni a sí mismo (auto-eliminación cubierta)
        assert (await ac.delete(f"/restaurants/{rid}/empleados/{ger2['id']}", headers=G1)).status_code == 403
        assert (await ac.delete(f"/restaurants/{rid}/empleados/{ger1['id']}", headers=G1)).status_code == 403
        print("5. ger1 NO puede quitar a ger2 ni a sí mismo (403) OK")

        # ger1 tampoco puede editar/degradar a un par
        r = await ac.put(f"/restaurants/{rid}/empleados/{ger2['id']}", headers=G1,
                         json={"nombre": "hackeado", "rolId": rol_mes})
        assert r.status_code == 403, r.text
        print("6. ger1 NO puede editar a ger2 (403) OK")

        # ger1 no puede borrar cuentas (no es dueño)
        assert (await ac.delete(f"/admin/users/{ger2['userId']}", headers=G1)).status_code == 403
        print("7. ger1 NO puede eliminar cuentas del sistema (403) OK")

        # ger1 SÍ gestiona empleados normales
        assert (await ac.delete(f"/restaurants/{rid}/empleados/{mesero1['id']}", headers=G1)).status_code == 204
        print("8. ger1 SÍ puede quitar a mesero1 (204) OK")

        # el dueño SÍ manda sobre los gerentes
        assert (await ac.delete(f"/restaurants/{rid}/empleados/{ger2['id']}", headers=D)).status_code == 204
        print("9. el dueño SÍ puede quitar a un gerente (204) OK")

        print("\n==> JERARQUÍA VERIFICADA (9/9)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
