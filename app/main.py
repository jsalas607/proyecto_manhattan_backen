import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.organization import User


async def bootstrap_admin() -> None:
    """Crea el admin global desde variables de entorno si la BD no tiene usuarios."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none() is not None:
            return
        admin = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            is_admin=True,
            is_superadmin=True,
            title="Administrador",
            name="Admin",
        )
        db.add(admin)
        await db.commit()
        print(f"[bootstrap] Admin creado: {settings.ADMIN_USERNAME}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    await bootstrap_admin()
    yield


app = FastAPI(title="Manhattan API", version="0.1.0", lifespan=lifespan)

origins = ["*"] if settings.CORS_ORIGINS.strip() == "*" else [
    o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# --- Routers ---
from app.api.routers import (  # noqa: E402
    admin_users,
    auth,
    cartera,
    despacho,
    empleados,
    inventory,
    menu,
    mesas,
    notifications,
    pedidos,
    profile,
    restaurants,
    uploads,
    ventas,
    ws,
)

for r in (
    admin_users.router,
    auth.router,
    restaurants.router,
    menu.router,
    mesas.router,
    pedidos.router,
    despacho.router,
    ventas.router,
    inventory.router,
    cartera.router,
    empleados.router,
    profile.router,
    notifications.router,
    uploads.router,
):
    app.include_router(r, prefix="/api")

# WebSockets (sin prefijo /api: rutas /ws/...)
app.include_router(ws.router)

# --- Estáticos para imágenes subidas ---
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOADS_DIR), name="uploads")
