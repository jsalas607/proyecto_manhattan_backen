from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import require_permission, require_restaurant_access
from app.models.orders import Mesa
from app.models.organization import User
from app.schemas.mesa import MesaCreate, MesaOut

router = APIRouter(prefix="/restaurants/{rid}", tags=["mesas"])


@router.get("/mesas", response_model=list[MesaOut])
async def list_mesas(
    rid: str, _: User = Depends(require_restaurant_access), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Mesa).where(Mesa.restaurant_id == rid).order_by(Mesa.orden)
    )
    return [MesaOut.model_validate(m) for m in result.scalars().all()]


@router.post("/mesas", response_model=MesaOut, status_code=201)
async def add_mesa(
    rid: str,
    body: MesaCreate,
    _: User = Depends(require_permission("crear_mesa")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.coalesce(func.max(Mesa.orden), 0)).where(Mesa.restaurant_id == rid)
    )
    next_orden = result.scalar_one() + 1
    m = Mesa(
        restaurant_id=rid, orden=next_orden, numero=body.numero, nombre=body.nombre, atendida=False
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return MesaOut.model_validate(m)


@router.patch("/mesas/{mesa_id}/atendida", response_model=MesaOut)
async def toggle_atendida(
    rid: str,
    mesa_id: str,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    m = await db.get(Mesa, mesa_id)
    if m is None or m.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    m.atendida = not m.atendida
    await db.commit()
    await db.refresh(m)
    return MesaOut.model_validate(m)


@router.delete("/mesas/{mesa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_mesa(
    rid: str,
    mesa_id: str,
    _: User = Depends(require_permission("cerrar_mesa")),
    db: AsyncSession = Depends(get_db),
):
    m = await db.get(Mesa, mesa_id)
    if m is None or m.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    await db.delete(m)
    await db.commit()
