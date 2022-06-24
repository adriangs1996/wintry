from typing import Any, TypeVar
from typing_extensions import Self
from wintry.drivers.mongo import MongoSession
from sqlalchemy.ext.asyncio import AsyncSession
from wintry import BACKENDS, DriverNotFoundError, DriverNotSetError
from wintry.sessions import Tracker
from wintry.settings import EngineType
from wintry.utils.keys import (
    __winter_manage_objects__,
    __winter_tracker__,
    __winter_session_key__,
    __RepositoryType__,
    __winter_backend_identifier_key__,
    __RepositoryType__,
    NO_SQL,
)

T = TypeVar("T")
TypeId = TypeVar("TypeId")


class UnitOfWorkError(Exception):
    pass


def get_backend_type(backend_name: str = "default") -> EngineType:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    return backend.driver.driver_class


async def get_session(backend_name: str = "default") -> AsyncSession | MongoSession:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    return await backend.driver.get_started_session()


async def commit(session: Any, backend_name: str = "default") -> None:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    await backend.driver.commit_transaction(session)


async def rollback(session: Any, backend_name: str = "default") -> None:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    await backend.driver.abort_transaction(session)


async def close_session(session: Any, backend_name: str = "default") -> None:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    await backend.driver.close_session(session)


class UnitOfWork:
    def __init__(self, **kwargs: Any) -> None:
        self.repositories = kwargs.copy()

    async def commit(self) -> None:
        """
        Commits a sequence of statements
        """
        for repo in self.repositories.values():
            backend_name = getattr(repo, __winter_backend_identifier_key__)
            session = getattr(repo, __winter_session_key__)
            tracker: Tracker = getattr(repo, __winter_tracker__)
            await tracker.flush(session)
            await commit(session, backend_name)

    async def rollback(self) -> None:
        for repository in self.repositories.values():
            backend_name = getattr(repository, __winter_backend_identifier_key__)
            session = getattr(repository, __winter_session_key__)
            await rollback(session, backend_name)

    async def __aenter__(self) -> Self:
        """
        Make a unify interface for sesssion management between
        repositories. `get_session()` returns a session based on
        the configured backend, and works on that interface.
        """
        # Repositories internally use a session for their operations.
        # If that session is None, then the operation is executed in
        # an isolated action, but if we managed the session from outside,
        # we can provide atomicity to a sequence of operations.

        # Trust that the provided session comes already initialized
        for repository in self.repositories.values():
            setattr(repository, "__nosql_session_managed__", True)
            backend_name = getattr(repository, __winter_backend_identifier_key__)
            session = await get_session(backend_name)
            setattr(repository, __winter_session_key__, session)
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """
        By deafault, `UnitOfWork` aborts transaction on context
        exit. This is intentionally to avoid unwanted changes
        to go to the DB, in fact, is safer than the alternative.
        Also, explicit commit makes read the code a little bit nicer
        """
        await self.rollback()
        for repository in self.repositories.values():
            backend_name = getattr(repository, __winter_backend_identifier_key__)
            session = getattr(repository, __winter_session_key__)
            await close_session(session, backend_name)
            setattr(repository, __winter_session_key__, None)
            tracker: Tracker = getattr(repository, __winter_tracker__)
            tracker.clean()

    def __getattribute__(self, __name: str) -> Any:
        """
        `UnitOfWork` is a handy place to provide access to all repositories.
        """
        repository = super().__getattribute__("repositories").get(__name, None)
        if repository is None:
            return super().__getattribute__(__name)
        else:
            return repository


__all__ = ["UnitOfWork"]
