from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Hashable,
    Optional,
    Type,
    TypeVar,
    Union,
    overload,
)
from inject import autoparams

T = TypeVar("T")
I = TypeVar("I")
Decorable = type | Callable[..., Any]
HashableDecorable = type | Hashable


class Factory(Generic[T]):
    def __init__(self, cls: Union[Type[T], Callable]) -> None:
        self.cls = cls

    def __call__(self) -> Union[T, Any]:
        return self.cls()


__mappings__: Dict[Union[Type[Any], Hashable], Union[Factory, Type[Any], Callable]] = {}


@overload
def service(fn: type[T]) -> type[T]:
    ...


@overload
def service(fn: Callable[..., T]) -> Callable[..., T]:
    ...


def service(fn: type[T] | Callable[..., T]) -> type[T] | Callable[..., T]:
    wrapper = autoparams()
    fn = wrapper(fn)
    return fn


@overload
def provider(cls: type[T], /) -> type[T]:
    ...


@overload
def provider(
    cls: None, /
) -> Callable[[type[T] | Callable[..., T]], type[T] | Callable[..., T]]:
    ...


@overload
def provider(
    *, interface: type[T] | None = None, as_provider: bool = True
) -> Callable[[type[T]], type[T]]:
    ...


def provider(  # type: ignore
    cls: type[T] | None = None,
    /,
    *,
    interface: type[I] | Hashable | None = None,
    as_provider: bool = True,
) -> type[T] | Callable[[type[T] | Callable[..., T]], type[T] | Callable[..., T]]:
    @overload
    def decorator(_cls: type[T]) -> type[T]:
        ...

    @overload
    def decorator(_cls: Callable[..., T]) -> Callable[..., T]:
        ...

    def decorator(_cls: type[T] | Callable[..., T]) -> type[T] | Callable[..., T]:
        _cls = service(_cls)

        if interface is None:
            key = _cls
        else:
            key = interface

        if as_provider:
            __mappings__[key] = Factory(_cls)
        else:
            __mappings__[key] = _cls

        return _cls

    if cls is None:
        return decorator

    else:
        return decorator(cls)
