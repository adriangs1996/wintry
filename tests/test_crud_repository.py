# Configure te mongo driver
from winter import init_backends
from winter.models import model

from winter.repository import Repository
import pytest


@pytest.fixture(scope="module", autouse=True)
def setup() -> None:
    init_backends()


@model
class User:
    id: int
    username: str
    password: str


class UserRepository(Repository[User, int], entity=User, dry=True):
    def __init__(self) -> None:
        pass


@pytest.mark.asyncio
async def test_repository_can_create_user() -> None:
    repo = UserRepository()

    str_query = await repo.create(entity=User(id=10, username="test", password="secret"))

    assert (
        str_query
        == "db.users.insert_one({'id': 10, 'username': 'test', 'password': 'secret'})"
    )


@pytest.mark.asyncio
async def test_repository_can_update_user() -> None:
    repo = UserRepository()
    str_query = await repo.update(entity=User(id=10, username="test", password="secret"))

    assert (
        str_query
        == "db.users.update_one({'id': 10}, {'username': 'test', 'password': 'secret'})"
    )


@pytest.mark.asyncio
async def test_repository_can_find_simple() -> None:
    repo = UserRepository()
    str_query = await repo.find()

    assert str_query == "db.users.find({}).to_list()"


@pytest.mark.asyncio
async def test_repository_can_find_by_id() -> None:
    repo = UserRepository()
    str_query = await repo.get_by_id(id=10)

    assert str_query == "db.users.find_one({'$and': [{'id': {'$eq': 10}}]})"


@pytest.mark.asyncio
async def test_repository_can_delete() -> None:
    repo = UserRepository()
    str_query = await repo.delete_by_id(id=10)

    assert str_query == "db.users.delete_many({'$and': [{'id': {'$eq': 10}}]})"


@pytest.mark.asyncio
async def test_repository_can_delete_all_users() -> None:
    repo = UserRepository()
    str_query = await repo.delete()

    assert str_query == "db.users.delete_many({})"
