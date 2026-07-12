from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user
from app.models.notification import Notification
from app.models.organization import Membership, User
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notificaciones"])


async def _visible_filter(db: AsyncSession, current: User):
    """Condición de visibilidad: admin ve todo; usuario ve globales + de sus restaurantes."""
    if current.is_admin:
        return None
    result = await db.execute(
        select(Membership.restaurant_id).where(Membership.user_id == current.id)
    )
    rids = [r for (r,) in result.all()]
    return or_(Notification.restaurant_id.is_(None), Notification.restaurant_id.in_(rids))


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    stmt = select(Notification).order_by(Notification.created_at.desc())
    cond = await _visible_filter(db, current)
    if cond is not None:
        stmt = stmt.where(cond)
    result = await db.execute(stmt)
    return [NotificationOut.model_validate(n) for n in result.scalars().all()]


@router.get("/unread-count", response_model=int)
async def unread_count(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    stmt = select(func.count()).select_from(Notification).where(Notification.status == "noLeida")
    cond = await _visible_filter(db, current)
    if cond is not None:
        stmt = stmt.where(cond)
    result = await db.execute(stmt)
    return result.scalar_one()


@router.patch("/{notif_id}/read", status_code=204)
async def mark_as_read(
    notif_id: str, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    n = await db.get(Notification, notif_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    n.status = "leida"
    await db.commit()


@router.post("/read-all", status_code=204)
async def mark_all_as_read(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    stmt = select(Notification).where(Notification.status == "noLeida")
    cond = await _visible_filter(db, current)
    if cond is not None:
        stmt = stmt.where(cond)
    result = await db.execute(stmt)
    for n in result.scalars().all():
        n.status = "leida"
    await db.commit()
