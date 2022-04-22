import re
from typing import Callable, Type, TypeVar
from sqlalchemy.orm import registry
from sqlalchemy import MetaData, Table
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DecoratedCallable = Callable[[Callable[[], Table]], Callable[[], Table]]

mapper_registry = registry()


def map_model(cls: Type[T], *args, **kwargs) -> DecoratedCallable:
    def create_map(fn: Callable[[], Table]):
        table = fn()
        mapper_registry.map_imperatively(cls, table, *args, **kwargs)
        return fn

    return create_map
