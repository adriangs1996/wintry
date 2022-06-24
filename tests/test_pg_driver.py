import pytest
from wintry.drivers.pg import SqlAlchemyDriver
from wintry.models import Model, ModelRegistry, VirtualDatabaseSchema
from sqlalchemy.exc import CompileError

from wintry.query.nodes import AndNode, Create, EqualToNode, Find, Get, OrNode, Update


class User(Model, table="Users"):
    id: int
    username: str


class Address(Model, table="Addresses"):
    id: int
    user: User


@pytest.fixture(scope="module", autouse=True)
def setup():
    ModelRegistry.configure()
    VirtualDatabaseSchema.use_sqlalchemy()


@pytest.mark.asyncio
async def test_pg_driver_handles_single_create_command() -> None:
    driver = SqlAlchemyDriver()
    user = User(id=1, username="test")

    query = Create()

    query_repr = await driver.get_query_repr(query, User, entity=user)

    assert query_repr == 'INSERT INTO "Users" (id, username) VALUES (:id, :username)'

@pytest.mark.asyncio
async def test_pg_driver_can_update_entity() -> None:
    driver = SqlAlchemyDriver()
    user = User(id=1, username="test")

    query = Update()

    query_expr = await driver.get_query_repr(query, User, entity=user)

    assert query_expr == 'UPDATE "Users" SET username=:username WHERE "Users".id = :id_1'


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
        query_expr
        == 'SELECT "Users".id, "Users".username FROM "Users" WHERE "Users".username = :username_1'
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
        AndNode(
            EqualToNode("username"),
            OrNode(EqualToNode("id"), AndNode(EqualToNode("username"), None)),
        )
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

    assert (
        query_expr
        == 'SELECT "Users".id, "Users".username FROM "Users" WHERE "Users".id = :id_1'
    )


@pytest.mark.asyncio
async def test_pg_driver_get_by_user__id() -> None:
    driver = SqlAlchemyDriver()
    query = Get(AndNode(EqualToNode("user.id"), None))

    query_expr = await driver.get_query_repr(query, Address, user__id=1)
    query_expr = query_expr.replace("\n", "")

    assert (
        query_expr
        == (
        'SELECT "Addresses".id, "Addresses"."user", "Users".id AS id_1, "Users".username '
        'FROM "Addresses" LEFT OUTER JOIN "Users" ON "Addresses"."user" = "Users".id '
        'WHERE "Users".id = :id_2'
        )
    )
