from typing import AsyncGenerator
import wintry.errors.definitions as errors
from wintry.models import Model, VirtualDatabaseSchema
from wintry import get_connection, init_backends, BACKENDS
from wintry.repository import Repository, RepositoryRegistry
from wintry.repository.base import managed
from wintry.settings import WinterSettings, BackendOptions, ConnectionOptions
from sqlalchemy import MetaData, delete
from sqlalchemy.ext.asyncio import AsyncSession
import pytest
import pytest_asyncio

metadata = MetaData()


class ErrorHandlingUser(Model):
    id: int
    name: str


class UserRepository(Repository[ErrorHandlingUser, int], entity=ErrorHandlingUser):
    @managed
    def bad_method(self):
        raise Exception("Bad Method")


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    session: AsyncSession = get_connection()
    async with session.begin():
        await session.execute(delete(ErrorHandlingUser))
        await session.commit()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup():
    VirtualDatabaseSchema.use_sqlalchemy(metadata=metadata)
    RepositoryRegistry.configure_for_sqlalchemy()
    init_backends(
        WinterSettings(
            backends=[
                BackendOptions(
                    driver="wintry.drivers.pg",
                    connection_options=ConnectionOptions(
                        url="postgresql+asyncpg://postgres:secret@localhost/tests"
                    ),
                )
            ],
        )
    )
    engine = getattr(BACKENDS["default"].driver, "_engine")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


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
