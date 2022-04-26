import abc
from typing import List, TypeVar
from pydantic import BaseModel

from winter.repository import IRepository

T = TypeVar("T")
TypeId = TypeVar("TypeId")


class CrudRepository(IRepository[T, TypeId]):
    async def find(self) -> List[T]:
        ...

    async def get_by_id(self, *, id: TypeId) -> T | None:
        ...

    async def update(self, *, entity: T) -> None:
        ...

    async def delete(self) -> None:
        ...

    async def delete_by_id(self, *, id: TypeId) -> None:
        ...

    async def create(self, *, entity: T) -> T:
        ...
