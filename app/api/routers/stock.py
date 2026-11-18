"""Venta al detalle: búsqueda por código de barras, kárdex de stock, reportes
de utilidad e importación desde Gecofi."""
from collections import defaultdict
from datetime import date as date_type
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routers.menu import get_producto_full, producto_out
from app.core.database import get_db
from app.core.timeutil import day_bounds_utc, local_today
from app.deps import require_permission, require_restaurant_access, require_restaurant_owner
from app.models.menu import Categoria, Producto, ProductoIngrediente
from app.models.organization import User
from app.models.sales import Venta
from app.models.stock import StockMovimiento
from app.schemas.menu import ProductoOut
from app.schemas.stock import (
    AjusteIn,
    CategoriaValor,
    CategoriaVentas,
    EntradaIn,
    ImportGecofiIn,
    ImportResultOut,
    InventarioValorOut,
    MovimientoOut,
    ProductoVendido,
    ReporteVentasOut,
    SalidaIn,
)
from app.services.stock import (
    asegurar_codigo_libre,
    costo_promedio,
    exigir_productos,
    mover_stock,
    normalizar_codigo,
)

router = APIRouter(prefix="/restaurants/{rid}", tags=["stock"])


# ----------------- Búsqueda (escáner) -----------------
@router.get("/productos/barcode/{codigo}", response_model=ProductoOut)
async def buscar_por_codigo(
    rid: str,
    codigo: str,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    """Lo que llama el punto de venta al escanear. 404 si el código no existe."""
    codigo = normalizar_codigo(codigo)
    pid = await db.scalar(
        select(Producto.id).where(Producto.restaurant_id == rid, Producto.codigo_barras == codigo)
    )
    if pid is None:
        raise HTTPException(status_code=404, detail="Código no registrado")
    return producto_out(await get_producto_full(db, rid, pid))


@router.get("/productos/buscar", response_model=list[ProductoOut])
async def buscar_productos(
    rid: str,
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    """Búsqueda por nombre (contiene, sin distinguir mayúsculas) o por código
    de barras (empieza por). Los que coinciden exacto con el código van primero."""
    texto = q.strip()
    patron = f"%{texto.lower()}%"
    result = await db.execute(
        select(Producto)
        .where(
            Producto.restaurant_id == rid,
            or_(
                func.lower(Producto.nombre).like(patron),
                Producto.codigo_barras.like(f"{texto}%"),
            ),
        )
        .options(selectinload(Producto.ingredientes).selectinload(ProductoIngrediente.opciones))
        .order_by(Producto.nombre)
        .limit(limit)
    )
    prods = sorted(result.scalars().all(), key=lambda p: p.codigo_barras != texto)
    return [producto_out(p) for p in prods]


# ----------------- Movimientos de stock -----------------
def _mov_out(m: StockMovimiento, nombre: str) -> MovimientoOut:
    return MovimientoOut(
        id=m.id,
        producto_id=m.producto_id,
        producto_nombre=nombre,
        tipo=m.tipo,
        cantidad=m.cantidad,
        stock_resultante=m.stock_resultante,
        costo_unitario=m.costo_unitario,
        motivo=m.motivo,
        nota=m.nota,
        venta_id=m.venta_id,
        usuario_id=m.usuario_id,
        fecha=m.fecha,
    )


def _solo_con_stock(prods: dict[str, Producto]) -> None:
    sin = [p.nombre for p in prods.values() if not p.controla_stock]
    if sin:
        raise HTTPException(
            status_code=409, detail=f"«{sin[0]}» no controla stock (actívalo en el producto)"
        )


@router.post("/stock/entradas", response_model=list[MovimientoOut], status_code=201)
async def registrar_entrada(
    rid: str,
    body: EntradaIn,
    current: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    """Compra / ingreso de mercancía. Con costo, actualiza el costo promedio."""
    prods = await exigir_productos(db, rid, [i.producto_id for i in body.items])
    _solo_con_stock(prods)
    movs = []
    for i in body.items:
        p = prods[i.producto_id]
        if i.costo_unitario is not None:
            p.costo = costo_promedio(p.stock or 0, p.costo or 0, i.cantidad, i.costo_unitario)
        movs.append(
            mover_stock(
                db, p, "entrada", i.cantidad,
                costo_unitario=i.costo_unitario, nota=body.nota, usuario_id=current.id,
            )
        )
    await db.commit()
    return [_mov_out(m, prods[m.producto_id].nombre) for m in movs]


@router.post("/stock/salidas", response_model=list[MovimientoOut], status_code=201)
async def registrar_salida(
    rid: str,
    body: SalidaIn,
    current: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    """Salida que no es venta (merma, consumo, cortesía...). Queda separada de
    las ventas para poder ver cuánto inventario se va sin venderse."""
    prods = await exigir_productos(db, rid, [i.producto_id for i in body.items])
    _solo_con_stock(prods)
    movs = [
        mover_stock(
            db, prods[i.producto_id], "salida", -i.cantidad,
            motivo=body.motivo, nota=body.nota, usuario_id=current.id,
        )
        for i in body.items
    ]
    await db.commit()
    return [_mov_out(m, prods[m.producto_id].nombre) for m in movs]


@router.post("/stock/ajustes", response_model=list[MovimientoOut], status_code=201)
async def registrar_ajuste(
    rid: str,
    body: AjusteIn,
    current: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    """Conteo físico. Solo genera movimiento si el contado difiere del sistema."""
    prods = await exigir_productos(db, rid, [i.producto_id for i in body.items])
    _solo_con_stock(prods)
    movs = []
    for i in body.items:
        p = prods[i.producto_id]
        diff = i.stock_real - (p.stock or 0)
        if diff:
            movs.append(mover_stock(db, p, "ajuste", diff, nota=body.nota, usuario_id=current.id))
    await db.commit()
    return [_mov_out(m, prods[m.producto_id].nombre) for m in movs]


@router.get("/stock/movimientos", response_model=list[MovimientoOut])
async def listar_movimientos(
    rid: str,
    producto_id: str | None = Query(default=None, alias="productoId"),
    tipo: str | None = Query(default=None),
    desde: date_type | None = Query(default=None),
    hasta: date_type | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    """Kárdex, del más reciente al más antiguo."""
    q = (
        select(StockMovimiento, Producto.nombre)
        .join(Producto, Producto.id == StockMovimiento.producto_id)
        .where(StockMovimiento.restaurant_id == rid)
    )
    if producto_id:
        q = q.where(StockMovimiento.producto_id == producto_id)
    if tipo:
        q = q.where(StockMovimiento.tipo == tipo)
    if desde:
        q = q.where(StockMovimiento.fecha >= day_bounds_utc(desde)[0])
    if hasta:
        q = q.where(StockMovimiento.fecha <= day_bounds_utc(hasta)[1])
    result = await db.execute(q.order_by(StockMovimiento.fecha.desc()).limit(limit))
    return [_mov_out(m, nombre) for m, nombre in result.all()]


@router.get("/stock/alertas", response_model=list[ProductoOut])
async def stock_bajo(
    rid: str,
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    """Productos con stock en o por debajo del mínimo (para pedir al proveedor)."""
    result = await db.execute(
        select(Producto)
        .where(
            Producto.restaurant_id == rid,
            Producto.controla_stock.is_(True),
            Producto.stock <= Producto.stock_minimo,
        )
        .options(selectinload(Producto.ingredientes).selectinload(ProductoIngrediente.opciones))
        .order_by(Producto.stock - Producto.stock_minimo, Producto.nombre)
    )
    return [producto_out(p) for p in result.scalars().all()]


# ----------------- Reportes -----------------
async def _nombres_categorias(db: AsyncSession, rid: str) -> dict[str, str]:
    result = await db.execute(
        select(Categoria.id, Categoria.nombre).where(Categoria.restaurant_id == rid)
    )
    return dict(result.all())


@router.get("/reportes/inventario", response_model=InventarioValorOut)
async def reporte_inventario(
    rid: str,
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    """Cuánto vale lo que hay en bodega, a costo y a precio de venta."""
    cats = await _nombres_categorias(db, rid)
    result = await db.execute(
        select(Producto).where(Producto.restaurant_id == rid, Producto.controla_stock.is_(True))
    )
    prods = result.scalars().all()
    por_cat: dict[str, CategoriaValor] = {}
    for p in prods:
        c = por_cat.setdefault(
            p.categoria_id,
            CategoriaValor(
                categoria_id=p.categoria_id, categoria=cats.get(p.categoria_id, ""),
                productos=0, unidades=0, valor_costo=0, valor_venta=0,
            ),
        )
        en_bodega = max(p.stock or 0, 0)
        c.productos += 1
        c.unidades += en_bodega
        c.valor_costo += en_bodega * (p.costo or 0)
        c.valor_venta += en_bodega * (p.precio or 0)
    filas = sorted(por_cat.values(), key=lambda c: -c.valor_costo)
    return InventarioValorOut(
        productos=len(prods),
        unidades=sum(c.unidades for c in filas),
        valor_costo=sum(c.valor_costo for c in filas),
        valor_venta=sum(c.valor_venta for c in filas),
        productos_sin_costo=sum(1 for p in prods if not p.costo),
        productos_stock_negativo=sum(1 for p in prods if (p.stock or 0) < 0),
        por_categoria=filas,
    )


def _rango_utc(desde: date_type, hasta: date_type, hora_corte: int) -> tuple[datetime, datetime]:
    """Rango [desde, hasta] en días locales. `hora_corte` desplaza el inicio
    del día comercial: con 6, la venta de las 2 a.m. del sábado cuenta para
    el viernes (negocios nocturnos)."""
    corte = timedelta(hours=hora_corte)
    return day_bounds_utc(desde)[0] + corte, day_bounds_utc(hasta)[1] + corte


@router.get("/reportes/ventas", response_model=ReporteVentasOut)
async def reporte_ventas(
    rid: str,
    desde: date_type | None = Query(default=None),
    hasta: date_type | None = Query(default=None),
    hora_corte: int = Query(default=0, ge=0, le=12, alias="horaCorte"),
    top: int = Query(default=20, ge=1, le=500),
    _: User = Depends(require_permission("ver_cartera")),
    db: AsyncSession = Depends(get_db),
):
    """Ventas, costo, utilidad y margen del rango, por categoría y por producto,
    más lo que salió del inventario sin venderse."""
    hasta = hasta or local_today()
    desde = desde or hasta
    if desde > hasta:
        raise HTTPException(status_code=422, detail="«desde» no puede ser posterior a «hasta»")
    inicio, fin = _rango_utc(desde, hasta, hora_corte)
    cats = await _nombres_categorias(db, rid)

    result = await db.execute(
        select(Venta)
        .where(Venta.restaurant_id == rid, Venta.fecha >= inicio, Venta.fecha <= fin)
        .options(selectinload(Venta.items))
    )
    ventas = result.scalars().all()

    por_cat: dict[str, CategoriaVentas] = {}
    por_prod: dict[str, ProductoVendido] = {}
    ventas_con_costo = costo_total = 0.0
    for v in ventas:
        for it in v.items:
            if it.precio_unitario is None:
                continue  # venta anterior a este cambio: solo cuenta en el total
            subtotal = it.precio_unitario * it.cantidad
            costo = (it.costo_unitario or 0) * it.cantidad
            if it.costo_unitario:
                ventas_con_costo += subtotal
                costo_total += costo
            c = por_cat.setdefault(
                it.categoria_id,
                CategoriaVentas(
                    categoria_id=it.categoria_id, categoria=cats.get(it.categoria_id, ""),
                    cantidad=0, ventas=0, costo=0, utilidad=0,
                ),
            )
            pv = por_prod.setdefault(
                it.producto_id,
                ProductoVendido(
                    producto_id=it.producto_id, producto_nombre=it.producto_nombre,
                    cantidad=0, ventas=0, costo=0, utilidad=0,
                ),
            )
            for fila in (c, pv):
                fila.cantidad += it.cantidad
                fila.ventas += subtotal
                fila.costo += costo
                fila.utilidad += subtotal - costo

    result = await db.execute(
        select(
            func.coalesce(func.sum(-StockMovimiento.cantidad), 0),
            func.coalesce(func.sum(-StockMovimiento.cantidad * StockMovimiento.costo_unitario), 0),
        ).where(
            StockMovimiento.restaurant_id == rid,
            StockMovimiento.tipo == "salida",
            StockMovimiento.fecha >= inicio,
            StockMovimiento.fecha <= fin,
        )
    )
    salidas_u, salidas_c = result.one()

    total = sum(v.total for v in ventas)
    utilidad = ventas_con_costo - costo_total
    return ReporteVentasOut(
        desde=desde,
        hasta=hasta,
        tickets=len(ventas),
        total_ventas=total,
        ticket_promedio=total / len(ventas) if ventas else 0,
        ventas_con_costo=ventas_con_costo,
        costo=costo_total,
        utilidad=utilidad,
        margen=utilidad / ventas_con_costo if ventas_con_costo else 0,
        salidas_unidades=float(salidas_u),
        salidas_costo=float(salidas_c),
        por_categoria=sorted(por_cat.values(), key=lambda c: -c.ventas),
        mas_vendidos=sorted(por_prod.values(), key=lambda p: -p.cantidad)[:top],
    )


# ----------------- Importación desde Gecofi -----------------
_UNIDADES = {"c/u": "und", "und": "und", "kg": "kg", "l": "l", "arroba": "arroba"}


def _clave(texto: str) -> str:
    return " ".join(texto.split()).lower()


@router.post("/import/gecofi", response_model=ImportResultOut)
async def importar_gecofi(
    rid: str,
    body: ImportGecofiIn,
    current: User = Depends(require_restaurant_owner),
    db: AsyncSession = Depends(get_db),
):
    """Carga categorías y productos exportados de Gecofi. Se puede repetir sin
    duplicar: la categoría se reconoce por nombre y el producto por código de
    barras (o por nombre si no tiene). El stock inicial entra al kárdex como
    «importacion». Solo el dueño."""
    result = await db.execute(select(Categoria).where(Categoria.restaurant_id == rid))
    cat_por_nombre = {_clave(c.nombre): c for c in result.scalars().all()}
    usadas = {str(p.categoria_id) for p in body.productos}
    cat_id: dict[str, str] = {}
    creadas = 0
    for c in body.categorias:
        if str(c.id) not in usadas:
            continue  # categorías vacías (p. ej. «PRUEBA») no se traen
        nombre = " ".join(c.nombre.split())
        existente = cat_por_nombre.get(_clave(nombre))
        if existente is None:
            existente = Categoria(restaurant_id=rid, nombre=nombre)
            db.add(existente)
            await db.flush()
            cat_por_nombre[_clave(nombre)] = existente
            creadas += 1
        cat_id[str(c.id)] = existente.id

    result = await db.execute(
        select(Producto).where(Producto.restaurant_id == rid).with_for_update()
    )
    actuales = result.scalars().all()
    por_codigo = {p.codigo_barras: p for p in actuales if p.codigo_barras}
    por_nombre = {_clave(p.nombre): p for p in actuales}

    nuevos = actualizados = 0
    unidades = 0.0
    for item in body.productos:
        if str(item.categoria_id) not in cat_id:
            raise HTTPException(
                status_code=422,
                detail=f"«{item.nombre}» apunta a una categoría que no viene en el archivo",
            )
        codigo = normalizar_codigo(item.codigo_barras)
        p = (por_codigo.get(codigo) if codigo else None) or por_nombre.get(_clave(item.nombre))
        stock = item.stock or 0
        datos = dict(
            nombre=" ".join(item.nombre.split()),
            precio=item.precio_venta,
            categoria_id=cat_id[str(item.categoria_id)],
            stock_minimo=item.stock_minimo or 0,
            unidad=_UNIDADES.get((item.unidad or "und").lower(), "und"),
            controla_stock=not item.inventario_infinito,
            visible=not item.oculto,
        )
        if item.precio_compra is not None:
            datos["costo"] = item.precio_compra
        if p is None:
            await asegurar_codigo_libre(db, rid, codigo)
            p = Producto(restaurant_id=rid, codigo_barras=codigo, stock=0.0, **datos)
            db.add(p)
            await db.flush()
            if p.controla_stock and stock:
                mover_stock(db, p, "importacion", stock, nota="Importado de Gecofi",
                            usuario_id=current.id)
                unidades += stock
            nuevos += 1
        else:
            for campo, valor in datos.items():
                setattr(p, campo, valor)
            if codigo and not p.codigo_barras:
                await asegurar_codigo_libre(db, rid, codigo, excepto_id=p.id)
                p.codigo_barras = codigo
            if body.actualizar_stock and p.controla_stock and stock != (p.stock or 0):
                diff = stock - (p.stock or 0)
                mover_stock(db, p, "importacion", diff, nota="Reimportado de Gecofi",
                            usuario_id=current.id)
                unidades += diff
            actualizados += 1
        if p.codigo_barras:
            por_codigo[p.codigo_barras] = p
        por_nombre[_clave(p.nombre)] = p

    await db.commit()
    return ImportResultOut(
        categorias_creadas=creadas,
        productos_creados=nuevos,
        productos_actualizados=actualizados,
        unidades_cargadas=unidades,
    )
