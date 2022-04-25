from typing import Any, Callable, Dict, Hashable, Type, TypeVar
from pydantic import BaseModel

TEntity = TypeVar("TEntity")
TSchema = TypeVar("TSchema")


__SQL_ENABLED_FLAG__ = "__sqlalchemy_managed_entity__"
__WINTER_MAPPED_CLASS__ = "__winter_mapped_class__"


def for_model(cls: Type[Any]) -> Callable[[Type[TSchema]], Type[TSchema]]:
    def create_map(table_definition: Type[TSchema]) -> Type[TSchema]:
        setattr(cls, __SQL_ENABLED_FLAG__, table_definition)
        setattr(table_definition, __WINTER_MAPPED_CLASS__, cls)
        return table_definition

    return create_map
