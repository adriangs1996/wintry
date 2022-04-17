from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
TypeId = TypeVar("TypeId")


class CrudRepository(Generic[T, TypeId]):
    async def find(self) -> List[T]:
        ...

    async def find_by_id(self, id: TypeId) -> T:
        ...

    async def update(self, model: T) -> None:
        ...

    async def delete(self) -> None:
        ...

    async def delete_by_id(self, id: TypeId) -> None:
        ...

    async def create(self, model: T) -> T:
        ...
