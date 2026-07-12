from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user
from app.models.organization import User
from app.schemas.profile import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["perfil"])


def _out(u: User) -> ProfileOut:
    return ProfileOut(
        id=u.id,
        username=u.username,
        title=u.title,
        name=u.name,
        lastname=u.lastname,
        description=u.description,
        role="Administrador" if u.is_admin else "",
    )


@router.get("", response_model=ProfileOut)
async def get_profile(current: User = Depends(get_current_user)):
    return _out(current)


@router.put("", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current.title = body.title
    current.name = body.name
    current.lastname = body.lastname
    current.description = body.description
    db.add(current)
    await db.commit()
    await db.refresh(current)
    return _out(current)
