from datetime import date, datetime
from types import GenericAlias, NoneType
from typing import Any, Callable, Iterable, Tuple, TypeVar, Union, get_args, overload
from dataclass_wizard import fromdict, fromlist
from dataclasses import Field, dataclass, fields, is_dataclass
from wintry.utils.keys import (
    __winter_in_session_flag__,
    __winter_tracker__,
    __winter_track_target__,
    __winter_modified_entity_state__,
    __winter_old_setattr__,
    __SQL_ENABLED_FLAG__
)
from wintry.sessions import MongoSessionTracker
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    Boolean,
    BINARY,
    Enum,
    ForeignKey,
    Table,
)
from sqlalchemy.orm import relation
from enum import Enum as std_enum
from wintry.orm import metadata, mapper_registry

_mapper: dict[type, type] = {
    int: Integer,
    str: String,
    float: Float,
    date: Date,
    datetime: DateTime,
    bool: Boolean,
    std_enum: Enum,
    bytes: BINARY,
}


T = TypeVar("T")


class ModelError(Exception):
    pass


def __dataclass_transform__(
    *,
    eq_default: bool = True,
    order_default: bool = False,
    kw_only_default: bool = False,
    field_descriptors: Tuple[Union[type, Callable[..., Any]], ...] = (()),
) -> Callable[[T], T]:
    # If used within a stub file, the following implementation can be
    # replaced with "...".
    return lambda a: a


def _is_private_attr(attr: str):
    return attr.startswith("_")


@overload
@__dataclass_transform__()
def model(cls: type[T], /) -> type[T]:
    ...


@overload
@__dataclass_transform__()
def model(cls: None, /) -> Callable[[type[T]], type[T]]:
    ...


@overload
@__dataclass_transform__()
def model(
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    match_args=True,
    kw_only=False,
    slots=False,
) -> Callable[[type[T]], type[T]]:
    ...


@__dataclass_transform__()
def model(
    cls: type[T] | None = None,
    /,
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    match_args=True,
    kw_only=False,
    slots=False,
) -> type[T] | Callable[[type[T]], type[T]]:
    def make_proxy_ref(cls: type[T]) -> type[T]:
        """
        Transform the given class in a Tracked entity.

        Tracked entities are used to automatically synchronize
        database with entities actions. This is done pretty nicely
        by SQLAlchemy session, but Motor (PyMongo) does not have the same
        goodness. So we must hand code one. This function augment the
        given entity so whenever a non_private attribute is being set,
        it is added to the tracker Updated set, and when an entity is created,
        it is added to the tracker's Created set. This resembles a little bit
        the states transitions in SQLAlchemy, but it is a lot simpler.

        Augmentation should work at instance level so we do not poison
        the global class, ie, proxy should check for specific flags so we
        can act on the instance. Flags must not be added directly to the
        class to avoid race conditions.
        """

        def _winter_proxied_setattr_(self, __name: str, __value: Any) -> None:
            # Check for presence of some state flag
            # same as self.__winter_in_session_flag__
            if getattr(self, __winter_in_session_flag__, False) and not _is_private_attr(__name):
                # all instances marked with __winter_in_session_flag__ should be augmented with
                # a __winter_track_target__ which contains the tracker
                # being marked for a session and not contain the tracker is an error

                # leave it to fail if no tracker present
                tracker: MongoSessionTracker = getattr(self, __winter_tracker__)
                target = getattr(self, __winter_track_target__)

                # Check for modified flag, so we ensure that this object is addded just once
                modified = getattr(target, __winter_modified_entity_state__, False)

                if not modified:
                    tracker.add(target)
                    setattr(target, __winter_modified_entity_state__, True)

            return super(cls, self).__setattr__(__name, __value)  # type: ignore

        cls = dataclass(
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=frozen,
            match_args=match_args,
            kw_only=kw_only,
            slots=slots,
        )(cls)

        # For each field in the dataclass, we recurse making a deep proxy ref
        # This is done at class creation, so not a big deal

        # save the old __setattr__ just in case. For future use
        setattr(cls, __winter_old_setattr__, cls.__setattr__)
        cls.__setattr__ = _winter_proxied_setattr_  # type: ignore
        return cls

    if cls is None:
        return make_proxy_ref
    else:
        return make_proxy_ref(cls)


