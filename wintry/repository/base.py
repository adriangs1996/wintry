import inspect
from functools import lru_cache, partial, update_wrapper
from typing import (
    Any,
    Callable,
    Coroutine,
    Iterable,
    List,
    SupportsIndex,
    Type,
    TypeVar,
    overload,
)

from sqlalchemy.exc import IntegrityError
from wintry import BACKENDS
from wintry.errors.definitions import InternalServerError, InvalidRequestError
from wintry.models import Model, _is_private_attr
from wintry.orm.mapping import __SQL_ENABLED_FLAG__, __WINTER_MAPPED_CLASS__
from wintry.sessions import Tracker
from wintry.settings import EngineType
from wintry.utils.decorators import alias
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
    __wintry_model_instance_phantom_fk__,
)
from wintry.utils.virtual_db_schema import (
    get_model_fields_names,
    get_model_sql_table,
    get_model_table_metadata,
)


class RepositoryError(Exception):
    pass


T = TypeVar("T")
TDecorated = TypeVar("TDecorated")

RuntimeDecorator = Callable[[Type[TDecorated]], Type[TDecorated]]
RuntimeParsedMethod = partial[Any], partial[Coroutine[Any, Any, Any]]
Func = Callable[..., Any]


class ProxyList(list[Model]):
    def set_tracking_info(self, tracker: Tracker, instance: Model):
        self.tracker = tracker
        self.instance = instance
        self.regs = False

    def track_new_obj(self, obj: Model):
        # Adding a new object to a list in a SQL ORM fashion
        # carries two consequences:
        # - First: The new obj should be tracked by Tracker
        # - Second: Obj should get populated its phantom
        #           foreign keys with the key name of the
        #           relation or its present foreign key
        #           with the current instance

        # Need to do some work here because is necessary to tell
        # if this relation is through a phantom fk or a concrete
        # one
        obj_table = get_model_table_metadata(type(obj))
        model_fields = get_model_fields_names(type(obj))

        for fk in obj_table.foreing_keys:
            if fk.target == type(self.instance):
                if fk.key_name not in model_fields:
                    # it is a phantom fk
                    instance_id_value = list(self.instance.ids().values())[0]
                    phantom_fks = getattr(obj, __wintry_model_instance_phantom_fk__, {})
                    phantom_fks[fk.key_name] = instance_id_value
                    setattr(obj, __wintry_model_instance_phantom_fk__, phantom_fks)
                else:
                    # is a concrete fk
                    setattr(obj, fk.key_name, self.instance)

        setattr(obj, __winter_track_target__, obj)
        self.tracker.new(obj)

    def track_obj_removal(self, obj: Model):
        obj_table = get_model_table_metadata(type(obj))
        model_fields = get_model_fields_names(type(obj))

        for fk in obj_table.foreing_keys:
            if fk.target == type(self.instance):
                if fk.key_name not in model_fields:
                    # it is a phantom fk
                    phantom_fks = getattr(obj, __wintry_model_instance_phantom_fk__, {})
                    phantom_fks[fk.key_name] = None
                    setattr(obj, __wintry_model_instance_phantom_fk__, phantom_fks)
            else:
                # is a concrete fk
                setattr(obj, fk.key_name, None)

        setattr(obj, __winter_track_target__, obj)
        self.tracker.add(obj)

    def track(self):
        # Check for modified flag, so we ensure that this object is addded just once
        modified = getattr(self.instance, __winter_modified_entity_state__, False)
        if not modified and not self.regs:
            self.tracker.add(self.instance)
            self.regs = True
            setattr(self.instance, __winter_modified_entity_state__, True)

    def append(self, __object: Model) -> None:
        if (
            getattr(self.instance, "__wintry_engine_type_in_instance__", EngineType.NoEngine)
            == EngineType.Sql
        ):
            self.track_new_obj(__object)
        else:
            self.track()
        return super().append(__object)

    def remove(self, __value: Model) -> None:
        if (
            getattr(self.instance, "__wintry_engine_type_in_instance__", EngineType.NoEngine)
            == EngineType.Sql
        ):
            self.track_obj_removal(__value)
        else:
            self.track()
        return super().remove(__value)

    def extend(self, __iterable: Iterable[Model]) -> None:
        if (
            getattr(self.instance, "__wintry_engine_type_in_instance__", EngineType.NoEngine)
            == EngineType.Sql
        ):
            for obj in __iterable:
                self.track_new_obj(obj)
        else:
            self.track()
        return super().extend(__iterable)

    def pop(self, __index: SupportsIndex = ...) -> Model:
        obj = super().pop(__index)

        if (
            getattr(self.instance, "__wintry_engine_type_in_instance__", EngineType.NoEngine)
            == EngineType.Sql
        ):
            self.track_obj_removal(obj)
        else:
            self.track()

        return obj


