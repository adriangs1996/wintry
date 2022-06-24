from dataclasses import field
from typing import Any, AsyncGenerator
from wintry import get_connection, init_backends
from wintry.models import Model

from wintry.repository import Repository, RepositoryRegistry
from wintry.repository.base import query, managed
from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings
from wintry.transactions import UnitOfWork
import pytest
import pytest_asyncio
from bson import ObjectId


class Address(Model):
    latitude: float
    longitude: float


class User(Model):
    id: int
    name: str
    age: int
    address: Address | None = None
    heroes: "list[Hero]" = field(default_factory=list)


class UserRepository(Repository[User, int], entity=User):
    @managed
    async def get_user_by_name(self, name: str):
        db = await self.connection()
        row = await db.users.find_one({"name": name})

        if row is not None:
            return User.build(row)
        else:
            return None


class Hero(Model):
    name: str
    id: str = field(default_factory=lambda: str(ObjectId()))


class HeroRepository(Repository[Hero, str], entity=Hero, table_name="heroes"):
    @query
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


@pytest_asyncio.fixture(scope="module", autouse=True)
async def db() -> Any:
    RepositoryRegistry.configure_for_nosql()
    init_backends(
        WinterSettings(
            backends=[
                BackendOptions(
                    connection_options=ConnectionOptions(
                        url="mongodb://localhost:27017/tests"
                    ),
                )
            ]
        )
    )

    return await get_connection()


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
async def test_unit_of_work_makes_context_for_objects_synchronization(
    clean: Any, db: Any
) -> None:
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
async def test_unit_of_work_automatically_creates_related_objects(
    clean: Any, db: Any
) -> None:
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
async def test_unit_of_work_synchronize_nested_objects(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    await db.users.insert_one(
        {
            "id": 1,
            "age": 28,
            "name": "Batman",
            "address": {"latitude": 1.0, "longitude": 2.0},
        }
    )

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        assert user.address is not None
        user.address.latitude = 3.0
        await uow.commit()

    user_row = await db.users.find_one({"id": 1})
    assert user_row["address"] == {"latitude": 3.0, "longitude": 2.0}


@pytest.mark.asyncio
async def test_unit_of_work_synchronize_on_list_append(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    await db.users.insert_one(
        {
            "id": 1,
            "age": 28,
            "name": "Batman",
            "address": {"latitude": 1.0, "longitude": 2.0},
        }
    )

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        user.heroes.append(Hero(name="Batgirl"))
        await uow.commit()

    user_row = await db.users.find_one({"id": 1})
    assert len(user_row["heroes"]) == 1


@pytest.mark.asyncio
async def test_unit_of_work_synchronize_on_list_remove(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    await db.users.insert_one(
        {
            "id": 1,
            "age": 28,
            "name": "Batman",
            "address": {"latitude": 1.0, "longitude": 2.0},
            "heroes": [{"id": str(ObjectId()), "name": "Batgirl"}],
        }
    )

    async with uow:
        user = await uow.users.get_by_id(id=1)
        assert user is not None
        assert user.heroes != []
        hero = user.heroes[0]
        user.heroes.remove(hero)
        await uow.commit()

    user = await db.users.find_one({"id": 1})
    assert user is not None
    assert user["heroes"] == []


@pytest.mark.asyncio
async def test_unit_of_work_updates_entity_after_creating_it(clean: Any, db: Any) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    async with uow:
        user = await uow.users.create(entity=User(id=1, name="Batman", age=28))
        user.name = "Superman"
        await uow.commit()

    new_user = await user_repository.get_by_id(id=1)
    assert new_user is not None
    assert new_user.name == "Superman"


@pytest.mark.asyncio
async def test_unit_of_work_updates_entity_after_creating_it_get_with_raw_method(
    clean: Any, db: Any
) -> None:
    user_repository = UserRepository()
    uow = Uow(user_repository)

    await db.users.insert_one({"id": 1, "name": "Batman", "age": 20})

    async with uow:
        user = await uow.users.get_user_by_name("Batman")
        assert user is not None
        user.name = "Superman"
        await uow.commit()

    new_user = await user_repository.get_by_id(id=1)
    assert new_user is not None
    assert new_user.name == "Superman"