def get_primary_key(_type: type) -> Field:
    for field in fields(_type):
        if field.name.lower() == "id" or field.metadata.get("id", False):
            return field

    raise ModelError(f"Model {_type} has not an id field or a field with metadata marked as an id")


def discard_nones(iterable: Iterable[type]) -> list[type]:
    return list(filter(lambda x: x != NoneType, iterable))


def resolve_generic_type_or_die(_type: type):
    """
    Get a simple or generic type and try to resolve it
    to the canonical form.

    Example:
    =======

    >>> resolve_generic_type_or_die(list[list[int | None]])
    >>> int

    Generic types can be nested, but this function aimed to resolve a table
    reference, so it must be constrained to at most 1 Concrete type or None.
    Like so, the following is an error:

    >>> resolve_generic_type_or_die(list[int | str])
    """

    # Base case, get_args(int) = ()
    concrete_types = get_args(_type)

    if not concrete_types:
        return _type

    # Ok, we got nested generics, maybe A | None
    # clean it up
    cleaned_types = discard_nones(concrete_types)

    # If we get a list with more than one element, then this was not
    # a single Concrete type  generic, so panic
    if len(cleaned_types) != 1:
        raise ModelError(
            f"Model cannot have a field configured for either {'or '.join(str(t) for t in cleaned_types)}"
        )

    return resolve_generic_type_or_die(cleaned_types[0])


def make_column_from_field(model: type, field: Field) -> Column | tuple[Column, dict[str, Any]] | None:
    if field.type in _mapper:
        sql_type = _mapper[field.type]
        # Check a configuration from metadata to check if this is
        # a primary key. We put primary key if metadata['id'] is set
        # or the field name is id (Ignoring case)
        if field.name.lower() == "id" or field.metadata.get("id", False):
            return Column(field.name, sql_type, primary_key=True)
        return Column(field.name, sql_type)
    else:
        # This is an object, not builtin, it probably is a reference to
        # another model. We check in the metadata for a 'not_persisted'
        # option and move to configure the relation
        if field.metadata.get("not_persisted", False):
            return

        if isinstance(field.type, GenericAlias) and field.type.__origin__ == list:
            return

        _type = resolve_generic_type_or_die(field.type)

        # If type is not an instance of dataclass, then also ignores it
        if not is_dataclass(_type):
            return

        # Ok, just do it, configure a relationship
        foreign_key = get_primary_key(_type)
        foreign_key_type = _mapper.get(foreign_key.type)
        foreign_key_column = Column(
            f"{field.name}_id", foreign_key_type, ForeignKey(getattr(_type, foreign_key.name))
        )

        for f in fields(_type):
            if f.type == list[model]:  # type: ignore
                # if isinstance(f.type, list) and get_args(f.type) == field.type:
                related_column = {field.name: relation(_type, lazy="joined", backref=f.name)}
                return foreign_key_column, related_column

        return foreign_key_column, {field.name: relation(_type, lazy="joined")}


@__dataclass_transform__()
def entity(
    cls: type[T] | None = None,
    /,
    *,
    name: str | None = None,
    create_metadata: bool = False,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    match_args=True,
    kw_only=False,
    slots=False,
    metadata=metadata
) -> type[T] | Callable[[type[T]], type[T]]:
    def _create_metadata(_cls: type[T]) -> type[T]:
        _cls = model(
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=frozen,
            match_args=match_args,
            kw_only=kw_only,
            slots=slots,
        )(_cls)

        if create_metadata:
            columns: list[Column] = []
            properties: dict[str, Any] = {}

            for field in fields(_cls):
                col_or_cols = make_column_from_field(_cls, field)
                if col_or_cols is not None:
                    if isinstance(col_or_cols, Column):
                        columns.append(col_or_cols)
                    else:
                        col, props = col_or_cols
                        properties.update(props)
                        columns.append(col)

            table_name = name or _cls.__name__.lower() + "s"
            table = Table(table_name, metadata, *columns)

            mapper_registry.map_imperatively(_cls, table, properties=properties)

            setattr(_cls, __SQL_ENABLED_FLAG__, True)

        return _cls

    if cls is None:
        return _create_metadata
    else:
        return _create_metadata(cls)


__all__ = ["model", "_is_private_attr", "entity"]
