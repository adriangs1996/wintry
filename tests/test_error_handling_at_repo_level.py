from typing import AsyncGenerator
import wintry.errors.definitions as errors
from wintry.models import Model, VirtualDatabaseSchema, ModelRegistry, metadata
from wintry import get_connection, init_backends, BACKENDS
from wintry.repository import Repository, RepositoryRegistry
from wintry.repository.base import managed
from wintry.settings import WinterSettings, BackendOptions, ConnectionOptions
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncConnection
import pytest
import pytest_asyncio

from wintry.utils.virtual_db_schema import get_model_sql_table


class ErrorHandlingUser(Model, table="ErrorUser"):
    id: int
    name: str


class UserRepository(Repository[ErrorHandlingUser, int], entity=ErrorHandlingUser):
    @managed
    def bad_method(self):
        raise Exception("Bad Method")


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    table = get_model_sql_table(ErrorHandlingUser)
    session: AsyncConnection = await get_connection()
    session.begin()
    await session.execute(delete(table))
    await session.commit()
    await session.close()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup():
    ModelRegistry.configure()
    VirtualDatabaseSchema.use_sqlalchemy(metadata=metadata)
    RepositoryRegistry.configure_for_sqlalchemy()
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
    engine = getattr(BACKENDS["default"].driver, "_engine")
    conn = await engine.connect()
    await conn.run_sync(metadata.create_all)
    await conn.commit()
    await conn.close()


@pytest.mark.asyncio
async def test_repository_detect_duplicated_key(clean):
    with pytest.raises(errors.InvalidRequestError):
        repo = UserRepository()

        await repo.create(entity=ErrorHandlingUser(id=1, name="Test"))
        await repo.create(entity=ErrorHandlingUser(id=1, name="Another"))


def test_repository_handles_general_exceptions(clean):
    with pytest.raises(errors.InternalServerError):
        repo = UserRepository()
        repo.bad_method()
