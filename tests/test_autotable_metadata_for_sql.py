from typing import Any, AsyncGenerator, List, Optional
from wintry import init_backends, get_connection, BACKENDS
from wintry.generators import AutoString
from wintry.models import Array, Id, ModelRegistry, metadata, Model
from wintry.repository.base import query

from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings

from sqlalchemy import delete, select, insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.engine.result import Result
import pytest
import pytest_asyncio
from wintry.transactions import UnitOfWork


# Now import the repository
from wintry.repository import Repository
from wintry.utils.virtual_db_schema import get_model_sql_table


class UserAddress(Model, table="AutotableUsers"):
    id: int
    latitude: float
    longitude: float
    users: "list[TestUser]" = Array()


class TestUser(Model, table="AutotableTestUsers"):
    id: int
    name: str
    age: int
    address: UserAddress | None = None


class Foo(Model, table="AutotableFoo"):
    x: int
    id: str = Id(default_factory=AutoString)
    bar: "Optional[Bar]" = None


class Bar(Model, table="AutotableBar"):
    y: int
    id: str = Id(default_factory=AutoString)
    foo: Foo | None = None


class UserRepository(Repository[TestUser, int], entity=TestUser):
    @query
    async def find_by_id_or_name_and_age_lowerThan(
        self, *, id: int, name: str, age: int
    ) -> List[TestUser]:
        ...


class FooRepository(Repository[Foo, str], entity=Foo):
    @query
    async def find_by_bar__y_lowerThan(self, *, bar__y: int) -> list[Foo]:
        ...


# define a custom uow so we got intellisense, this is for type-checkers only
class Uow(UnitOfWork):
    users: UserRepository
    foos: FooRepository

    def __init__(self, users: UserRepository, foos: FooRepository) -> None:
        super().__init__(users=users, foos=foos)


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
    conn = await engine.connect()
    await conn.run_sync(metadata.create_all)
    await conn.commit()
    await conn.close()


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    testuser = get_model_sql_table(TestUser)
    useraddress = get_model_sql_table(UserAddress)
    foo = get_model_sql_table(Foo)
    bar = get_model_sql_table(Bar)
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(delete(testuser))
    await session.execute(delete(useraddress))
    await session.execute(delete(foo))
    await session.execute(delete(bar))
    await session.commit()
    await session.close()


@pytest.mark.asyncio
async def test_repository_can_insert(clean: Any) -> None:
    repo = UserRepository()
    user = TestUser(id=2, name="test", age=10)

    await repo.create(entity=user)
    testuser = get_model_sql_table(TestUser)
    session: AsyncConnection = await get_connection()
    results = (await session.execute(select(testuser))).fetchall()
    await session.close()
    assert len(results) == 1


@pytest.mark.asyncio
async def test_repository_can_delete(clean: Any) -> None:
    repo = UserRepository()
    testuser = get_model_sql_table(TestUser)
    session: AsyncConnection = await get_connection()
    async with session.begin():
        await session.execute(insert(testuser).values(id=1, name="test", age=26))

    await repo.delete()

    async with session.begin():
        result: Result = await session.execute(select(testuser))
        rows = result.fetchall()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_delete_by_id(clean: Any) -> None:
    repo = UserRepository()
    testuser = get_model_sql_table(TestUser)
    session: AsyncConnection = await get_connection()
    async with session.begin():
        await session.execute(insert(testuser).values(id=1, name="test", age=26))

    await repo.delete_by_id(id=1)

    async with session.begin():
        result: Result = await session.execute(select(testuser))
        rows = result.fetchall()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_get_by_id(clean: Any) -> None:
    repo = UserRepository()
    testuser = get_model_sql_table(TestUser)
    session: AsyncConnection = await get_connection()
    async with session.begin():
        await session.execute(insert(testuser).values(id=1, name="test", age=26))

    user = await repo.get_by_id(id=1)

    assert isinstance(user, TestUser)
    assert user.name == "test" and user.age == 26


@pytest.mark.asyncio
async def test_repository_can_list_all_users(clean: Any) -> None:
    repo = UserRepository()
    testuser = get_model_sql_table(TestUser)
    session: AsyncConnection = await get_connection()
    async with session.begin():
        await session.execute(insert(testuser).values(id=1, name="test", age=26))
        await session.execute(insert(testuser).values(id=2, name="test1", age=26))
        await session.execute(insert(testuser).values(id=3, name="test2", age=26))
        await session.execute(insert(testuser).values(id=4, name="test3", age=26))

    users = await repo.find()

    assert len(users) == 4
    assert all(isinstance(user, TestUser) for user in users)


@pytest.mark.asyncio
async def test_repository_can_get_object_with_related_data_loaded(clean: Any) -> None:
    repo = UserRepository()
    address = get_model_sql_table(UserAddress)
    testuser = get_model_sql_table(TestUser)
    session: AsyncConnection = await get_connection()
    async with session.begin():
        await session.execute(
            insert(address).values(id=1, latitude=3.43, longitude=10.111)
        )
        await session.execute(
            insert(testuser).values(id=1, name="test", age=26, address=1)
        )

    user = await repo.get_by_id(id=1)

    assert isinstance(user, TestUser)
    assert user.address is not None
    assert user.address.latitude == 3.43 and user.address.longitude == 10.111
    assert isinstance(user.address, UserAddress)


