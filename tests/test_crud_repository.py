# Configure te mongo driver
import os

import winter.backend
from winter.drivers.mongo import MongoDbDriver
from winter.repository.base import repository
from winter.repository.crud_repository import CrudRepository
from pydantic import BaseModel, Field
import pytest


@pytest.fixture(scope="module", autouse=True)
def setup() -> None:
    winter.backend.Backend.driver = MongoDbDriver()


class User(BaseModel):
    id: int = Field(..., alias="_id")
    username: str
    password: str


@repository(User, dry=True)
class Repository(CrudRepository[User, int]):
    def __init__(self) -> None:
        pass


@pytest.mark.asyncio
async def test_repository_can_create_user() -> None:
    repo = Repository()

    str_query = await repo.create(entity=User(_id=10, username="test", password="secret"))

    assert str_query == "db.users.insert_one({'_id': 10, 'username': 'test', 'password': 'secret'})"


@pytest.mark.asyncio
async def test_repository_can_update_user() -> None:
    repo = Repository()
    str_query = await repo.update(entity=User(_id=10, username="test", password="secret"))

    assert str_query == "db.users.update_one({'_id': 10}, {'username': 'test', 'password': 'secret'})"


@pytest.mark.asyncio
async def test_repository_can_find_simple() -> None:
    repo = Repository()
    str_query = await repo.find()

    assert str_query == "db.users.find({}).to_list()"


@pytest.mark.asyncio
async def test_repository_can_find_by_id() -> None:
    repo = Repository()
    str_query = await repo.get_by_id(id=10)

    assert str_query == "db.users.find_one({'$and': [{'_id': {'$eq': 10}}]})"


@pytest.mark.asyncio
async def test_repository_can_delete() -> None:
    repo = Repository()
    str_query = await repo.delete_by_id(id=10)

    assert str_query == "db.users.delete_many({'$and': [{'_id': {'$eq': 10}}]})"


@pytest.mark.asyncio
async def test_repository_can_delete_all_users() -> None:
    repo = Repository()
    str_query = await repo.delete()

    assert str_query == "db.users.delete_many({})"
