from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.timeutil import day_bounds_utc, local_today
from app.deps import require_permission, require_restaurant_access
from app.models.organization import User
from app.models.sales import Venta, VentaItem, VentaPago
from app.schemas.venta import (
    PagoMetodoOut,
    VentaCreate,
    VentaItemOut,
    VentaOut,
)

router = APIRouter(prefix="/restaurants/{rid}", tags=["ventas"])


def _out(v: Venta) -> VentaOut:
    return VentaOut(
        id=v.id,
        mesa_numero=v.mesa_numero,
        orden=v.orden,
        nombre_cliente=v.nombre_cliente,
        total=v.total,
        fecha=v.fecha,
        items=[
            VentaItemOut(
                producto_id=i.producto_id,
                producto_nombre=i.producto_nombre,
                categoria_id=i.categoria_id,
                cantidad=i.cantidad,
                config=i.config,
            )
            for i in v.items
        ],
        pagos=[PagoMetodoOut(metodo=pg.metodo, monto=pg.monto) for pg in v.pagos],
    )


async def _get_full(db: AsyncSession, vid: str) -> Venta:
    result = await db.execute(
        select(Venta)
        .where(Venta.id == vid)
        .options(selectinload(Venta.items), selectinload(Venta.pagos))
    )
    return result.scalar_one()


@router.post("/ventas", response_model=VentaOut, status_code=201)
async def registrar_venta(
    rid: str,
    body: VentaCreate,
    _: User = Depends(require_permission("cobrar_mesa")),
    db: AsyncSession = Depends(get_db),
):
    v = Venta(
        restaurant_id=rid,
        mesa_numero=body.mesa_numero,
        orden=body.orden,
        nombre_cliente=body.nombre_cliente,
        total=body.total,
    )
    v.items = [
        VentaItem(
            producto_id=i.producto_id,
            producto_nombre=i.producto_nombre,
            categoria_id=i.categoria_id,
            cantidad=i.cantidad,
            config=i.config,
        )
        for i in body.items
    ]
    v.pagos = [VentaPago(metodo=pg.metodo, monto=pg.monto) for pg in body.pagos]
    db.add(v)
    await db.commit()
    return _out(await _get_full(db, v.id))


@router.get("/ventas", response_model=list[VentaOut])
async def list_ventas(
    rid: str,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Venta)
        .where(Venta.restaurant_id == rid)
        .options(selectinload(Venta.items), selectinload(Venta.pagos))
        .order_by(Venta.fecha.desc())
    )
    return [_out(v) for v in result.scalars().all()]


@router.get("/ventas/dia", response_model=list[VentaOut])
async def list_ventas_dia(
    rid: str,
    date: date_type | None = Query(default=None),
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    dia = date or local_today()
    inicio, fin = day_bounds_utc(dia)
    result = await db.execute(
        select(Venta)
        .where(Venta.restaurant_id == rid, Venta.fecha >= inicio, Venta.fecha <= fin)
        .options(selectinload(Venta.items), selectinload(Venta.pagos))
        .order_by(Venta.fecha.desc())
    )
    return [_out(v) for v in result.scalars().all()]
