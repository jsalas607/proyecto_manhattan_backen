from app.schemas.base import CamelModel


class RestaurantBase(CamelModel):
    title: str
    name: str = ""
    description: str = ""
    country: str = ""
    city: str = ""
    address: str = ""
    payment_methods: list[str] = []
    is_active: bool = True


class RestaurantCreate(RestaurantBase):
    pass


class RestaurantUpdate(RestaurantBase):
    pass


class RestaurantOut(RestaurantBase):
    id: str


class StatusOut(CamelModel):
    restaurant_id: str
    status: str  # abierto|cerrado


class StatusUpdate(CamelModel):
    status: str
