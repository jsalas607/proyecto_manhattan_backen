"""Venta al detalle sobre SQLite: código de barras, kárdex, venta que descuenta
stock, reportes de utilidad e importación desde Gecofi. Ejecutar:
    python test_stock.py
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./stock.db"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin"

import httpx  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app, bootstrap_admin  # noqa: E402

AGUILA = "7702004002013"


def cerca(a: float, b: float) -> bool:
    return abs(a - b) < 0.01


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

        S = await login("admin", "admin")
        for user in ("maria", "juan"):
            r = await ac.post("/admin/users", headers=S,
                              json={"username": user, "password": "123", "nombre": user, "isAdmin": True})
            assert r.status_code == 201, r.text
        M = await login("maria", "123")
        J = await login("juan", "123")
        rid = (await ac.post("/restaurants", headers=M,
                             json={"title": "Licorera", "paymentMethods": ["efectivo"]})).json()["id"]
        rol = (await ac.post(f"/restaurants/{rid}/roles", headers=M,
                             json={"nombre": "cajero", "permisos": ["cobrar_mesa"]})).json()["id"]
        r = await ac.post(f"/restaurants/{rid}/empleados/nuevo-usuario", headers=M,
                          json={"username": "caja1", "password": "x", "nombre": "Caja", "rolId": rol})
        assert r.status_code == 201, r.text
        C = await login("caja1", "x")
        print("1. dueña, restaurante y cajero (solo cobrar_mesa) OK")

        base = f"/restaurants/{rid}"
        cat = (await ac.post(f"{base}/categorias", headers=M, json={"nombre": "Cervezas"})).json()["id"]
        r = await ac.post(f"{base}/productos", headers=M, json={
            "nombre": "Cerveza Aguila", "precio": 4000, "categoriaId": cat,
            "codigoBarras": AGUILA, "costo": 2283, "controlaStock": True,
            "stockInicial": 24, "stockMinimo": 30,
        })
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        assert r.json()["stock"] == 24 and r.json()["codigoBarras"] == AGUILA
        print("2. producto con código, costo y stock inicial OK")

        for codigo in (AGUILA, f"  {AGUILA} "):
            r = await ac.post(f"{base}/productos", headers=M, json={
                "nombre": "Otra", "precio": 1, "categoriaId": cat, "codigoBarras": codigo})
            assert r.status_code == 409, r.text
        r = await ac.post(f"{base}/productos", headers=M, json={
            "nombre": "Sin categoría", "precio": 1, "categoriaId": "cat-nope"})
        assert r.status_code == 404, r.text
        print("3. código repetido (con o sin espacios) → 409, categoría ajena → 404 OK")

        r = await ac.get(f"{base}/productos/barcode/{AGUILA}", headers=C)
        assert r.status_code == 200 and r.json()["id"] == pid, r.text
        assert (await ac.get(f"{base}/productos/barcode/000", headers=M)).status_code == 404
        assert (await ac.get(f"{base}/productos/barcode/{AGUILA}", headers=J)).status_code == 403
        print("4. escaneo: cajero lo encuentra, código desconocido 404, otro dueño 403 OK")

        for q in ("aguila", "77020"):
            r = await ac.get(f"{base}/productos/buscar", headers=C, params={"q": q})
            assert [p["id"] for p in r.json()] == [pid], (q, r.text)
        print("5. búsqueda por nombre y por inicio de código OK")

        r = await ac.post(f"{base}/stock/entradas", headers=M, json={
            "items": [{"productoId": pid, "cantidad": 12, "costoUnitario": 2500}], "nota": "Bavaria"})
        assert r.status_code == 201, r.text
        prod = (await ac.get(f"{base}/productos/barcode/{AGUILA}", headers=M)).json()
        costo_prom = (24 * 2283 + 12 * 2500) / 36
        assert prod["stock"] == 36 and cerca(prod["costo"], costo_prom), prod
        assert (await ac.post(f"{base}/stock/entradas", headers=C, json={
            "items": [{"productoId": pid, "cantidad": 1}]})).status_code == 403
        print(f"6. entrada de 12 → stock 36, costo promedio {costo_prom:.2f}; cajero 403 OK")

        r = await ac.post(f"{base}/ventas", headers=C, json={
            "mesaNumero": 0, "orden": 1, "total": 9000,
            "items": [
                {"productoId": pid, "productoNombre": "Cerveza Aguila", "cantidad": 2},
                {"productoId": "mock-1", "productoNombre": "Item viejo", "cantidad": 1},
            ],
            "pagos": [{"metodo": "efectivo", "monto": 9000}],
        })
        assert r.status_code == 201, r.text
        venta = r.json()
        it = venta["items"][0]
        assert it["precioUnitario"] == 4000 and cerca(it["costoUnitario"], costo_prom), it
        assert it["categoriaId"] == cat, it
        assert venta["items"][1]["precioUnitario"] is None, venta["items"][1]
        prod = (await ac.get(f"{base}/productos/barcode/{AGUILA}", headers=M)).json()
        assert prod["stock"] == 34, prod
        print("7. venta: precio y costo congelados, descuenta 2 (stock 34); ítem sin producto no rompe OK")

        r = await ac.post(f"{base}/stock/salidas", headers=M, json={
            "items": [{"productoId": pid, "cantidad": 1}], "motivo": "merma", "nota": "rota"})
        assert r.status_code == 201 and r.json()[0]["stockResultante"] == 33, r.text
        r = await ac.post(f"{base}/stock/ajustes", headers=M, json={
            "items": [{"productoId": pid, "stockReal": 30}]})
        assert r.status_code == 201 and r.json()[0]["cantidad"] == -3, r.text
        r = await ac.post(f"{base}/stock/ajustes", headers=M, json={
            "items": [{"productoId": pid, "stockReal": 30}]})
        assert r.status_code == 201 and r.json() == [], r.text
        print("8. salida por merma (33) y ajuste por conteo (30); conteo igual no genera movimiento OK")

        r = await ac.get(f"{base}/stock/movimientos", headers=M, params={"productoId": pid})
        movs = r.json()
        assert [m["tipo"] for m in movs] == ["ajuste", "salida", "venta", "entrada", "entrada"], movs
        assert movs[0]["stockResultante"] == 30
        assert sum(m["cantidad"] for m in movs) == 30
        assert movs[2]["ventaId"] == venta["id"]
        print("9. kárdex: 5 movimientos que suman el stock actual (30) OK")

        alertas = (await ac.get(f"{base}/stock/alertas", headers=M)).json()
        assert [p["id"] for p in alertas] == [pid], alertas
        inv = (await ac.get(f"{base}/reportes/inventario", headers=M)).json()
        assert inv["unidades"] == 30 and cerca(inv["valorCosto"], 30 * costo_prom), inv
        assert inv["valorVenta"] == 120000 and inv["porCategoria"][0]["categoria"] == "Cervezas", inv
        print("10. alerta de stock mínimo y valor del inventario OK")

        rep = (await ac.get(f"{base}/reportes/ventas", headers=M)).json()
        assert rep["tickets"] == 1 and rep["totalVentas"] == 9000, rep
        assert rep["ventasConCosto"] == 8000 and cerca(rep["costo"], 2 * costo_prom), rep
        assert cerca(rep["utilidad"], 8000 - 2 * costo_prom), rep
        assert rep["salidasUnidades"] == 1 and cerca(rep["salidasCosto"], costo_prom), rep
        assert rep["masVendidos"][0]["productoId"] == pid, rep
        assert (await ac.get(f"{base}/reportes/ventas", headers=C)).status_code == 403
        print(f"11. reporte de ventas: utilidad {rep['utilidad']:.0f}, margen {rep['margen']:.1%}; cajero 403 OK")

        r = await ac.patch(f"{base}/productos/{pid}", headers=M,
                           json={"precio": 4500, "codigoBarras": None})
        assert r.status_code == 200 and r.json()["precio"] == 4500 and r.json()["codigoBarras"] is None
        assert r.json()["stock"] == 30, r.json()
        assert (await ac.get(f"{base}/productos/barcode/{AGUILA}", headers=M)).status_code == 404
        print("12. PATCH cambia precio y quita el código sin tocar el stock OK")

        # --- Importación desde Gecofi (otro restaurante limpio) ---
        rid2 = (await ac.post("/restaurants", headers=M,
                              json={"title": "Sede 2", "paymentMethods": []})).json()["id"]
        payload = {
            "categorias": [{"id": 128, "nombre": "BEBIDAS "}, {"id": 127, "nombre": "PRUEBA"},
                           {"id": 129, "nombre": "LICORES"}],
            "productos": [
                {"nombre": "AGUA CRISTAL 600ml ", "categoria_id": 128, "codigo_barras": "7702090022711",
                 "precio_venta": 2500, "precio_compra": 1250, "stock": 18, "stock_minimo": 2,
                 "unidad": "C/U"},
                {"nombre": "CHIVAS 12 AÑOS", "categoria_id": 129, "codigo_barras": "080432402931",
                 "precio_venta": 185000, "precio_compra": 0, "stock": 1, "unidad": "C/U"},
                {"nombre": "Papas 60gr", "categoria_id": 128, "codigo_barras": None,
                 "precio_venta": 4000, "precio_compra": 2500, "stock": 1, "unidad": "C/U"},
            ],
        }
        url = f"/restaurants/{rid2}/import/gecofi"
        assert (await ac.post(url, headers=J, json=payload)).status_code == 403
        r = await ac.post(url, headers=M, json=payload)
        assert r.status_code == 200, r.text
        assert r.json() == {"categoriasCreadas": 2, "productosCreados": 3,
                            "productosActualizados": 0, "unidadesCargadas": 20}, r.json()
        cats2 = sorted(c["nombre"] for c in (await ac.get(f"/restaurants/{rid2}/categorias", headers=M)).json())
        assert cats2 == ["BEBIDAS", "LICORES"], cats2
        agua = (await ac.get(f"/restaurants/{rid2}/productos/barcode/7702090022711", headers=M)).json()
        assert agua["nombre"] == "AGUA CRISTAL 600ml" and agua["stock"] == 18 and agua["unidad"] == "und", agua
        print("13. importación: 2 categorías (sin la vacía), 3 productos, 20 unidades OK")

        r = await ac.post(url, headers=M, json=payload)
        assert r.json() == {"categoriasCreadas": 0, "productosCreados": 0,
                            "productosActualizados": 3, "unidadesCargadas": 0}, r.json()
        payload["productos"][0]["stock"] = 10
        payload["actualizarStock"] = True
        r = await ac.post(url, headers=M, json=payload)
        assert r.json()["unidadesCargadas"] == -8, r.json()
        agua = (await ac.get(f"/restaurants/{rid2}/productos/barcode/7702090022711", headers=M)).json()
        assert agua["stock"] == 10, agua
        assert len((await ac.get(f"/restaurants/{rid2}/productos", headers=M)).json()) == 3
        print("14. reimportar no duplica; con actualizarStock iguala el stock (18 → 10) OK")

    print("\n==> TODOS LOS CHECKS DE STOCK PASARON (14/14)")


if __name__ == "__main__":
    asyncio.run(main())
