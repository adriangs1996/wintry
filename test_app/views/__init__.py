from pydantic import BaseModel


class HeroViewModel(BaseModel):
    id: str
    name: str
    city: str

    class Config:
        orm_mode = True


class HeroCreateModel(BaseModel):
    name: str
    city: str
