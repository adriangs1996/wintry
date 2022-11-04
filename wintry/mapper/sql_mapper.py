from typing import ClassVar, Type, Any
from sqlalchemy.orm import registry
from sqlalchemy import Column, Table
from sqlmodel import SQLModel


class SQLMapper(object):
    registry: ClassVar[registry] = registry(metadata=SQLModel.metadata)

    @classmethod
    def map(
        cls,
        class_: Type[Any] | str,
        *columns: Column,
        table_name: str | None = None,
        **properties: Any
    ):
        table_identifier = table_name or class_.__name__.lower()
        table = Table(table_identifier, *columns)
        cls.registry.map_imperatively(class_, table, **properties)
