# configure backend
import os
os.environ['backend'] = "winter.drivers.mongo"

# Import backend, so it is configured with MongoDb
from typing import List, Optional
import winter.backend as bkd
import pydantic as pdc
from winter.repository.base import repository, raw_method
from winter.repository.crud_repository import CrudRepository
import pytest
import pytest_asyncio


class Address(pdc.BaseModel):
    latitude: float
    longitude: float


class User(pdc.BaseModel):
    id: int = pdc.Field(..., alias="_id")
    name: str
    age: int
    address: Optional[Address] = None


bkd.Backend.configure_for_driver(host="localhost", port=27017)
db = bkd.Backend.get_connection()  # type: ignore


@repository(User)
class UserRepository(CrudRepository[User, int]):
    @raw_method
    async def get_user_by_name(self, name: str):
        row = await db.users.find_one({"name": name})
        if row is not None:
            return User(**row)
        else:
            return None

    @raw_method
    async def list(self):
        return await self.find()

    async def find_by_name_or_age_lowerThan(self, *, name: str, age: int) -> List[User]:
        ...

    async def find_by_address__latitude(
        self, *, address__latitude: float
    ) -> List[User]:
        ...


@pytest_asyncio.fixture()
async def clean():
    yield
    await db.users.delete_many({})


@pytest.mark.asyncio
async def test_repository_can_create_user_against_db(clean):
    repo = UserRepository()

    await repo.create(entity=User(_id=1, name="test", age=26))

    rows = await db.users.find({}).to_list(None)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_repository_can_update_against_db(clean):
    await db.users.insert_one({"_id": 1, "name": "test", "age": 10})

    repo = UserRepository()
    await repo.update(entity=User(_id=1, name="test", age=20))

    new_user = await db.users.find_one({"_id": 1})
    assert new_user["age"] == 20


@pytest.mark.asyncio
async def test_repository_can_retrieve_all_users_from_db(clean):
    await db.users.insert_one({"_id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"_id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    users = await repo.find()

    assert len(users) == 2
    assert all(isinstance(user, User) for user in users)


@pytest.mark.asyncio
async def test_repository_can_get_by_id(clean):
    await db.users.insert_one({"_id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"_id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    user = await repo.get_by_id(id=2)

    assert isinstance(user, User)
    assert user.age == 20


@pytest.mark.asyncio
async def test_repository_returns_none_when_no_id(clean):
    await db.users.insert_one({"_id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"_id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    user = await repo.get_by_id(id=3)
    assert user is None


@pytest.mark.asyncio
async def test_repository_runs_raw_method(clean):
    await db.users.insert_one({"_id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"_id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    user = await repo.get_user_by_name("test2")
    assert user is not None
    assert user.id == 2


@pytest.mark.asyncio
async def test_raw_method_can_call_compiled_method(clean):
    await db.users.insert_one({"_id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"_id": 2, "name": "test2", "age": 20})

    repo = UserRepository()
    users = await repo.list()

    assert len(users) == 2
    assert all(isinstance(user, User) for user in users)


@pytest.mark.asyncio
async def test_custom_or_method(clean):
    await db.users.insert_one({"_id": 1, "name": "test", "age": 10})
    await db.users.insert_one({"_id": 2, "name": "test2", "age": 20})
    await db.users.insert_one({"_id": 3, "name": "test3", "age": 30})

    repo = UserRepository()
    users = await repo.find_by_name_or_age_lowerThan(name="test3", age=15)

    assert len(users) == 2


@pytest.mark.asyncio
async def test_nested_field_find_query(clean):
    await db.users.insert_one({"_id": 1, "name": "test", "age": 10})
    await db.users.insert_one(
        {
            "_id": 2,
            "name": "test2",
            "age": 20,
            "address": {"latitude": 12.345, "longitude": 1.101},
        }
    )
    await db.users.insert_one(
        {
            "_id": 3,
            "name": "test3",
            "age": 30,
            "address": {"latitude": 12.345, "longitude": 1.101},
        }
    )

    repo = UserRepository()

    users = await repo.find_by_address__latitude(address__latitude=12.345)

    assert len(users) == 2


@pytest.mark.asyncio
async def test_repository_insert_nested_field(clean):
    user = User(
        _id=1, name="test", age=10, address=Address(latitude=3.0, longitude=4.0)
    )
    repo = UserRepository()
    await repo.create(entity=user)

    rows = await db.users.find({}).to_list(None)
    assert len(rows) == 1
