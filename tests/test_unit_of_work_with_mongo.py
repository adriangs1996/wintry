from dataclasses import dataclass
from typing import Any, AsyncGenerator
from winter import get_connection, init_backend

from winter.repository.base import repository
from winter.repository.crud_repository import CrudRepository
from winter.settings import ConnectionOptions, WinterSettings
from winter.unit_of_work import UnitOfWork
import pytest
import pytest_asyncio


@dataclass
class Address:
    latitude: float
    longitude: float


@dataclass
class User:
    id: int
    name: str
    age: int
    address: Address | None = None


@repository(User)
class UserRepository(CrudRepository[User, int]):
    pass


class Uow(UnitOfWork):
    users: UserRepository

    def __init__(self, users: UserRepository) -> None:
        super().__init__(users=users)


@pytest.fixture(scope="module", autouse=True)
def db() -> Any:
    init_backend(
        WinterSettings(
            backend="winter.drivers.mongo",
            connection_options=ConnectionOptions(url="mongodb://localhost:27017/?replicaSet=dbrs"),
        )
    )

    return get_connection()


@pytest_asyncio.fixture()
async def clean(db: Any) -> AsyncGenerator[None, None]:
    yield
    await db.users.delete_many({})


@pytest.mark.asyncio
async def test_unit_of_work_abort_transaction_by_default(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    async with uow:
        user = User(id=1, age=28, name="Batman")
        await uow.users.create(entity=user)

    rows = await db.users.find({}).to_list(None)
    assert rows == []


@pytest.mark.asyncio
async def test_unit_of_work_save_object_on_commit(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    async with uow:
        user = User(id=1, age=28, name="Batman")
        await uow.users.create(entity=user)
        await uow.commit()

    rows = await db.users.find({}).to_list(None)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_unit_of_work_rollbacks_when_error(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    with pytest.raises(ZeroDivisionError):
        async with uow:
            user = User(id=1, age=28, name="Batman")
            await uow.users.create(entity=user)
            await uow.users.create(entity=User(id=2, age=20 // 0, name="tests"))
            await uow.commit()

    rows = await db.users.find({}).to_list(None)
    assert rows == []


@pytest.mark.asyncio
async def test_unit_of_work_makes_context_for_objects_synchronization(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    await db.users.insert_one({"id": 1, "age": 28, "name": "Batman"})

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.age = 30
        user.name = "Superman"

        await uow.commit()

    user_row = await db.users.find_one({"id": 1})
    assert user_row["name"] == "Superman"
    assert user_row["age"] == 30
