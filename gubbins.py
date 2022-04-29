from dataclasses import dataclass, asdict as std_asdict
from typing import cast
from winter.repository.base import proxyfied
from dataclass_wizard import fromdict, asdict
import pydantic

class AModel(pydantic.BaseModel):
    x: int

    class Config:
        orm_mode = True

class Model(pydantic.BaseModel):
    a: AModel
    b: int

    class Config:
        orm_mode = True


@dataclass(unsafe_hash=True)
class A:
    x: int

    def some_method(self, string):
        print(string)


@dataclass(unsafe_hash=True)
class B:
    a: A
    b: int

b = fromdict(B, {"a": {"x": 10}, "b": 20})

c = cast(B, proxyfied(b, set(), b))

c.a.x = 1

print(b.a.x)
print(c.a.x)
print(asdict(b, cls=B))
print(asdict(c, cls=B))

print(std_asdict(c))
print(std_asdict(b))

d = Model.from_orm(c)

e = proxyfied(d, set(), d)
print(e.dict())