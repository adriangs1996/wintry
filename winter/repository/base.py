from datetime import date, datetime
from enum import Enum
from functools import lru_cache, partial
from typing import Any, Callable, Coroutine, List, Optional, Set, Type, TypeVar
import inspect
from pydantic import BaseModel

from winter.backend import Backend
from winter.orm import __SQL_ENABLED_FLAG__
import inspect
from winter.orm import __WINTER_MAPPED_CLASS__
import jsons


__mappings_builtins__ = (int, str, Enum, float, bool, bytes, date, datetime)

__sequences_like__ = (dict, list, set)


class RepositoryError(Exception):
    pass


T = TypeVar("T", Any, BaseModel)
TDecorated = TypeVar("TDecorated")

RuntimeDecorator = Callable[[Type[TDecorated]], Type[TDecorated]]
RuntimeParsedMethod = partial[Any], partial[Coroutine[Any, Any, Any]]
Func = Callable[..., Any]


def is_processable(method: Callable[..., Any]) -> bool:
    try:
        return method.__name__ != "__init__" and not getattr(method, "_raw_method", False)
    except:
        return False


def marked(method: Callable[..., Any]) -> bool:
    return not getattr(method, "_raw_method", False)


def _map_to_inner_model_class(_table_instance: Any) -> Any:
    """
    Generate a new object with keys from `vars` where values are either
    builins or mapped classes.
    """

    # This is needed 'cuz when a driver returns an result object,
    # it is usually populated with weird fields or it is just
    # augmented with data that our simple entity does not expect
    # for example ForeignKeys. Lets just get rid of them and try to
    # make the best effort to use a valid kw to the entity constructor
    instance_class = _table_instance.__class__
    target_class = getattr(instance_class, __WINTER_MAPPED_CLASS__, None)

    if target_class is None:
        return _table_instance

    initial_dict = vars(_table_instance)

    # Dive recursively into the dictionary, so nested
    # objects get mapped
    for key, value in initial_dict.items():
        class_ = value.__class__
        if class_ not in __mappings_builtins__:
            if class_ in __sequences_like__:
                new_list = [_map_to_inner_model_class(ent) for ent in value]
                initial_dict[key] = new_list
            else:
                new_obj = _map_to_inner_model_class(value)
                initial_dict[key] = new_obj

    _constructor_params = _get_type_constructor_params(target_class)
    valid_keys = _constructor_params.intersection(initial_dict.keys())
    valid_values = {k: initial_dict[k] for k in valid_keys}

    try:
        return target_class(**valid_values)
    except:
        return _table_instance


def build_from_dict(entity: Any, instance: dict[str, Any]) -> Any:
    return jsons.load(instance, entity)


@lru_cache
def _get_type_constructor_params(_type: Type[Any]) -> Set[str]:
    entity_constructor_signature = inspect.signature(_type)
    return set(entity_constructor_signature.parameters.keys())


def map_result_to_entity(entity: Type[T], result: List[Any] | Any | None) -> List[T] | T | None:
    if isinstance(result, list):
        try:
            # Try to build from a list using from_orm
            return [entity.from_orm(instance) for instance in result]  # type: ignore
        except:
            try:
                # try to build from list of dicts
                return [build_from_dict(entity, instance) for instance in result]  # type: ignore
            except:
                # try to build from list of objects with no from_orm configuration
                try:
                    return [entity(**instance) for instance in result] #type: ignore
                except:
                    try:
                        return [_map_to_inner_model_class(instance) for instance in result]  # type: ignore
                    except:
                        return result

    try:
        # try to build from object with from_orm
        return entity.from_orm(result)  # type: ignore
    except:
        try:
            # try to build from object if it is a dict
            return build_from_dict(entity, result)  # type: ignore
        except:
            try:
                return entity(**result) #type: ignore
            except:
            # try to build from object using its defined vars
                try:
                    return _map_to_inner_model_class(result)
                except:
                    return result


def repository(
    entity: Type[T], table_name: Optional[str] = None, dry: bool = False
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
    >>> user = loop.run_until_complete(repo.get_by_id(id=2)) # It works!
    >>>                                                      # And if an user exists, it automatically retrieves an
    >>>                                                      # `User` instance. Use MongoDB by default

    """

    def _runtime_method_parsing(cls: Type[TDecorated]) -> Type[TDecorated]:
        def _getattribute(self: Any, __name: str) -> Any:
            if (__target := getattr(entity, __SQL_ENABLED_FLAG__, None)) is not None:
                target_name = __target  # type: ignore
            else:
                target_name = table_name or f"{entity.__name__}s".lower()  # type: ignore

            attr = super(cls, self).__getattribute__(__name)  # type: ignore
            # Need to call super on this because we need to obtain a session without passing
            # through this method
            session = super(cls, self).__getattribute__("session")  # type: ignore
            use_session = False
            new_attr = _parse_function_name(__name, attr, target_name, dry)  # type: ignore

            def wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                if use_session:
                    result = new_attr(*args, session=session, **kwargs)
                else:
                    result = new_attr(*args, **kwargs)
                return map_result_to_entity(entity, result)

            async def async_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
                if use_session:
                    result = await new_attr(*args, session=session, **kwargs)
                else:
                    result = await new_attr(*args, **kwargs)
                return map_result_to_entity(entity, result)  # type: ignore

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
