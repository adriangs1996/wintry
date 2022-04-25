from typing import Any, Callable, Dict, Hashable, Type, TypeVar
from pydantic import BaseModel

TEntity = TypeVar("TEntity")
TSchema = TypeVar("TSchema")


__mapper__: Dict[Type[Any], Type[Any]] = {}

__SQL_ENABLED_FLAG__ = "__sqlalchemy_managed_entity__"


def for_model(cls: Type[Any]) -> Callable[[Type[TSchema]], Type[TSchema]]:
    setattr(cls, __SQL_ENABLED_FLAG__, True)
    def create_map(table_definition: Type[TSchema]) -> Type[TSchema]:
        __mapper__[cls] = table_definition
        return table_definition

    return create_map
