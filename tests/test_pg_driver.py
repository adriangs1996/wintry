import pytest
from winter.drivers.pg import ExecutionError, SqlAlchemyDriver
from winter.models import model
from winter.orm import for_model
from sqlalchemy.orm import relation
from sqlalchemy import Integer, String, Column, ForeignKey, MetaData
from sqlalchemy.exc import CompileError
from dataclass_wizard import asdict

from winter.query.nodes import AndNode, Create, EqualToNode, Find, Get, OrNode, Update

metadata = MetaData()


@model
class User:
    id: int
    username: str


@model
class Address:
    id: int
    user: User


UserTable = for_model(User, metadata, Column("id", Integer, primary_key=True), Column("username", String))


AddressTable = for_model(
    Address,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey(User.id)),
    table_name="Addresses",
    user=relation(User),
)


@pytest.mark.asyncio
async def test_pg_driver_handles_single_create_command() -> None:
    driver = SqlAlchemyDriver()
    user = User(id=1, username="test")

    query = Create()

    query_repr = await driver.get_query_repr(query, User, entity=user)

    assert query_repr == 'INSERT INTO "Users" (id, username) VALUES (:id, :username)'


@pytest.mark.asyncio
async def test_pg_driver_fails_to_create_command_with_entity_with_relations() -> None:
    driver = SqlAlchemyDriver()
    address = Address(id=1, user=User(id=2, username="test"))

    query = Create()

    with pytest.raises(CompileError):
        query_repr = await driver.get_query_repr(query, Address, entity=address)


@pytest.mark.asyncio
async def test_pg_driver_can_update_entity() -> None:
    driver = SqlAlchemyDriver()
    user = User(id=1, username="test")

    query = Update()

    query_expr = await driver.get_query_repr(query, User, entity=user)

    assert query_expr == 'UPDATE "Users" SET username=:username WHERE "Users".id = :id_1'


@pytest.mark.asyncio
async def test_pg_driver_panics_when_update_with_no_id() -> None:
    driver = SqlAlchemyDriver()
    user = User(id=1, username="test")

    query = Update()

    with pytest.raises(ExecutionError):
        query_expr = await driver.get_query_repr(query, User, entity=asdict(user, exclude=["id"]))


@pytest.mark.asyncio
async def test_pg_driver_handles_find() -> None:
    driver = SqlAlchemyDriver()
    query = Find()

    query_expr = await driver.get_query_repr(query, User)
    query_expr = query_expr.replace("\n", "")

    assert query_expr == '''SELECT "Users".id, "Users".username FROM "Users"'''


@pytest.mark.asyncio
async def test_pg_driver_handles_find_by() -> None:
    driver = SqlAlchemyDriver()
    query = Find(AndNode(EqualToNode("username"), None))

    query_expr = await driver.get_query_repr(query, User, username="test")
    query_expr = query_expr.replace("\n", "")

    assert (
        query_expr == 'SELECT "Users".id, "Users".username FROM "Users" WHERE "Users".username = :username_1'
    )


@pytest.mark.asyncio
async def test_pg_driver_handles_find_by_username_or_id() -> None:
    driver = SqlAlchemyDriver()
    query = Find(OrNode(EqualToNode("username"), AndNode(EqualToNode("id"), None)))

    query_expr = await driver.get_query_repr(query, User, username="test", id=2)
    query_expr = query_expr.replace("\n", "")

    assert (
        query_expr
        == 'SELECT "Users".id, "Users".username FROM "Users" WHERE "Users".username = :username_1 OR "Users".id = :id_1'
    )


@pytest.mark.asyncio
async def test_pg_driver_find_by_username_and_id() -> None:
    driver = SqlAlchemyDriver()
    query = Find(AndNode(EqualToNode("username"), AndNode(EqualToNode("id"), None)))

    query_expr = await driver.get_query_repr(query, User, username="test", id=2)
    query_expr = query_expr.replace("\n", "")

    assert (
        query_expr
        == 'SELECT "Users".id, "Users".username FROM "Users" WHERE "Users".username = :username_1 AND "Users".id = :id_1'
    )


@pytest.mark.asyncio
async def test_pg_driver_find_by_username_and_id_or_username() -> None:
    driver = SqlAlchemyDriver()
    query = Find(
        AndNode(EqualToNode("username"), OrNode(EqualToNode("id"), AndNode(EqualToNode("username"), None)))
    )

    query_expr = await driver.get_query_repr(query, User, username="test", id=2)
    query_expr = query_expr.replace("\n", "")

    assert (
        query_expr
        == 'SELECT "Users".id, "Users".username FROM "Users" WHERE "Users".username = :username_1 AND ("Users".id = :id_1 OR "Users".username = :username_2)'
    )


@pytest.mark.asyncio
async def test_pg_driver_get_by_id() -> None:
    driver = SqlAlchemyDriver()
    query = Get(AndNode(EqualToNode("id"), None))

    query_expr = await driver.get_query_repr(query, User, id=2)
    query_expr = query_expr.replace("\n", "")

    assert query_expr == 'SELECT "Users".id, "Users".username FROM "Users" WHERE "Users".id = :id_1'


@pytest.mark.asyncio
async def test_pg_driver_get_by_user__id() -> None:
    driver = SqlAlchemyDriver()
    query = Get(AndNode(EqualToNode("user.id"), None))

    query_expr = await driver.get_query_repr(query, Address, user__id=1)
    query_expr = query_expr.replace("\n", "")

    assert (
        query_expr
        == 'SELECT "Addresses".id, "Addresses".user_id FROM "Addresses" JOIN "Users" ON "Users".id = "Addresses".user_id WHERE "Users".id = :id_1'
    )
