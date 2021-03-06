# Configure te mongo driver
from wintry import init_backends, WinterSettings, BackendOptions
from wintry.models import Model

from wintry.repository import Repository, RepositoryRegistry
import pytest


@pytest.fixture(scope="module", autouse=True)
def setup() -> None:
    RepositoryRegistry.configure_for_nosql()
    init_backends(WinterSettings(backends=[BackendOptions()]))


class User(Model):
    id: int
    username: str
    password: str


class UserRepository(Repository[User, int], entity=User, dry=True):
    ...


@pytest.mark.asyncio
async def test_repository_can_create_user() -> None:
    repo = UserRepository()

    str_query = await repo.create(
        entity=User(id=10, username="test", password="secret")
    )

    assert (
        str_query
        == "db.users.insert_one({'id': 10, 'username': 'test', 'password': 'secret'})"
    )


@pytest.mark.asyncio
async def test_repository_can_update_user() -> None:
    repo = UserRepository()
    str_query = await repo.update(
        entity=User(id=10, username="test", password="secret")
    )

    assert (
        str_query
        == "db.users.update_one({'id': 10}, {'id': 10, 'username': 'test', 'password': 'secret'})"
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

    assert str_query == "db.users.find_one({'id': {'$eq': 10}})"


@pytest.mark.asyncio
async def test_repository_can_delete() -> None:
    repo = UserRepository()
    str_query = await repo.delete_by_id(id=10)

    assert str_query == "db.users.delete_many({'id': {'$eq': 10}})"


@pytest.mark.asyncio
async def test_repository_can_delete_all_users() -> None:
    repo = UserRepository()
    str_query = await repo.delete()

    assert str_query == "db.users.delete_many({})"
