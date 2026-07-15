from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.deps import require_admin
from app.models.organization import User
from app.schemas.base import CamelModel

router = APIRouter(prefix="/admin/users", tags=["admin-usuarios"])


class PasswordIn(CamelModel):
    password: str


class CrearUsuarioIn(CamelModel):
    username: str
    password: str
    nombre: str = ""
    is_admin: bool = False


class UsuarioCreadoOut(CamelModel):
    id: str
    username: str
    is_admin: bool
    nombre: str


@router.post("", response_model=UsuarioCreadoOut, status_code=201)
async def crear_usuario(
    body: CrearUsuarioIn,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Crea un usuario nuevo. Solo un admin existente puede llamarlo (require_admin),
    así se pueden crear dueños/administradores sin tocar la BD a mano. 409 si el
    username ya existe."""
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
        name=body.nombre.strip(),
        title="Administrador" if body.is_admin else "",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return UsuarioCreadoOut(
        id=u.id, username=u.username, is_admin=u.is_admin, nombre=u.name
    )


@router.put("/{user_id}/password", status_code=204)
async def cambiar_password(
    user_id: str,
    body: PasswordIn,
    current: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Cambia la contraseña de un usuario. Un admin puede cambiar la de cualquier
    usuario normal y la suya propia, pero no la de OTRO admin."""
    if not body.password.strip():
        raise HTTPException(status_code=422, detail="La contraseña no puede estar vacía")
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if u.is_admin and u.id != current.id:
        raise HTTPException(
            status_code=403, detail="No puedes cambiar la contraseña de otro administrador"
        )
    u.password_hash = hash_password(body.password)
    await db.commit()


@router.delete("/{user_id}", status_code=204)
async def eliminar_usuario(
    user_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Elimina la cuenta de un usuario del sistema. Sus membresías se borran en
    cascada (sale de todos los restaurantes). No permite borrar admins."""
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if u.is_admin:
        raise HTTPException(status_code=403, detail="No se puede eliminar un administrador")
    await db.delete(u)
    await db.commit()
