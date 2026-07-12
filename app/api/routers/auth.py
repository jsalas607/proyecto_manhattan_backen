from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import K_PERMISOS
from app.core.security import create_access_token, verify_password
from app.deps import get_current_user
from app.models.organization import Membership, Restaurant, Role, User
from app.schemas.auth import (
    LoginRequest,
    MembershipOut,
    MyRestaurantsResponse,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _authenticate(db: AsyncSession, username: str, password: str) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña inválidos"
        )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await _authenticate(db, body.username, body.password)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login-form", response_model=TokenResponse, include_in_schema=False)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """Compatibilidad con el botón Authorize de /docs (OAuth2 password flow)."""
    user = await _authenticate(db, form.username, form.password)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)):
    return UserOut.model_validate(current)


@router.get("/my-restaurants", response_model=MyRestaurantsResponse)
async def my_restaurants(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if current.is_admin:
        result = await db.execute(select(Restaurant))
        restos = result.scalars().all()
        return MyRestaurantsResponse(
            is_admin=True,
            restaurants=[
                MembershipOut(
                    restaurant_id=r.id,
                    restaurant_title=r.title,
                    role_id=None,
                    role_nombre="Administrador",
                    permisos=list(K_PERMISOS),
                )
                for r in restos
            ],
        )

    result = await db.execute(
        select(Membership)
        .where(Membership.user_id == current.id)
        .options(
            selectinload(Membership.role).selectinload(Role.permissions),
        )
    )
    memberships = result.scalars().all()

    out: list[MembershipOut] = []
    for m in memberships:
        resto = await db.get(Restaurant, m.restaurant_id)
        permisos = [p.permiso for p in m.role.permissions] if m.role else []
        out.append(
            MembershipOut(
                restaurant_id=m.restaurant_id,
                restaurant_title=resto.title if resto else "",
                role_id=m.role_id,
                role_nombre=m.role.nombre if m.role else None,
                permisos=permisos,
            )
        )
    return MyRestaurantsResponse(is_admin=False, restaurants=out)
