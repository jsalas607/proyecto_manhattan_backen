import uuid
from datetime import datetime, timezone


def gen_id(prefix: str) -> str:
    """Genera un id legible tipo 'r-ab12cd34' con un prefijo por entidad."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Prefijos de id por entidad (coherentes con los mocks de la app)
ID_PREFIX = {
    "user": "u",
    "restaurant": "r",
    "role": "rol",
    "membership": "emp",
    "inventory_item": "i",
    "categoria": "cat",
    "producto": "prod",
    "mesa": "mesa",
    "pedido": "ped",
    "pantalla": "pd",
    "venta": "venta",
    "gasto": "g",
    "perdida": "p",
    "notification": "n",
    "caja": "caja",
}
