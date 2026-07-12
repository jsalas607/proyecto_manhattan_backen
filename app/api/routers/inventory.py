from datetime import date as date_type
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.timeutil import local_today
from app.deps import require_permission, require_restaurant_access
from app.models.inventory import (
    DailyInventory,
    InventoryDayClosed,
    InventoryItem,
    InventoryMovement,
)
from app.models.organization import User
from app.schemas.inventory import (
    DayInventoryOut,
    EntryOut,
    ItemCreate,
    ItemOut,
    MovimientoIn,
    RecordOut,
    UpdateRealIn,
)

router = APIRouter(prefix="/restaurants/{rid}", tags=["inventario"])


async def _prev_real(db: AsyncSession, rid: str, item_id: str, fecha: date_type) -> float:
    """invReal del día anterior (para arrastrar a invApp). 0 si no hay."""
    prev = fecha - timedelta(days=1)
    result = await db.execute(
        select(DailyInventory).where(
            DailyInventory.restaurant_id == rid,
            DailyInventory.item_id == item_id,
            DailyInventory.fecha == prev,
        )
    )
    e = result.scalar_one_or_none()
    if e and e.inv_real is not None:
        return e.inv_real
    return 0.0


async def _ensure_entry(
    db: AsyncSession, rid: str, item_id: str, fecha: date_type
) -> DailyInventory:
    result = await db.execute(
        select(DailyInventory).where(
            DailyInventory.restaurant_id == rid,
            DailyInventory.item_id == item_id,
            DailyInventory.fecha == fecha,
        )
    )
    e = result.scalar_one_or_none()
    if e is None:
        inv_app = await _prev_real(db, rid, item_id, fecha)
        e = DailyInventory(restaurant_id=rid, item_id=item_id, fecha=fecha, inv_app=inv_app)
        db.add(e)
        await db.flush()
    return e


async def _is_closed(db: AsyncSession, rid: str, fecha: date_type) -> bool:
    result = await db.execute(
        select(InventoryDayClosed).where(
            InventoryDayClosed.restaurant_id == rid, InventoryDayClosed.fecha == fecha
        )
    )
    return result.scalar_one_or_none() is not None


def _entry_out(e: DailyInventory) -> EntryOut:
    counted = e.inv_real is not None
    diff = (e.inv_real - e.inv_app) if counted else 0.0
    return EntryOut(
        item_id=e.item_id,
        inv_app=e.inv_app,
        inv_real=e.inv_real,
        is_counted=counted,
        diff=diff,
        has_diff=counted and diff != 0,
    )


@router.get("/inventory/dates", response_model=list[date_type])
async def available_dates(
    rid: str, _: User = Depends(require_permission("ver_inventario")), db: AsyncSession = Depends(get_db)
):
    hoy = local_today()
    return [hoy - timedelta(days=i) for i in range(7)]


@router.get("/inventory", response_model=DayInventoryOut)
async def get_by_date(
    rid: str,
    date: date_type | None = Query(default=None),
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    fecha = date or local_today()
    result = await db.execute(select(InventoryItem).where(InventoryItem.restaurant_id == rid))
    items = result.scalars().all()

    records: list[RecordOut] = []
    for it in items:
        e = await _ensure_entry(db, rid, it.id, fecha)
        records.append(
            RecordOut(
                item=ItemOut(id=it.id, name=it.name, unidad=it.unidad),
                entry=_entry_out(e),
            )
        )
    await db.commit()
    return DayInventoryOut(date=fecha, closed=await _is_closed(db, rid, fecha), records=records)


@router.post("/inventory/items", response_model=ItemOut, status_code=201)
async def add_item(
    rid: str,
    body: ItemCreate,
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    it = InventoryItem(restaurant_id=rid, name=body.name, unidad=body.unidad)
    db.add(it)
    await db.flush()
    await _ensure_entry(db, rid, it.id, local_today())
    await db.commit()
    await db.refresh(it)
    return ItemOut(id=it.id, name=it.name, unidad=it.unidad)


@router.delete("/inventory/{item_id}", status_code=204)
async def delete_item(
    rid: str,
    item_id: str,
    _: User = Depends(require_permission("eliminar_inventario")),
    db: AsyncSession = Depends(get_db),
):
    """Elimina un ingrediente del inventario. El FK ON DELETE CASCADE borra
    también sus conteos diarios y movimientos. No afecta el menú."""
    it = await db.get(InventoryItem, item_id)
    if it is None or it.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    await db.delete(it)
    await db.commit()


@router.put("/inventory/{item_id}/real", response_model=EntryOut)
async def update_real(
    rid: str,
    item_id: str,
    body: UpdateRealIn,
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    e = await _ensure_entry(db, rid, item_id, body.date)
    e.inv_real = body.inv_real
    # propaga al día siguiente: su invApp = este invReal
    siguiente = await _ensure_entry(db, rid, item_id, body.date + timedelta(days=1))
    siguiente.inv_app = body.inv_real
    await db.commit()
    return _entry_out(e)


async def _add_movimiento(
    db: AsyncSession, rid: str, body: MovimientoIn, tipo: str
) -> EntryOut:
    e = await _ensure_entry(db, rid, body.item_id, body.date)
    e.inv_app += body.cantidad
    if e.inv_real is not None:
        e.inv_real += body.cantidad
    db.add(
        InventoryMovement(
            restaurant_id=rid, item_id=body.item_id, fecha=body.date, cantidad=body.cantidad, tipo=tipo
        )
    )
    await db.commit()
    return _entry_out(e)


@router.post("/inventory/compra", response_model=EntryOut)
async def add_compra(
    rid: str,
    body: MovimientoIn,
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    return await _add_movimiento(db, rid, body, "compra")


@router.post("/inventory/merma", response_model=EntryOut)
async def registrar_merma(
    rid: str,
    body: MovimientoIn,
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    # merma = compra negativa (igual que el mock)
    body.cantidad = -abs(body.cantidad)
    return await _add_movimiento(db, rid, body, "merma")


@router.post("/inventory/close", status_code=204)
async def close_day(
    rid: str,
    date: date_type | None = Query(default=None),
    _: User = Depends(require_permission("ver_inventario")),
    db: AsyncSession = Depends(get_db),
):
    fecha = date or local_today()
    if not await _is_closed(db, rid, fecha):
        db.add(InventoryDayClosed(restaurant_id=rid, fecha=fecha))
        await db.commit()
