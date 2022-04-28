from typing import Any, Callable, Type, TypeVar, overload
from dataclasses import dataclass, field
from dataclass_wizard import fromdict, asdict

T = TypeVar("T")


def deco(cls):
    cls.__do_something__ = lambda x: print("Hello")
    return cls

@deco
class Test:
    def __init__(self) -> None:
        pass



@dataclass
class A:
    x: int
    _private: str = field(default="Hello")


@dataclass
class B:
    y: int
    a: A

b = fromdict(B, {"y": 1, "a": {"x": 2}})

print(asdict(b, skip_defaults=True))
