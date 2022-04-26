from typing import Any, AsyncGenerator, List
from winter import init_backend, get_connection

from winter.settings import ConnectionOptions, WinterSettings


import winter.backend

from winter.orm import for_model
from sqlalchemy import Integer, Column, String, ForeignKey, Float, delete, select, insert
from sqlalchemy.orm import relation, declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine.result import Result
import pydantic as pdc
import pytest
import pytest_asyncio


# Now import the repository
from winter.repository.base import repository
from winter.repository.crud_repository import CrudRepository


class Address:
    def __init__(self, latitude: float, longitude: float, users: List['User'] = []) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.users = users


class User:
    def __init__(self, *, id: int, name: str, age: int, address: Address | None = None) -> None:
        self.id = id
        self.name = name
        self.age = age
        self.address = address


# Define the table schemas
Base: Any = declarative_base()


@for_model(Address)
class AddressTable(Base):
    __tablename__ = "Addresses"
    id = Column(Integer, primary_key=True)
    latitude = Column(Float)
    longitude = Column(Float)


@for_model(User)
class UserTable(Base):
    __tablename__ = "Users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)
    address_id = Column(Integer, ForeignKey("Addresses.id"))
    address = relation(AddressTable, lazy="joined", backref="users")


@repository(User)
class UserRepository(CrudRepository[User, int]):
    async def find_by_id_or_name_and_age_lowerThan(self, *, id: int, name: str, age: int) -> List[User]:
        ...


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
        await conn.run_sync(Base.metadata.create_all)


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
    session: AsyncSession = winter.backend.Backend.get_connection()
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
        await session.execute(insert(AddressTable).values(id=1, latitude=3.43, longitude=10.111))
        await session.execute(insert(UserTable).values(id=1, name="test", age=26, address_id=1))

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
async def test_repository_can_update_entity(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(UserTable).values(id=1, name="test", age=20))

    