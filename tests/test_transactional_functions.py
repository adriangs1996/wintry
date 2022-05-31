from typing import Any, AsyncGenerator
from wintry import get_connection, init_backends
from wintry.generators import AutoString
from wintry.models import Array, Id, Model
from wintry.repository.base import managed, query
from wintry.settings import WinterSettings, BackendOptions, ConnectionOptions
from wintry.repository import Repository, RepositoryRegistry
import pytest
import pytest_asyncio


class Address(Model):
    latitude: float
    longitude: float


class User(Model):
    id: int
    name: str
    age: int
    address: Address | None = None
    heroes: list["Hero"] = Array()


class Hero(Model):
    name: str
    id: str = Id(default_factory=AutoString)


class UserRepository(Repository[User, int], entity=User, mongo_session_managed=True):
    @managed
    async def get_user_by_name(self, name: str):
        db = self.connection()
        row = await db.users.find_one({"name": name})

        if row is not None:
            return User.build(row)
        else:
            return None


class HeroRepository(Repository[Hero, str], entity=Hero, table_name="heroes"):
    @query
    async def get_by_name(self, *, name: str) -> Hero | None:
        ...


@pytest.fixture(scope="module", autouse=True)
def db() -> Any:
    RepositoryRegistry.configure_for_nosql()
    init_backends(
        WinterSettings(
            backends=[
                BackendOptions(
                    connection_options=ConnectionOptions(
                        url="mongodb://localhost:27017/?replicaSet=dbrs"
                    ),
                )
            ]
        )
    )

    return get_connection()


@pytest_asyncio.fixture()
async def clean(db: Any) -> AsyncGenerator[None, None]:
    yield
    await db.users.delete_many({})
    await db.heroes.delete_many({})


@pytest.mark.asyncio
async def test_transactional_decorator_save_objects_on_success(clean: Any, db: Any):
    @transactional
    async def create_user():
        repository = UserRepository()
        user = await repository.create(entity=User(id=1, age=28, name="Batman"))

    await create_user()
    rows = await db.users.find({}).to_list(None)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_transactional_decorator_rollback_on_error(clean: Any, db: Any):
    @transactional
    async def create_user_with_error():
        repository = UserRepository()
        user1 = await repository.create(entity=User(id=1, age=28, name="Batman"))
        user2 = await repository.create(entity=User(id=2, age=20 // 0, name="tests"))

    with pytest.raises(ZeroDivisionError):
        await create_user_with_error()

    rows = await db.users.find({}).to_list(None)
    assert rows == []


@pytest.mark.asyncio
async def test_transactional_decorator_updates_simple_object_properties(
    clean: Any, db: Any
):
    @transactional
    async def update_user():
        repository = UserRepository()
        user = await repository.get_by_id(id=1)
        assert user is not None
        user.age = 30
        user.name = "Superman"

    await db.users.insert_one({"id": 1, "age": 28, "name": "Batman"})
    await update_user()
    user_row = await db.users.find_one({"id": 1})
    assert user_row["name"] == "Superman"
    assert user_row["age"] == 30


@pytest.mark.asyncio
async def test_transactional_decorator_create_nested_object(clean: Any, db: Any):
    @transactional
    async def create_nested_object():
        repository = UserRepository()
        user = await repository.get_by_id(id=1)
        assert user is not None
        user.address = Address(latitude=12.1, longitude=1.1)

    await db.users.insert_one({"id": 1, "age": 28, "name": "Batman"})
    await create_nested_object()
    user_row = await db.users.find_one({"id": 1})
    assert user_row["address"] == {"latitude": 12.1, "longitude": 1.1}


@pytest.mark.asyncio
async def test_transactional_decorator_updates_object_in_list(clean: Any, db: Any):
    @transactional
    async def update_object_in_list():
        user_repository = UserRepository()
        users = await user_repository.find()
        users[2].name = "Luke"

    await db.users.insert_one({"id": 1, "age": 28, "name": "Batman"})
    await db.users.insert_one({"id": 2, "age": 30, "name": "Superman"})
    await db.users.insert_one({"id": 3, "age": 24, "name": "Flash"})
    await db.users.insert_one({"id": 4, "age": 26, "name": "Aquaman"})
    await db.users.insert_one({"id": 5, "age": 29, "name": "IronMan"})

    await update_object_in_list()
    user_row = await db.users.find_one({"name": "Luke"})
    assert user_row is not None

@pytest.mark.asyncio
async def test_transactional_decorator_updates_nested_object(clean: Any, db: Any):
    @transactional
    async def update_nested_object():
        user_repository = UserRepository()
        user = await user_repository.get_by_id(id=1)
        assert user is not None
        assert user.address is not None
        user.address.latitude = 3.0
    
    await db.users.insert_one(
        {
            "id": 1,
            "age": 28,
            "name": "Batman",
            "address": {"latitude": 1.0, "longitude": 2.0},
        }
    )
    await update_nested_object()
    user_row = await db.users.find_one({"id": 1})
    assert user_row["address"] == {"latitude": 3.0, "longitude": 2.0}
