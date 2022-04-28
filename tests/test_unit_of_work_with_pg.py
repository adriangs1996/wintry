from typing import Any, AsyncGenerator, List
from winter import get_connection, init_backend
from winter.orm import for_model
from winter.repository import repository
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relation
from sqlalchemy import Column, Integer, Float, String, ForeignKey, select, delete, insert, MetaData
from winter.repository.crud_repository import CrudRepository
from winter.settings import ConnectionOptions, WinterSettings
from winter.unit_of_work import UnitOfWork
import pytest_asyncio
import pytest
import winter.backend
from dataclasses import dataclass, field


@dataclass
class Address:
    id: int
    latitude: float
    longitude: float
    users: list["User"] = field(default_factory=list)


@dataclass
class User:
    id: int
    name: str
    age: int
    address: Address | None = None


@dataclass(unsafe_hash=True)
class Hero:
    name: str
    id: int
    occupation: str


# Define the table schemas
metadata = MetaData()


AddressTable = for_model(
    Address,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("latitude", Float),
    Column("longitude", Float),
    table_name="Addresses",
)


UserTable = for_model(
    User,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("age", Integer),
    Column("address_id", Integer, ForeignKey("Addresses.id")),
    table_name="Users",
    address=relation(Address, lazy="joined", backref="users"),
)


HeroTable = for_model(
    Hero,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("occupation", String),
    table_name="Heroes",
)


@repository(User)
class UserRepository(CrudRepository[User, int]):
    async def find_by_id_or_name_and_age_lowerThan(self, *, id: int, name: str, age: int) -> List[User]:
        ...


@repository(Hero)
class HeroRepository(CrudRepository[Hero, int]):
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


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup() -> None:
    init_backend(
        WinterSettings(
            backend="winter.drivers.pg",
            connection_options=ConnectionOptions(url="postgresql+asyncpg://postgres:secret@localhost/tests"),
        )
    )
    engine = getattr(winter.backend.Backend.driver, "_engine")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(delete(UserTable))
        await session.execute(delete(AddressTable))
        await session.execute(delete(HeroTable))
        await session.commit()


@pytest.mark.asyncio
async def test_uow_abort_transaction_by_default(clean: Any) -> Any:
    repo = UserRepository()
    uow = Uow(repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)

    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(UserTable))

    assert results.all() == []


@pytest.mark.asyncio
async def test_uow_commits_transaction_with_explicit_commit(clean: Any) -> None:
    repo = UserRepository()
    uow = Uow(repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)
        await uow.commit()

    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(UserTable))

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

    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(UserTable))

    assert results.all() == []


@pytest.mark.asyncio
async def test_uow_handles_multiple_repositories_under_the_same_session(clean: Any) -> None:
    user_repo = UserRepository()
    hero_repo = HeroRepository()
    uow = MultiUow(user_repo, hero_repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)
        await uow.heroes.create(entity=Hero(name="Batman", id=1, occupation="Vigilante"))

    session: AsyncSession = get_connection()
    async with session.begin():
        users_results: Result = await session.execute(select(UserTable))
        heroes_results: Result = await session.execute(select(HeroTable))

    assert users_results.all() == []
    assert heroes_results.all() == []


@pytest.mark.asyncio
async def test_uow_commit_multiple_repositories_under_the_same_session(clean: Any) -> None:
    user_repo = UserRepository()
    hero_repo = HeroRepository()
    uow = MultiUow(user_repo, hero_repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)
        await uow.heroes.create(entity=Hero(name="Batman", id=1, occupation="Vigilante"))
        await uow.commit()

    session: AsyncSession = get_connection()
    async with session.begin():
        users_results: Result = await session.execute(select(UserTable))
        heroes_results: Result = await session.execute(select(HeroTable))

    assert len(users_results.all()) == 1
    assert len(heroes_results.all()) == 1


@pytest.mark.asyncio
async def test_uow_automatically_synchronize_objects(clean: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(UserTable).values(id=1, name="test", age=20))

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.address = Address(id=3, latitude=1.12, longitude=4.13)

        await uow.commit()

    async with session.begin():
        results: Result = await session.execute(select(AddressTable))

    assert len(results.all()) == 1
