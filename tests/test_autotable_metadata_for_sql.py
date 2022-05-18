from typing import Any, AsyncGenerator, List, Optional
from wintry import init_backends, get_connection, BACKENDS
from wintry.models import VirtualDatabaseSchema, Model

from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings

from sqlalchemy import delete, select, insert, MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine.result import Result
import pytest
import pytest_asyncio
from dataclasses import field
from wintry.transactions import UnitOfWork
from uuid import uuid4


# Now import the repository
from wintry.repository import Repository, RepositoryRegistry


metadata = MetaData()


class UserAddress(Model):
    id: int
    latitude: float
    longitude: float
    users: list["TestUser"] = field(default_factory=list)


class TestUser(Model):
    id: int
    name: str
    age: int
    address: UserAddress | None = None


class Foo(Model):
    x: int
    id: str = field(default_factory=lambda : uuid4().hex)
    bar: Optional["Bar"] = None


class Bar(Model):
    y: int
    id: str = field(default_factory=lambda : uuid4().hex)
    foo: Foo | None = None


class UserRepository(Repository[TestUser, int], entity=TestUser):
    async def find_by_id_or_name_and_age_lowerThan(
        self, *, id: int, name: str, age: int
    ) -> List[TestUser]:
        ...

class FooRepository(Repository[Foo, str], entity=Foo):
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
    VirtualDatabaseSchema.use_sqlalchemy(metadata=metadata)
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
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(delete(TestUser))
        await session.execute(delete(UserAddress))
        await session.execute(delete(Foo))
        await session.execute(delete(Bar))
        await session.commit()


@pytest.mark.asyncio
async def test_repository_can_insert(clean: Any) -> None:
    repo = UserRepository()
    user = TestUser(id=2, name="test", age=10)

    await repo.create(entity=user)
    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(TestUser))
    assert len(results.unique().all()) == 1


@pytest.mark.asyncio
async def test_repository_can_delete(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(TestUser).values(id=1, name="test", age=26))

    await repo.delete()

    async with session.begin():
        result: Result = await session.execute(select(TestUser))
        rows = result.all()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_delete_by_id(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(TestUser).values(id=1, name="test", age=26))

    await repo.delete_by_id(id=1)

    async with session.begin():
        result: Result = await session.execute(select(TestUser))
        rows = result.all()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_get_by_id(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(TestUser).values(id=1, name="test", age=26))

    user = await repo.get_by_id(id=1)

    assert isinstance(user, TestUser)
    assert user.name == "test" and user.age == 26


@pytest.mark.asyncio
async def test_repository_can_list_all_users(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(TestUser).values(id=1, name="test", age=26))
        await session.execute(insert(TestUser).values(id=2, name="test1", age=26))
        await session.execute(insert(TestUser).values(id=3, name="test2", age=26))
        await session.execute(insert(TestUser).values(id=4, name="test3", age=26))

    users = await repo.find()

    assert len(users) == 4
    assert all(isinstance(user, TestUser) for user in users)


@pytest.mark.asyncio
async def test_repository_can_get_object_with_related_data_loaded(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(
            insert(UserAddress).values(id=1, latitude=3.43, longitude=10.111)
        )
        await session.execute(
            insert(TestUser).values(id=1, name="test", age=26, address_id=1)
        )

    user = await repo.get_by_id(id=1)

    assert isinstance(user, TestUser)
    assert user.address is not None
    assert user.address.latitude == 3.43 and user.address.longitude == 10.111
    assert isinstance(user.address, UserAddress)


@pytest.mark.asyncio
async def test_repository_can_make_logical_queries(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(TestUser).values(id=1, name="test", age=20))
        await session.execute(insert(TestUser).values(id=2, name="test1", age=21))
        await session.execute(insert(TestUser).values(id=3, name="test2", age=22))
        await session.execute(insert(TestUser).values(id=4, name="test3", age=23))

    users = await repo.find_by_id_or_name_and_age_lowerThan(id=4, name="test2", age=23)
    assert len(users) == 2

    ids = [u.id for u in users]
    assert sorted(ids) == [3, 4]


@pytest.mark.asyncio
async def test_uow_abort_transaction_by_default(clean: Any) -> Any:
    repo = UserRepository()
    uow = Uow(repo, FooRepository())

    async with uow:
        user = TestUser(id=2, name="test", age=10)
        await uow.users.create(entity=user)

    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(TestUser))

    assert results.all() == []


@pytest.mark.asyncio
async def test_uow_commits_transaction_with_explicit_commit(clean: Any) -> None:
    repo = UserRepository()
    uow = Uow(repo, FooRepository())

    async with uow:
        user = TestUser(id=2, name="test", age=10)
        await uow.users.create(entity=user)
        await uow.commit()

    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(TestUser))

    assert len(results.unique().all()) == 1


@pytest.mark.asyncio
async def test_uow_rollbacks_on_error(clean: Any) -> None:
    repo = UserRepository()
    uow = Uow(repo, FooRepository())

    with pytest.raises(ZeroDivisionError):
        async with uow:
            user = TestUser(id=2, name="test", age=10)
            await uow.users.create(entity=user)
            user2 = TestUser(id=1, name="test", age=int(10 / 0))
            await uow.users.create(entity=user2)
            await uow.commit()

    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(TestUser))

    assert results.all() == []


@pytest.mark.asyncio
async def test_uow_automatically_synchronize_objects(clean: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository, FooRepository())

    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(TestUser).values(id=1, name="test", age=20))

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.address = UserAddress(id=3, latitude=1.12, longitude=4.13)

        await uow.commit()

    async with session.begin():
        results: Result = await session.execute(select(UserAddress))

    assert len(results.unique().all()) == 1


@pytest.mark.asyncio
async def test_uow_automatically_updates_object(clean: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository, FooRepository())

    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(TestUser).values(id=1, name="test", age=20))

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.age = 30
        user.name = "updated"

        await uow.commit()

    async with session.begin():
        results: Result = await session.execute(select(TestUser))

    user = results.unique().scalars().all()[0]
    assert user.age == 30 and user.name == "updated"


@pytest.mark.asyncio
async def test_one_to_one_relation(clean: Any):
    repo = FooRepository()
    foo = Foo(x=10, bar=Bar(y=30))

    await repo.create(entity=foo)

    session: AsyncSession = get_connection()
    async with session.begin():
        foo_results: Result = await session.execute(select(Foo))
        bar_results: Result = await session.execute(select(Bar))

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