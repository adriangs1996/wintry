from functools import lru_cache, partial
from typing import Any, Callable, Coroutine, List, Optional, Type, TypeVar
import inspect
from pydantic import BaseModel

from winter.backend import Backend
from winter.orm import __mapper__, __SQL_ENABLED_FLAG__


class RepositoryError(Exception):
    pass


T = TypeVar("T", bound=BaseModel)
TDecorated = TypeVar("TDecorated")

RuntimeDecorator = Callable[[Type[TDecorated]], Type[TDecorated]]
RuntimeParsedMethod = partial[Any], partial[Coroutine[Any, Any, Any]]
Func = Callable[..., Any]


def is_processable(method: Callable[..., Any]) -> bool:
    return method.__name__ != "__init__" and not getattr(method, "_raw_method", False)


def marked(method: Callable[..., Any]) -> bool:
    return not getattr(method, "_raw_method", False)


def map_result_to_entity(entity: Type[T], result: List[Any] | Any | None) -> List[T] | T | None:
    if isinstance(result, list):
        try:
            # Try to build from a list using from_orm
            return [entity.from_orm(instance) for instance in result]
        except:
            try:
                # try to build from list of dicts
                return [entity(**instance) for instance in result]
            except:
                # try to build from list of objects with no from_orm configuration
                try:
                    return [entity(**vars(instance)) for instance in result]
                except:
                    return result

    try:
        # try to build from object with from_orm
        return entity.from_orm(result)
    except:
        try:
            #try to build from object if it is a dict
            return entity(**result)  # type: ignore
        except:
            # try to build from object using its defined vars
            try:
                return entity(**vars(result))
            except:
                return result


def repository(
    entity: Type[T], table_name: Optional[str] = None, dry: bool = False
) -> Callable[[Type[TDecorated]], Type[TDecorated]]:
    """
    Convert a class into a repository (basically an object factory) of `entity`.
    Methods not marked with :func:`raw_method` will be compiled and processed by
    the winter engine to automatically generate a query for the given function name.

    This resembles JPA behaviour, but `entity` is not enforced to contain any DB
    information. In fact, is possible to create a `Backend` based on Python's
    built-in `Set` type, so in-memory testing is posible.

    Repository classes are can be used with MongoDB, or any relational DB supported
    by SQLAlchemy. `entity` does not need to fulfill any special rule, but if it is
    recomended that it derives from `pydantic.BaseModel`.

    Example
    =======

    >>> class User(BaseModel):
    >>>     id: int
    >>>     name: str
    >>>
    >>> @repository(User)
    >>> class UserRepository:
    >>>     async def get_by_id(self, *, id: int) -> User | None:
    >>>         ...
    >>>
    >>> repo = UserRepository()
    >>> loop = asyncio.get_event_loop()
    >>> user = loop.run_until_complete(repo.get_by_id(id=2)) # It works! And if an user exists, it automatically retrieves an `User` instance. Use MongoDB by default

    """

    def _runtime_method_parsing(cls: Type[TDecorated]) -> Type[TDecorated]:
        def _getattribute(self: Any, __name: str) -> Any:
            if getattr(entity, __SQL_ENABLED_FLAG__, False):
                target_name = __mapper__[entity]
            else:
                target_name = table_name or f"{entity.__name__}s".lower()  # type: ignore

            attr = super(cls, self).__getattribute__(__name)  # type: ignore
            new_attr = _parse_function_name(__name, attr, target_name, dry)  # type: ignore

            def wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                result = new_attr(*args, **kwargs)
                return map_result_to_entity(entity, result)

            async def async_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                result = await new_attr(*args, **kwargs)
                return map_result_to_entity(entity, result)

            if isinstance(new_attr, partial):
                if inspect.iscoroutinefunction(new_attr.func):
                    return async_wrapper
                else:
                    return wrapper
            elif inspect.iscoroutinefunction(new_attr):
                return async_wrapper
            elif inspect.isfunction(new_attr):
                return wrapper
            else:
                return attr

        cls.__getattribute__ = _getattribute  # type: ignore

        return cls

    return _runtime_method_parsing


FuncT = TypeVar("FuncT", bound=Callable[..., Any])


def raw_method(method: FuncT) -> FuncT:
    # annotate this function as a raw method, so it is ignored
    # by the engine
    setattr(method, "_raw_method", True)
    return method


@lru_cache(typed=True, maxsize=1000)
def _parse_function_name(fname: str, fobject: Func, target: str | Type[Any], dry: bool = False) -> Func:
    if is_processable(fobject):
        if inspect.iscoroutinefunction(fobject):
            return Backend.run_async(fname, target, dry_run=dry)
        else:
            return Backend.run(fname, target, dry_run=dry)
    else:
        return fobject