@pytest.mark.asyncio
async def test_repository_can_make_logical_queries(clean: Any) -> None:
    repo = UserRepository()
    testuser = get_model_sql_table(TestUser)
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(testuser).values(id=1, name="test", age=20))
    await session.execute(insert(testuser).values(id=2, name="test1", age=21))
    await session.execute(insert(testuser).values(id=3, name="test2", age=22))
    await session.execute(insert(testuser).values(id=4, name="test3", age=23))
    await session.commit()
    await session.close()

    users = await repo.find_by_id_or_name_and_age_lowerThan(id=4, name="test2", age=23)
    assert len(users) == 1

    ids = [u.id for u in users]
    assert sorted(ids) == [3]


@pytest.mark.asyncio
async def test_uow_abort_transaction_by_default(clean: Any) -> Any:
    testuser = get_model_sql_table(TestUser)
    repo = UserRepository()
    uow = Uow(repo, FooRepository())

    async with uow:
        user = TestUser(id=2, name="test", age=10)
        await uow.users.create(entity=user)

    session: AsyncConnection = await get_connection()
    session.begin()
    results: Result = await session.execute(select(testuser))
    await session.close()
    assert results.fetchall() == []


@pytest.mark.asyncio
async def test_uow_commits_transaction_with_explicit_commit(clean: Any) -> None:
    testuser = get_model_sql_table(TestUser)
    repo = UserRepository()
    uow = Uow(repo, FooRepository())

    async with uow:
        user = TestUser(id=2, name="test", age=10)
        await uow.users.create(entity=user)
        await uow.commit()

    session: AsyncConnection = await get_connection()
    session.begin()
    results: Result = await session.execute(select(testuser))
    session.close()

    assert len(results.all()) == 1


@pytest.mark.asyncio
async def test_uow_rollbacks_on_error(clean: Any) -> None:
    testuser = get_model_sql_table(TestUser)
    repo = UserRepository()
    uow = Uow(repo, FooRepository())

    with pytest.raises(ZeroDivisionError):
        async with uow:
            user = TestUser(id=2, name="test", age=10)
            await uow.users.create(entity=user)
            user2 = TestUser(id=1, name="test", age=int(10 / 0))
            await uow.users.create(entity=user2)
            await uow.commit()

    session: AsyncConnection = await get_connection()
    results: Result = await session.execute(select(testuser))

    assert results.all() == []


@pytest.mark.asyncio
async def test_uow_automatically_synchronize_objects(clean: Any) -> None:
    testuser = get_model_sql_table(TestUser)
    address = get_model_sql_table(UserAddress)
    user_repository = UserRepository()
    uow = Uow(user_repository, FooRepository())

    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(testuser).values(id=1, name="test", age=20))
    await session.commit()
    await session.close()

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.address = UserAddress(id=3, latitude=1.12, longitude=4.13)

        await uow.commit()

    session: AsyncConnection = await get_connection()
    results: Result = await session.execute(select(address))
    await session.close()

    assert len(results.all()) == 1


@pytest.mark.asyncio
async def test_uow_automatically_updates_object(clean: Any) -> None:
    testuser = get_model_sql_table(TestUser)
    user_repository = UserRepository()
    uow = Uow(user_repository, FooRepository())

    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(insert(testuser).values(id=1, name="test", age=20))
    await session.commit()
    await session.close()

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.age = 30
        user.name = "updated"

        await uow.commit()

    session: AsyncConnection = await get_connection()
    results = await session.execute(select(testuser))
    await session.close()

    user = results.fetchall()[0]
    assert user.age == 30 and user.name == "updated"


@pytest.mark.asyncio
async def test_one_to_one_relation(clean: Any):
    footable = get_model_sql_table(Foo)
    bartable = get_model_sql_table(Bar)
    repo = FooRepository()
    foo = Foo(x=10, bar=Bar(y=30))

    await repo.create(entity=foo)

    session: AsyncConnection = await get_connection()
    session.begin()
    foo_results = await session.execute(select(footable))
    bar_results = await session.execute(select(bartable))
    await session.commit()
    await session.close()

    assert len(foo_results.unique().all()) == 1
    assert len(bar_results.unique().all()) == 1


@pytest.mark.asyncio
async def test_one_to_one_relation_retrieve_related(clean: Any):
    repo = FooRepository()
    foo = Foo(x=10, bar=Bar(y=30))

    await repo.create(entity=foo)

    new_foo = await repo.get_by_id(id=foo.id)

    assert new_foo is not None
    assert new_foo.bar is not None


@pytest.mark.asyncio
async def test_foo_repo_can_ask_for_related_field(clean: Any):
    repo = FooRepository()
    await repo.create(entity=Foo(x=10, bar=Bar(y=30)))
    await repo.create(entity=Foo(x=10, bar=Bar(y=40)))
    await repo.create(entity=Foo(x=10, bar=Bar(y=50)))
    await repo.create(entity=Foo(x=10, bar=Bar(y=60)))
    await repo.create(entity=Foo(x=10, bar=Bar(y=70)))

    foos = await repo.find_by_bar__y_lowerThan(bar__y=50)

    assert len(foos) == 2
