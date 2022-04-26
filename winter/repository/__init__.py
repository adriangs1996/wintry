from typing import Any, Generic, TypeVar
from .base import raw_method, repository


T = TypeVar("T")
TypeId = TypeVar("TypeId")


class IRepository(Generic[T, TypeId]):
    session: Any = None


__all__ = ["raw_method", "repository", "IRepository"]
