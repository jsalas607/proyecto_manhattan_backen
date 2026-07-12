from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import gen_id, utcnow


class User(Base):
    """Identidad global del usuario. El rol NO vive aquí: es por restaurante (Membership)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("u"))
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Datos de perfil (UserProfile en los mocks)
    title: Mapped[str] = mapped_column(String, default="")
    name: Mapped[str] = mapped_column(String, default="")
    lastname: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(String, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("r"))
    title: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(String, default="")
    country: Mapped[str] = mapped_column(String, default="")
    city: Mapped[str] = mapped_column(String, default="")
    address: Mapped[str] = mapped_column(String, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    payment_methods: Mapped[list["RestaurantPaymentMethod"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    status: Mapped["RestaurantStatus"] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan", uselist=False
    )


class RestaurantPaymentMethod(Base):
    __tablename__ = "restaurant_payment_methods"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("pm"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)

    restaurant: Mapped["Restaurant"] = relationship(back_populates="payment_methods")


class RestaurantStatus(Base):
    """Estado abierto/cerrado de la sucursal (RestaurantViewData)."""

    __tablename__ = "restaurant_status"

    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String, default="cerrado", nullable=False)  # abierto|cerrado

    restaurant: Mapped["Restaurant"] = relationship(back_populates="status")


class Role(Base):
    """Rol personalizado de una sucursal (RolRestaurante)."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("rol"))
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("perm"))
    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    permiso: Mapped[str] = mapped_column(String, nullable=False)

    role: Mapped["Role"] = relationship(back_populates="permissions")


class Membership(Base):
    """Relación muchos-a-muchos usuario<->restaurante con un rol (Empleado en los mocks).

    Un usuario puede tener varias membresías (una por restaurante) con role_id distinto.
    """

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "restaurant_id", name="uq_user_restaurant"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("emp"))
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role_id: Mapped[str | None] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String, default="")  # nombre mostrado del empleado

    user: Mapped["User"] = relationship(back_populates="memberships")
    role: Mapped["Role | None"] = relationship()
