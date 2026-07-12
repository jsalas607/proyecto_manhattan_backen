from datetime import datetime

from app.schemas.base import CamelModel


class NotificationOut(CamelModel):
    id: str
    title: str
    message: str
    type: str  # info|advertencia|alerta
    status: str  # leida|noLeida
    created_at: datetime
