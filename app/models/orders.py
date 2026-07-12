from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import gen_id


class Mesa(Base):
    __tablename__ = "mesas"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("mesa"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)  # incremental global por sucursal
    numero: Mapped[int] = mapped_column(Integer, nullable=False)  # número físico de mesa
    nombre: Mapped[str] = mapped_column(String, default="")  # nombre del cliente
    atendida: Mapped[bool] = mapped_column(Boolean, default=False)


class Pedido(Base):
    """PedidoActivo: un pedido abierto asociado a una mesa."""

    __tablename__ = "pedidos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("ped"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mesa_id: Mapped[str] = mapped_column(
        ForeignKey("mesas.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    mesa_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)

    items: Mapped[list["PedidoItem"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", order_by="PedidoItem.posicion"
    )


class PedidoItem(Base):
    __tablename__ = "pedido_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("pit"))
    pedido_id: Mapped[str] = mapped_column(
        ForeignKey("pedidos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    posicion: Mapped[int] = mapped_column(Integer, default=0)  # orden estable del item en el pedido
    producto_id: Mapped[str] = mapped_column(String, nullable=False)
    producto_nombre: Mapped[str] = mapped_column(String, nullable=False)
    categoria_id: Mapped[str] = mapped_column(String, default="")
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    config: Mapped[str] = mapped_column(String, default="")  # "Proteína: Pollo · ..."
    listo: Mapped[bool] = mapped_column(Boolean, default=False)  # reemplaza el Set<int> del mock

    pedido: Mapped["Pedido"] = relationship(back_populates="items")


class PantallaDespacho(Base):
    __tablename__ = "pantallas_despacho"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("pd"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    icono_index: Mapped[int] = mapped_column(Integer, default=0)
    color_index: Mapped[int] = mapped_column(Integer, default=0)

    categorias: Mapped[list["PantallaCategoria"]] = relationship(
        back_populates="pantalla", cascade="all, delete-orphan"
    )


class PantallaCategoria(Base):
    __tablename__ = "pantalla_categorias"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("pdc"))
    pantalla_id: Mapped[str] = mapped_column(
        ForeignKey("pantallas_despacho.id", ondelete="CASCADE"), index=True, nullable=False
    )
    categoria_id: Mapped[str] = mapped_column(String, nullable=False)

    pantalla: Mapped["PantallaDespacho"] = relationship(back_populates="categorias")
