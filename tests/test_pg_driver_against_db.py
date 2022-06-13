from typing import Any, AsyncGenerator, List
from wintry import init_backends, get_connection, BACKENDS
from wintry.models import Array, Model, ModelRegistry, metadata
from wintry.orm.aql import get
from wintry.repository.base import managed, query

from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings
from wintry.utils.virtual_db_schema import get_model_sql_table

from wintry.orm.mapping import for_model
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
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.engine.result import Result
import pytest
import pytest_asyncio
from dataclasses import field


# Now import the repository
from wintry.repository import Repository, managed


class Address(Model, table="TestPgDriverAddress"):
    id: int
    latitude: float
    longitude: float
    users: "list[User]" = Array()


class User(Model, table="TestPgDriverUser"):
    id: int
    name: str
    age: int
    address: Address | None = None


class UserRepository(Repository[User, int], entity=User):
    @query
    async def find_by_id_or_name_and_age_lowerThan(
        self, *, id: int, name: str, age: int
    ) -> List[User]:
        ...

    @managed
    async def get_user(self, id: int) -> User | None:
        return await self.exec(get(User).by(User.id == id))


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup():
    ModelRegistry.configure()
    init_backends(
        WinterSettings(
            backends=[
                BackendOptions(
                    driver="wintry.drivers.pg",
                    connection_options=ConnectionOptions(
                        url="sqlite+aiosqlite:///:memory:"
                    ),
                )
            ],
        )
    )
    engine = getattr(BACKENDS["default"].driver, "_engine")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


@pytest.fixture(scope="module")
def UserTable():
    return get_model_sql_table(User)


@pytest.fixture(scope="module")
def AddressTable():
    return get_model_sql_table(Address)


@pytest_asyncio.fixture
async def clean(UserTable, AddressTable) -> AsyncGenerator[None, None]:
    yield
    session = await get_connection()
    session.begin()
    await session.execute(delete(UserTable))
    await session.execute(delete(AddressTable))
    await session.commit()
    await session.close()


@pytest.mark.asyncio
async def test_repository_can_insert(clean: Any) -> None:
    user_table = get_model_sql_table(User)
    repo = UserRepository()
    user = User(id=2, name="test", age=10)

    await repo.create(entity=user)
    session: AsyncConnection = await get_connection()
    session.begin()
    results: Result = await session.execute(select(user_table))
    assert len(results.all()) == 1
    await session.close()


@pytest.mark.asyncio
async def test_repository_can_delete(clean: Any, UserTable) -> None:
    repo = UserRepository()
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(UserTable).values(id=1, name="test", age=26))
    await session.commit()
    await session.close()

    await repo.delete()

    session: AsyncConnection = await get_connection()
    session.begin()
    result: Result = await session.execute(select(UserTable))
    rows = result.all()
    await session.commit()
    await session.close()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_delete_by_id(clean: Any, UserTable) -> None:
    repo = UserRepository()
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(UserTable).values(id=1, name="test", age=26))
    await session.commit()
    await session.close()

    await repo.delete_by_id(id=1)

    session: AsyncConnection = await get_connection()
    session.begin()
    result: Result = await session.execute(select(UserTable))
    rows = result.all()
    await session.close()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_get_by_id(clean: Any, UserTable) -> None:
    repo = UserRepository()
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(UserTable).values(id=1, name="test", age=26))
    await session.commit()
    await session.close()

    user = await repo.get_by_id(id=1)

    assert isinstance(user, User)
    assert user.name == "test" and user.age == 26


@pytest.mark.asyncio
async def test_repository_can_list_all_users(clean: Any, UserTable) -> None:
    repo = UserRepository()
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(UserTable).values(id=1, name="test", age=26))
    await session.execute(insert(UserTable).values(id=2, name="test1", age=26))
    await session.execute(insert(UserTable).values(id=3, name="test2", age=26))
    await session.execute(insert(UserTable).values(id=4, name="test3", age=26))
    await session.commit()
    await session.close()

    users = await repo.find()

    assert len(users) == 4
    assert all(isinstance(user, User) for user in users)


@pytest.mark.asyncio
async def test_repository_can_get_object_with_related_data_loaded(
    clean: Any, UserTable, AddressTable
) -> None:
    repo = UserRepository()
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(
        insert(AddressTable).values(id=1, latitude=3.43, longitude=10.111)
    )
    await session.execute(insert(UserTable).values(id=1, name="test", age=26, address=1))
    await session.commit()
    await session.close()

    user = await repo.get_by_id(id=1)

    assert isinstance(user, User)
    assert user.address is not None
    assert user.address.latitude == 3.43 and user.address.longitude == 10.111
    assert isinstance(user.address, Address)


@pytest.mark.asyncio
async def test_repository_can_make_logical_queries(clean: Any, UserTable) -> None:
    repo = UserRepository()
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(UserTable).values(id=1, name="test", age=20))
    await session.execute(insert(UserTable).values(id=2, name="test1", age=21))
    await session.execute(insert(UserTable).values(id=3, name="test2", age=22))
    await session.execute(insert(UserTable).values(id=4, name="test3", age=23))
    await session.commit()
    await session.close()

    # this should run : (id or name) and age < 23 -> User(id=3, name="Test2", age=22)
    users = await repo.find_by_id_or_name_and_age_lowerThan(id=4, name="test2", age=23)
    assert len(users) == 1

    ids = [u.id for u in users]
    assert sorted(ids) == [3]


@pytest.mark.asyncio
async def test_repository_can_use_raw_method_entity(clean: Any, UserTable) -> None:
    repo = UserRepository()
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(UserTable).values(id=1, name="test", age=20))
    await session.commit()
    await session.close()

    user = await repo.get_user(1)

    assert user is not None
    assert user.id == 1
    assert user.name == "test" and user.age == 20
