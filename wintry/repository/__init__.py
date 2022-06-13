import abc
import inspect
from typing import Any, Generic, TypeVar, overload

from wintry.orm.aql import (
    Create,
    Delete,
    FilteredClause,
    FilteredDelete,
    FilteredFind,
    FilteredGet,
    Find,
    Get,
    QueryAction,
    Update,
    execute,
)
from .base import TDecorated, raw_method, query, managed
from wintry import get_connection
from wintry.utils.keys import (
    NO_SQL,
    SQL,
    __winter_backend_identifier_key__,
    __RepositoryType__,
    __winter_repository_is_using_sqlalchemy__,
    __winter_session_key__,
    __winter_repo_old_init__,
    __winter_tracker__,
    __winter_manage_objects__,
)
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorClientSession
from wintry.models import Model
from wintry.sessions import Tracker


T = TypeVar("T", bound=Model)
TypeId = TypeVar("TypeId")


class RepositoryRegistry:
    repositories: list[type["Repository"]] = []

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


class Repository(abc.ABC, Generic[T, TypeId]):
    def __init__(self) -> None:
        ...

    async def connection(self) -> Any:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")

        if (session := getattr(self, __winter_session_key__, None)) is not None:
            if isinstance(session, AsyncIOMotorClientSession):
                # This is an AsyncioMotorSession. Inside that session, we have
                # a client property that maps to the
                db_name = await get_connection(backend_name).name  # type: ignore
                return session.client[db_name]
            return session

        return await get_connection(backend_name)

    @overload
    async def exec(self, statement: Update) -> None:
        ...

    @overload
    async def exec(self, statement: Create) -> T:
        ...

    @overload
    async def exec(self, statement: Find) -> list[T]:
        ...

    @overload
    async def exec(self, statement: Get) -> T | None:
        ...

    @overload
    async def exec(self, statement: Delete) -> None:
        ...

    @overload
    async def exec(self, statement: FilteredGet) -> T | None:
        ...

    @overload
    async def exec(self, statement: FilteredFind) -> list[T]:
        ...

    @overload
    async def exec(self, statement: FilteredDelete) -> None:
        ...

    async def exec(self, statement: FilteredClause | QueryAction) -> T | list[T] | None:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")
        session = getattr(self, __winter_session_key__, None)

        return await execute(statement, backend_name, session)

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

    def __init_subclass__(
        cls,
        *,
        entity: type[T],
        for_backend: str = "default",
        table_name: str | None = None,
        dry: bool = False,
    ) -> None:
        RepositoryRegistry.repositories.append(cls)

        def __winter_init__(self, *args, **kwargs):
            original_init = getattr(self, __winter_repo_old_init__)
            original_init(*args, **kwargs)

            # init tracker in the instance, because we do not
            # want to share trackers among repositories
            setattr(self, __winter_tracker__, Tracker(entity, for_backend))

        # Augment the repository with a special property to reference the backend this
        # repository is going to use
        setattr(cls, __winter_backend_identifier_key__, for_backend)

        # update the init method and save the original init
        setattr(cls, __winter_repo_old_init__, cls.__init__)

        # Need to stablish the signature of the new init as the old
        # one for the sake of the framework inspection
        sig = inspect.signature(cls.__init__)
        setattr(__winter_init__, "__signature__", sig)

        # replace the original init
        setattr(cls, "__init__", __winter_init__)

        if table_name is not None:
            setattr(entity, "__tablename__", table_name)

        # Prepare the repository with augmented properties
        setattr(cls, __winter_session_key__, None)

        setattr(cls, "__dry__", dry)

        setattr(cls, "__winter_entity__", entity)

        setattr(cls, "find", query(cls.find))
        vars(cls)["find"].__set_name__(cls, "find")

        setattr(cls, "get_by_id", query(cls.get_by_id))
        vars(cls)["get_by_id"].__set_name__(cls, "get_by_id")

        setattr(cls, "update", query(cls.update))
        vars(cls)["update"].__set_name__(cls, "update")

        setattr(cls, "delete", query(cls.delete))
        vars(cls)["delete"].__set_name__(cls, "delete")

        setattr(cls, "delete_by_id", query(cls.delete_by_id))
        vars(cls)["delete_by_id"].__set_name__(cls, "delete_by_id")

        setattr(cls, "create", query(cls.create))
        vars(cls)["create"].__set_name__(cls, "create")


__all__ = [
    "raw_method",
    "query",
    "managed",
    "Repository",
]
