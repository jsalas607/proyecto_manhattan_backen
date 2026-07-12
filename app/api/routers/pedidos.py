from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.deps import require_permission, require_restaurant_access
from app.models.orders import Mesa, Pedido, PedidoItem
from app.models.organization import User
from app.schemas.pedido import (
    ItemPedidoOut,
    PedidoOut,
    PedidoUpsert,
    SetListoIn,
)
from app.ws.manager import manager

router = APIRouter(prefix="/restaurants/{rid}", tags=["pedidos"])


def _pedido_out(p: Pedido) -> PedidoOut:
    return PedidoOut(
        id=p.mesa_id,
        mesa_id=p.mesa_id,
        mesa_numero=p.mesa_numero,
        orden=p.orden,
        items=[
            ItemPedidoOut(
                producto_id=it.producto_id,
                producto_nombre=it.producto_nombre,
                categoria_id=it.categoria_id,
                cantidad=it.cantidad,
                config=it.config,
                listo=it.listo,
            )
            for it in p.items
        ],
    )


async def _get_by_mesa(db: AsyncSession, rid: str, mesa_id: str) -> Pedido | None:
    result = await db.execute(
        select(Pedido)
        .where(Pedido.restaurant_id == rid, Pedido.mesa_id == mesa_id)
        .options(selectinload(Pedido.items))
    )
    return result.scalar_one_or_none()


async def _broadcast(rid: str, evento: str, data: dict) -> None:
    await manager.broadcast(rid, "pedidos", {"event": evento, **data})
    await manager.broadcast(rid, "despacho", {"event": evento, **data})


@router.get("/pedidos", response_model=list[PedidoOut])
async def list_pedidos(
    rid: str,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Pedido)
        .where(Pedido.restaurant_id == rid)
        .options(selectinload(Pedido.items))
        .order_by(Pedido.orden)
    )
    return [_pedido_out(p) for p in result.scalars().all()]


@router.get("/pedidos/mesas-atendidas", response_model=list[str])
async def mesas_atendidas(
    rid: str,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    """Ids de mesa cuyos items están TODOS marcados como listos."""
    result = await db.execute(
        select(Pedido).where(Pedido.restaurant_id == rid).options(selectinload(Pedido.items))
    )
    out = []
    for p in result.scalars().all():
        if p.items and all(it.listo for it in p.items):
            out.append(p.mesa_id)
    return out


@router.get("/pedidos/{mesa_id}", response_model=PedidoOut | None)
async def get_pedido(
    rid: str,
    mesa_id: str,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    p = await _get_by_mesa(db, rid, mesa_id)
    return _pedido_out(p) if p else None


@router.put("/pedidos/{mesa_id}", response_model=PedidoOut | None)
async def upsert_pedido(
    rid: str,
    mesa_id: str,
    body: PedidoUpsert,
    _: User = Depends(require_permission("crear_pedidos")),
    db: AsyncSession = Depends(get_db),
):
    mesa = await db.get(Mesa, mesa_id)
    if mesa is None or mesa.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")

    p = await _get_by_mesa(db, rid, mesa_id)

    # items vacíos => elimina el pedido (igual que el mock)
    if not body.items:
        if p is not None:
            await db.delete(p)
            await db.commit()
            await _broadcast(rid, "pedido_eliminado", {"mesaId": mesa_id})
        return None

    prev: dict[tuple[str, str], bool] = {}
    if p is None:
        p = Pedido(restaurant_id=rid, mesa_id=mesa_id, mesa_numero=body.mesa_numero, orden=body.orden)
        db.add(p)
    else:
        p.mesa_numero = body.mesa_numero
        p.orden = body.orden
        # conserva el flag "listo" por (productoId+config) al reemplazar
        prev = {(it.producto_id, it.config): it.listo for it in p.items}
        for it in list(p.items):
            await db.delete(it)
        p.items = []

    for i, it in enumerate(body.items):
        p.items.append(
            PedidoItem(
                posicion=i,
                producto_id=it.producto_id,
                producto_nombre=it.producto_nombre,
                categoria_id=it.categoria_id,
                cantidad=it.cantidad,
                config=it.config,
                listo=prev.get((it.producto_id, it.config), False),
            )
        )
    await db.commit()
    full = await _get_by_mesa(db, rid, mesa_id)
    out = _pedido_out(full)
    await _broadcast(rid, "pedido_actualizado", {"mesaId": mesa_id})
    return out


@router.delete("/pedidos/{mesa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pedido(
    rid: str,
    mesa_id: str,
    _: User = Depends(require_permission("cerrar_pedidos")),
    db: AsyncSession = Depends(get_db),
):
    p = await _get_by_mesa(db, rid, mesa_id)
    if p is not None:
        await db.delete(p)
        await db.commit()
        await _broadcast(rid, "pedido_eliminado", {"mesaId": mesa_id})


@router.patch("/pedidos/{mesa_id}/items/{idx}/listo", response_model=PedidoOut)
async def set_listo(
    rid: str,
    mesa_id: str,
    idx: int,
    body: SetListoIn,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    p = await _get_by_mesa(db, rid, mesa_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    items = sorted(p.items, key=lambda x: x.posicion)
    if idx < 0 or idx >= len(items):
        raise HTTPException(status_code=400, detail="Índice de item fuera de rango")
    items[idx].listo = body.listo
    await db.commit()
    full = await _get_by_mesa(db, rid, mesa_id)
    out = _pedido_out(full)
    await _broadcast(rid, "item_listo", {"mesaId": mesa_id, "index": idx, "listo": body.listo})
    return out