def proxyfied(result: Any | list[Any], tracker, origin: Any, engine_type: EngineType):
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
        # Ignore already proxified objects. This might not be
        # true very often because this is only used when querying
        # for objects that hasn't already been commited to the db
        if getattr(result, "__wintry_proxy_processed_object__", False):
            return result
        for k, v in vars(result).items():
            # Proxify recursively this instance.
            # Ignore private attributes as well as builtin ones
            if not _is_private_attr(k) and not v.__class__ in __mappings_builtins__:
                if isinstance(v, list):
                    # If this is a list, we must convert it to a proxylist
                    # to allow for append and remove synchronization
                    proxy_list = ProxyList(
                        proxyfied(val, tracker, origin, engine_type) for val in v
                    )
                    # Set tracking information for the list
                    if engine_type == EngineType.NoSql:
                        proxy_list.set_tracking_info(tracker, origin)
                    else:
                        proxy_list.set_tracking_info(tracker, result)
                    # Update value for k
                    setattr(result, k, proxy_list)
                else:
                    # Update value for K with a Proxified version
                    setattr(result, k, proxyfied(v, tracker, origin, engine_type))

        # Augment instance with special variables so tracking is possible
        # Set track target (this allow to child objects to reference the root entity)
        if engine_type == EngineType.NoSql:
            setattr(result, __winter_track_target__, origin)
        else:
            setattr(result, __winter_track_target__, result)

        setattr(result, "__wintry_engine_type_in_instance__", engine_type)

        # Mark this instance as being tracked by a session
        setattr(result, __winter_in_session_flag__, True)
        # Save the repo tracker associated with this instance
        setattr(result, __winter_tracker__, tracker)
        # Set the instance state (not modified)
        setattr(result, __winter_modified_entity_state__, False)
        setattr(result, "__wintry_proxy_processed_object__", True)
        return result
    else:
        if isinstance(origin, list):
            return list(proxyfied(r, tracker, r, engine_type) for r in result)
        else:
            return list(proxyfied(r, tracker, origin, engine_type) for r in result)


def is_processable(method: Callable[..., Any]) -> bool:
    try:
        return method.__name__ != "__init__" and not getattr(method, "_raw_method", False)
    except:
        return False


def marked(method: Callable[..., Any]) -> bool:
    return not getattr(method, "_raw_method", False)


FuncT = TypeVar("FuncT", bound=Callable[..., Any])


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


def track_result_instances(instance: Model | list[Model], tracker: Tracker):
    if isinstance(instance, list):
        for i, obj in enumerate(instance):
            if obj in tracker:
                instance[i] = tracker.get_tracked_instance(obj)
            else:
                tracker.track(obj)
    else:
        if instance in tracker:
            instance = tracker.get_tracked_instance(instance)
        else:
            tracker.track(instance)

    return instance


class Managed:
    def __init__(self, fget=None):
        self.fget = fget
        self.driver_class: EngineType | None = None

    def __set_name__(self, owner, name):
        self.__winter_owner__ = owner

    def __get__(self, obj, objtype=None):
        __no_sql_session_manged__ = getattr(obj, "__nosql_session_managed__", False)

        if self.driver_class is None:
            backend = getattr(
                self.__winter_owner__, __winter_backend_identifier_key__, "default"
            )
            bkd = BACKENDS[backend]
            assert bkd.driver is not None
            self.driver_class = bkd.driver.driver_class

        def raw_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
            try:
                result = self.fget(obj, *args, **kwargs)
            except Exception as e:
                handle_error(e)
            if __no_sql_session_manged__:
                # Track the results, get the tracker instance from
                # the repo instance
                tracker = getattr(obj, __winter_tracker__)
                result = track_result_instances(result, tracker)
                return proxyfied(result, tracker, result, self.driver_class)  # type: ignore
            return result

        async def async_raw_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
            try:
                result = await self.fget(obj, *args, **kwargs)
            except Exception as e:
                handle_error(e)
            if __no_sql_session_manged__:
                tracker = getattr(obj, __winter_tracker__)
                result = track_result_instances(result, tracker)
                return proxyfied(result, tracker, result, self.driver_class)  # type: ignore
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
        self.__func_application__ = None
        self.driver_class = None

    def __set_name__(self, owner, name):
        self.__winter_name__ = name
        self.__winter_owner__ = owner

    def __get__(self, obj, objtype=None):
        dry = getattr(self.__winter_owner__, "__dry__", False)
        backend = getattr(
            self.__winter_owner__, __winter_backend_identifier_key__, "default"
        )
        ent = getattr(self.__winter_owner__, "__winter_entity__")

        if self.__func_application__ is None:
            self.__func_application__ = _parse_function_name(
                backend, self.__winter_name__, self.fget, ent, dry
            )

        __no_sql_session_manged__ = getattr(obj, "__nosql_session_managed__", False)

        session = getattr(obj, __winter_session_key__, None)

        if self.driver_class is None:
            backend = getattr(
                self.__winter_owner__, __winter_backend_identifier_key__, "default"
            )
            bkd = BACKENDS[backend]
            assert bkd.driver is not None
            self.driver_class = bkd.driver.driver_class

        def wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
            try:
                result = self.__func_application__(*args, session=session, **kwargs)  # type: ignore
            except Exception as e:
                handle_error(e)
            if __no_sql_session_manged__:
                # Track the results, get the tracker instance from
                # the repo instance
                tracker = getattr(obj, __winter_tracker__)
                result = track_result_instances(result, tracker)
                return proxyfied(result, tracker, result, self.driver_class)  # type: ignore
            return result

        async def async_wrapper(*args: Any, **kwargs: Any) -> List[T] | T | None:
            try:
                result = await self.__func_application__(*args, session=session, **kwargs)  # type: ignore
            except Exception as e:
                print(e)
                handle_error(e)
            if __no_sql_session_manged__:
                tracker = getattr(obj, __winter_tracker__)
                result = track_result_instances(result, tracker)
                return proxyfied(result, tracker, result, self.driver_class)  # type: ignore
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


@alias(managed)
def raw_method(method: FuncT) -> FuncT:
    ...
