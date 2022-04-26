import abc
from typing import Any, Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")
TypeId = TypeVar("TypeId")


class IRepository(Generic[T, TypeId]):
    session: Any = None


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
