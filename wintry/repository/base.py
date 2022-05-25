import inspect
from functools import lru_cache, partial
from typing import Any, Callable, Coroutine, List, Optional, Type, TypeVar
from wintry.errors.definitions import InternalServerError, InvalidRequestError
from wintry.models import _is_private_attr
from wintry import BACKENDS
from wintry.orm import __SQL_ENABLED_FLAG__, __WINTER_MAPPED_CLASS__
from wintry.sessions import MongoSessionTracker
from wintry.utils.keys import (
    __mappings_builtins__,
    __RepositoryType__,
    __winter_in_session_flag__,
    __winter_track_target__,
    __winter_tracker__,
    __winter_modified_entity_state__,
    __winter_old_setattr__,
    __winter_repo_old_init__,
    __winter_manage_objects__,
    __winter_session_key__,
    __winter_backend_identifier_key__,
    __winter_backend_for_repository__,
    __winter_repository_for_model__,
    __winter_repository_is_using_sqlalchemy__,
)

from sqlalchemy.exc import IntegrityError


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


def repository(
    entity: Type[T],
    for_backend: str = "default",
    table_name: Optional[str] = None,
    dry: bool = False,
    mongo_session_managed: bool = False,
    force_nosql: bool = False,
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

    def __winter_init__(self, *args, **kwargs):
        original_init = getattr(self, __winter_repo_old_init__)
        original_init(*args, **kwargs)

        # init tracker in the instance, because we do not
        # want to share trackers among repositories
        if mongo_session_managed:
            setattr(self, __winter_tracker__, MongoSessionTracker(entity, for_backend))

    def _runtime_method_parsing(cls: Type[TDecorated]) -> Type[TDecorated]:
        # Augment the repository with a special property to reference the backend this
        # repository is going to use
        setattr(cls, __winter_backend_identifier_key__, for_backend)

        # update the init method and save the original init
        setattr(cls, __winter_repo_old_init__, cls.__init__)

        # Need to stablish the signature of the new init as the old
        # one for the sake of the framework inspection
        sig = inspect.signature(cls.__init__)
        setattr(__winter_init__, "__signature__", sig)

        # replace the original init
        setattr(cls, "__init__", __winter_init__)

        if table_name is not None:
            setattr(entity, "__tablename__", table_name)

        # Prepare the repository with augmented properties
        setattr(cls, __winter_session_key__, None)
        if mongo_session_managed:
            setattr(cls, __winter_manage_objects__, True)

        def _getattribute(self: Any, __name: str) -> Any:
            using_sqlalchemy = super(cls, self).__getattribute__(  # type: ignore
                __winter_repository_is_using_sqlalchemy__
            )

            attr = super(cls, self).__getattribute__(__name)  # type: ignore
            # Need to call super on this because we need to obtain a session without passing
            # through this method
            session = super(cls, self).__getattribute__(__winter_session_key__)  # type: ignore
            try:
                new_attr = _parse_function_name(for_backend, __name, attr, entity, dry)  # type: ignore
            except Exception as e:
                return attr

            def wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                try:
                    result = new_attr(*args, session=session, **kwargs)
                except Exception as e:
                    handle_error(e)
                if not using_sqlalchemy and mongo_session_managed:
                    # Track the results, get the tracker instance from
                    # the repo instance
                    tracker = getattr(self, __winter_tracker__)
                    return proxyfied(result, tracker, result)  # type: ignore
                return result

            async def async_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                try:
                    result = await new_attr(*args, session=session, **kwargs)
                except Exception as e:
                    handle_error(e)
                if not using_sqlalchemy and mongo_session_managed:
                    tracker = getattr(self, __winter_tracker__)
                    return proxyfied(result, tracker, result)  # type: ignore
                return result

            def raw_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                try:
                    result = new_attr(*args, **kwargs)
                except Exception as e:
                    handle_error(e)
                if not using_sqlalchemy and mongo_session_managed:
                    # Track the results, get the tracker instance from
                    # the repo instance
                    tracker = getattr(self, __winter_tracker__)
                    return proxyfied(result, tracker, result)  # type: ignore
                return result

            async def async_raw_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                try:
                    result = await new_attr(*args, **kwargs)
                except Exception as e:
                    handle_error(e)
                if not using_sqlalchemy and mongo_session_managed:
                    tracker = getattr(self, __winter_tracker__)
                    return proxyfied(result, tracker, result)  # type: ignore
                return result

            if isinstance(new_attr, partial):
                if inspect.iscoroutinefunction(new_attr.func):
                    return async_wrapper
                else:
                    return wrapper
            elif inspect.iscoroutinefunction(new_attr) and is_raw(new_attr):
                return async_raw_wrapper
            elif (inspect.isfunction(new_attr) or inspect.ismethod(new_attr)) and is_raw(
                new_attr
            ):
                return raw_wrapper
            else:
                return new_attr

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
def _parse_function_name(
    backend: str, fname: str, fobject: Func, target: str | Type[Any], dry: bool = False
) -> Func:
    repo_backend = BACKENDS.get(backend, None)
    if repo_backend is None:
        raise RepositoryError(f"Not configured backend: {backend}")

    if is_processable(fobject):
        if inspect.iscoroutinefunction(fobject):
            return repo_backend.run_async(fname, target, dry_run=dry)
        else:
            return repo_backend.run(fname, target, dry_run=dry)
    else:
        return fobject


def handle_error(exc: Exception):
    match exc:
        case IntegrityError():
            raise InvalidRequestError(details={"error": str(exc)})
        case _:
            raise InternalServerError(details={"error": str(exc)})


def is_raw(func):
    return getattr(func, "_raw_method", False)
