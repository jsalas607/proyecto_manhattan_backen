from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.timeutil import day_bounds_utc, local_today
from app.deps import require_permission, require_restaurant_access
from app.models.cartera import (
    Caja,
    CajaMontoInicial,
    Gasto,
    GastoProducto,
    Perdida,
    PerdidaProducto,
    ServicioCategoria,
)
from app.models.common import utcnow
from app.models.organization import User
from app.models.sales import Venta, VentaPago
from app.schemas.cartera import (
    AbrirCajaIn,
    CajaStateOut,
    DailyStatsOut,
    GastoCreate,
    GastoOut,
    GastoProductoOut,
    PaymentMethodTotalOut,
    PerdidaCreate,
    PerdidaOut,
    PerdidaProductoOut,
    ServicioCreate,
)

router = APIRouter(prefix="/restaurants/{rid}", tags=["cartera"])


def _hoy_rango():
    return day_bounds_utc(local_today())


async def _get_caja(db: AsyncSession, rid: str) -> Caja:
    stmt = (
        select(Caja).where(Caja.restaurant_id == rid).options(selectinload(Caja.montos_iniciales))
    )
    caja = (await db.execute(stmt)).scalar_one_or_none()
    if caja is None:
        caja = Caja(restaurant_id=rid, status="cerrada")
        db.add(caja)
        await db.commit()
        caja = (await db.execute(stmt)).scalar_one()
    return caja


def _caja_out(caja: Caja) -> CajaStateOut:
    montos = {m.metodo: m.monto for m in caja.montos_iniciales}
    return CajaStateOut(
        status=caja.status,
        abierta_en=caja.abierta_en,
        montos_iniciales=montos,
        monto_total=sum(montos.values()),
    )


@router.get("/caja", response_model=CajaStateOut)
async def get_caja(
    rid: str, _: User = Depends(require_permission("ver_cartera")), db: AsyncSession = Depends(get_db)
):
    return _caja_out(await _get_caja(db, rid))


@router.post("/caja/abrir", response_model=CajaStateOut)
async def abrir_caja(
    rid: str,
    body: AbrirCajaIn,
    _: User = Depends(require_permission("ver_cartera")),
    db: AsyncSession = Depends(get_db),
):
    caja = await _get_caja(db, rid)
    caja.status = "abierta"
    caja.abierta_en = utcnow()
    for m in list(caja.montos_iniciales):
        await db.delete(m)
    caja.montos_iniciales = [
        CajaMontoInicial(metodo=k, monto=v) for k, v in body.montos_iniciales.items()
    ]
    await db.commit()
    return _caja_out(await _get_caja(db, rid))


@router.post("/caja/cerrar", response_model=CajaStateOut)
async def cerrar_caja(
    rid: str,
    _: User = Depends(require_permission("ver_cartera")),
    db: AsyncSession = Depends(get_db),
):
    caja = await _get_caja(db, rid)
    caja.status = "cerrada"
    caja.abierta_en = None
    for m in list(caja.montos_iniciales):
        await db.delete(m)
    await db.commit()
    return _caja_out(await _get_caja(db, rid))


@router.get("/caja/totales", response_model=list[PaymentMethodTotalOut])
async def totales_por_metodo(
    rid: str,
    metodos: str = Query(default="", description="lista de métodos separados por coma"),
    _: User = Depends(require_permission("ver_cartera")),
    db: AsyncSession = Depends(get_db),
):
    lista = [m.strip() for m in metodos.split(",") if m.strip()]
    caja = await _get_caja(db, rid)
    if caja.status == "cerrada":
        return [PaymentMethodTotalOut(name=m, total=0.0) for m in lista]

    montos = {m.metodo: m.monto for m in caja.montos_iniciales}
    inicio, fin = _hoy_rango()
    result = await db.execute(
        select(VentaPago.metodo, VentaPago.monto)
        .join(Venta, Venta.id == VentaPago.venta_id)
        .where(Venta.restaurant_id == rid, Venta.fecha >= inicio, Venta.fecha <= fin)
    )
    ventas_por_metodo: dict[str, float] = {}
    for metodo, monto in result.all():
        ventas_por_metodo[metodo] = ventas_por_metodo.get(metodo, 0.0) + monto

    return [
        PaymentMethodTotalOut(name=m, total=montos.get(m, 0.0) + ventas_por_metodo.get(m, 0.0))
        for m in lista
    ]


