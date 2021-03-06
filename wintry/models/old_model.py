from datetime import date, datetime
from functools import cache
from mashumaro import DataClassDictMixin
from mashumaro.dialect import Dialect
from mashumaro import config
from types import GenericAlias, NoneType
from typing import (
    Any,
    ClassVar,
    Annotated,
    Callable,
    ClassVar,
    ForwardRef,
    Generator,
    Iterable,
    Literal,
    Mapping,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    Optional,
    List,
    Dict,
    Set,
    ItemsView,
    Iterator,
    cast,
    get_args,
    overload,
    NewType,
)

from pydantic.fields import Undefined
from typing_extensions import Self
from uuid import uuid4
from dataclass_wizard.enums import LetterCase
from dataclasses import (
    MISSING,
    Field,
    asdict,
    dataclass,
    field,
    fields,
    is_dataclass,
)
from wintry.generators import AutoIncrement, Increment
from wintry.query.nodes import EqualToNode, GreaterThanNode, LowerThanNode
from wintry.utils.decorators import alias
from wintry.utils.keys import (
    __winter_in_session_flag__,
    __winter_tracker__,
    __winter_track_target__,
    __winter_modified_entity_state__,
    __winter_old_setattr__,
    __SQL_ENABLED_FLAG__,
    __winter_model_collection_name__,
    __winter_model_primary_keys__,
    __winter_model_instance_state__,
    __winter_model_fields_set__,
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
from sqlalchemy.orm import relationship, backref
from enum import Enum as std_enum
from wintry.orm.mapping import metadata, mapper_registry
from pydantic import BaseModel

from wintry.utils.type_helpers import resolve_generic_type_or_die
from wintry.generators import code_gen

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


class ModelRegistry(object):
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

    @classmethod
    def configure(cls):
        for model in cls.get_all_models():
            # Configure generate this model from_orm method
            try:
                code_gen.model_from_orm(model, globals() | ModelRegistry.models.copy())
                code_gen.compile(globals() | ModelRegistry.models.copy())
            except NameError as e:
                print(e)

                @classmethod
                def from_orm(cls, obj: Any):
                    code_gen.model_from_orm(
                        cls, globals() | ModelRegistry.models.copy(), locals()
                    )
                    code_gen.compile(globals() | ModelRegistry.models.copy())

                setattr(cls, "from_orm", from_orm)

            # Compile the map method
            try:
                code_gen.map_to(model, globals() | ModelRegistry.models.copy(), locals())
                text = code_gen.compile(
                    globals() | ModelRegistry.models.copy(), return_=True
                )
                print(text)
            except NameError as e:
                print(e)

                def map_(self, _dict: dict[str, Any]):
                    code_gen.map_to(
                        model, globals() | ModelRegistry.models.copy(), locals()
                    )
                    code_gen.compile(globals() | ModelRegistry.models.copy())

                setattr(model, "map", map_)


def get_type_by_str(type_str: str):
    new_ = ModelRegistry.get_model_by_str(type_str) or _builtin_str_mapper.get(
        type_str, None
    )
    if new_ is None:
        return eval(type_str, globals() | ModelRegistry.models.copy(), locals())


def get_primary_key(_type: type) -> Field:
    for field in fields(_type):
        if field.name.lower() == "id" or field.metadata.get("id", False):
            return field

    raise ModelError(
        f"Model {_type} has not an id field or a field with metadata marked as an id"
    )


def is_iterable(model: type):
    return isinstance(model, GenericAlias) and model.__origin__ in sequences


def resolve_field_type(field: Field):
    t = resolve_generic_type_or_die(field.type)
    if isinstance(t, str):
        t = ModelRegistry.get_model_by_str(t)
    elif isinstance(t, ForwardRef):
        str_type = t.__forward_arg__
        t = ModelRegistry.get_model_by_str(str_type)
    return t


def is_one_to_one(model: type, with_: type):
    right = False
    for field in fields(with_):
        t = resolve_field_type(field)
        if not is_iterable(field.type) and t == model or t == (model | None):
            right = True
            break

    left = False
    for field in fields(model):
        t = resolve_field_type(field)
        if not is_iterable(field.type) and t == with_ or t == (with_ | None):
            left = True
            break

    return left and right


@dataclass
class Relation:
    with_model: type["Model"]
    field_name: str
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
    many_to_one_relations: list[Relation] = field(default_factory=list)

    def many_to_one_relation(self, field: Field) -> Relation:
        # Here we have a many_to relation, the other endpoint must define either
        # a foreign_key to this model, either if it is not explicit
        target_model = resolve_generic_type_or_die(field.type)  # type: ignore
        if isinstance(target_model, str):
            target_model = ModelRegistry.get_model_by_str(target_model)
        elif isinstance(target_model, ForwardRef):
            str_type = target_model.__forward_arg__
            target_model = ModelRegistry.get_model_by_str(str_type)

        if target_model is None:
            raise ModelError(f"{field.type} is not registered as Model.")
        # Specify the foreign key as a reverse foreing key on the target_model.
        # For this we need to append the foreign key to the target model virtual
        # table schema, if it does not already exists
        foreign_key = ForeignKeyInfo(self.model, f"{self.model.__name__.lower()}_id")

        # Resolve the other endpoint table
        target_virtual_table = VirtualDatabaseSchema[target_model]  # type: ignore
        if target_virtual_table is None:
            # Create the table but do not autobegin it
            target_virtual_table = TableMetadata(
                metadata=self.metadata,
                table_name=getattr(target_model, __winter_model_collection_name__),
                model=target_model,  # type: ignore
            )
        # Add the foreign key
        if foreign_key not in target_virtual_table.foreing_keys:
            target_virtual_table.foreing_keys.append(foreign_key)

        # Return the many to one relation
        return Relation(target_model, field.name)  # type: ignore

    def dispatch_column_type_for_field(self, field: Field) -> None:
        if (ref := field.metadata.get("ref", None)) is not None:
            # This field is a ForeignKey to another model
            if isinstance(ref, str):
                ref = get_type_by_str(ref)
            fk = ForeignKeyInfo(ref, field.name)  # type: ignore
            if fk not in self.foreing_keys:
                self.foreing_keys.append(fk)
            return
        if isinstance(field.type, str):
            field.type = get_type_by_str(field.type)
        elif isinstance(field.type, ForwardRef):
            type_str = field.type.__forward_arg__
            field.type = get_type_by_str(type_str)
        if field.type in _mapper:
            self.columns.append(field)
            return

        if isinstance(field.type, GenericAlias) and field.type.__origin__ in sequences:
            self.many_to_one_relations.append(self.many_to_one_relation(field))
            self.relations.append(self.many_to_one_relation(field))
            return

        _type = resolve_generic_type_or_die(field.type)  # type: ignore

        if isinstance(_type, str):
            _type = get_type_by_str(_type)
        elif isinstance(_type, ForwardRef):
            type_str = _type.__forward_arg__
            _type = get_type_by_str(type_str)

        # If type is not an instance of dataclass, then also ignores it
        if not is_dataclass(_type):
            return

        # At this point, this is a one_to relation, so we just add a foreing key and a
        # relation
        foregin_key = ForeignKeyInfo(_type, field.name)  # type: ignore
        relationship = Relation(with_model=_type, field_name=field.name)  # type: ignore

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
    sql_generated_tables: dict[type["Model"], Table] = {}

    @classmethod
    def get_table(cls, model: type["Model"]):
        return cls.sql_generated_tables.get(model)

    @staticmethod
    def create_table_for_model(model: type["Model"], table_metadata: TableMetadata):
        if model not in VirtualDatabaseSchema.sql_generated_tables:
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
                columns.append(
                    Column("id", Integer, primary_key=True, autoincrement=True)
                )

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
                            ForeignKey(
                                f"{getattr(fk.target, __winter_model_collection_name__)}.id"
                            ),
                            nullable=True,
                        )
                    )

            table = Table(table_metadata.table_name, table_metadata.metadata, *columns)
            VirtualDatabaseSchema.sql_generated_tables[model] = table

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
            if getattr(model, "__class_is_mapped__"):
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
            if getattr(model, "__class_is_mapped__") and not inspect(
                model, raiseerr=False
            ):
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


