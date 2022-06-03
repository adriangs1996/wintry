from typing import Callable, TypeVar, cast

T = TypeVar("T")


def alias(target: Callable) -> Callable[[T], T]:
    def wrapper(_f: T):
        return cast(T, target)

    return wrapper
