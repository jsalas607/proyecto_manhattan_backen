from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import gen_id


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("cat"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String, nullable=True)
    foto: Mapped[str | None] = mapped_column(String, nullable=True)


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("prod"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    precio: Mapped[float] = mapped_column(Float, default=0.0)
    categoria_id: Mapped[str] = mapped_column(
        ForeignKey("categorias.id", ondelete="CASCADE"), index=True, nullable=False
    )
    foto: Mapped[str | None] = mapped_column(String, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)

    ingredientes: Mapped[list["ProductoIngrediente"]] = relationship(
        back_populates="producto", cascade="all, delete-orphan", order_by="ProductoIngrediente.orden"
    )


class ProductoIngrediente(Base):
    """IngredienteReceta: un grupo de opciones dentro de un producto compuesto."""

    __tablename__ = "producto_ingredientes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("ing"))
    producto_id: Mapped[str] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=False)
    orden: Mapped[int] = mapped_column(default=0)

    producto: Mapped["Producto"] = relationship(back_populates="ingredientes")
    opciones: Mapped[list["IngredienteOpcion"]] = relationship(
        back_populates="ingrediente", cascade="all, delete-orphan", order_by="IngredienteOpcion.orden"
    )


class IngredienteOpcion(Base):
    """OpcionReceta: una opción seleccionable de un ingrediente."""

    __tablename__ = "ingrediente_opciones"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("opt"))
    ingrediente_id: Mapped[str] = mapped_column(
        ForeignKey("producto_ingredientes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    orden: Mapped[int] = mapped_column(default=0)

    ingrediente: Mapped["ProductoIngrediente"] = relationship(back_populates="opciones")
