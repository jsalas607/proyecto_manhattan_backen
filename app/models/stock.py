from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import gen_id, utcnow

# Tipos de movimiento del kárdex. La cantidad lleva signo: + entra, - sale.
TIPOS_MOVIMIENTO = ("entrada", "venta", "salida", "ajuste", "importacion")


class StockMovimiento(Base):
    """Kárdex: cada cambio de stock de un producto queda registrado aquí."""

    __tablename__ = "stock_movimientos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("sm"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    producto_id: Mapped[str] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    cantidad: Mapped[float] = mapped_column(Float, nullable=False)
    stock_resultante: Mapped[float] = mapped_column(Float, nullable=False)
    costo_unitario: Mapped[float] = mapped_column(Float, default=0.0)
    motivo: Mapped[str] = mapped_column(String, default="")
    nota: Mapped[str] = mapped_column(String, default="")
    venta_id: Mapped[str | None] = mapped_column(
        ForeignKey("ventas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    usuario_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
