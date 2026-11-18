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
    # Venta al detalle (opcionales: un plato de restaurante no los usa)
    codigo_barras: str | None = None
    costo: float = 0.0
    controla_stock: bool = False
    stock_inicial: float = 0.0
    stock_minimo: float = 0.0
    unidad: str = "und"


class ProductoUpdate(CamelModel):
    """Edición parcial: solo se cambian los campos enviados. El stock no se
    edita aquí: se mueve con entradas, salidas o ajustes para que quede en el
    kárdex."""

    nombre: str | None = None
    precio: float | None = None
    categoria_id: str | None = None
    foto: str | None = None
    codigo_barras: str | None = None
    costo: float | None = None
    controla_stock: bool | None = None
    stock_minimo: float | None = None
    unidad: str | None = None


class ProductoOut(CamelModel):
    id: str
    nombre: str
    precio: float
    categoria_id: str
    foto: str | None = None
    visible: bool
    ingredientes: list[IngredienteRecetaOut] = []
    codigo_barras: str | None = None
    costo: float = 0.0
    controla_stock: bool = False
    stock: float = 0.0
    stock_minimo: float = 0.0
    unidad: str = "und"
