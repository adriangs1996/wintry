import abc
from enum import Enum
from typing import TypeVar, Any, Type, Generic, Dict, List, Protocol

from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T", bound=BaseModel)
TId = TypeVar("TId")


# This has to serve as an abstraction over the concept of a session
# that many ORM handles, so we can provide a UoW and Repository unified
# experience
class DbContext(abc.ABC):
    @abc.abstractmethod
    async def commit(self) -> None:
        """
        Flushes current state to DB

        Returns:

        """
        pass

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Rollback current state"""
        pass

    @abc.abstractmethod
    def begin(self) -> None:
        """Start a new transaction"""
        pass

    @abc.abstractmethod
    async def dispose(self):
        """Release resources"""
        pass


class SyncDbContext(abc.ABC):
    @abc.abstractmethod
    def commit(self) -> None:
        """
        Flushes current state to DB

        Returns:

        """
        pass

    @abc.abstractmethod
    def rollback(self) -> None:
        """Rollback current state"""
        pass

    @abc.abstractmethod
    def begin(self) -> None:
        """Start a new transaction"""
        pass

    @abc.abstractmethod
    def dispose(self):
        """Release resources"""
        pass


class Order(str, Enum):
    asc = "ASC"
    desc = "DESC"


class QuerySpecification(BaseModel):
    ordering: Order = Order.asc
    order_by: List[Any] = []
    filters: List[Any] = []
    limit: int | None = None
    offset: int | None = None


class AbstractRepository(abc.ABC, Generic[T, TId]):
    @abc.abstractmethod
    async def get_by_id(self, id_: TId, load_spec: List[Any] | None = None) -> T | None:
        ...

    @abc.abstractmethod
    async def find(
        self,
        load_spec: List[Any] | None = None,
        query_spec: QuerySpecification = QuerySpecification(),
    ) -> List[T]:
        ...

    @abc.abstractmethod
    async def delete(self, entity: T) -> None:
        ...

    @abc.abstractmethod
    async def add(self, entity: T) -> None:
        ...


TSQLModel = TypeVar("TSQLModel", bound=SQLModel)


class SQLRepository(AbstractRepository, Generic[TSQLModel, TId]):
    @abc.abstractmethod
    def __init__(self, session: AsyncSession, model: Type[TSQLModel]):
        self.session = session
        self.model = model

    async def get_by_id(
        self, id_: TId, load_spec: List[Any] | None = None
    ) -> TSQLModel | None:
        query = select(self.model).where(self.model.id == id_)

        if load_spec is not None:
            for spec in load_spec:
                query = query.options(selectinload(spec))
        else:
            query = query.options(selectinload("*"))

        result = await self.session.exec(query)
        return result.one_or_none()

    async def find(
        self,
        load_spec: List[Any] | None = None,
        query_spec: QuerySpecification = QuerySpecification(),
    ) -> List[TSQLModel]:
        query = select(self.model)

        for filter_ in query_spec.filters:
            query = query.where(filter_)

        if load_spec is not None:
            for spec in load_spec:
                query = query.options(selectinload(spec))

        if query_spec.limit is not None:
            query = query.limit(query_spec.limit)

        if query_spec.offset is not None:
            query = query.offset(query_spec.offset)

        if query_spec.order_by:
            query = query.order_by(*query_spec.order_by)

        result = await self.session.exec(query)
        return result.all()

    async def delete(self, entity: TSQLModel) -> None:
        await self.session.delete(entity)

    async def add(self, entity: TSQLModel) -> None:
        self.session.add(entity)
