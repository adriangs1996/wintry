from datetime import date, datetime
from types import GenericAlias, NoneType
from typing import (
    Any,
    Callable,
    ClassVar,
    Iterable,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    get_args,
    overload,
)
from typing_extensions import Self
from dataclass_wizard import fromdict, fromlist
from dataclasses import Field, asdict, dataclass, field, fields, is_dataclass
from wintry.utils.keys import (
    __winter_in_session_flag__,
    __winter_tracker__,
    __winter_track_target__,
    __winter_modified_entity_state__,
    __winter_old_setattr__,
    __SQL_ENABLED_FLAG__,
    __winter_model_collection_name__,
)
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
    MetaData,
    inspect,
)
from sqlalchemy.orm import relation, relationship
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


_builtin_str_mapper: dict[str, type] = {
    "int": int,
    "str": str,
    "float": float,
    "date": date,
    "datetime": datetime,
    "bool": bool,
    "Enum": std_enum,
    "bytes": bytes,
}

sequences = [list, set, Iterable, Sequence]


T = TypeVar("T")


class ModelError(Exception):
    pass


class ModelOperationError(Exception):
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


class ModelRegistry:
    models: ClassVar[dict[str, type["Model"]]] = {}

    @classmethod
    def get_all_models(cls) -> list[type["Model"]]:
        return list(cls.models.values())

    @classmethod
    def get_model_by_str(cls, model_str: str) -> type["Model"] | None:
        return cls.models.get(model_str, None)

    @classmethod
    def register(cls, model_declaration: type["Model"]):
        model_name = model_declaration.__name__
        cls.models[model_name] = model_declaration


def get_type_by_str(type_str: str):
    return ModelRegistry.get_model_by_str(type_str) or _builtin_str_mapper.get(
        type_str, None
    )


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
    name=None,
    mapped=True,
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
    name=None,
    mapped=True,
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
            if getattr(self, __winter_in_session_flag__, False) and not _is_private_attr(
                __name
            ):
                # all instances marked with __winter_in_session_flag__ should be augmented with
                # a __winter_track_target__ which contains the tracker
                # being marked for a session and not contain the tracker is an error

                # leave it to fail if no tracker present
                tracker = getattr(self, __winter_tracker__)
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
        table_name = name or cls.__name__.lower() + "s"
        setattr(cls, __winter_model_collection_name__, table_name)
        cls.__setattr__ = _winter_proxied_setattr_  # type: ignore

        # Register model if it is mapped
        if mapped:
            ModelRegistry.register(cls)  # type: ignore
        return cls

    if cls is None:
        return make_proxy_ref
    else:
        return make_proxy_ref(cls)


def get_primary_key(_type: type) -> Field:
    for field in fields(_type):
        if field.name.lower() == "id" or field.metadata.get("id", False):
            return field

    raise ModelError(
        f"Model {_type} has not an id field or a field with metadata marked as an id"
    )


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


def make_column_from_field(
    model: type, field: Field
) -> Column | tuple[Column, dict[str, Any]] | None:
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
            f"{field.name}_id",
            foreign_key_type,
            ForeignKey(getattr(_type, foreign_key.name)),
        )

        for f in fields(_type):
            if f.type == list[model]:  # type: ignore
                # if isinstance(f.type, list) and get_args(f.type) == field.type:
                related_column = {
                    field.name: relation(_type, lazy="joined", backref=f.name)
                }
                return foreign_key_column, related_column

        return foreign_key_column, {field.name: relation(_type, lazy="joined")}


class RelationTag(std_enum):
    one_to_many = 0
    many_to_one = 1
    one_to_one = 2
    one_to_none = 4
    many_to_none = 8


@dataclass
class Relation:
    with_model: type["Model"]
    field_name: str
    tag: RelationTag
    backref: str = ""


@dataclass
class ForeignKeyInfo:
    target: type["Model"]
    key_name: str

    def __eq__(self, __o: "ForeignKeyInfo") -> bool:
        return self.key_name == __o.key_name


@dataclass
class RelationWithForeignKey:
    foreign_key: ForeignKeyInfo
    relation: Relation


@dataclass
class TableMetadata:
    metadata: MetaData
    table_name: str
    model: type["Model"]
    foreing_keys: list[ForeignKeyInfo] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    columns: list[Field] = field(default_factory=list)

    def many_to_one_relation(self, field: Field) -> Relation:
        # Here we have a many_to relation, the other endpoint must define either
        # a foreign_key to this model, either if it is not explicit
        target_model = resolve_generic_type_or_die(field.type)  # type: ignore
        if isinstance(target_model, str):
            target_model = ModelRegistry.get_model_by_str(target_model)

        if target_model is None:
            raise ModelError(f"{field.type} is not registered as Model.")
        # Specify the foreign key as a reverse foreing key on the target_model.
        # For this we need to append the foreign key to the target model virtual
        # table schema, if it does not already exists
        foreign_key = ForeignKeyInfo(self.model, f"{self.model.__name__.lower()}_id")

        # Resolve the other endpoint table
        target_virtual_table = VirtualDatabaseSchema[target_model]
        if target_virtual_table is None:
            # Create the table but do not autobegin it
            target_virtual_table = TableMetadata(
                metadata=self.metadata,
                table_name=getattr(target_model, __winter_model_collection_name__),
                model=target_model,
            )
        # Add the foreign key
        if foreign_key not in target_virtual_table.foreing_keys:
            target_virtual_table.foreing_keys.append(foreign_key)

        # Return the many to one relation
        return Relation(target_model, field.name, RelationTag.many_to_one)

    def dispatch_column_type_for_field(self, field: Field) -> None:
        if isinstance(field.type, str):
            field.type = get_type_by_str(field.type)
        if field.type in _mapper:
            self.columns.append(field)
            return

        if isinstance(field.type, GenericAlias) and field.type.__origin__ in sequences:
            self.relations.append(self.many_to_one_relation(field))
            return

        _type = resolve_generic_type_or_die(field.type)

        if isinstance(_type, str):
            _type = get_type_by_str(_type)

        # If type is not an instance of dataclass, then also ignores it
        if not is_dataclass(_type):
            return

        # At this point, this is a one_to relation, so we just add a foreing key and a
        # relation
        foregin_key = ForeignKeyInfo(_type, f"{field.name}_id")
        relationship = Relation(
            with_model=_type, field_name=field.name, tag=RelationTag.one_to_one
        )

        if foregin_key not in self.foreing_keys:
            self.foreing_keys.append(foregin_key)

        self.relations.append(relationship)

    def autobegin(self):
        for field in fields(self.model):
            self.dispatch_column_type_for_field(field)

    def __hash__(self) -> int:
        return hash(self.table_name)


