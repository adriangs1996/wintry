from typing import Any
import pytest_asyncio
import pytest
from winter import get_connection, init_backends, BACKENDS
from winter.models import model
from winter.orm import for_model
from winter.unit_of_work import UnitOfWork, UnitOfWorkError
from winter.repository import NoSqlCrudRepository, SqlCrudRepository
from winter.settings import BackendOptions, ConnectionOptions, WinterSettings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import MetaData, select, delete, insert, Column, Integer, String
from sqlalchemy.engine.result import Result


@model
class User:
    id: int
    name: str
    age: int


# Define the table schemas
metadata = MetaData()

UserTable = for_model(
    User,
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("age", Integer),
    table_name="users",
)

# Create the repositories

# specify the backend just for clarity here, it will go with 'default' by default
# This is wrong, but winter allows to force this as a nosql repository, even if
# User has already been mapped to a SQLAlchemy Table. And User could still be used
# as a regular POPO class, and for MONGO, winter is really powerful
class UserMongoRepository(
    NoSqlCrudRepository[User, int], entity=User, mongo_session_managed=True, for_backend="default"
):
    pass


# this is wrong, like very wrong, the same application should not
# define two data sources for the same model, at least not in this way.
# But winter is powerful, and winter is comming, so I will allow it here
class UserPostgressRepository(SqlCrudRepository[User, int], entity=User, for_backend="postgres"):
    pass


class InvalidUnitOfWork(UnitOfWork):
    pg_users: UserPostgressRepository
    mg_users: UserMongoRepository

    def __init__(self, pg_users: UserPostgressRepository, mg_users: UserMongoRepository) -> None:
        super().__init__(pg_users=pg_users, mg_users=mg_users)


async def create_users():
    pg = get_connection("postgres")
    db = get_connection()

    async with pg.begin():
        await pg.execute(insert(User).values(id=1, name="tes1t", age=20))
        await pg.execute(insert(User).values(id=2, name="test2", age=22))
        await pg.execute(insert(User).values(id=3, name="test3", age=24))
        await pg.execute(insert(User).values(id=4, name="test4", age=26))

    await db.users.insert_one({"id": 1, "name": "test1", "age": 20})  # type: ignore
    await db.users.insert_one({"id": 2, "name": "test2", "age": 22})  # type: ignore
    await db.users.insert_one({"id": 3, "name": "test3", "age": 24})  # type: ignore
    await db.users.insert_one({"id": 4, "name": "test4", "age": 26})  # type: ignore


# Create two backends, leave one as default and name the other
@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup():
    init_backends(
        WinterSettings(
            backends=[
                # leave this as default, this is the mongo backend
                BackendOptions(),
                # Use a named driver for the sqlalchemy with postgresql
                BackendOptions(
                    driver="winter.drivers.pg",
                    name="postgres",
                    connection_options=ConnectionOptions(
                        url="postgresql+asyncpg://postgres:secret@localhost/tests"
                    ),
                ),
            ]
        )
    )

    # Configure the posgresql, mongo is ready to run
    engine = getattr(BACKENDS["postgres"].driver, "_engine")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


@pytest_asyncio.fixture
async def clean():
    # clean both databases
    yield
    # get a connection from postgres backend
    postgres_session: AsyncSession = get_connection("postgres")
    async with postgres_session.begin():
        await postgres_session.execute(delete(User))
        await postgres_session.commit()

    # get a connection from mongo backend, named 'default'
    db: Any = get_connection()
    await db.users.delete_many({})


@pytest.mark.asyncio
async def test_repos_can_create_users_to_their_respective_databases(clean: Any) -> None:
    posgres = UserPostgressRepository()
    mongo = UserMongoRepository()

    # Create an user with posgtres
    await posgres.create(entity=User(id=1, name="posgres", age=10))
    # create an user with mongo
    await mongo.create(entity=User(id=1, name="mongo", age=10))

    # query each database for a single row
    pg = get_connection("postgres")
    db = get_connection()

    async with pg.begin():
        results: Result = await pg.execute(select(User))

    assert len(results.all()) == 1

    rows = await db.users.find({}).to_list(None)  # type: ignore
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


def test_cannot_use_a_uow_with_different_backends(clean: Any) -> None:
    with pytest.raises(UnitOfWorkError):
        pg = UserPostgressRepository()
        mng = UserMongoRepository()

        uow = InvalidUnitOfWork(pg_users=pg, mg_users=mng)


@pytest.mark.asyncio
async def test_uow_can_be_created_from_either_repository(clean: Any) -> None:
    pg = UserPostgressRepository()
    mng = UserMongoRepository()

    pg_uow = UnitOfWork(users=pg)
    mongo_uow = UnitOfWork(users=mng)

    async with pg_uow:
        pg_user = User(id=1, name="test", age=20)
        await pg_uow.users.create(entity=pg_user)

        pg_user.age = 30
        await pg_uow.commit()

    pg_session = get_connection("postgres")
    async with pg_session.begin():
        results: User = await pg_session.get(User, 1)

    assert results.age == 30

    async with mongo_uow:
        user = User(id=1, name="test", age=20)
        await mongo_uow.users.create(entity=pg_user)

        user.age = 30
        await mongo_uow.commit()

    db = get_connection()
    user_row = await db.users.find_one({"id": 1})  # type: ignore
    assert user_row["age"] == 30
