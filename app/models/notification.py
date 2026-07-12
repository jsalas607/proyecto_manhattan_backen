from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import gen_id, utcnow


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("n"))
    # restaurant_id NULL = notificación global (visible para admin)
    restaurant_id: Mapped[str | None] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String, default="info")  # info|advertencia|alerta
    status: Mapped[str] = mapped_column(String, default="noLeida")  # leida|noLeida
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
