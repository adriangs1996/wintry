import inspect
from functools import lru_cache, partial, update_wrapper
from typing import Any, Callable, Coroutine, List, Type, TypeVar, overload

from sqlalchemy.exc import IntegrityError
from wintry import BACKENDS
from wintry.errors.definitions import InternalServerError, InvalidRequestError
from wintry.models import _is_private_attr
from wintry.orm import __SQL_ENABLED_FLAG__, __WINTER_MAPPED_CLASS__
from wintry.utils.keys import (
    __mappings_builtins__,
    __RepositoryType__,
    __winter_backend_for_repository__,
    __winter_backend_identifier_key__,
    __winter_in_session_flag__,
    __winter_manage_objects__,
    __winter_modified_entity_state__,
    __winter_old_setattr__,
    __winter_repo_old_init__,
    __winter_repository_for_model__,
    __winter_repository_is_using_sqlalchemy__,
    __winter_session_key__,
    __winter_track_target__,
    __winter_tracker__,
)


class RepositoryError(Exception):
    pass


T = TypeVar("T")
TDecorated = TypeVar("TDecorated")

RuntimeDecorator = Callable[[Type[TDecorated]], Type[TDecorated]]
RuntimeParsedMethod = partial[Any], partial[Coroutine[Any, Any, Any]]
Func = Callable[..., Any]


class ProxyList(list):
    def set_tracking_info(self, tracker, instance):
        self.tracker = tracker
        self.instance = instance
        self.regs = False

    def track(self):
        # Check for modified flag, so we ensure that this object is addded just once
        modified = getattr(self.instance, __winter_modified_entity_state__, False)
        if not modified and not self.regs:
            self.tracker.add(self.instance)
            self.regs = True
            setattr(self.instance, __winter_modified_entity_state__, True)

    def append(self, __object: Any) -> None:
        self.track()
        return super().append(__object)

    def remove(self, __value: Any) -> None:
        self.track()
        return super().remove(__value)


def proxyfied(result: Any | list[Any], tracker, origin: Any):
    """
    When a Domain class (A dataclass) is bound to a repository, it
    gets overwrite its :func:`__setattr__` to add tracker information
    on attribute change. This means that we need to augment this instance
    to comply to the interface defined by the new :func:`__setattr__` implemented
    with a call to :func:`make_proxy_ref`
    """
    if result is None or type(result) in __mappings_builtins__:
        return result

    if not isinstance(result, list):
        for k, v in vars(result).items():
            # Proxify recursively this instance.
            # Ignore private attributes as well as builtin ones
            if not _is_private_attr(k) and not v.__class__ in __mappings_builtins__:
                if isinstance(v, list):
                    # If this is a list, we must convert it to a proxylist
                    # to allow for append and remove synchronization
                    proxy_list = ProxyList(proxyfied(val, tracker, origin) for val in v)
                    # Set tracking information for the list
                    proxy_list.set_tracking_info(tracker, origin)
                    # Update value for k
                    setattr(result, k, proxy_list)
                else:
                    # Update value for K with a Proxified version
                    setattr(result, k, proxyfied(v, tracker, origin))

        # Augment instance with special variables so tracking is possible
        # Set track target (this allow to child objects to reference the root entity)
        setattr(result, __winter_track_target__, origin)
        # Mark this instance as being tracked by a session
        setattr(result, __winter_in_session_flag__, True)
        # Save the repo tracker associated with this instance
        setattr(result, __winter_tracker__, tracker)
        # Set the instance state (not modified)
        setattr(result, __winter_modified_entity_state__, False)
        return result
    else:
        if isinstance(origin, list):
            return list(proxyfied(r, tracker, r) for r in result)
        else:
            return list(proxyfied(r, tracker, origin) for r in result)


def is_processable(method: Callable[..., Any]) -> bool:
    try:
        return method.__name__ != "__init__" and not getattr(method, "_raw_method", False)
    except:
        return False


def marked(method: Callable[..., Any]) -> bool:
    return not getattr(method, "_raw_method", False)


FuncT = TypeVar("FuncT", bound=Callable[..., Any])


def raw_method(method: FuncT) -> FuncT:
    # annotate this function as a raw method, so it is ignored
    # by the engine
    setattr(method, "_raw_method", True)
    return method


