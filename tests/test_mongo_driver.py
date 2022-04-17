from winter.query.nodes import (
    AndNode,
    Create,
    EqualToNode,
    Find,
    LowerThanNode,
    OrNode,
    Update,
)
from winter.drivers import MongoDbDriver
import pytest


@pytest.mark.asyncio
async def test_driver_handles_single_create_command():
    query = Create()
    driver = MongoDbDriver()

    query_repr = await driver.get_query_repr(
        query, "tests", entity={"name": "test", "age": 10}
    )

    assert query_repr == "db.tests.insert_one({'name': 'test', 'age': 10})"


@pytest.mark.asyncio
async def test_driver_panics_on_update_with_no_id():
    query = Update()
    driver = MongoDbDriver()

    query_repr = await driver.get_query_repr(
        query, "tests", _id=1, name="tests", age=10
    )

    assert query_repr == "db.tests.update_one({'_id': 1}, {'name': 'tests', 'age': 10})"


@pytest.mark.asyncio
async def test_driver_translate_nested_find_query():
    query = Find(
        AndNode(
            EqualToNode("id"),
            OrNode(LowerThanNode("age"), AndNode(EqualToNode("username"), None)),
        )
    )

    driver = MongoDbDriver()

    query_repr = await driver.get_query_repr(
        query, "tests", id=1, age=27, username="username@test"
    )

    assert (
        query_repr
        == "db.tests.find({'$and': [{'_id': {'$eq': 1}}, {'$or': [{'age': {'$lt': 27}}, {'$and': [{'username': {'$eq': 'username@test'}}]}]}]})"
    )