class VirtualDatabaseMeta(type):
    def __getitem__(self, key: type["Model"]) -> TableMetadata | None:
        return self.tables.get(key, None)  # type: ignore

    def __setitem__(self, key: type["Model"], value: TableMetadata):
        self.tables[key] = value  # type: ignore


class VirtualDatabaseSchema(metaclass=VirtualDatabaseMeta):
    tables: dict[type["Model"], TableMetadata] = {}

    @staticmethod
    def create_table_for_model(model: type["Model"], table_metadata: TableMetadata):
        columns: list[Column] = []

        for c in table_metadata.columns:
            column_type = _mapper[c.type]
            if c.name.lower() == "id" or c.metadata.get("id", False):
                columns.append(Column(c.name, column_type, primary_key=True))
            else:
                columns.append(Column(c.name, column_type))

        try:
            get_primary_key(model)
        except ModelError:
            columns.append(Column("id", Integer, primary_key=True, autoincrement=True))

        for fk in table_metadata.foreing_keys:
            try:
                foreign_key = get_primary_key(fk.target)
                foreign_key_type = _mapper.get(foreign_key.type)
                columns.append(
                    Column(
                        fk.key_name,
                        foreign_key_type,
                        ForeignKey(
                            f"{getattr(fk.target, __winter_model_collection_name__)}.{foreign_key.name}"
                        ),
                        nullable=True,
                    )
                )
            except ModelError:
                columns.append(
                    Column(
                        fk.key_name,
                        Integer,
                        ForeignKey(f"{getattr(fk.target, __winter_model_collection_name__)}.id"),
                        nullable=True,
                    )
                )

        properties = {}

        for rel in table_metadata.relations:
            other_endpoint = None
            endpoint_metadata = VirtualDatabaseSchema[rel.with_model]
            assert endpoint_metadata is not None

            for fk_rel in endpoint_metadata.relations:
                if fk_rel.with_model == model:
                    other_endpoint = fk_rel.field_name

            if other_endpoint is None:
                properties[rel.field_name] = relationship(rel.with_model, lazy="joined")
            else:
                properties[rel.field_name] = relationship(
                    rel.with_model, lazy="joined", back_populates=other_endpoint
                )

        mapper_registry.map_imperatively(
            model,
            Table(table_metadata.table_name, table_metadata.metadata, *columns),
            properties=properties,
        )

    @classmethod
    def use_sqlalchemy(cls, metadata: MetaData = metadata):
        """Configure the registered models to use sqlalchemy as the database engine.
        This is also the place where we can build DatabaseSchemas. Right now this is
        only supported for SQLAlchemy, but in the future, Also MongoDB would be configured
        with sharded documents, refs relations, etc.

        Args:
            metadata(MetaData): the metadata to use for SQLAlchemy Tables.

        Returns:
            None

        """
        for model in ModelRegistry.get_all_models():
            table = cls[model]
            if table is None:
                table = TableMetadata(
                    metadata=metadata,
                    table_name=getattr(model, __winter_model_collection_name__),
                    model=model,
                )
                cls[model] = table

            table.autobegin()

        for model, table_metadata in cls.tables.items():
            if not inspect(model, raiseerr=False):
                # only create tables for models that are not already
                # mapped. This is needed to ensure compatibility with
                # the for_model function from orm module
                VirtualDatabaseSchema.create_table_for_model(model, table_metadata)

    @classmethod
    def use_nosql(cls):
        """Configure the registered models to use nosql engine.
        This method Remains empty for now, as there is no specific (yet) config to do
        for either engine. Here we should augment model with special variables, but this is
        discourage, unless there is not other choice."""
        pass


@__dataclass_transform__()
class ModelMeta(type):
    pass


class Model(metaclass=ModelMeta):
    def __init_subclass__(
        cls,
        name: str | None = None,
        init=True,
        repr=True,
        eq=True,
        order=False,
        unsafe_hash=False,
        frozen=False,
        match_args=True,
        kw_only=False,
        mapped=True,
    ) -> None:
        cls = model(
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=frozen,
            match_args=match_args,
            kw_only=kw_only,
            slots=False,
            name=name,
            mapped=mapped,
        )(cls)

    @overload
    @classmethod
    def build(cls, _dict: dict[str, Any]) -> Self:
        ...

    @overload
    @classmethod
    def build(cls, _dict: list[dict[str, Any]]) -> list[Self]:
        ...

    @classmethod
    def build(cls, _dict: dict[str, Any] | list[dict[str, Any]]) -> Self | list[Self]:
        if isinstance(_dict, list):
            return fromlist(cls, _dict)
        return fromdict(cls, _dict)

    def to_dict(self):
        return asdict(self)


__all__ = ["model", "_is_private_attr"]
