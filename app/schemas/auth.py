from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    is_admin: bool
    title: str = ""
    name: str = ""
    lastname: str = ""
    description: str = ""

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MembershipOut(BaseModel):
    restaurant_id: str
    restaurant_title: str
    role_id: str | None
    role_nombre: str | None
    permisos: list[str]


class MyRestaurantsResponse(BaseModel):
    is_admin: bool
    restaurants: list[MembershipOut]
