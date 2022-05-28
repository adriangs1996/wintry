from wintry.models import Model
from wintry.query.nodes import (
    AndNode,
    Create,
    EqualToNode,
    Find,
    LowerThanNode,
    OrNode,
    Update,
)
from wintry.drivers.mongo import MongoDbDriver
import pytest


class User(Model):
    id: int
    name: str
    age: int


@pytest.mark.asyncio
async def test_driver_handles_single_create_command():
    query = Create()
    driver = MongoDbDriver()

    query_repr = await driver.get_query_repr(query, User, entity=User(id=1, name='test', age=10))

    assert query_repr == "db.users.insert_one({'id': 1, 'name': 'test', 'age': 10})"


@pytest.mark.asyncio
async def test_driver_panics_on_update_with_no_id():
    query = Update()
    driver = MongoDbDriver()

    query_repr = await driver.get_query_repr(query, User, entity=User(id=1, name="tests", age=10))

    assert query_repr == "db.users.update_one({'id': 1}, {'id': 1, 'name': 'tests', 'age': 10})"


@pytest.mark.asyncio
async def test_driver_translate_nested_find_query():
    query = Find(
        AndNode(
            EqualToNode("id"),
            OrNode(LowerThanNode("age"), AndNode(EqualToNode("username"), None)),
        )
    )

    driver = MongoDbDriver()

    query_repr = await driver.get_query_repr(query, User, id=1, age=27, username="username@test")

    assert (
        query_repr
        == "db.users.find({'$and': [{'id': {'$eq': 1}}, {'$or': [{'age': {'$lt': 27}}, {'$and': [{'username': {'$eq': 'username@test'}}]}]}]}).to_list()"
    )


@pytest.mark.asyncio
async def test_driver_flattens_nested_continuos_and_queries():
    query = Find(
        AndNode(
            EqualToNode("username"),
            AndNode(EqualToNode("lastName"), AndNode(LowerThanNode("age"), None)),
        )
    )

    driver = MongoDbDriver()
    query_repr = await driver.get_query_repr(query, User, username="myUserName", lastName="last", age=30)

    assert (
        query_repr
        == "db.users.find({'$and': [{'username': {'$eq': 'myUserName'}}, {'lastName': {'$eq': 'last'}}, {'age': {'$lt': 30}}]}).to_list()"
    )
