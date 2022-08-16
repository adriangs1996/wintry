from functools import update_wrapper, wraps
from inspect import iscoroutinefunction, signature
from typing import Any, Callable, TypeVar, overload, Type

from sqlmodel.ext.asyncio.session import AsyncSession

from wintry.ioc.container import IGlooContainer, igloo
from wintry.repository import Repository
from wintry.repository.dbcontext import DbContext
from wintry.sessions import Tracker
from wintry.transactions.unit_of_work import (
    close_session,
    commit,
    get_session,
    rollback,
)
from wintry.utils.keys import (
    NO_SQL,
    __RepositoryType__,
    __winter_backend_identifier_key__,
    __winter_manage_objects__,
    __winter_session_key__,
    __winter_tracker__,
)


def collect_repositories_from_self(self_object: Any) -> list[Repository]:
    # Do this looks clumsy ??? I think it is beautiful, but still...
    return list(
        filter(lambda value: isinstance(value, Repository), vars(self_object).values())
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
        setattr(repository, "__nosql_session_managed__", True)
        backend_name = getattr(repository, __winter_backend_identifier_key__)
        session = await get_session(backend_name)
        setattr(repository, __winter_session_key__, session)


async def commit_repositories_sessions(repositories: list[Repository]):
    for repository in repositories:
        backend_name = getattr(repository, __winter_backend_identifier_key__)
        session = getattr(repository, __winter_session_key__)
        tracker: Tracker = getattr(repository, __winter_tracker__)
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
        setattr(repository, __winter_session_key__, None)
        tracker: Tracker = getattr(repository, __winter_tracker__)
        tracker.clean()


T = TypeVar("T")


async def run_transaction(func, repositories, args, kwargs):
    await set_session_in_repositories(repositories)
    try:
        if iscoroutinefunction(func):
            func_result = await func(*args, **kwargs)  # type: ignore
        else:
            func_result = func(*args, **kwargs)
        await commit_repositories_sessions(repositories)
        return func_result
    except Exception as e:
        await rollback_repositories_sessions(repositories)
        raise e
    finally:
        await close_repositories_sessions(repositories)


@overload
def transactional(func: T) -> T:
    ...


def transactional(func: Callable[..., Any]):
    @wraps(func)
    async def _transaction(*args, **kwargs):
        repositories = collect_repositories_from_args(args, kwargs)
        result = await run_transaction(func, repositories, args, kwargs)
        return result

    sig = signature(func)
    setattr(_transaction, "__signature__", sig)
    return _transaction


@overload
def transaction(func: T) -> T:  # type: ignore
    ...


def transaction(fn: Callable):
    @wraps(fn)
    async def transactional_function(self, *args, **kwargs):
        repositories = collect_repositories_from_self(self)
        result = await run_transaction(fn, repositories, (self,) + args, kwargs)
        return result

    sig = signature(fn)
    setattr(transactional_function, "__signature__", sig)
    return transactional_function


def atomic(
    *, with_context: Type[DbContext] = AsyncSession, container: IGlooContainer = igloo
):
    def decorator(fn: Callable):
        @wraps(fn)
        async def transactional_function(*args, **kwargs):
            # get the DbContext from the container
            context: DbContext = container[with_context]
            context.begin()
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                await context.rollback()
                raise e
            finally:
                await context.commit()

        sig = signature(fn)
        setattr(transactional_function, "__signature__", sig)
        return transactional_function

    return decorator
