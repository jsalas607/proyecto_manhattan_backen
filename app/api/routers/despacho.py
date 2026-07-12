from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.deps import require_permission, require_restaurant_access
from app.models.orders import PantallaCategoria, PantallaDespacho
from app.models.organization import User
from app.schemas.despacho import PantallaCreate, PantallaOut

router = APIRouter(prefix="/restaurants/{rid}", tags=["despacho"])


def _out(p: PantallaDespacho) -> PantallaOut:
    return PantallaOut(
        id=p.id,
        nombre=p.nombre,
        categoria_ids=[c.categoria_id for c in p.categorias],
        icono_index=p.icono_index,
        color_index=p.color_index,
    )


@router.get("/despacho", response_model=list[PantallaOut])
async def list_pantallas(
    rid: str, _: User = Depends(require_restaurant_access), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PantallaDespacho)
        .where(PantallaDespacho.restaurant_id == rid)
        .options(selectinload(PantallaDespacho.categorias))
    )
    return [_out(p) for p in result.scalars().all()]


@router.post("/despacho", response_model=PantallaOut, status_code=201)
async def add_pantalla(
    rid: str,
    body: PantallaCreate,
    _: User = Depends(require_permission("ver_pedidos_vivo")),
    db: AsyncSession = Depends(get_db),
):
    p = PantallaDespacho(
        restaurant_id=rid,
        nombre=body.nombre,
        icono_index=body.icono_index,
        color_index=body.color_index,
    )
    p.categorias = [PantallaCategoria(categoria_id=cid) for cid in body.categoria_ids]
    db.add(p)
    await db.commit()
    result = await db.execute(
        select(PantallaDespacho)
        .where(PantallaDespacho.id == p.id)
        .options(selectinload(PantallaDespacho.categorias))
    )
    return _out(result.scalar_one())


@router.delete("/despacho/{pantalla_id}", status_code=204)
async def delete_pantalla(
    rid: str,
    pantalla_id: str,
    _: User = Depends(require_permission("ver_pedidos_vivo")),
    db: AsyncSession = Depends(get_db),
):
    p = await db.get(PantallaDespacho, pantalla_id)
    if p is None or p.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Pantalla no encontrada")
    await db.delete(p)
    await db.commit()
