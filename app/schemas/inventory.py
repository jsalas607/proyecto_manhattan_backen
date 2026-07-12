from datetime import date as date_type

from app.schemas.base import CamelModel


class ItemCreate(CamelModel):
    name: str
    unidad: str = "und"


class ItemOut(CamelModel):
    id: str
    name: str
    unidad: str


class EntryOut(CamelModel):
    item_id: str
    inv_app: float
    inv_real: float | None = None
    is_counted: bool
    diff: float
    has_diff: bool


class RecordOut(CamelModel):
    item: ItemOut
    entry: EntryOut


class DayInventoryOut(CamelModel):
    date: date_type
    closed: bool
    records: list[RecordOut]


class UpdateRealIn(CamelModel):
    date: date_type
    inv_real: float


class MovimientoIn(CamelModel):
    date: date_type
    item_id: str
    cantidad: float
