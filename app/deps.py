from fastapi import Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.organization import Membership, Restaurant, Role, User

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
    if not user.is_active:
        # Invalida los tokens ya emitidos: si no, un desactivado seguiría
        # entrando hasta que expire su sesión.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Cuenta desactivada"
        )
    return user


async def require_admin(current: User = Depends(get_current_user)) -> User:
    """Dueño o superadmin (los que pueden tener/crear restaurantes)."""
    if not current.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere admin")
    return current


async def require_superadmin(current: User = Depends(get_current_user)) -> User:
    """Solo la plataforma (crea dueños, ve todo)."""
    if not current.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere superadmin")
    return current


async def _get_membership(db: AsyncSession, user_id: str, restaurant_id: str) -> Membership | None:
    result = await db.execute(
        select(Membership)
        .where(Membership.user_id == user_id, Membership.restaurant_id == restaurant_id)
        .options(selectinload(Membership.role).selectinload(Role.permissions))
    )
    return result.scalar_one_or_none()


async def _es_dueno(db: AsyncSession, user_id: str, restaurant_id: str) -> bool:
    """True si `user_id` es el dueño del restaurante `restaurant_id`."""
    owner_id = await db.scalar(
        select(Restaurant.owner_id).where(Restaurant.id == restaurant_id)
    )
    return owner_id is not None and owner_id == user_id


async def es_dueno_o_super(db: AsyncSession, current: User, restaurant_id: str) -> bool:
    """True si `current` manda sobre TODO el restaurante: superadmin o su dueño.
    Los routers lo usan para decidir qué puede ver/tocar un gerente vs el dueño."""
    if current.is_superadmin:
        return True
    return await _es_dueno(db, current.id, restaurant_id)


async def _owner_activo(db: AsyncSession, restaurant_id: str) -> bool:
    """True si el restaurante no tiene dueño o su dueño sigue activo.
    Si el dueño se desactivó (dejó de pagar) se congela todo el inquilino:
    sus empleados tampoco pueden entrar."""
    owner_id = await db.scalar(
        select(Restaurant.owner_id).where(Restaurant.id == restaurant_id)
    )
    if owner_id is None:
        return True
    activo = await db.scalar(select(User.is_active).where(User.id == owner_id))
    return bool(activo)


async def _asegurar_inquilino_activo(
    db: AsyncSession, current: User, restaurant_id: str
) -> None:
    if current.is_superadmin:
        return
    if not await _owner_activo(db, restaurant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta está desactivada. Contacta al administrador.",
        )


async def require_restaurant_access(
    rid: str = Path(...),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Superadmin, o dueño del restaurante, o miembro del mismo."""
    if current.is_superadmin:
        return current
    await _asegurar_inquilino_activo(db, current, rid)
    if await _es_dueno(db, current.id, rid):
        return current
    membership = await _get_membership(db, current.id, rid)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a este restaurante")
    return current


async def require_restaurant_owner(
    rid: str = Path(...),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Solo el dueño del restaurante (o superadmin). Para acciones destructivas."""
    if current.is_superadmin:
        return current
    if await _es_dueno(db, current.id, rid):
        return current
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres el dueño de este restaurante")


def require_permission(permiso: str):
    """Factory: exige un permiso concreto en el restaurante de la ruta.
    Superadmin y el dueño del restaurante omiten el chequeo (tienen todo)."""

    async def checker(
        rid: str = Path(...),
        current: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current.is_superadmin:
            return current
        await _asegurar_inquilino_activo(db, current, rid)
        if await _es_dueno(db, current.id, rid):
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
