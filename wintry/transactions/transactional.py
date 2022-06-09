from functools import update_wrapper, wraps
from inspect import iscoroutinefunction
from typing import Any, Callable, TypeVar, overload

from wintry.repository import Repository
from wintry.sessions import Tracker
from wintry.transactions.unit_of_work import close_session, commit, get_session, rollback
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


def transactional(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    async def transaction(*args, **kwargs):
        repositories = collect_repositories_from_args(args, kwargs)
        result = await run_transaction(func, repositories, args, kwargs)
        return result

    return transaction


class transaction_method:
    def __init__(self, fget: Callable):
        self.fget = fget

    def __get__(self, obj: Any, type_: type | None = None):
        async def transactional_function(*args, **kwargs):
            repositories = collect_repositories_from_self(obj)
            result = await run_transaction(self.fget, repositories, (obj,) + args, kwargs)
            return result

        return transactional_function


@overload
def transaction(func: T) -> T:  # type: ignore
    ...


def transaction(func: Callable):  # type: ignore
    new_func = transaction_method(func)
    return update_wrapper(new_func, func)
