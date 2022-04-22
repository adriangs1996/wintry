import re
from typing import Callable, Type, TypeVar
from sqlalchemy.orm import mapper
from sqlalchemy import MetaData, Table
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DecoratedCallable = Callable[[Callable[[], Table]], Callable[[], Table]]


def map_model(cls: Type[T], *args, **kwargs) -> DecoratedCallable:
    def create_map(fn: Callable[[], Table]):
        table = fn()
        mapper(cls, table, *args, **kwargs)
        return fn

    return create_map
