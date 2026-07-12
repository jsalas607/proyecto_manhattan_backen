"""Importa todos los modelos para que Base.metadata los registre (Alembic, create_all)."""

from app.models.cartera import (
    Caja,
    CajaMontoInicial,
    Gasto,
    GastoProducto,
    Perdida,
    PerdidaProducto,
    ServicioCategoria,
)
from app.models.inventory import (
    DailyInventory,
    InventoryDayClosed,
    InventoryItem,
    InventoryMovement,
)
from app.models.menu import Categoria, IngredienteOpcion, Producto, ProductoIngrediente
from app.models.notification import Notification
from app.models.orders import (
    Mesa,
    PantallaCategoria,
    PantallaDespacho,
    Pedido,
    PedidoItem,
)
from app.models.organization import (
    Membership,
    Restaurant,
    RestaurantPaymentMethod,
    RestaurantStatus,
    Role,
    RolePermission,
    User,
)
from app.models.sales import Venta, VentaItem, VentaPago

__all__ = [
    "Caja",
    "CajaMontoInicial",
    "Gasto",
    "GastoProducto",
    "Perdida",
    "PerdidaProducto",
    "ServicioCategoria",
    "DailyInventory",
    "InventoryDayClosed",
    "InventoryItem",
    "InventoryMovement",
    "Categoria",
    "IngredienteOpcion",
    "Producto",
    "ProductoIngrediente",
    "Notification",
    "Mesa",
    "PantallaCategoria",
    "PantallaDespacho",
    "Pedido",
    "PedidoItem",
    "Membership",
    "Restaurant",
    "RestaurantPaymentMethod",
    "RestaurantStatus",
    "Role",
    "RolePermission",
    "User",
    "Venta",
    "VentaItem",
    "VentaPago",
]