def to_dict(cls: type, obj: Any):
    fields_names = [f.name for f in fields(cls)]
    if isinstance(obj, BaseModel):
        d = obj.dict()

    elif is_dataclass(obj):
        d = asdict(obj)

    else:
        d = vars(obj)

    for k in d.copy().keys():
        if k not in fields_names:
            d.pop(k)

    return d


def fromobj(cls: type["Model"], obj: Any):
    ...


def inspect_model(cls: type["Model"]):
    model_fields = fields(cls)
    primary_keys: dict[str, Field] = {}
    refs: dict[str, type[Model]] = {}

    for f in model_fields:
        # save the primary key, this might be a composite one
        if f.metadata.get("id", False) or f.name.lower() == "id":
            primary_keys[f.name] = f

        if (model := f.metadata.get("ref", None)) is not None:
            refs[f.name] = model

    if not primary_keys:
        primary_keys["id"] = Id()

    setattr(cls, __winter_model_primary_keys__, primary_keys)


def Id(
    *,
    default_factory: Callable[[], T] | None = None,
    repr: bool = True,
    compare: bool = True,
    hash: bool = True,
):
    if default_factory is None:
        default_factory = Increment()  # type: ignore

    return field(
        default_factory=default_factory,  # type: ignore
        repr=repr,
        compare=compare,
        hash=hash,
        kw_only=True,
        metadata={"id": True},
    )


def Array(*, repr: bool = True) -> Any:
    return field(default_factory=list, repr=repr, compare=False, hash=False, kw_only=True)


def ModelSet(*, repr: bool = True):
    return field(default_factory=set, repr=repr, compare=False, hash=False, kw_only=True)


