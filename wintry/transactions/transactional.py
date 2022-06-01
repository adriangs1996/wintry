from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, Callable, Coroutine, TypeVar, overload
from wintry.ioc.container import IGlooContainer, igloo
from wintry.ioc.injector import inject

from wintry.repository import Repository
from wintry.transactions.unit_of_work import commit, rollback, close_session
from wintry.sessions import MongoSessionTracker
from wintry.transactions.unit_of_work import get_session
from wintry.utils.keys import (
    __winter_backend_identifier_key__,
    __winter_session_key__,
    __winter_manage_objects__,
    __RepositoryType__,
    NO_SQL,
    __winter_tracker__,
)


def collect_repositories_from_args(args: tuple[Any, ...], kwargs: dict[str, Any]):
    repositories: list[Repository] = []

    for arg in args:
        if isinstance(arg, Repository):
            repositories.append(arg)

    for arg in kwargs.values():
        if isinstance(arg, Repository):
            repositories.append(arg)

    return repositories


async def set_session_in_repositories(repositories: list[Repository]):
    for repository in repositories:
        backend_name = getattr(repository, __winter_backend_identifier_key__)
        session = await get_session(backend_name)
        setattr(repository, __winter_session_key__, session)


async def commit_repositories_sessions(repositories: list[Repository]):
    for repository in repositories:
        backend_name = getattr(repository, __winter_backend_identifier_key__)
        session = getattr(repository, __winter_session_key__)
        if (
            getattr(repository, __winter_manage_objects__, False)
            and getattr(repository, __RepositoryType__, None) == NO_SQL
        ):
            tracker: MongoSessionTracker = getattr(repository, __winter_tracker__)
            await tracker.flush(session)
        await commit(session, backend_name)


async def rollback_repositories_sessions(repositories: list[Repository]):
    for repository in repositories:
        backend_name = getattr(repository, __winter_backend_identifier_key__)
        session = getattr(repository, __winter_session_key__)
        await rollback(session, backend_name)


async def close_repositories_sessions(repositories: list[Repository]):
    for repository in repositories:
        backend_name = getattr(repository, __winter_backend_identifier_key__)
        session = getattr(repository, __winter_session_key__)
        await close_session(session, backend_name)
        if (
            getattr(repository, __winter_manage_objects__, False)
            and getattr(repository, __RepositoryType__, None) == NO_SQL
        ):
            tracker: MongoSessionTracker = getattr(repository, __winter_tracker__)
            tracker.clean()


T = TypeVar("T")


def transactional(
    func: Callable[..., Any] | None = None,
    /,
    *,
    container: IGlooContainer = igloo,
    use_injection: bool = True,
) -> Callable[..., Any]:
    def decorate(f) -> Any:
        @wraps(f)
        async def transaction(*args, **kwargs):
            repositories = collect_repositories_from_args(args, kwargs)
            await set_session_in_repositories(repositories)
            try:
                if iscoroutinefunction(f):
                    func_result = await f(*args, **kwargs)  # type: ignore
                else:
                    func_result = f(*args, **kwargs)
                await commit_repositories_sessions(repositories)
                return func_result
            except Exception as e:
                await rollback_repositories_sessions(repositories)
                raise e
            finally:
                await close_repositories_sessions(repositories)

        if use_injection:
            return inject(container=container)(transaction)
        else:
            return transaction

    if func is None:
        return decorate

    return decorate(func)
