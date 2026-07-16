from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import hash_password
from app.deps import es_dueno_o_super, require_permission, require_restaurant_access
from app.models.organization import Membership, Role, RolePermission, User
from app.schemas.empleado import (
    EmpleadoCreate,
    EmpleadoNuevoUsuarioCreate,
    EmpleadoOut,
    EmpleadoUpdate,
    RolCreate,
    RolOut,
    UsuarioFindOut,
)

router = APIRouter(prefix="/restaurants/{rid}", tags=["empleados"])


# --- Empleados (memberships) ---
def _es_gerente(m: Membership) -> bool:
    """True si la membresía tiene un rol con `administrar_restaurante` (puede
    entrar a Gestionar empleado). Solo el dueño manda sobre los gerentes."""
    if m.role is None:
        return False
    return any(p.permiso == "administrar_restaurante" for p in m.role.permissions)


async def _get_membership_con_rol(db: AsyncSession, empleado_id: str, rid: str) -> Membership:
    result = await db.execute(
        select(Membership)
        .where(Membership.id == empleado_id, Membership.restaurant_id == rid)
        .options(selectinload(Membership.role).selectinload(Role.permissions))
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return m


async def _proteger_gerente(
    db: AsyncSession, current: User, rid: str, m: Membership, accion: str
) -> None:
    """Un gerente no puede tocar a otro gerente (ni a sí mismo: él también lo es).
    Solo el dueño/superadmin manda sobre los gerentes."""
    if _es_gerente(m) and not await es_dueno_o_super(db, current, rid):
        raise HTTPException(
            status_code=403,
            detail=f"Solo el dueño puede {accion} a un administrador del restaurante",
        )


@router.get("/empleados", response_model=list[EmpleadoOut])
async def list_empleados(
    rid: str,
    current: User = Depends(require_restaurant_access),
    db: AsyncSession = Depends(get_db),
):
    """El dueño ve a todos; un gerente solo ve a los empleados que NO son gerentes."""
    result = await db.execute(
        select(Membership)
        .where(Membership.restaurant_id == rid)
        .options(selectinload(Membership.role).selectinload(Role.permissions))
    )
    memberships = list(result.scalars().all())
    if not await es_dueno_o_super(db, current, rid):
        memberships = [m for m in memberships if not _es_gerente(m)]
    return [
        EmpleadoOut(id=m.id, user_id=m.user_id, nombre=m.nombre, rol_id=m.role_id)
        for m in memberships
    ]


@router.get("/usuarios/{user_id}", response_model=UsuarioFindOut | None)
async def find_usuario(
    rid: str,
    user_id: str,
    _: User = Depends(require_permission("invitar_empleado")),
    db: AsyncSession = Depends(get_db),
):
    u = await db.get(User, user_id)
    if u is None:
        return None
    nombre = f"{u.name} {u.lastname}".strip() or u.username
    return UsuarioFindOut(id=u.id, nombre=nombre)


@router.get("/usuarios", response_model=UsuarioFindOut | None)
async def find_usuario_by_username(
    rid: str,
    username: str = Query(...),
    _: User = Depends(require_permission("invitar_empleado")),
    db: AsyncSession = Depends(get_db),
):
    """Busca un usuario global por su username (para agregarlo como empleado)."""
    result = await db.execute(select(User).where(User.username == username.strip().lower()))
    u = result.scalar_one_or_none()
    if u is None:
        return None
    nombre = f"{u.name} {u.lastname}".strip() or u.username
    return UsuarioFindOut(id=u.id, nombre=nombre)


@router.post("/empleados", response_model=EmpleadoOut, status_code=201)
async def add_empleado(
    rid: str,
    body: EmpleadoCreate,
    _: User = Depends(require_permission("crear_empleado")),
    db: AsyncSession = Depends(get_db),
):
    u = await db.get(User, body.user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    existing = await db.execute(
        select(Membership).where(
            Membership.restaurant_id == rid, Membership.user_id == body.user_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="El usuario ya pertenece a este restaurante")
    m = Membership(
        restaurant_id=rid, user_id=body.user_id, nombre=body.nombre, role_id=body.rol_id
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return EmpleadoOut(id=m.id, user_id=m.user_id, nombre=m.nombre, rol_id=m.role_id)


@router.post("/empleados/nuevo-usuario", response_model=EmpleadoOut, status_code=201)
async def add_empleado_nuevo_usuario(
    rid: str,
    body: EmpleadoNuevoUsuarioCreate,
    _: User = Depends(require_permission("crear_empleado")),
    db: AsyncSession = Depends(get_db),
):
    """El dueño crea la cuenta del empleado (User) y la membresía en un solo paso."""
    username = body.username.strip()
    if not username or not body.password:
        raise HTTPException(status_code=422, detail="Usuario y contraseña son obligatorios")

    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Ese usuario ya existe")

    if body.rol_id is not None:
        rol = await db.get(Role, body.rol_id)
        if rol is None or rol.restaurant_id != rid:
            raise HTTPException(status_code=404, detail="Rol no encontrado")

    user = User(
        username=username,
        password_hash=hash_password(body.password),
        name=body.nombre,
        is_admin=False,
    )
    db.add(user)
    await db.flush()

    m = Membership(restaurant_id=rid, user_id=user.id, nombre=body.nombre, role_id=body.rol_id)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return EmpleadoOut(id=m.id, user_id=m.user_id, nombre=m.nombre, rol_id=m.role_id)


@router.put("/empleados/{empleado_id}", response_model=EmpleadoOut)
async def edit_empleado(
    rid: str,
    empleado_id: str,
    body: EmpleadoUpdate,
    current: User = Depends(require_permission("crear_empleado")),
    db: AsyncSession = Depends(get_db),
):
    m = await _get_membership_con_rol(db, empleado_id, rid)
    await _proteger_gerente(db, current, rid, m, "editar")
    m.nombre = body.nombre
    m.role_id = body.rol_id
    await db.commit()
    await db.refresh(m)
    return EmpleadoOut(id=m.id, user_id=m.user_id, nombre=m.nombre, rol_id=m.role_id)


@router.delete("/empleados/{empleado_id}", status_code=204)
async def remove_empleado(
    rid: str,
    empleado_id: str,
    current: User = Depends(require_permission("crear_empleado")),
    db: AsyncSession = Depends(get_db),
):
    m = await _get_membership_con_rol(db, empleado_id, rid)
    await _proteger_gerente(db, current, rid, m, "quitar")
    await db.delete(m)
    await db.commit()


# --- Roles ---
def _rol_out(r: Role) -> RolOut:
    return RolOut(id=r.id, nombre=r.nombre, permisos=[p.permiso for p in r.permissions])


@router.get("/roles", response_model=list[RolOut])
async def list_roles(
    rid: str, _: User = Depends(require_restaurant_access), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Role).where(Role.restaurant_id == rid).options(selectinload(Role.permissions))
    )
    return [_rol_out(r) for r in result.scalars().all()]


@router.post("/roles", response_model=RolOut, status_code=201)
async def add_rol(
    rid: str,
    body: RolCreate,
    _: User = Depends(require_permission("crear_empleado")),
    db: AsyncSession = Depends(get_db),
):
    r = Role(restaurant_id=rid, nombre=body.nombre)
    r.permissions = [RolePermission(permiso=p) for p in body.permisos]
    db.add(r)
    await db.commit()
    result = await db.execute(
        select(Role).where(Role.id == r.id).options(selectinload(Role.permissions))
    )
    return _rol_out(result.scalar_one())


@router.delete("/roles/{rol_id}", status_code=204)
async def remove_rol(
    rid: str,
    rol_id: str,
    _: User = Depends(require_permission("crear_empleado")),
    db: AsyncSession = Depends(get_db),
):
    r = await db.get(Role, rol_id)
    if r is None or r.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    await db.delete(r)
    await db.commit()
