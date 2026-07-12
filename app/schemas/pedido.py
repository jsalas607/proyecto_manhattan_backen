from app.schemas.base import CamelModel


class ItemPedidoIn(CamelModel):
    producto_id: str
    producto_nombre: str
    categoria_id: str = ""
    cantidad: int = 1
    config: str = ""


class ItemPedidoOut(CamelModel):
    producto_id: str
    producto_nombre: str
    categoria_id: str
    cantidad: int
    config: str
    listo: bool = False


class PedidoUpsert(CamelModel):
    mesa_numero: int
    orden: int
    items: list[ItemPedidoIn]


class PedidoOut(CamelModel):
    id: str  # = mesa_id (coincide con el mock)
    mesa_id: str
    mesa_numero: int
    orden: int
    items: list[ItemPedidoOut]


class SetListoIn(CamelModel):
    listo: bool