@lru_cache(typed=True, maxsize=1000)
def _parse_function_name(
    backend: str, fname: str, fobject: Func, target: str | Type[Any], dry: bool = False
) -> Func:
    repo_backend = BACKENDS.get(backend, None)
    if repo_backend is None:
        raise RepositoryError(f"Not configured backend: {backend}")

    if inspect.iscoroutinefunction(fobject):
        return repo_backend.run_async(fname, target, dry_run=dry)
    else:
        return repo_backend.run(fname, target, dry_run=dry)


def handle_error(exc: Exception):
    match exc:
        case IntegrityError():
            raise InvalidRequestError(details={"error": str(exc)})
        case _:
            raise InternalServerError(details={"error": str(exc)})


def is_raw(func):
    return getattr(func, "_raw_method", False)


class Managed:
    def __init__(self, fget=None):
        self.fget = fget

    def __set_name__(self, owner, name):
        self.__winter_owner__ = owner

    def __get__(self, obj, objtype=None):
        self.__no_sql_session_manged__ = getattr(
            self.__winter_owner__, "__nosql_session_managed__"
        )
        using_sqlalchemy = getattr(obj, __winter_repository_is_using_sqlalchemy__)

        def raw_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
            try:
                result = self.fget(obj, *args, **kwargs)
            except Exception as e:
                handle_error(e)
            if not using_sqlalchemy and self.__no_sql_session_manged__:
                # Track the results, get the tracker instance from
                # the repo instance
                tracker = getattr(obj, __winter_tracker__)
                return proxyfied(result, tracker, result)  # type: ignore
            return result

        async def async_raw_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
            try:
                result = await self.fget(obj, *args, **kwargs)
            except Exception as e:
                handle_error(e)
            if not using_sqlalchemy and self.__no_sql_session_manged__:
                tracker = getattr(obj, __winter_tracker__)
                return proxyfied(result, tracker, result)  # type: ignore
            return result

        if inspect.iscoroutinefunction(self.fget):
            return async_raw_wrapper
        else:
            return raw_wrapper


class Query:
    def __init__(self, fget=None, doc=None):
        self.fget = fget
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self.__winter_name__ = name
        self.__winter_owner__ = owner

    def __get__(self, obj, objtype=None):
        dry = getattr(self.__winter_owner__, "__dry__", False)
        backend = getattr(
            self.__winter_owner__, __winter_backend_identifier_key__, "default"
        )
        ent = getattr(self.__winter_owner__, "__winter_entity__")

        self.__func_application__ = _parse_function_name(
            backend, self.__winter_name__, self.fget, ent, dry
        )

        self.__no_sql_session_manged__ = getattr(
            self.__winter_owner__, "__nosql_session_managed__"
        )

        session = getattr(obj, __winter_session_key__, None)
        using_sqlalchemy = getattr(obj, __winter_repository_is_using_sqlalchemy__)

        def wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
            try:
                result = self.__func_application__(*args, session=session, **kwargs)
            except Exception as e:
                handle_error(e)
            if not using_sqlalchemy and self.__no_sql_session_manged__:
                # Track the results, get the tracker instance from
                # the repo instance
                tracker = getattr(obj, __winter_tracker__)
                return proxyfied(result, tracker, result)  # type: ignore
            return result

        async def async_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
            try:
                result = await self.__func_application__(*args, session=session, **kwargs)
            except Exception as e:
                handle_error(e)
            if not using_sqlalchemy and self.__no_sql_session_manged__:
                tracker = getattr(obj, __winter_tracker__)
                return proxyfied(result, tracker, result)  # type: ignore
            return result

        if inspect.iscoroutinefunction(self.fget):
            return async_wrapper
        else:
            return wrapper


@overload
def query(func: T) -> T:  # type: ignore
    ...


def query(  # type: ignore
    func: Callable[..., T] | Callable[..., Coroutine[None, None, T]]
) -> Callable[..., T] | Callable[..., Coroutine[None, None, T]]:
    new_func = Query(func)
    return update_wrapper(new_func, func)  # type: ignore


@overload
def managed(func: T) -> T:  # type: ignore
    ...


def managed(func):  # type: ignore
    new_func = Managed(func)
    return update_wrapper(new_func, func)
