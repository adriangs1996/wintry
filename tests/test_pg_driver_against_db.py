from typing import Any, AsyncGenerator, List
from wintry import init_backends, get_connection, BACKENDS
from wintry.models import Model
from wintry.repository.base import managed, query

from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings

from wintry.orm import for_model
from sqlalchemy import (
    Integer,
    Column,
    String,
    ForeignKey,
    Float,
    delete,
    select,
    insert,
    MetaData,
)
from sqlalchemy.orm import relation
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine.result import Result
import pytest
import pytest_asyncio
from dataclasses import field


# Now import the repository
from wintry.repository import Repository, managed


class Address(Model):
    id: int
    latitude: float
    longitude: float
    users: list["User"] = field(default_factory=list)


class User(Model):
    id: int
    name: str
    age: int
    address: Address | None = None


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


class UserRepository(Repository[User, int], entity=User):
    @query
    async def find_by_id_or_name_and_age_lowerThan(
        self, *, id: int, name: str, age: int
    ) -> List[User]:
        ...

    @managed
    async def get_user(self, id: int) -> User | None:
        session = self.connection()
        return await session.get(User, id)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup():
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
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(delete(UserTable))
        await session.execute(delete(AddressTable))
        await session.commit()


@pytest.mark.asyncio
async def test_repository_can_insert(clean: Any) -> None:
    repo = UserRepository()
    user = User(id=2, name="test", age=10)

    await repo.create(entity=user)
    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(UserTable))
    assert len(results.all()) == 1


@pytest.mark.asyncio
async def test_repository_can_delete(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(UserTable).values(id=1, name="test", age=26))

    await repo.delete()

    async with session.begin():
        result: Result = await session.execute(select(UserTable))
        rows = result.all()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_delete_by_id(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(UserTable).values(id=1, name="test", age=26))

    await repo.delete_by_id(id=1)

    async with session.begin():
        result: Result = await session.execute(select(UserTable))
        rows = result.all()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_get_by_id(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(UserTable).values(id=1, name="test", age=26))

    user = await repo.get_by_id(id=1)

    assert isinstance(user, User)
    assert user.name == "test" and user.age == 26


@pytest.mark.asyncio
async def test_repository_can_list_all_users(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(UserTable).values(id=1, name="test", age=26))
        await session.execute(insert(UserTable).values(id=2, name="test1", age=26))
        await session.execute(insert(UserTable).values(id=3, name="test2", age=26))
        await session.execute(insert(UserTable).values(id=4, name="test3", age=26))

    users = await repo.find()

    assert len(users) == 4
    assert all(isinstance(user, User) for user in users)


@pytest.mark.asyncio
async def test_repository_can_get_object_with_related_data_loaded(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(
            insert(AddressTable).values(id=1, latitude=3.43, longitude=10.111)
        )
        await session.execute(
            insert(UserTable).values(id=1, name="test", age=26, address_id=1)
        )

    user = await repo.get_by_id(id=1)

    assert isinstance(user, User)
    assert user.address is not None
    assert user.address.latitude == 3.43 and user.address.longitude == 10.111
    assert isinstance(user.address, Address)


@pytest.mark.asyncio
async def test_repository_can_make_logical_queries(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(UserTable).values(id=1, name="test", age=20))
        await session.execute(insert(UserTable).values(id=2, name="test1", age=21))
        await session.execute(insert(UserTable).values(id=3, name="test2", age=22))
        await session.execute(insert(UserTable).values(id=4, name="test3", age=23))

    users = await repo.find_by_id_or_name_and_age_lowerThan(id=4, name="test2", age=23)
    assert len(users) == 2

    ids = [u.id for u in users]
    assert sorted(ids) == [3, 4]


@pytest.mark.asyncio
async def test_repository_can_use_raw_method_entity(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(UserTable).values(id=1, name="test", age=20))

    user = await repo.get_user(1)

    assert user is not None
    assert user.id == 1
    assert user.name == "test" and user.age == 20
