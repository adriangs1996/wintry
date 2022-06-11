from typing import Any, AsyncGenerator
from wintry import BACKENDS, get_connection, init_backends
from wintry.models import Array, Id, Model, metadata
from wintry.repository import Repository
from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings
from wintry.utils.model_binding import load_model
from wintry.transactions.transactional import transactional
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text, delete
import pytest
import pytest_asyncio

from wintry.utils.virtual_db_schema import get_model_sql_table


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


class StateRepository(Repository[OrmState, int], entity=OrmState):
    ...


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


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    connection: AsyncConnection = await get_connection()
    connection.begin()
    UserTable = get_model_sql_table(OrmUser)
    AddressTable = get_model_sql_table(OrmAddress)
    StateTable = get_model_sql_table(OrmState)
    CityTable = get_model_sql_table(OrmCity)
    await connection.execute(delete(UserTable))
    await connection.execute(delete(AddressTable))
    await connection.execute(delete(StateTable))
    await connection.execute(delete(CityTable))

    await create_addresses(connection)
    await create_cities(connection)
    await create_users(connection)
    await create_states(connection)

    await connection.commit()
    await connection.close()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def engine():
    init_backends(
        WinterSettings(
            backends=[
                BackendOptions(
                    driver="wintry.drivers.pg",
                    connection_options=ConnectionOptions(
                        url="sqlite+aiosqlite:///:memory:"
                    ),
                )
            ],
        )
    )
    async_engine = getattr(BACKENDS["default"].driver, "_engine")

    conn: AsyncConnection = await async_engine.connect()
    await conn.run_sync(metadata.create_all)
    await create_addresses(conn)
    await create_cities(conn)
    await create_users(conn)
    await create_states(conn)
    await conn.commit()
    await conn.close()
    return async_engine


@pytest.mark.asyncio
async def test_simple_model_binding(engine: Any):
    async with engine.connect() as conn:
        results = await load_model(OrmState, conn)
        assert results == [OrmState(id=1, name="Miami")]


@pytest.mark.asyncio
async def test_model_binding_whole_tree(engine: Any):
    async with engine.connect() as conn:
        results = await load_model(OrmAddress, conn)
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


@pytest.mark.asyncio
async def test_repository_can_load_simple_model():
    state_repository = StateRepository()
    states = await state_repository.find()

    assert states == [OrmState(id=1, name="Miami")]


@pytest.mark.asyncio
async def test_repository_can_get_by_id_simple():
    state_repository = StateRepository()
    state = await state_repository.get_by_id(id=1)

    assert state is not None
    assert state == OrmState(id=1, name="Miami")


@pytest.mark.asyncio
async def test_repository_get_by_id_return_none_if_no_found():
    state_repository = StateRepository()
    state = await state_repository.get_by_id(id=2)

    assert state is None


@pytest.mark.asyncio
async def test_repository_can_create_simple_model(engine, clean):
    state_repository = StateRepository()
    state = await state_repository.create(entity=OrmState(name="NewState"))

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT * FROM OrmState"))).fetchall()
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_repository_can_update_simple_model(engine, clean):
    state_repository = StateRepository()
    await state_repository.update(entity=OrmState(id=1, name="NewState"))

    async with engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT * FROM OrmState WHERE id = 1"))
        ).fetchall()
        assert len(rows) == 1
        assert rows[0].name == "NewState"


@pytest.mark.asyncio
async def test_repository_can_delete_simple_model_by_id(engine, clean):
    state_repository = StateRepository()
    await state_repository.delete_by_id(id=1)

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT * FROM OrmState"))).fetchall()
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_transactions_works_on_simple_model(engine, clean):
    @transactional
    async def create_state(repository: StateRepository):
        state = await repository.create(entity=OrmState(id=300,name="NewState"))
    
    await create_state(StateRepository())
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT * FROM OrmState"))).fetchall()
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_transactions_rollbacks_on_error(engine, clean):
    @transactional
    async def create_state_with_error(repository: StateRepository):
        state1 = await repository.create(entity=OrmState(id=100, name="NewState"))
        state2 = await repository.create(entity=OrmState(id=23, name="BOOM"[10]))
    
    with pytest.raises(IndexError):
        await create_state_with_error(StateRepository())
    
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT * FROM OrmState"))).fetchall()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_transactions_commit_changes_on_property_update(engine, clean):
    @transactional
    async def update_state_property(repository: StateRepository):
        state = await repository.get_by_id(id=1)
        assert state is not None
        state.name = "UpdatedState"
    
    await update_state_property(StateRepository())

    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT * FROM OrmState"))).fetchall()
        assert len(rows) == 1
        assert rows[0].name == "UpdatedState"

@pytest.mark.asyncio
async def test_transactions_can_add_object_to_list(engine, clean):
    @transactional
    async def update_state_cities(repository: StateRepository):
        state = await repository.get_by_id(id=1)
        assert state is not None
        state.cities.append(OrmCity(id=109, name="NewCity"))
    
    await update_state_cities(StateRepository())
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT * FROM OrmCity ORDER BY id"))).fetchall()
        assert len(rows) == 2
        # Assert that the FK was updated
        assert rows[1].ormstate_id == 1
    