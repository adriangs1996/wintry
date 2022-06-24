from typing import Any
import pytest_asyncio
import pytest
from wintry import get_connection, init_backends, BACKENDS
from wintry.models import Model, metadata, ModelRegistry
from wintry.transactions.unit_of_work import UnitOfWork
from wintry.repository import Repository
from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings
from sqlalchemy.ext.asyncio import AsyncSession, AsyncConnection
from sqlalchemy import select, delete, insert
from sqlalchemy.engine.result import Result

from wintry.utils.virtual_db_schema import get_model_sql_table


class User(Model, table="MultiRepoUser"):
    id: int
    name: str
    age: int


# Create the repositories

# specify the backend just for clarity here, it will go with 'default' by default
# This is wrong, but winter allows to force this as a nosql repository, even if
# User has already been mapped to a SQLAlchemy Table. And User could still be used
# as a regular POPO class, and for MONGO, winter is really powerful
class UserMongoRepository(Repository[User, int], entity=User, for_backend="default"):
    ...


# this is wrong, like very wrong, the same application should not
# define two data sources for the same model, at least not in this way.
# But winter is powerful, and winter is comming, so I will allow it here
class UserPostgressRepository(Repository[User, int], entity=User, for_backend="postgres"):
    ...


class InvalidUnitOfWork(UnitOfWork):
    pg_users: UserPostgressRepository
    mg_users: UserMongoRepository

    def __init__(
        self, pg_users: UserPostgressRepository, mg_users: UserMongoRepository
    ) -> None:
        super().__init__(pg_users=pg_users, mg_users=mg_users)


async def create_users():
    table = get_model_sql_table(User)
    pg: AsyncConnection = await get_connection("postgres")
    db = await get_connection()

    pg.begin()
    await pg.execute(insert(table).values(id=1, name="tes1t", age=20))
    await pg.execute(insert(table).values(id=2, name="test2", age=22))
    await pg.execute(insert(table).values(id=3, name="test3", age=24))
    await pg.execute(insert(table).values(id=4, name="test4", age=26))
    await pg.commit()
    await pg.close()

    await db.MultiRepoUser.insert_one({"id": 1, "name": "test1", "age": 20})  # type: ignore
    await db.MultiRepoUser.insert_one({"id": 2, "name": "test2", "age": 22})  # type: ignore
    await db.MultiRepoUser.insert_one({"id": 3, "name": "test3", "age": 24})  # type: ignore
    await db.MultiRepoUser.insert_one({"id": 4, "name": "test4", "age": 26})  # type: ignore


# Create two backends, leave one as default and name the other
@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup():
    ModelRegistry.configure()
    init_backends(
        WinterSettings(
            backends=[
                # leave this as default, this is the mongo backend
                BackendOptions(),
                # Use a named driver for the sqlalchemy with postgresql
                BackendOptions(
                    driver="wintry.drivers.pg",
                    name="postgres",
                    connection_options=ConnectionOptions(
                        url="sqlite+aiosqlite:///:memory:"
                    ),
                ),
            ]
        )
    )

    # Configure the posgresql, mongo is ready to run
    engine = getattr(BACKENDS["postgres"].driver, "_engine")
    conn = await engine.connect()
    await conn.run_sync(metadata.create_all)
    await conn.commit()
    await conn.close()


@pytest_asyncio.fixture
async def clean():
    # clean both databases
    yield
    # get a connection from postgres backend
    user_table = get_model_sql_table(User)
    postgres_session: AsyncConnection = await get_connection("postgres")
    postgres_session.begin()
    await postgres_session.execute(delete(user_table))
    await postgres_session.commit()
    await postgres_session.close()

    # get a connection from mongo backend, named 'default'
    db: Any = await get_connection()
    await db.MultiRepoUser.delete_many({})


@pytest.mark.asyncio
async def test_repos_can_create_users_to_their_respective_databases(clean: Any) -> None:
    table = get_model_sql_table(User)
    posgres = UserPostgressRepository()
    mongo = UserMongoRepository()

    # Create an user with posgtres
    await posgres.create(entity=User(id=1, name="posgres", age=10))
    # create an user with mongo
    await mongo.create(entity=User(id=1, name="mongo", age=10))

    # query each database for a single row
    pg: AsyncConnection = await get_connection("postgres")
    db = await get_connection()

    pg.begin()
    results: Result = await pg.execute(select(table))
    await pg.close()

    assert len(results.all()) == 1

    rows = await db.MultiRepoUser.find({}).to_list(None)  # type: ignore
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_repos_retrieve_from_different_databases(clean: Any) -> None:
    posgres = UserPostgressRepository()
    mongo = UserMongoRepository()

    await create_users()

    mongo_users = await mongo.find()

    assert len(mongo_users) == 4

    postgres_users = await posgres.find()

    assert len(postgres_users) == 4


@pytest.mark.asyncio
async def test_uow_can_be_created_from_either_repository(clean: Any) -> None:
    pg = UserPostgressRepository()
    mng = UserMongoRepository()
    table = get_model_sql_table(User)

    pg_uow = UnitOfWork(users=pg)
    mongo_uow = UnitOfWork(users=mng)

    async with pg_uow:
        pg_user = User(id=1, name="test", age=20)
        await pg_uow.users.create(entity=pg_user)

        pg_user.age = 30
        await pg_uow.commit()

    pg_session: AsyncConnection = await get_connection("postgres")
    pg_session.begin()
    results = await pg_session.execute(select(table).where(table.c.id == 1))
    await pg_session.close()

    assert results.all()[0]["age"] == 30

    async with mongo_uow:
        user = User(id=1, name="test", age=20)
        await mongo_uow.users.create(entity=pg_user)

        user.age = 30
        await mongo_uow.commit()

    db = await get_connection()
    user_row = await db.MultiRepoUser.find_one({"id": 1})  # type: ignore
    assert user_row["age"] == 30