def Ref(*, model: type["Model"], default=None):
    return field(default=default, kw_only=True, metadata={"ref": model})


def RequiredId(repr: bool = True, compare: bool = True, hash: bool = True):
    return field(
        repr=repr, compare=compare, hash=hash, kw_only=True, metadata={"id": True}
    )


def is_obj_marked(obj: Any):
    return isinstance(obj, Model) and getattr(obj, "__wintry_obj_is_used_by_sql__", False)


@cache
def get_model_fields_names(model: type["Model"]) -> set[str]:
    return set(f.name for f in fields(model))


class FieldClassProxy(str):
    def __hash__(self) -> int:
        return hash(str(self))

    def __getattr__(self, item):
        return FieldClassProxy(f"{self}.{item}")

    def __getitem__(self, item):
        return FieldClassProxy(f"{self}.{item}")

    def __gt__(self, other: Any):
        return GreaterThanNode(self, other)

    def __lt__(self, other: Any):
        return LowerThanNode(self, other)

    def __eq__(self, __o: object):
        return EqualToNode(self, __o)


@__dataclass_transform__(kw_only_default=True, field_descriptors=(field, Field))
class Model(DataClassDictMixin):
    class Config(config.BaseConfig):
        code_generation_options = [
            config.ADD_DIALECT_SUPPORT,
            config.TO_DICT_ADD_BY_ALIAS_FLAG,
            config.TO_DICT_ADD_OMIT_NONE_FLAG,
        ]

    def __setattr__(self, __name: str, __value: Any) -> None:
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

            # Check for modified flag, so we ensure that this object is added just once
            modified = getattr(target, __winter_modified_entity_state__, False)

            if not modified:
                tracker.add(target)
                setattr(target, __winter_modified_entity_state__, True)

            # This distinction is needed for SQL, so new entities assigned
            # to properties got tracked. IF they are new, then no big deal,
            # add it to the new group in tracker, otherwise, just ignore it
            if is_obj_marked(self) and isinstance(__value, Model) and __value not in tracker:
                setattr(__value, __winter_track_target__, __value)
                setattr(__value, __winter_tracker__, tracker)
                tracker.new(__value)

        return super().__setattr__(__name, __value)  # type: ignore

    def __init_subclass__(
        cls,
        *,
        table: str | None = None,
        init: bool = True,
        repr: bool = True,
        eq: bool = True,
        order: bool = False,
        unsafe_hash: bool = False,
        match_args: bool = True,
        mapped: bool = True,
    ) -> None:
        cls = dataclass(
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=False,
            match_args=match_args,
            kw_only=True,
            slots=False,
        )(cls)

        table_name = table or cls.__name__.lower() + "s"
        setattr(cls, __winter_model_collection_name__, table_name)
        setattr(cls, __winter_model_fields_set__, tuple(f.name for f in fields(cls)))

        inspect_model(cls)

        super().__init_subclass__()

        # Register model if it is mapped
        setattr(cls, "__class_is_mapped__", mapped)

        for field in fields(cls):
            setattr(cls, field.name, FieldClassProxy(field.name))

        ModelRegistry.register(cls)  # type: ignore

    @classmethod
    def id_name(cls) -> tuple[str]:
        pks: dict[str, Field] = getattr(cls, __winter_model_primary_keys__)
        return tuple(pks.keys())

    def ids(self):
        pks: dict[str, Field] = getattr(self, __winter_model_primary_keys__)
        return {name: getattr(self, name) for name in pks}

    @overload
    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Self:  # type: ignore
        ...

    @overload
    def to_dict(  # type: ignore
        self,
        *,
        omit_none: bool = False,
        by_alias: bool = False,
        dialect: Dialect | None = None,
    ) -> dict[str, Any]:
        ...

    @classmethod
    def from_list(cls, l: Sequence[Mapping[str, Any]]) -> list[Self]:
        return list(map(cls.from_dict, l))

    @overload
    @classmethod
    def build(cls, _dict: dict[str, Any]) -> Self:
        ...

    @overload
    @classmethod
    def build(cls, _dict: list[dict[str, Any]]) -> list[Self]:
        ...

    @overload
    @classmethod
    def build(cls, _dict: Any) -> Self:
        ...

    @overload
    @classmethod
    def build(cls, _dict: list[Any]) -> list[Self]:
        ...

    @classmethod
    def build(
        cls, _dict: dict[str, Any] | list[dict[str, Any]] | Any | list[Any]
    ) -> Self | list[Self]:
        if isinstance(_dict, list):
            return [cls.build(d) for d in _dict]
        if isinstance(_dict, dict):
            return cls.from_dict(_dict)

        return cls.from_orm(_dict)

    @overload
    @classmethod
    def from_orm(cls, obj: list[Any]) -> list[Self]:
        ...

    @overload
    @classmethod
    def from_orm(cls, obj: Any) -> Self:
        ...

    @classmethod
    def from_orm(cls, obj: list[Any] | Any) -> list[Self] | Self:
        ...

    def map(self, _dict: dict[str, Any]) -> None:
        ...