@router.get("/stats", response_model=DailyStatsOut)
async def get_stats(
    rid: str,
    _: User = Depends(require_permission("ver_cartera")),
    db: AsyncSession = Depends(get_db),
):
    inicio, fin = _hoy_rango()
    ventas = (
        await db.execute(
            select(Venta).where(Venta.restaurant_id == rid, Venta.fecha >= inicio, Venta.fecha <= fin)
        )
    ).scalars().all()
    ordenes = len(ventas)
    facturado = sum(v.total for v in ventas)

    gastos = (
        await db.execute(
            select(Gasto).where(Gasto.restaurant_id == rid, Gasto.fecha >= inicio, Gasto.fecha <= fin)
        )
    ).scalars().all()
    gastos_dia = sum(g.monto for g in gastos)

    perdidas = (
        await db.execute(
            select(Perdida)
            .where(Perdida.restaurant_id == rid, Perdida.fecha >= inicio, Perdida.fecha <= fin)
            .options(selectinload(Perdida.productos))
        )
    ).scalars().all()
    perdidas_dia = sum(sum(p.cantidad for p in per.productos) for per in perdidas)

    return DailyStatsOut(
        ordenes_creadias=ordenes,
        dinero_facturado=facturado,
        promedio_orden=(facturado / ordenes) if ordenes else 0.0,
        gastos_dia=gastos_dia,
        perdidas_dia=perdidas_dia,
    )


# --- Gastos ---
def _gasto_out(g: Gasto) -> GastoOut:
    return GastoOut(
        id=g.id,
        descripcion=g.descripcion,
        monto=g.monto,
        fecha=g.fecha,
        metodo_pago=g.metodo_pago,
        productos=[
            GastoProductoOut(name=p.name, unidad=p.unidad, cantidad=p.cantidad) for p in g.productos
        ],
    )


@router.get("/gastos", response_model=list[GastoOut])
async def list_gastos(
    rid: str, _: User = Depends(require_permission("ver_cartera")), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Gasto)
        .where(Gasto.restaurant_id == rid)
        .options(selectinload(Gasto.productos))
        .order_by(Gasto.fecha.desc())
    )
    return [_gasto_out(g) for g in result.scalars().all()]


@router.post("/gastos", response_model=GastoOut, status_code=201)
async def add_gasto(
    rid: str,
    body: GastoCreate,
    _: User = Depends(require_permission("ver_cartera")),
    db: AsyncSession = Depends(get_db),
):
    g = Gasto(
        restaurant_id=rid, descripcion=body.descripcion, monto=body.monto, metodo_pago=body.metodo_pago
    )
    g.productos = [
        GastoProducto(name=p.name, unidad=p.unidad, cantidad=p.cantidad) for p in body.productos
    ]
    db.add(g)
    await db.commit()
    result = await db.execute(
        select(Gasto).where(Gasto.id == g.id).options(selectinload(Gasto.productos))
    )
    return _gasto_out(result.scalar_one())


# --- Pérdidas ---
def _perdida_out(p: Perdida) -> PerdidaOut:
    return PerdidaOut(
        id=p.id,
        titulo=p.titulo,
        descripcion=p.descripcion,
        categoria=p.categoria,
        fecha=p.fecha,
        productos=[
            PerdidaProductoOut(name=x.name, cantidad=x.cantidad, unidad=x.unidad, item_id=x.item_id)
            for x in p.productos
        ],
        monto=sum(x.cantidad for x in p.productos),
    )


@router.get("/perdidas", response_model=list[PerdidaOut])
async def list_perdidas(
    rid: str, _: User = Depends(require_permission("ver_cartera")), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Perdida)
        .where(Perdida.restaurant_id == rid)
        .options(selectinload(Perdida.productos))
        .order_by(Perdida.fecha.desc())
    )
    return [_perdida_out(p) for p in result.scalars().all()]


@router.post("/perdidas", response_model=PerdidaOut, status_code=201)
async def add_perdida(
    rid: str,
    body: PerdidaCreate,
    _: User = Depends(require_permission("ver_cartera")),
    db: AsyncSession = Depends(get_db),
):
    p = Perdida(
        restaurant_id=rid, titulo=body.titulo, descripcion=body.descripcion, categoria=body.categoria
    )
    p.productos = [
        PerdidaProducto(name=x.name, cantidad=x.cantidad, unidad=x.unidad, item_id=x.item_id)
        for x in body.productos
    ]
    db.add(p)
    await db.commit()
    result = await db.execute(
        select(Perdida).where(Perdida.id == p.id).options(selectinload(Perdida.productos))
    )
    return _perdida_out(result.scalar_one())


# --- Servicios (categorías personalizadas) ---
@router.get("/servicios", response_model=list[str])
async def list_servicios(
    rid: str, _: User = Depends(require_restaurant_access), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ServicioCategoria).where(ServicioCategoria.restaurant_id == rid)
    )
    return [s.nombre for s in result.scalars().all()]


@router.post("/servicios", response_model=list[str], status_code=201)
async def add_servicio(
    rid: str,
    body: ServicioCreate,
    _: User = Depends(require_permission("ver_cartera")),
    db: AsyncSession = Depends(get_db),
):
    nombre = body.nombre.strip()
    if nombre:
        result = await db.execute(
            select(ServicioCategoria).where(ServicioCategoria.restaurant_id == rid)
        )
        existentes = {s.nombre.lower() for s in result.scalars().all()}
        if nombre.lower() not in existentes:
            db.add(ServicioCategoria(restaurant_id=rid, nombre=nombre))
            await db.commit()
    result = await db.execute(
        select(ServicioCategoria).where(ServicioCategoria.restaurant_id == rid)
    )
    return [s.nombre for s in result.scalars().all()]
