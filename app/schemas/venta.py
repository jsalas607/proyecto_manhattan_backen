from datetime import datetime

from app.schemas.base import CamelModel
from app.schemas.pedido import ItemPedidoIn


class PagoMetodoIn(CamelModel):
    metodo: str
    monto: float


class PagoMetodoOut(CamelModel):
    metodo: str
    monto: float


class VentaItemOut(CamelModel):
    producto_id: str
    producto_nombre: str
    categoria_id: str
    cantidad: int
    config: str


class VentaCreate(CamelModel):
    mesa_numero: int
    orden: int
    nombre_cliente: str = ""
    items: list[ItemPedidoIn]
    pagos: list[PagoMetodoIn]
    total: float


class VentaOut(CamelModel):
    id: str
    mesa_numero: int
    orden: int
    nombre_cliente: str
    items: list[VentaItemOut]
    pagos: list[PagoMetodoOut]
    total: float
    fecha: datetime
