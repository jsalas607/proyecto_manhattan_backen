from datetime import datetime

from app.schemas.base import CamelModel


# --- Caja ---
class CajaStateOut(CamelModel):
    status: str  # abierta|cerrada
    abierta_en: datetime | None = None
    montos_iniciales: dict[str, float] = {}
    monto_total: float = 0.0


class AbrirCajaIn(CamelModel):
    montos_iniciales: dict[str, float] = {}


class PaymentMethodTotalOut(CamelModel):
    name: str
    total: float


class DailyStatsOut(CamelModel):
    ordenes_creadias: int
    dinero_facturado: float
    promedio_orden: float
    gastos_dia: float
    perdidas_dia: float


# --- Gastos ---
class GastoProductoIn(CamelModel):
    name: str
    unidad: str = "und"
    cantidad: float = 0.0


class GastoProductoOut(GastoProductoIn):
    pass


class GastoCreate(CamelModel):
    descripcion: str
    monto: float
    metodo_pago: str = "efectivo"
    productos: list[GastoProductoIn] = []


class GastoOut(CamelModel):
    id: str
    descripcion: str
    monto: float
    fecha: datetime
    metodo_pago: str
    productos: list[GastoProductoOut] = []


# --- Pérdidas ---
class PerdidaProductoIn(CamelModel):
    name: str
    cantidad: float = 0.0
    unidad: str | None = None
    item_id: str | None = None


class PerdidaProductoOut(PerdidaProductoIn):
    pass


class PerdidaCreate(CamelModel):
    titulo: str
    descripcion: str = ""
    categoria: str = "otro"
    productos: list[PerdidaProductoIn] = []


class PerdidaOut(CamelModel):
    id: str
    titulo: str
    descripcion: str
    categoria: str
    fecha: datetime
    productos: list[PerdidaProductoOut] = []
    monto: float = 0.0


# --- Servicios ---
class ServicioCreate(CamelModel):
    nombre: str
