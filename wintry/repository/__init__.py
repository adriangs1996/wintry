import abc
from typing import Any, Generic, TypeVar
from .base import raw_method, repository
from wintry import get_connection
from wintry.utils.keys import (
    NO_SQL,
    SQL,
    __winter_backend_identifier_key__,
    __RepositoryType__,
    __winter_repository_is_using_sqlalchemy__,
    __winter_session_key__,
)
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorClientSession


T = TypeVar("T")
TypeId = TypeVar("TypeId")


class RepositoryRegistry:
    repositories: list[type["ICrudRepository"] | type["IRepository"]] = []

    @classmethod
    def configure_for_sqlalchemy(cls, backend: str = "default"):
        for repo in cls.repositories:
            backend_name = getattr(repo, __winter_backend_identifier_key__)
            if backend_name == backend:
                setattr(repo, __RepositoryType__, SQL)
                setattr(repo, __winter_repository_is_using_sqlalchemy__, True)

    @classmethod
    def configure_for_nosql(cls, backend: str = "default"):
        for repo in cls.repositories:
            backend_name = getattr(repo, __winter_backend_identifier_key__)
            if backend_name == backend:
                setattr(repo, __winter_repository_is_using_sqlalchemy__, False)
                setattr(repo, __RepositoryType__, NO_SQL)


class ICrudRepository(Generic[T, TypeId]):
    def __init__(self) -> None:
        ...

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
    def __init__(self) -> None:
        ...

    def connection(self) -> Any:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")

        if (session := getattr(self, __winter_session_key__, None)) is not None:
            if isinstance(session, AsyncIOMotorClientSession):
                # This is an AsyncioMotorSession. Inside that session, we have
                # a client property that maps to the
                db_name = get_connection(backend_name).name  # type: ignore
                return session.client[db_name]
            return session

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
        RepositoryRegistry.repositories.append(cls)
        repository(
            entity,
            for_backend=for_backend,
            table_name=table_name,
            dry=dry,
            mongo_session_managed=mongo_session_managed,
            force_nosql=force_nosql,
        )(cls)


class IRepository(abc.ABC):
    def __init__(self) -> None:
        ...

    def connection(self) -> Any:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")

        if (session := getattr(self, __winter_session_key__, None)) is not None:
            if isinstance(session, AsyncIOMotorClientSession):
                # This is an AsyncioMotorSession. Inside that session, we have
                # a client property that maps to the AsyncIOMotorClient. need to
                # build the db from that
                db_name = get_connection(backend_name).name  # type: ignore
                return session.client[db_name]
            return session

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
        RepositoryRegistry.repositories.append(cls)
        repository(
            entity,
            for_backend=for_backend,
            table_name=table_name,
            dry=dry,
            mongo_session_managed=mongo_session_managed,
            force_nosql=force_nosql,
        )(cls)


class NoSqlCrudRepository(abc.ABC, ICrudRepository[T, TypeId]):
    def __init__(self) -> None:
        ...

    def connection(self) -> Any:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")

        if (session := getattr(self, __winter_session_key__, None)) is not None:
            # NOSQL Repository is for Mongo purpouses only
            db_name = get_connection(backend_name).name  # type: ignore
            return session.client[db_name]

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
        RepositoryRegistry.repositories.append(cls)
        repository(
            entity,
            for_backend=for_backend,
            table_name=table_name,
            dry=dry,
            mongo_session_managed=mongo_session_managed,
            force_nosql=True,
        )(cls)


class SqlCrudRepository(abc.ABC, ICrudRepository[T, TypeId]):
    def __init__(self) -> None:
        ...

    def connection(self) -> AsyncSession:
        if (session := getattr(self, __winter_session_key__, None)) is not None:
            # This is for sqlalchemy purpouses only
            return session

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
        RepositoryRegistry.repositories.append(cls)
        repository(
            entity,
            for_backend=for_backend,
            table_name=table_name,
            dry=dry,
        )(cls)


__all__ = [
    "raw_method",
    "repository",
    "Repository",
    "NoSqlCrudRepository",
    "SqlCrudRepository",
    "IRepository",
]
