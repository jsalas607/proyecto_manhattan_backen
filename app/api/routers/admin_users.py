from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.deps import require_admin, require_superadmin
from app.models.organization import Membership, Restaurant, User
from app.schemas.base import CamelModel

router = APIRouter(prefix="/admin/users", tags=["admin-usuarios"])


class PasswordIn(CamelModel):
    password: str


class CrearUsuarioIn(CamelModel):
    username: str
    password: str
    nombre: str = ""
    is_admin: bool = False  # True → dueño de restaurantes


class UsuarioCreadoOut(CamelModel):
    id: str
    username: str
    is_admin: bool
    nombre: str


async def _es_empleado_de(db: AsyncSession, owner_id: str, target_id: str) -> bool:
    """True si `target_id` es miembro de algún restaurante de `owner_id`."""
    row = await db.scalar(
        select(Membership.id)
        .join(Restaurant, Restaurant.id == Membership.restaurant_id)
        .where(Membership.user_id == target_id, Restaurant.owner_id == owner_id)
        .limit(1)
    )
    return row is not None


@router.post("", response_model=UsuarioCreadoOut, status_code=201)
async def crear_usuario(
    body: CrearUsuarioIn,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Crea un usuario nuevo. SOLO la plataforma (superadmin) puede llamarlo — así
    se crean los dueños (is_admin=True) sin tocar la BD a mano. Un dueño crea sus
    empleados por /empleados/nuevo-usuario. 409 si el username ya existe."""
    username = body.username.strip()
    if not username or not body.password.strip():
        raise HTTPException(status_code=422, detail="Usuario y contraseña son obligatorios")
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Ese usuario ya existe")
    u = User(
        username=username,
        password_hash=hash_password(body.password),
        is_admin=body.is_admin,
        is_superadmin=False,  # nunca se crean superadmins por API
        name=body.nombre.strip(),
        title="Administrador" if body.is_admin else "",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return UsuarioCreadoOut(id=u.id, username=u.username, is_admin=u.is_admin, nombre=u.name)


@router.put("/{user_id}/password", status_code=204)
async def cambiar_password(
    user_id: str,
    body: PasswordIn,
    current: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Cambia la contraseña de un usuario. Un dueño solo puede cambiar la de SUS
    empleados; el superadmin la de cualquiera (salvo otro superadmin). Cada quien
    puede cambiar la suya."""
    if not body.password.strip():
        raise HTTPException(status_code=422, detail="La contraseña no puede estar vacía")
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if u.id == current.id:
        pass  # su propia contraseña
    elif current.is_superadmin:
        if u.is_superadmin:
            raise HTTPException(status_code=403, detail="No puedes cambiar la de otro superadmin")
    else:  # dueño
        if u.is_admin or u.is_superadmin:
            raise HTTPException(status_code=403, detail="No puedes cambiar la de otro administrador")
        if not await _es_empleado_de(db, current.id, u.id):
            raise HTTPException(status_code=403, detail="Ese usuario no es tu empleado")

    u.password_hash = hash_password(body.password)
    await db.commit()


@router.delete("/{user_id}", status_code=204)
async def eliminar_usuario(
    user_id: str,
    current: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Elimina la cuenta de un usuario. Un dueño solo puede eliminar a SUS empleados;
    el superadmin a cualquier usuario que no sea admin/superadmin. Sus membresías se
    borran en cascada."""
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if u.id == current.id:
        raise HTTPException(status_code=403, detail="No puedes eliminar tu propia cuenta")
    if u.is_admin or u.is_superadmin:
        raise HTTPException(status_code=403, detail="No se puede eliminar un administrador")
    if not current.is_superadmin and not await _es_empleado_de(db, current.id, u.id):
        raise HTTPException(status_code=403, detail="Ese usuario no es tu empleado")
    await db.delete(u)
    await db.commit()
