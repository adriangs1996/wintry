from winter.backend import Backend
from winter.drivers import MongoDbDriver
from winter.repository.base import repository
from winter.repository.crud_repository import CrudRepository
from pydantic import BaseModel, Field
import pytest


class User(BaseModel):
    id: int = Field(..., alias="_id")
    username: str
    password: str


driver = MongoDbDriver()
Backend.driver = driver


@repository(User, dry=True)
class Repository(CrudRepository[User, int]):
    def __init__(self) -> None:
        pass


@pytest.mark.asyncio
async def test_repository_can_create_user():
    repo = Repository()

    str_query = await repo.create(
        entity=User(_id=10, username="test", password="secret")
    )

    assert (
        str_query
        == "db.users.insert_one({'_id': 10, 'username': 'test', 'password': 'secret'})"
    )
