"""Prueba de aislamiento multi-inquilino (dueños independientes) sobre SQLite.

Verifica que dos dueños (maría, juan) NO se ven entre sí: cada uno solo ve y
gestiona sus restaurantes y empleados. Ejecutar:
    python test_isolation.py
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./iso.db"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin"

import httpx  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app, bootstrap_admin  # noqa: E402


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

        # superadmin crea a maría y juan (dueños)
        S = await login("admin", "admin")
        for user in ("maria", "juan"):
            r = await ac.post("/admin/users", headers=S,
                              json={"username": user, "password": "123", "nombre": user, "isAdmin": True})
            assert r.status_code == 201, r.text
        print("1. superadmin creó a maría y juan OK")

        M = await login("maria", "123")
        J = await login("juan", "123")

        # cada dueño crea su restaurante
        rA = (await ac.post("/restaurants", headers=M, json={"title": "Rest A", "paymentMethods": []})).json()["id"]
        rB = (await ac.post("/restaurants", headers=J, json={"title": "Rest B", "paymentMethods": []})).json()["id"]
        print("2. maría creó Rest A, juan creó Rest B OK")

        # cada uno ve SOLO el suyo
        listaM = [x["id"] for x in (await ac.get("/restaurants", headers=M)).json()]
        listaJ = [x["id"] for x in (await ac.get("/restaurants", headers=J)).json()]
        assert listaM == [rA], listaM
        assert listaJ == [rB], listaJ
        print("3. maría ve [A], juan ve [B] — listas aisladas OK")

        # my-restaurants también aislado
        # (my-restaurants usa snake_case: restaurant_id)
        myM = [x["restaurant_id"] for x in (await ac.get("/auth/my-restaurants", headers=M)).json()["restaurants"]]
        assert myM == [rA], myM
        print("4. my-restaurants de maría = [A] OK")

        # cruce prohibido: juan no accede al de maría y viceversa
        assert (await ac.get(f"/restaurants/{rA}", headers=J)).status_code == 403
        assert (await ac.get(f"/restaurants/{rB}", headers=M)).status_code == 403
        assert (await ac.get(f"/restaurants/{rA}/stats", headers=J)).status_code == 403
        assert (await ac.delete(f"/restaurants/{rA}", headers=J)).status_code == 403
        print("5. juan recibe 403 en el restaurante de maría (ver/stats/borrar) OK")

        # maría crea empleado pedro en su restaurante
        r = await ac.post(f"/restaurants/{rA}/empleados/nuevo-usuario", headers=M,
                          json={"username": "pedro", "password": "x", "nombre": "Pedro"})
        assert r.status_code == 201, r.text
        pedro_id = r.json()["userId"]

        # juan no ve ni toca al empleado de maría
        assert (await ac.get(f"/restaurants/{rA}/empleados", headers=J)).status_code == 403
        assert (await ac.delete(f"/admin/users/{pedro_id}", headers=J)).status_code == 403
        assert (await ac.put(f"/admin/users/{pedro_id}/password", headers=J, json={"password": "hack"})).status_code == 403
        print("6. juan no ve ni gestiona al empleado de maría (403) OK")

        # maría SÍ gestiona a su propio empleado
        assert (await ac.put(f"/admin/users/{pedro_id}/password", headers=M, json={"password": "nueva"})).status_code == 204
        assert (await ac.post("/auth/login", json={"username": "pedro", "password": "nueva"})).status_code == 200
        print("7. maría cambia la contraseña de SU empleado OK")

        # un dueño NO puede crear otros dueños (solo superadmin)
        assert (await ac.post("/admin/users", headers=M,
                              json={"username": "otro", "password": "1", "isAdmin": True})).status_code == 403
        print("8. un dueño no puede crear usuarios globales (403) OK")

        # superadmin sí ve todo
        todos = [x["id"] for x in (await ac.get("/restaurants", headers=S)).json()]
        assert set(todos) == {rA, rB}, todos
        print("9. superadmin ve TODOS los restaurantes OK")

        print("\n==> AISLAMIENTO VERIFICADO (9/9)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
