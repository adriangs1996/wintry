from dataclasses import dataclass
import inspect
from datetime import date, datetime
from enum import Enum
from functools import lru_cache, partial
from typing import Any, Callable, Coroutine, List, Optional, Type, TypeVar

from pydantic import BaseModel
from winter.backend import Backend
from winter.orm import __SQL_ENABLED_FLAG__, __WINTER_MAPPED_CLASS__
from winter.sessions import MongoSessionTracker

__mappings_builtins__ = (int, str, Enum, float, bool, bytes, date, datetime)

__sequences_like__ = (dict, list, set)

__RepositoryType__ = "__winter_repository_type__"

NO_SQL = "NO_SQL"
SQL = "SQL"


class RepositoryError(Exception):
    pass


T = TypeVar("T", Any, BaseModel)
TDecorated = TypeVar("TDecorated")

RuntimeDecorator = Callable[[Type[TDecorated]], Type[TDecorated]]
RuntimeParsedMethod = partial[Any], partial[Coroutine[Any, Any, Any]]
Func = Callable[..., Any]


@dataclass
class Proxy:
    def __init__(self, instance, tracker) -> None:
        super().__setattr__("instance", instance)
        super().__setattr__("tracker", tracker)

    def __getattribute__(self, __name: str) -> Any:
        return getattr(super().__getattribute__("instance"), __name)

    def __setattr__(self, __name: str, __value: Any) -> None:
        tracker: MongoSessionTracker = super().__getattribute__("tracker")
        instance = super().__getattribute__("instance")
        tracker.add(instance)
        return setattr(super().__getattribute__("instance"), __name, __value)


def proxyfied(result: Any | list[Any], tracker):
    if result is None:
        return result
    if not isinstance(result, list):
        return Proxy(result, tracker)
    else:
        return list(proxyfied(r, tracker) for r in result)


def is_processable(method: Callable[..., Any]) -> bool:
    try:
        return method.__name__ != "__init__" and not getattr(method, "_raw_method", False)
    except:
        return False


def marked(method: Callable[..., Any]) -> bool:
    return not getattr(method, "_raw_method", False)


def repository(
    entity: Type[T], table_name: Optional[str] = None, dry: bool = False, mongo_session_managed: bool = False
) -> Callable[[Type[TDecorated]], Type[TDecorated]]:
    """
    Convert a class into a repository (basically an object store) of `entity`.
    Methods not marked with :func:`raw_method` will be compiled and processed by
    the winter engine to automatically generate a query for the given function name.

    This resembles JPA behaviour, but `entity` is not enforced to contain any DB
    information. In fact, is possible to create a `Backend` based on Python's
    built-in `Set` type, so in-memory testing is posible.

    Repository classes are can be used with MongoDB, or any relational DB supported
    by SQLAlchemy. `entity` does not need to fulfill any special rule, but if it is
    recomended that it'd be a `dataclass`.

    Example
    =======

    >>> @dataclass
    >>> class User:
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
    >>> user = loop.run_until_complete(repo.get_by_id(id=2)) # It works!
    >>>                                                      # And if an user exists, it automatically retrieves an
    >>>                                                      # `User` instance. Use MongoDB by default

    """

    def _runtime_method_parsing(cls: Type[TDecorated]) -> Type[TDecorated]:
        # Mark the repository type so we can distinguish between drivers
        # before each run
        if getattr(entity, __SQL_ENABLED_FLAG__, False):
            setattr(cls, __RepositoryType__, SQL)
            using_sqlalchemy = True
        else:
            using_sqlalchemy = False
            setattr(cls, __RepositoryType__, NO_SQL)
            if table_name is not None:
                setattr(entity, "__tablename__", table_name)

        # Prepare the repository with augmented properties
        setattr(cls, "session", None)
        if mongo_session_managed:
            setattr(cls, "__winter_tracker__", MongoSessionTracker(entity))
            setattr(cls, "__winter_manage_objects__", True)

        def _getattribute(self: Any, __name: str) -> Any:
            attr = super(cls, self).__getattribute__(__name)  # type: ignore
            # Need to call super on this because we need to obtain a session without passing
            # through this method
            session = super(cls, self).__getattribute__("session")  # type: ignore
            use_session = False
            try:
                new_attr = _parse_function_name(__name, attr, entity, dry)  # type: ignore
            except:
                return attr

            def wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                if use_session:
                    result = new_attr(*args, session=session, **kwargs)
                    if not using_sqlalchemy and mongo_session_managed:
                        tracker = getattr(cls, "__winter_tracker__")
                        return proxyfied(result, tracker)  # type: ignore
                else:
                    result = new_attr(*args, **kwargs)
                return result

            async def async_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                if use_session:
                    result = await new_attr(*args, session=session, **kwargs)
                    if not using_sqlalchemy and mongo_session_managed:
                        tracker = getattr(cls, "__winter_tracker__")
                        return proxyfied(result, tracker)  # type: ignore
                else:
                    result = await new_attr(*args, **kwargs)
                return result

            if isinstance(new_attr, partial):
                use_session = True
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
