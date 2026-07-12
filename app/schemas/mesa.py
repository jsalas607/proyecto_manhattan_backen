from app.schemas.base import CamelModel


class MesaCreate(CamelModel):
    numero: int
    nombre: str = ""


class MesaOut(CamelModel):
    id: str
    orden: int
    numero: int
    nombre: str
    atendida: bool
