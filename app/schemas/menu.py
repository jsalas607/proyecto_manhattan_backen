from app.schemas.base import CamelModel


# --- Categorías ---
class CategoriaCreate(CamelModel):
    nombre: str
    descripcion: str | None = None
    foto: str | None = None


class CategoriaOut(CamelModel):
    id: str
    nombre: str
    descripcion: str | None = None
    foto: str | None = None


# --- Recetas ---
class OpcionRecetaIn(CamelModel):
    nombre: str


class IngredienteRecetaIn(CamelModel):
    nombre: str
    obligatorio: bool = False
    opciones: list[OpcionRecetaIn] = []


class OpcionRecetaOut(CamelModel):
    nombre: str


class IngredienteRecetaOut(CamelModel):
    nombre: str
    obligatorio: bool
    opciones: list[OpcionRecetaOut] = []


# --- Productos ---
class ProductoCreate(CamelModel):
    nombre: str
    precio: float
    categoria_id: str
    foto: str | None = None
    ingredientes: list[IngredienteRecetaIn] = []


class ProductoOut(CamelModel):
    id: str
    nombre: str
    precio: float
    categoria_id: str
    foto: str | None = None
    visible: bool
    ingredientes: list[IngredienteRecetaOut] = []
