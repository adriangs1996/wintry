from dataclasses import asdict, dataclass
from functools import partial
from typing import Any


@dataclass
class A:
    x: int

    def some_method(self, string):
        print(string)


@dataclass
class Proxy:
    def __init__(self, instance) -> None:
        super().__setattr__('instance', instance)

    def __getattribute__(self, __name: str) -> Any:
        return getattr(super().__getattribute__('instance'), __name)

    def __setattr__(self, __name: str, __value: Any) -> None:
        print("PROXYED")
        return setattr(super().__getattribute__('instance'), __name, __value)


def _setattr(self, __name, value):
    print(__name)
    return super(self.__class__, self).__setattr__(__name, value)


setattr(A, "dirty", False)

a = A(x=1)
a = Proxy(a)

a.x = 2
a.some_method("Hello")
b = A(x=2)

print(asdict(a))
print(isinstance(a, A))
