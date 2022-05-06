from typing import Any, AsyncGenerator, List
from winter import init_backends, get_connection, BACKENDS
from winter.models import entity

from winter.settings import BackendOptions, ConnectionOptions, WinterSettings

from sqlalchemy import delete, select, insert, MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine.result import Result
import pytest
import pytest_asyncio
from dataclasses import field
from winter.transactions import UnitOfWork


# Now import the repository
from winter.repository import Repository


metadata = MetaData()


@entity(create_metadata=True, name="Addresses", metadata=metadata)
class Address:
    id: int
    latitude: float
    longitude: float
    users: list["User"] = field(default_factory=list)


@entity(create_metadata=True, metadata=metadata)
class User:
    id: int
    name: str
    age: int
    address: Address | None = None


class UserRepository(Repository[User, int], entity=User):
    async def find_by_id_or_name_and_age_lowerThan(
        self, *, id: int, name: str, age: int
    ) -> List[User]:
        ...


# define a custom uow so we got intellisense, this is for type-checkers only
class Uow(UnitOfWork):
    users: UserRepository

    def __init__(self, users: UserRepository) -> None:
        super().__init__(users=users)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup() -> None:
    init_backends(
        WinterSettings(
            backends=[
                BackendOptions(
                    driver="winter.drivers.pg",
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
        await session.execute(delete(User))
        await session.execute(delete(Address))
        await session.commit()


@pytest.mark.asyncio
async def test_repository_can_insert(clean: Any) -> None:
    repo = UserRepository()
    user = User(id=2, name="test", age=10)

    await repo.create(entity=user)
    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(User))
    assert len(results.all()) == 1


@pytest.mark.asyncio
async def test_repository_can_delete(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(User).values(id=1, name="test", age=26))

    await repo.delete()

    async with session.begin():
        result: Result = await session.execute(select(User))
        rows = result.all()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_delete_by_id(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(User).values(id=1, name="test", age=26))

    await repo.delete_by_id(id=1)

    async with session.begin():
        result: Result = await session.execute(select(User))
        rows = result.all()

    assert rows == []


@pytest.mark.asyncio
async def test_repository_can_get_by_id(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(User).values(id=1, name="test", age=26))

    user = await repo.get_by_id(id=1)

    assert isinstance(user, User)
    assert user.name == "test" and user.age == 26


@pytest.mark.asyncio
async def test_repository_can_list_all_users(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(User).values(id=1, name="test", age=26))
        await session.execute(insert(User).values(id=2, name="test1", age=26))
        await session.execute(insert(User).values(id=3, name="test2", age=26))
        await session.execute(insert(User).values(id=4, name="test3", age=26))

    users = await repo.find()

    assert len(users) == 4
    assert all(isinstance(user, User) for user in users)


@pytest.mark.asyncio
async def test_repository_can_get_object_with_related_data_loaded(clean: Any) -> None:
    repo = UserRepository()
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(
            insert(Address).values(id=1, latitude=3.43, longitude=10.111)
        )
        await session.execute(
            insert(User).values(id=1, name="test", age=26, address_id=1)
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
        await session.execute(insert(User).values(id=1, name="test", age=20))
        await session.execute(insert(User).values(id=2, name="test1", age=21))
        await session.execute(insert(User).values(id=3, name="test2", age=22))
        await session.execute(insert(User).values(id=4, name="test3", age=23))

    users = await repo.find_by_id_or_name_and_age_lowerThan(id=4, name="test2", age=23)
    assert len(users) == 2

    ids = [u.id for u in users]
    assert sorted(ids) == [3, 4]


@pytest.mark.asyncio
async def test_uow_abort_transaction_by_default(clean: Any) -> Any:
    repo = UserRepository()
    uow = Uow(repo)

    async with uow:
        user = User(id=2, name="test", age=10)
        await uow.users.create(entity=user)

    session: AsyncSession = get_connection()
    async with session.begin():
        results: Result = await session.execute(select(User))

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
        results: Result = await session.execute(select(User))

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
        results: Result = await session.execute(select(User))

    assert results.all() == []


@pytest.mark.asyncio
async def test_uow_automatically_synchronize_objects(clean: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(User).values(id=1, name="test", age=20))

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.address = Address(id=3, latitude=1.12, longitude=4.13)

        await uow.commit()

    async with session.begin():
        results: Result = await session.execute(select(Address))

    assert len(results.all()) == 1


@pytest.mark.asyncio
async def test_uow_automatically_updates_object(clean: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(insert(User).values(id=1, name="test", age=20))

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.age = 30
        user.name = "updated"

        await uow.commit()

    async with session.begin():
        results: Result = await session.execute(select(User))

    user = results.scalars().all()[0]
    assert user.age == 30 and user.name == "updated"