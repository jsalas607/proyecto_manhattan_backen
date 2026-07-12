from app.schemas.base import CamelModel


class PantallaCreate(CamelModel):
    nombre: str
    categoria_ids: list[str] = []
    icono_index: int = 0
    color_index: int = 0


class PantallaOut(CamelModel):
    id: str
    nombre: str
    categoria_ids: list[str]
    icono_index: int
    color_index: int
