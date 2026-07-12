"""Utilidades de fecha/hora en la zona horaria local de la operación.

Los timestamps se guardan en UTC, pero "hoy" y los rangos de día (inventario,
ventas del día, estadísticas, caja) deben calcularse en la hora local del
restaurante (por defecto Colombia, UTC-5). Así, una venta hecha a las 7pm no
"salta" al día siguiente por diferencia con UTC.
"""
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone

from app.core.config import settings


def local_tz() -> timezone:
    return timezone(timedelta(hours=settings.APP_TZ_OFFSET_HOURS))


def local_today() -> date_type:
    """La fecha de 'hoy' en la zona horaria local."""
    return datetime.now(local_tz()).date()


def day_bounds_utc(d: date_type) -> tuple[datetime, datetime]:
    """Devuelve (inicio, fin) de un día local, convertidos a UTC (aware),
    para comparar contra timestamps almacenados en UTC."""
    tz = local_tz()
    inicio = datetime.combine(d, time.min, tzinfo=tz).astimezone(timezone.utc)
    fin = datetime.combine(d, time.max, tzinfo=tz).astimezone(timezone.utc)
    return inicio, fin
