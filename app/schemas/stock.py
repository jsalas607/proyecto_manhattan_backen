from datetime import date as date_type
from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class EntradaItem(CamelModel):
    producto_id: str
    cantidad: float = Field(gt=0)
    costo_unitario: float | None = Field(default=None, ge=0)


class EntradaIn(CamelModel):
    """Compra o ingreso de mercancía. Si trae costo, recalcula el costo promedio."""

    items: list[EntradaItem] = Field(min_length=1)
    nota: str = ""


class SalidaItem(CamelModel):
    producto_id: str
    cantidad: float = Field(gt=0)


class SalidaIn(CamelModel):
    """Salida que no es venta: merma, consumo propio, cortesía, vencido..."""

    items: list[SalidaItem] = Field(min_length=1)
    motivo: str = "merma"
    nota: str = ""


class AjusteItem(CamelModel):
    producto_id: str
    stock_real: float = Field(ge=0)


class AjusteIn(CamelModel):
    """Conteo físico: el stock pasa a ser el contado y la diferencia queda en el kárdex."""

    items: list[AjusteItem] = Field(min_length=1)
    nota: str = ""


class MovimientoOut(CamelModel):
    id: str
    producto_id: str
    producto_nombre: str
    tipo: str
    cantidad: float
    stock_resultante: float
    costo_unitario: float
    motivo: str
    nota: str
    venta_id: str | None = None
    usuario_id: str | None = None
    fecha: datetime


class CategoriaValor(CamelModel):
    categoria_id: str
    categoria: str
    productos: int
    unidades: float
    valor_costo: float
    valor_venta: float


class InventarioValorOut(CamelModel):
    productos: int
    unidades: float
    valor_costo: float
    valor_venta: float
    productos_sin_costo: int
    productos_stock_negativo: int
    por_categoria: list[CategoriaValor]


class ProductoVendido(CamelModel):
    producto_id: str
    producto_nombre: str
    cantidad: float
    ventas: float
    costo: float
    utilidad: float


class CategoriaVentas(CamelModel):
    categoria_id: str
    categoria: str
    cantidad: float
    ventas: float
    costo: float
    utilidad: float


class ReporteVentasOut(CamelModel):
    desde: date_type
    hasta: date_type
    tickets: int
    total_ventas: float
    ticket_promedio: float
    # Ventas de ítems con costo conocido (las anteriores a este cambio no lo tienen)
    ventas_con_costo: float
    costo: float
    utilidad: float
    margen: float  # utilidad / ventas_con_costo
    salidas_unidades: float  # salidas que no son venta (merma, consumo...)
    salidas_costo: float
    por_categoria: list[CategoriaVentas]
    mas_vendidos: list[ProductoVendido]


class ImportCategoria(CamelModel):
    id: int | str
    nombre: str


class ImportProducto(CamelModel):
    nombre: str
    categoria_id: int | str
    codigo_barras: str | None = None
    precio_venta: float = 0
    precio_compra: float | None = None
    stock: float | None = 0
    stock_minimo: float | None = 0
    unidad: str | None = None
    inventario_infinito: bool = False
    oculto: bool = False


class ImportGecofiIn(CamelModel):
    """Formato de los JSON exportados de Gecofi (categorias.json + productos.json)."""

    categorias: list[ImportCategoria]
    productos: list[ImportProducto]
    # Si un producto ya existe: True pone su stock igual al del archivo (con
    # un ajuste en el kárdex); False solo actualiza precios y datos.
    actualizar_stock: bool = False


class ImportResultOut(CamelModel):
    categorias_creadas: int
    productos_creados: int
    productos_actualizados: int
    unidades_cargadas: float
