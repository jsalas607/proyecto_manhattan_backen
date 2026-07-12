from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import gen_id, utcnow


class Venta(Base):
    __tablename__ = "ventas"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("venta"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mesa_numero: Mapped[int] = mapped_column(Integer, default=0)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    nombre_cliente: Mapped[str] = mapped_column(String, default="")
    total: Mapped[float] = mapped_column(Float, default=0.0)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    items: Mapped[list["VentaItem"]] = relationship(
        back_populates="venta", cascade="all, delete-orphan"
    )
    pagos: Mapped[list["VentaPago"]] = relationship(
        back_populates="venta", cascade="all, delete-orphan"
    )


class VentaItem(Base):
    __tablename__ = "venta_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("vit"))
    venta_id: Mapped[str] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    producto_id: Mapped[str] = mapped_column(String, default="")
    producto_nombre: Mapped[str] = mapped_column(String, nullable=False)
    categoria_id: Mapped[str] = mapped_column(String, default="")
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    config: Mapped[str] = mapped_column(String, default="")

    venta: Mapped["Venta"] = relationship(back_populates="items")


class VentaPago(Base):
    __tablename__ = "venta_pagos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("pago"))
    venta_id: Mapped[str] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    metodo: Mapped[str] = mapped_column(String, nullable=False)
    monto: Mapped[float] = mapped_column(Float, default=0.0)

    venta: Mapped["Venta"] = relationship(back_populates="pagos")
