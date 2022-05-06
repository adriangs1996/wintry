from typing import Any, Callable, Type, TypeVar
from sqlalchemy.orm import registry
from sqlalchemy import Table, Column, MetaData
from wintry.utils.keys import __SQL_ENABLED_FLAG__, __WINTER_MAPPED_CLASS__

TEntity = TypeVar("TEntity")
TSchema = TypeVar("TSchema")


mapper_registry = registry()
metadata = MetaData()

TableDef = Callable[[], Table]


def for_model(
    cls: Type[Any], metadata: MetaData, *columns: Column, table_name: str | None = None, **kwargs
) -> Table:

    setattr(cls, __SQL_ENABLED_FLAG__, True)
    if table_name is None:
        table_name = cls.__name__ + "s"

    table = Table(table_name, metadata, *columns)
    mapper_registry.map_imperatively(cls, table, properties=kwargs)
    return table


__all__ = ["__SQL_ENABLED_FLAG__", "__WINTER_MAPPED_CLASS__", "for_model"]
