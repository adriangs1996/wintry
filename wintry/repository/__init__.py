import abc
from typing import Any, Generic, TypeVar
from .base import raw_method, repository
from wintry import get_connection
from wintry.utils.keys import __winter_backend_identifier_key__
from sqlalchemy.ext.asyncio import AsyncSession


T = TypeVar("T")
TypeId = TypeVar("TypeId")


class ICrudRepository(Generic[T, TypeId]):
    async def find(self) -> list[T]:
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


class Repository(abc.ABC, ICrudRepository[T, TypeId]):
    def connection(self) -> Any:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")
        return get_connection(backend_name)

    def __init_subclass__(
        cls,
        *,
        entity: type[T],
        for_backend: str = "default",
        table_name: str | None = None,
        dry: bool = False,
        mongo_session_managed: bool = False,
        force_nosql: bool = False,
    ) -> None:
        repository(
            entity,
            for_backend=for_backend,
            table_name=table_name,
            dry=dry,
            mongo_session_managed=mongo_session_managed,
            force_nosql=force_nosql,
        )(cls)


class NoSqlCrudRepository(abc.ABC, ICrudRepository[T, TypeId]):
    def connection(self) -> Any:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")
        return get_connection(backend_name)

    def __init_subclass__(
        cls,
        *,
        entity: type[T],
        for_backend: str = "default",
        table_name: str | None = None,
        dry: bool = False,
        mongo_session_managed: bool = False,
    ) -> None:
        repository(
            entity,
            for_backend=for_backend,
            table_name=table_name,
            dry=dry,
            mongo_session_managed=mongo_session_managed,
            force_nosql=True,
        )(cls)


class SqlCrudRepository(abc.ABC, ICrudRepository[T, TypeId]):
    def connection(self) -> AsyncSession:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")
        return get_connection(backend_name)

    def __init_subclass__(
        cls,
        *,
        entity: type[T],
        for_backend: str = "default",
        table_name: str | None = None,
        dry: bool = False,
    ) -> None:
        repository(
            entity,
            for_backend=for_backend,
            table_name=table_name,
            dry=dry,
        )(cls)


__all__ = ["raw_method", "repository", "Repository", "NoSqlCrudRepository", "SqlCrudRepository"]
