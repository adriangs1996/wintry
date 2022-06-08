from wintry.models import Array, Id, Model, VirtualDatabaseSchema
from wintry.utils.model_binding import load_model
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import Table
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import MetaData
from sqlalchemy import text
import pytest
import pytest_asyncio

metadata = MetaData()


class OrmCity(Model, table="OrmCity"):
    id: int = Id()
    name: str


class OrmState(Model, table="OrmState"):
    id: int = Id()
    name: str
    cities: list[OrmCity] = Array()


class OrmUser(Model, table="OrmUsers"):
    id: int = Id()
    name: str
    city: OrmCity | None = None


class OrmAddress(Model, table="OrmAddress"):
    id: int = Id()
    dir: str
    user: OrmUser | None = None


async def create_users(conn: AsyncConnection):
    await conn.execute(
        text("INSERT INTO OrmUsers VALUES (:id, :name, :city)"),
        [
            {"id": 1, "name": "adrian", "city": 1},
            {"id": 2, "name": "tom", "city": None},
            {"id": 3, "name": "kmi", "city": None},
        ],
    )


async def create_cities(conn: AsyncConnection):
    await conn.execute(
        text("INSERT INTO OrmCity VALUES (:id, :name, :ormstate_id)"),
        dict(id=1, name="Matanzas", ormstate_id=None),
    )


async def create_addresses(conn: AsyncConnection):
    await conn.execute(
        text("INSERT INTO OrmAddress VALUES (:id, :dir, :user)"),
        [dict(id=1, dir="Address 1", user=1), dict(id=2, dir="Address 2", user=2)],
    )


async def create_states(conn: AsyncConnection):
    await conn.execute(
        text("INSERT INTO OrmState VALUES (:id, :name)"), dict(id=1, name="Miami")
    )


@pytest_asyncio.fixture(scope="module")
async def connection():
    async_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=True, future=True
    )
    VirtualDatabaseSchema.use_sqlalchemy(metadata)
    conn: AsyncConnection = await async_engine.connect()
    await conn.run_sync(metadata.create_all)

    await create_addresses(conn)
    await create_cities(conn)
    await create_users(conn)
    await create_states(conn)
    yield conn
    await conn.close()
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_simple_model_binding(connection: AsyncConnection):
    results = await load_model(OrmState, connection)
    assert results == [OrmState(id=1, name="Miami")]


@pytest.mark.asyncio
async def test_model_binding_whole_tree(connection: AsyncConnection):
    results = await load_model(OrmAddress, connection)
    assert results == [
        OrmAddress(
            id=1,
            dir="Address 1",
            user=OrmUser(
                **{"id": 1, "name": "adrian", "city": OrmCity(id=1, name="Matanzas")}
            ),
        ),
        OrmAddress(
            id=2,
            dir="Address 2",
            user=OrmUser(**{"id": 2, "name": "tom", "city": None}),
        ),
    ]
