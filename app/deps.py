from fastapi import Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.organization import Membership, Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


async def require_admin(current: User = Depends(get_current_user)) -> User:
    if not current.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere admin global")
    return current


async def _get_membership(db: AsyncSession, user_id: str, restaurant_id: str) -> Membership | None:
    result = await db.execute(
        select(Membership)
        .where(Membership.user_id == user_id, Membership.restaurant_id == restaurant_id)
        .options(selectinload(Membership.role).selectinload(Role.permissions))
    )
    return result.scalar_one_or_none()


async def require_restaurant_access(
    rid: str = Path(...),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Valida que el usuario sea admin global o tenga membership en el restaurante de la ruta."""
    if current.is_admin:
        return current
    membership = await _get_membership(db, current.id, rid)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a este restaurante")
    return current


def require_permission(permiso: str):
    """Factory de dependencia: exige un permiso concreto en el restaurante de la ruta (admin omite)."""

    async def checker(
        rid: str = Path(...),
        current: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current.is_admin:
            return current
        membership = await _get_membership(db, current.id, rid)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a este restaurante"
            )
        permisos = {p.permiso for p in membership.role.permissions} if membership.role else set()
        if permiso not in permisos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Falta el permiso: {permiso}"
            )
        return current

    return checker
