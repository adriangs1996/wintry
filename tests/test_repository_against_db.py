from typing import Any, AsyncGenerator, List, Optional
from wintry import init_backends, get_connection
from wintry.models import Model
from wintry.repository import raw_method
from wintry.repository import Repository, RepositoryRegistry
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase
from dataclasses import field
from dataclass_wizard import fromdict
from bson import ObjectId


class Address(Model):
    latitude: float
    longitude: float


class User(Model):
    id: int
    name: str
    age: int
    address: Optional[Address] = None


class City(Model):
    name: str
    id: str = field(default_factory=lambda: str(ObjectId()))


class Hero(Model, unsafe_hash=True):
    id: int
    name: str
    cities: list[City] = field(default_factory=list)


@pytest.fixture(scope="module", autouse=True)
def db() -> AsyncIOMotorDatabase:
    RepositoryRegistry.configure_for_nosql()
    init_backends()
    return get_connection()  # type: ignore


class UserRepository(Repository[User, int], entity=User):
    @raw_method
    async def get_user_by_name(self, name: str, session: Any = None) -> User | None:
        db = self.connection()
        row = await db.users.find_one({"name": name})
        if row is not None:
            return User.build(row)
        else:
            return None

    @raw_method
    async def list(self, session: Any = None) -> List[User]:
        return await self.find()

    async def find_by_name_or_age_lowerThan(self, *, name: str, age: int) -> List[User]:
        ...

    async def find_by_address__latitude(self, *, address__latitude: float) -> List[User]:
        ...


class HeroRepository(Repository[Hero, int], entity=Hero, table_name="heroes"):
    pass


@pytest_asyncio.fixture()
async def clean(db: AsyncIOMotorDatabase) -> AsyncGenerator[None, None]:
    yield
    await db.users.delete_many({})
    await db.heroes.delete_many({})


@pytest.mark.asyncio
async def test_repository_can_create_user_against_db(clean: Any, db: AsyncIOMotorDatabase) -> None:
    repo = UserRepository()

    await repo.create(entity=User(id=1, name="test", age=26))

    rows = await db.users.find({}).to_list(None)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_repository_can_update_against_db(clean: Any, db: AsyncIOMotorDatabase) -> None:
    await db.users.insert_one({"id": 1, "name": "test", "age": 10})

    repo = UserRepository()
    await repo.update(entity=User(id=1, name="test", age=20))

    new_user = await db.users.find_one({"id": 1})
    assert new_user["age"] == 20


@pytest.mark.asyncio
async def test_repository_can_retrieve_all_users_from_db(clean: Any, db: AsyncIOMotorDatabase) -> None:
    await db.users.insert_one({"id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    users = await repo.find()

    assert len(users) == 2
    assert all(isinstance(user, User) for user in users)


@pytest.mark.asyncio
async def test_repository_can_get_by_id(clean: Any, db: AsyncIOMotorDatabase) -> None:
    await db.users.insert_one({"id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    user = await repo.get_by_id(id=2)

    assert isinstance(user, User)
    assert user.age == 20


@pytest.mark.asyncio
async def test_repository_returns_none_when_no_id(clean: Any, db: AsyncIOMotorDatabase) -> None:
    await db.users.insert_one({"id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    user = await repo.get_by_id(id=3)
    assert user is None


@pytest.mark.asyncio
async def test_repository_runs_raw_method(clean: Any, db: AsyncIOMotorDatabase) -> None:
    await db.users.insert_one({"id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    user = await repo.get_user_by_name("test2")
    assert user is not None
    assert user.id == 2


@pytest.mark.asyncio
async def test_raw_method_can_call_compiled_method(clean: Any, db: AsyncIOMotorDatabase) -> None:
    await db.users.insert_one({"id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    users = await repo.list()

    assert len(users) == 2
    assert all(isinstance(user, User) for user in users)


@pytest.mark.asyncio
async def test_custom_or_method(clean: Any, db: AsyncIOMotorDatabase) -> None:
    await db.users.insert_one({"id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"id": 2, "name": "test2", "age": 20})
    await db.users.insert_one({"id": 3, "name": "test3", "age": 30})

    repo = UserRepository()
    users = await repo.find_by_name_or_age_lowerThan(name="test3", age=15)

    assert len(users) == 2


@pytest.mark.asyncio
async def test_nested_field_find_query(clean: Any, db: AsyncIOMotorDatabase) -> None:
    await db.users.insert_one({"id": 1, "name": "test", "age": 10})
    await db.users.insert_one(
        {
            "id": 2,
            "name": "test2",
            "age": 20,
            "address": {"latitude": 12.345, "longitude": 1.101},
        }
    )
    await db.users.insert_one(
        {
            "id": 3,
            "name": "test3",
            "age": 30,
            "address": {"latitude": 12.345, "longitude": 1.101},
        }
    )

    repo = UserRepository()

    users = await repo.find_by_address__latitude(address__latitude=12.345)

    assert len(users) == 2


@pytest.mark.asyncio
async def test_repository_insert_nested_field(clean: Any, db: AsyncIOMotorDatabase) -> None:
    user = User(id=1, name="test", age=10, address=Address(latitude=3.0, longitude=4.0))
    repo = UserRepository()
    await repo.create(entity=user)

    rows = await db.users.find({}).to_list(None)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_repository_can_insert_dataclass(clean: Any, db: Any) -> None:
    hero = Hero(id=1, name="Batman", cities=[City(name="Gotham")])
    repo = HeroRepository()

    await repo.create(entity=hero)

    rows = await db.heroes.find({}).to_list(None)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_repository_can_retrieve_dataclass(clean: Any, db: Any) -> None:
    await db.heroes.insert_one(
        {
            "id": 2,
            "name": "test2",
            "cities": [{"id": ObjectId(), "name": "Gotham"}],
        }
    )

    repo = HeroRepository()
    hero = await repo.get_by_id(id=2)

    assert hero is not None
    assert hero.name == "test2"
    assert len(hero.cities) == 1
    assert isinstance(hero.cities[0], City)
