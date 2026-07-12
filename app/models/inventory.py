from datetime import date as date_type

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import gen_id


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("i"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    unidad: Mapped[str] = mapped_column(String, default="und")


class DailyInventory(Base):
    """Conteo diario de un item (DailyEntry)."""

    __tablename__ = "daily_inventory"
    __table_args__ = (UniqueConstraint("item_id", "fecha", name="uq_item_fecha"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("di"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_id: Mapped[str] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fecha: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    inv_app: Mapped[float] = mapped_column(Float, default=0.0)
    inv_real: Mapped[float | None] = mapped_column(Float, nullable=True)  # null = no contado aún


class InventoryDayClosed(Base):
    __tablename__ = "inventory_day_closed"

    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), primary_key=True
    )
    fecha: Mapped[date_type] = mapped_column(Date, primary_key=True)


class InventoryMovement(Base):
    """Compras y mermas (addCompra / registrarMerma). cantidad negativa = merma."""

    __tablename__ = "inventory_movements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("mov"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_id: Mapped[str] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fecha: Mapped[date_type] = mapped_column(Date, nullable=False)
    cantidad: Mapped[float] = mapped_column(Float, default=0.0)
    tipo: Mapped[str] = mapped_column(String, default="compra")  # compra|merma
