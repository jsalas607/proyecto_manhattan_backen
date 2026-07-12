from app.schemas.base import CamelModel


class EmpleadoCreate(CamelModel):
    user_id: str
    nombre: str
    rol_id: str | None = None


class EmpleadoNuevoUsuarioCreate(CamelModel):
    username: str
    password: str
    nombre: str
    rol_id: str | None = None


class EmpleadoUpdate(CamelModel):
    nombre: str
    rol_id: str | None = None


class EmpleadoOut(CamelModel):
    id: str  # id de la membership
    user_id: str
    nombre: str
    rol_id: str | None = None


class UsuarioFindOut(CamelModel):
    id: str
    nombre: str


class RolCreate(CamelModel):
    nombre: str
    permisos: list[str] = []


class RolOut(CamelModel):
    id: str
    nombre: str
    permisos: list[str] = []
