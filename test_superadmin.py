"""Panel del superadmin: listar/crear dueños, contraseñas y desactivar.

Verifica que "desactivar" corta de verdad: el dueño no entra, su token previo
muere y su inquilino queda congelado (sus empleados tampoco entran).

Ejecutar: python test_superadmin.py
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./sup.db"
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
        async def login(u, p, expect=200):
            r = await ac.post("/auth/login", json={"username": u, "password": p})
            assert r.status_code == expect, f"{u}: esperaba {expect}, fue {r.status_code} {r.text}"
            if r.status_code != 200:
                return None
            return {"Authorization": f"Bearer {r.json()['access_token']}"}

        # el login del superadmin expone is_superadmin (la app lo necesita)
        r = await ac.post("/auth/login", json={"username": "admin", "password": "admin"})
        assert r.json()["user"]["is_superadmin"] is True, r.text
        S = {"Authorization": f"Bearer {r.json()['access_token']}"}
        print("1. login superadmin expone is_superadmin=true OK")

        # lista vacía al inicio
        assert (await ac.get("/admin/users", headers=S)).json() == []
        # crear 2 dueños
        for u in ("maria", "juan"):
            r = await ac.post("/admin/users", headers=S,
                              json={"username": u, "password": "123", "nombre": u.capitalize(),
                                    "isAdmin": True})
            assert r.status_code == 201, r.text
        print("2. superadmin creó a maría y juan OK")

        M = await login("maria", "123")
        J = await login("juan", "123")
        # el login del dueño NO es superadmin
        r = await ac.post("/auth/login", json={"username": "maria", "password": "123"})
        assert r.json()["user"]["is_superadmin"] is False
        assert r.json()["user"]["is_admin"] is True
        print("3. el dueño es is_admin pero NO superadmin OK")

        # maría crea 2 restaurantes, juan 1
        rid_m = (await ac.post("/restaurants", headers=M,
                               json={"title": "M1", "paymentMethods": []})).json()["id"]
        await ac.post("/restaurants", headers=M, json={"title": "M2", "paymentMethods": []})
        await ac.post("/restaurants", headers=J, json={"title": "J1", "paymentMethods": []})

        duenos = {d["username"]: d for d in (await ac.get("/admin/users", headers=S)).json()}
        assert duenos["maria"]["numRestaurantes"] == 2, duenos
        assert duenos["juan"]["numRestaurantes"] == 1, duenos
        assert duenos["maria"]["nombre"] == "Maria" and duenos["maria"]["isActive"] is True
        assert set(duenos) == {"maria", "juan"}, "solo dueños, ni superadmin ni empleados"
        print("4. lista de dueños con nombre/usuario/nº restaurantes OK")

        # maría crea un empleado en su restaurante
        r = await ac.post(f"/restaurants/{rid_m}/empleados/nuevo-usuario", headers=M,
                          json={"username": "pedro", "password": "x", "nombre": "Pedro"})
        assert r.status_code == 201, r.text
        P = await login("pedro", "x")
        assert (await ac.get(f"/restaurants/{rid_m}", headers=P)).status_code == 200
        print("5. el empleado pedro entra al restaurante de maría OK")

        # el superadmin cambia la contraseña de maría
        assert (await ac.put(f"/admin/users/{duenos['maria']['id']}/password", headers=S,
                             json={"password": "nueva"})).status_code == 204
        M = await login("maria", "nueva")
        print("6. superadmin cambió la contraseña de maría (entra con la nueva) OK")

        # === DESACTIVAR a maría ===
        r = await ac.patch(f"/admin/users/{duenos['maria']['id']}/activo", headers=S,
                           json={"isActive": False})
        assert r.status_code == 200 and r.json()["isActive"] is False, r.text

        await login("maria", "nueva", expect=403)          # no puede entrar
        assert (await ac.get("/restaurants", headers=M)).status_code == 401  # token viejo muerto
        # inquilino congelado: su empleado tampoco entra
        assert (await ac.get(f"/restaurants/{rid_m}", headers=P)).status_code == 403
        # juan (otro dueño) sigue normal
        assert (await ac.get("/restaurants", headers=J)).status_code == 200
        print("7. desactivada: login 403, token viejo 401, empleado congelado, juan intacto OK")

        # el superadmin sigue viéndolo todo
        assert len((await ac.get("/restaurants", headers=S)).json()) == 3
        print("8. el superadmin sigue viendo todos los restaurantes OK")

        # === REACTIVAR ===
        assert (await ac.patch(f"/admin/users/{duenos['maria']['id']}/activo", headers=S,
                               json={"isActive": True})).status_code == 200
        M = await login("maria", "nueva")
        assert (await ac.get(f"/restaurants/{rid_m}", headers=M)).status_code == 200
        assert (await ac.get(f"/restaurants/{rid_m}", headers=P)).status_code == 200
        print("9. reactivada: maría y su empleado vuelven a entrar OK")

        # un dueño NO puede usar el panel del superadmin
        assert (await ac.get("/admin/users", headers=M)).status_code == 403
        assert (await ac.patch(f"/admin/users/{duenos['juan']['id']}/activo", headers=M,
                               json={"isActive": False})).status_code == 403
        print("10. un dueño no puede listar ni desactivar dueños (403) OK")

        # no se puede desactivar a un superadmin ni a uno mismo
        me = (await ac.get("/auth/me", headers=S)).json()["id"]
        assert (await ac.patch(f"/admin/users/{me}/activo", headers=S,
                               json={"isActive": False})).status_code == 403
        print("11. el superadmin no puede desactivarse a sí mismo (403) OK")

        print("\n==> PANEL DEL SUPERADMIN VERIFICADO (11/11)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
