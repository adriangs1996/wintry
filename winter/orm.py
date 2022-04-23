from typing import Any, Callable, Dict, Type, TypeVar
from pydantic import BaseModel

TEntity = TypeVar("TEntity", bound=BaseModel)
TSchema = TypeVar("TSchema")


__mapper__: Dict[Type[Any], Type[Any]] = {}

__SQL_ENABLED_FLAG__ = "__sqlalchemy_managed_entity__"


def for_model(cls: Type[TEntity]) -> Callable[[Type[TSchema]], Type[TSchema]]:
    setattr(cls, __SQL_ENABLED_FLAG__, True)
    def create_map(table_definition: Type[TSchema]) -> Type[TSchema]:
        __mapper__[cls] = table_definition
        return table_definition

    return create_map
