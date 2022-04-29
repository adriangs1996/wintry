from dataclasses import dataclass, asdict as std_asdict
from typing import Any, Callable, Tuple, Type, TypeVar, Union
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

_T = TypeVar('_T')

def __dataclass_transform__(
    *,
    eq_default: bool = True,
    order_default: bool = False,
    kw_only_default: bool = False,
    field_descriptors: Tuple[Union[type, Callable[..., Any]], ...] = (()),
) -> Callable[[_T], _T]:
    # If used within a stub file, the following implementation can be
    # replaced with "...".
    return lambda a: a


@__dataclass_transform__()
def deco(cls: Type[_T]) -> Type[_T]:
    return dataclass(cls)


@deco
class A:
    x: int


@deco
class B:
    a: A
    b: int

b = fromdict(B, {"a": {"x": 10}, "b": 20})


def _winter_setattr_(self, __name: str, __value: Any):
    print("PROXYED")
    return super(self.__class__, self).__setattr__(__name, __value)


def _winter_init_(self, *args, **kwargs):
    old_init = getattr(self, '__winter_old_init__')
    old_init(*args, **kwargs)

    print(f"Added new entity: {self}")


setattr(B, '__winter_old_init__', B.__init__)
B.__setattr__ = _winter_setattr_
B.__init__ = _winter_init_

b.b = 10
print(b.b)

c = B(a=A(x=10), b=25)
print(c)