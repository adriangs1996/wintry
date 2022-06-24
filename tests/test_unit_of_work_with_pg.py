from typing import Any, AsyncGenerator, List
from wintry import get_connection, init_backends, BACKENDS
from wintry.models import Model, metadata, ModelRegistry
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio import AsyncSession, AsyncConnection
from sqlalchemy import select, delete, insert
from wintry.repository import Repository, RepositoryRegistry
from wintry.repository.base import query
from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings
from wintry.transactions import UnitOfWork
import pytest_asyncio
import pytest
from dataclasses import field

from wintry.utils.virtual_db_schema import get_model_sql_table


class Address(Model, table="PGUoWAddress"):
    id: int
    latitude: float
    longitude: float
    users: "list[User]" = field(default_factory=list)


class User(Model, table="PGUoWUser"):
    id: int
    name: str
    age: int
    address: Address | None = None


class Hero(Model, unsafe_hash=True, table="PGUoWHero"):
    name: str
    id: int
    occupation: str


class UserRepository(Repository[User, int], entity=User):
    @query
    async def find_by_id_or_name_and_age_lowerThan(
        self, *, id: int, name: str, age: int
    ) -> List[User]:
        ...


class HeroRepository(Repository[Hero, int], entity=Hero):
    pass


# define a custom uow so we got intellisense, this is for type-checkers only
class Uow(UnitOfWork):
    users: UserRepository

    def __init__(self, users: UserRepository) -> None:
        super().__init__(users=users)


class MultiUow(UnitOfWork):
    users: UserRepository
    heroes: HeroRepository

    def __init__(self, users: UserRepository, heroes: HeroRepository) -> None:
        super().__init__(users=users, heroes=heroes)


async def get_all_users_and_heroes():
    users = get_model_sql_table(User)
    heroes = get_model_sql_table(Hero)
    session: AsyncConnection = await get_connection()
    session.begin()
    users_results: Result = await session.execute(select(users))
    heroes_results: Result = await session.execute(select(heroes))
    await session.close()
    return heroes_results, users_results


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup():
    ModelRegistry.configure()
    RepositoryRegistry.configure_for_sqlalchemy()
    init_backends(
        WinterSettings(
            backends=[
                BackendOptions(
                    driver="wintry.drivers.pg",
                    connection_options=ConnectionOptions(
                        url="postgresql+asyncpg://postgres:secret@localhost/tests"
                    ),
                )
            ],
        )
    )
    engine = getattr(BACKENDS["default"].driver, "_engine")
    conn = await engine.connect()
    await conn.run_sync(metadata.create_all)
    await conn.commit()
    await conn.close()


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(delete(get_model_sql_table(User)))
    await session.execute(delete(get_model_sql_table(Address)))
    await session.execute(delete(get_model_sql_table(Hero)))
    await session.commit()
    await session.close()


@pytest.mark.asyncio
async def test_uow_abort_transaction_by_default(clean: Any) -> Any:
    repo = UserRepository()
    uow = Uow(repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)

    table = get_model_sql_table(User)
    session: AsyncConnection = await get_connection()
    session.begin()
    results: Result = await session.execute(select(table))
    await session.close()

    assert results.all() == []


@pytest.mark.asyncio
async def test_uow_commits_transaction_with_explicit_commit(clean: Any) -> None:
    repo = UserRepository()
    uow = Uow(repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)
        await uow.commit()

    table = get_model_sql_table(User)
    session: AsyncConnection = await get_connection()
    session.begin()
    results: Result = await session.execute(select(table))
    await session.close()

    assert len(results.all()) == 1


@pytest.mark.asyncio
async def test_uow_rollbacks_on_error(clean: Any) -> None:
    repo = UserRepository()
    uow = Uow(repo)

    with pytest.raises(ZeroDivisionError):
        async with uow:
            user = User(id=2, name="test", age=10)
            await uow.users.create(entity=user)
            user2 = User(id=1, name="test", age=int(10 / 0))
            await uow.users.create(entity=user2)
            await uow.commit()

    table = get_model_sql_table(User)
    session: AsyncConnection = await get_connection()
    session.begin()
    results: Result = await session.execute(select(table))
    await session.close()

    assert results.all() == []


@pytest.mark.asyncio
async def test_uow_handles_multiple_repositories_under_the_same_session(
    clean: Any,
) -> None:
    user_repo = UserRepository()
    hero_repo = HeroRepository()
    uow = MultiUow(user_repo, hero_repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)
        await uow.heroes.create(entity=Hero(name="Batman", id=1, occupation="Vigilante"))

    heroes_results, users_results = await get_all_users_and_heroes()

    assert users_results.all() == []
    assert heroes_results.all() == []


@pytest.mark.asyncio
async def test_uow_commit_multiple_repositories_under_the_same_session(
    clean: Any,
) -> None:
    user_repo = UserRepository()
    hero_repo = HeroRepository()
    uow = MultiUow(user_repo, hero_repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)
        await uow.heroes.create(entity=Hero(name="Batman", id=1, occupation="Vigilante"))
        await uow.commit()

    heroes_results, users_results = await get_all_users_and_heroes()

    assert len(users_results.all()) == 1
    assert len(heroes_results.all()) == 1


@pytest.mark.asyncio
async def test_uow_automatically_synchronize_objects(clean: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    table = get_model_sql_table(User)
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(table).values(id=1, name="test", age=20))
    await session.commit()
    await session.close()

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.address = Address(id=3, latitude=1.12, longitude=4.13)

        await uow.commit()

    table = get_model_sql_table(Address)
    session: AsyncConnection = await get_connection()
    session.begin()
    results: Result = await session.execute(select(table))
    await session.close()

    assert len(results.all()) == 1


@pytest.mark.asyncio
async def test_uow_automatically_updates_object(clean: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(get_model_sql_table(User)).values(id=1, name="test", age=20))
    await session.commit()
    await session.close()

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.age = 30
        user.name = "updated"

        await uow.commit()

    session: AsyncConnection = await get_connection()
    session.begin()
    results: Result = await session.execute(select(get_model_sql_table(User)))
    await session.close()

    user = results.all()[0]
    assert user["age"] == 30 and user["name"] == "updated"
