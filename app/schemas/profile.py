from app.schemas.base import CamelModel


class ProfileOut(CamelModel):
    id: str
    username: str
    title: str
    name: str
    lastname: str
    description: str
    role: str


class ProfileUpdate(CamelModel):
    title: str = ""
    name: str = ""
    lastname: str = ""
    description: str = ""
