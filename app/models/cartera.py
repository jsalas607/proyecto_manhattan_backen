from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import gen_id, utcnow


class Caja(Base):
    __tablename__ = "caja"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("caja"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="cerrada")  # abierta|cerrada
    abierta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    montos_iniciales: Mapped[list["CajaMontoInicial"]] = relationship(
        back_populates="caja", cascade="all, delete-orphan"
    )


class CajaMontoInicial(Base):
    __tablename__ = "caja_montos_iniciales"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("cmi"))
    caja_id: Mapped[str] = mapped_column(
        ForeignKey("caja.id", ondelete="CASCADE"), index=True, nullable=False
    )
    metodo: Mapped[str] = mapped_column(String, nullable=False)
    monto: Mapped[float] = mapped_column(Float, default=0.0)

    caja: Mapped["Caja"] = relationship(back_populates="montos_iniciales")


class Gasto(Base):
    __tablename__ = "gastos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("g"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    descripcion: Mapped[str] = mapped_column(String, default="")
    monto: Mapped[float] = mapped_column(Float, default=0.0)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    metodo_pago: Mapped[str] = mapped_column(String, default="efectivo")

    productos: Mapped[list["GastoProducto"]] = relationship(
        back_populates="gasto", cascade="all, delete-orphan"
    )


class GastoProducto(Base):
    __tablename__ = "gasto_productos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("gp"))
    gasto_id: Mapped[str] = mapped_column(
        ForeignKey("gastos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    unidad: Mapped[str] = mapped_column(String, default="und")
    cantidad: Mapped[float] = mapped_column(Float, default=0.0)

    gasto: Mapped["Gasto"] = relationship(back_populates="productos")


class Perdida(Base):
    __tablename__ = "perdidas"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("p"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    titulo: Mapped[str] = mapped_column(String, default="")
    descripcion: Mapped[str] = mapped_column(String, default="")
    categoria: Mapped[str] = mapped_column(String, default="otro")  # ventas|cocina|almacén|caducidad|otro
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    productos: Mapped[list["PerdidaProducto"]] = relationship(
        back_populates="perdida", cascade="all, delete-orphan"
    )


class PerdidaProducto(Base):
    __tablename__ = "perdida_productos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("pp"))
    perdida_id: Mapped[str] = mapped_column(
        ForeignKey("perdidas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    cantidad: Mapped[float] = mapped_column(Float, default=0.0)
    unidad: Mapped[str | None] = mapped_column(String, nullable=True)
    item_id: Mapped[str | None] = mapped_column(String, nullable=True)  # id de inventario si aplica

    perdida: Mapped["Perdida"] = relationship(back_populates="productos")


class ServicioCategoria(Base):
    """Categorías de servicios/gastos definidas por el admin (mock_servicios_api)."""

    __tablename__ = "servicios_categorias"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("sc"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
