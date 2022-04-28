from typing import Any, TypeVar
from winter.repository import IRepository
from winter import get_session, commit, close_session, rollback

T = TypeVar("T")
TypeId = TypeVar("TypeId")


class UnitOfWork:
    def __init__(self, **kwargs: IRepository[Any, Any]) -> None:
        self.repositories = kwargs.copy()
        self.session: Any | None = None

    async def commit(self) -> None:
        """
        Commits a sequence of statements
        """
        if self.session is not None:
            await commit(self.session)

    async def rollback(self) -> None:
        if self.session is not None:
            await rollback(self.session)

    async def __aenter__(self) -> "UnitOfWork":
        """
        Make a unify interface for sesssion management between
        repositories. `get_session()` returns a session based on
        the configured backend, and works on that interface.
        """
        self.session = await get_session()
        # Repositories internally use a session for their operations.
        # If that session is None, then the operation is executed in
        # an isolated action, but if we managed the session from outside,
        # we can provide atomicity to a sequence of operations.

        # Trust that the provided session comes already initialized
        for repo in self.repositories.values():
            repo.session = self.session
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """
        By deafault, `UnitOfWork` aborts transaction on context
        exit. This is intentionally to avoid unwanted changes
        to go to the DB, in fact, is safer than the alternative.
        Also, explicit commit makes read the code a little bit nicer
        """
        await self.rollback()
        await close_session(self.session)
        self.session = None
        for repo in self.repositories.values():
            if repo.session is not None:
                repo.session = None

    def __getattribute__(self, __name: str) -> IRepository[Any, Any] | Any:
        """
        `UnitOfWork` is a handy place to provide access to all repositories.
        """
        repository = super().__getattribute__("repositories").get(__name, None)
        if repository is None:
            return super().__getattribute__(__name)
        else:
            return repository


__all__ = ["UnitOfWork"]