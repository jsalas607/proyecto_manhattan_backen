from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.deps import (
    get_current_user,
    require_admin,
    require_permission,
    require_restaurant_access,
    require_restaurant_owner,
)
from app.models.organization import (
    Membership,
    Restaurant,
    RestaurantPaymentMethod,
    RestaurantStatus,
    User,
)
from app.schemas.restaurant import (
    RestaurantCreate,
    RestaurantOut,
    RestaurantUpdate,
    StatusOut,
    StatusUpdate,
)

router = APIRouter(tags=["restaurantes"])


def _to_out(r: Restaurant) -> RestaurantOut:
    return RestaurantOut(
        id=r.id,
        title=r.title,
        name=r.name,
        description=r.description,
        country=r.country,
        city=r.city,
        address=r.address,
        payment_methods=[pm.name for pm in r.payment_methods],
        is_active=r.is_active,
    )


async def _get_full(db: AsyncSession, rid: str) -> Restaurant:
    result = await db.execute(
        select(Restaurant)
        .where(Restaurant.id == rid)
        .options(selectinload(Restaurant.payment_methods))
    )
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurante no encontrado")
    return r


@router.get("/restaurants", response_model=list[RestaurantOut])
async def list_restaurants(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    stmt = select(Restaurant).options(selectinload(Restaurant.payment_methods))
    if current.is_superadmin:
        pass  # la plataforma ve todos
    elif current.is_admin:
        stmt = stmt.where(Restaurant.owner_id == current.id)  # dueño: solo los suyos
    else:
        sub = select(Membership.restaurant_id).where(Membership.user_id == current.id)
        stmt = stmt.where(Restaurant.id.in_(sub))  # empleado: donde tiene membresía
    result = await db.execute(stmt)
    return [_to_out(r) for r in result.scalars().all()]


@router.post("/restaurants", response_model=RestaurantOut, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    body: RestaurantCreate,
    current: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    r = Restaurant(
        owner_id=current.id,  # el que lo crea es su dueño
        title=body.title,
        name=body.name,
        description=body.description,
        country=body.country,
        city=body.city,
        address=body.address,
        is_active=body.is_active,
    )
    r.payment_methods = [RestaurantPaymentMethod(name=n) for n in body.payment_methods]
    db.add(r)
    db.add(RestaurantStatus(restaurant=r, status="cerrado"))
    await db.commit()
    await db.refresh(r)
    return await _to_out_refreshed(db, r.id)


async def _to_out_refreshed(db: AsyncSession, rid: str) -> RestaurantOut:
    return _to_out(await _get_full(db, rid))


@router.get("/restaurants/{rid}", response_model=RestaurantOut)
async def get_restaurant(
    rid: str,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    return _to_out(await _get_full(db, rid))


@router.put("/restaurants/{rid}", response_model=RestaurantOut)
async def update_restaurant(
    rid: str,
    body: RestaurantUpdate,
    _: User = Depends(require_permission("administrar_restaurante")),
    db: AsyncSession = Depends(get_db),
):
    r = await _get_full(db, rid)
    r.title = body.title
    r.name = body.name
    r.description = body.description
    r.country = body.country
    r.city = body.city
    r.address = body.address
    r.is_active = body.is_active
    # reemplaza métodos de pago
    for pm in list(r.payment_methods):
        await db.delete(pm)
    r.payment_methods = [RestaurantPaymentMethod(restaurant_id=rid, name=n) for n in body.payment_methods]
    await db.commit()
    return await _to_out_refreshed(db, rid)


@router.post("/restaurants/{rid}/duplicate", response_model=RestaurantOut, status_code=201)
async def duplicate_restaurant(
    rid: str, current: User = Depends(require_restaurant_owner), db: AsyncSession = Depends(get_db)
):
    src = await _get_full(db, rid)
    copy = Restaurant(
        owner_id=src.owner_id or current.id,  # la copia mantiene al dueño
        title=f"{src.title} (copia)",
        name=src.name,
        description=src.description,
        country=src.country,
        city=src.city,
        address=src.address,
        is_active=src.is_active,
    )
    copy.payment_methods = [RestaurantPaymentMethod(name=pm.name) for pm in src.payment_methods]
    db.add(copy)
    db.add(RestaurantStatus(restaurant=copy, status="cerrado"))
    await db.commit()
    await db.refresh(copy)
    return await _to_out_refreshed(db, copy.id)


@router.delete("/restaurants/{rid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_restaurant(
    rid: str, _: User = Depends(require_restaurant_owner), db: AsyncSession = Depends(get_db)
):
    r = await db.get(Restaurant, rid)
    if r is None:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")
    await db.delete(r)
    await db.commit()


# --- Estado de la sucursal ---
@router.get("/restaurants/{rid}/status", response_model=StatusOut)
async def get_status(
    rid: str,
    _: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    st = await db.get(RestaurantStatus, rid)
    if st is None:
        st = RestaurantStatus(restaurant_id=rid, status="cerrado")
        db.add(st)
        await db.commit()
    return StatusOut(restaurant_id=rid, status=st.status)


@router.put("/restaurants/{rid}/status", response_model=StatusOut)
async def update_status(
    rid: str,
    body: StatusUpdate,
    _: User = Depends(require_permission("administrar_restaurante")),
    db: AsyncSession = Depends(get_db),
):
    if body.status not in ("abierto", "cerrado"):
        raise HTTPException(status_code=400, detail="status debe ser 'abierto' o 'cerrado'")
    st = await db.get(RestaurantStatus, rid)
    if st is None:
        st = RestaurantStatus(restaurant_id=rid, status=body.status)
        db.add(st)
    else:
        st.status = body.status
    await db.commit()
    return StatusOut(restaurant_id=rid, status=body.status)
