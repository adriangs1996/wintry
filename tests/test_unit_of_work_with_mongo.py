from dataclasses import dataclass, field
from typing import Any, AsyncGenerator
from winter import get_connection, init_backend

from winter.repository.base import repository
from winter.repository.crud_repository import CrudRepository
from winter.settings import ConnectionOptions, WinterSettings
from winter.unit_of_work import UnitOfWork
import pytest
import pytest_asyncio
from bson import ObjectId


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


@repository(User, mongo_session_managed=True)
class UserRepository(CrudRepository[User, int]):
    pass


@dataclass
class Hero:
    name: str
    id: str = field(default_factory=lambda: str(ObjectId()))


@repository(Hero, table_name="heroes")
class HeroRepository(CrudRepository[Hero, str]):
    async def get_by_name(self, *, name: str) -> Hero | None:
        ...


class HeroUow(UnitOfWork):
    heroes: HeroRepository

    def __init__(self, heroes: HeroRepository) -> None:
        super().__init__(heroes=heroes)


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
    await db.heroes.delete_many({})


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


@pytest.mark.asyncio
async def test_unit_of_work_automatically_creates_related_objects(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    await db.users.insert_one({"id": 1, "age": 28, "name": "Batman"})

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.address = Address(latitude=12.1, longitude=1.1)
        await uow.commit()

    user_row = await db.users.find_one({"id": 1})
    assert user_row["address"] == {"latitude": 12.1, "longitude": 1.1}


@pytest.mark.asyncio
async def test_unit_of_work_can_track_objects_in_lists(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    await db.users.insert_one({"id": 1, "age": 28, "name": "Batman"})
    await db.users.insert_one({"id": 2, "age": 30, "name": "Superman"})
    await db.users.insert_one({"id": 3, "age": 24, "name": "Flash"})
    await db.users.insert_one({"id": 4, "age": 26, "name": "Aquaman"})
    await db.users.insert_one({"id": 5, "age": 29, "name": "IronMan"})

    async with uow:
        users = await uow.users.find()
        users[2].name = "Luke"
        await uow.commit()

    user_row = await db.users.find_one({"name": "Luke"})
    assert user_row is not None


@pytest.mark.asyncio
async def test_unit_of_work_respects_ignore_synchronization_flag(clean: Any, db: Any) -> None:
    hero_repository = HeroRepository()
    uow = HeroUow(hero_repository)

    await db.heroes.insert_one({"id": str(ObjectId()), "name": "Batman"})

    async with uow:
        hero = await uow.heroes.get_by_name(name="Batman")
        assert hero is not None
        hero.name = "Superman"
        await uow.commit()

    row = await db.heroes.find_one({"name": "Superman"})
    assert row is None

    rows = await db.heroes.find({}).to_list(None)
    assert len(rows) == 1
