# Configure te mongo driver
from dataclasses import dataclass
import os
from winter import init_backend

import winter.backend
from winter.drivers.mongo import MongoDbDriver
from winter.repository.base import repository
from winter.repository.crud_repository import CrudRepository
import pytest


@pytest.fixture(scope="module", autouse=True)
def setup() -> None:
    init_backend()


@dataclass
class User:
    id: int
    username: str
    password: str


@repository(User, dry=True)
class Repository(CrudRepository[User, int]):
    def __init__(self) -> None:
        pass


@pytest.mark.asyncio
async def test_repository_can_create_user() -> None:
    repo = Repository()

    str_query = await repo.create(entity=User(id=10, username="test", password="secret"))

    assert str_query == "db.users.insert_one({'id': 10, 'username': 'test', 'password': 'secret'})"


@pytest.mark.asyncio
async def test_repository_can_update_user() -> None:
    repo = Repository()
    str_query = await repo.update(entity=User(id=10, username="test", password="secret"))

    assert str_query == "db.users.update_one({'id': 10}, {'username': 'test', 'password': 'secret'})"


@pytest.mark.asyncio
async def test_repository_can_find_simple() -> None:
    repo = Repository()
    str_query = await repo.find()

    assert str_query == "db.users.find({}).to_list()"


@pytest.mark.asyncio
async def test_repository_can_find_by_id() -> None:
    repo = Repository()
    str_query = await repo.get_by_id(id=10)

    assert str_query == "db.users.find_one({'$and': [{'id': {'$eq': 10}}]})"


@pytest.mark.asyncio
async def test_repository_can_delete() -> None:
    repo = Repository()
    str_query = await repo.delete_by_id(id=10)

    assert str_query == "db.users.delete_many({'$and': [{'id': {'$eq': 10}}]})"


@pytest.mark.asyncio
async def test_repository_can_delete_all_users() -> None:
    repo = Repository()
    str_query = await repo.delete()

    assert str_query == "db.users.delete_many({})"
