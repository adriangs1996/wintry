from typing import Any, AsyncGenerator
from winter.drivers.pg import SqlAlchemyDriver

from winter.settings import ConnectionOptions, WinterSettings


import winter.backend

from winter.orm import for_model
from sqlalchemy import Integer, Column, String, ForeignKey, Float, delete, select
from sqlalchemy.orm import relation, declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
import pydantic as pdc
import pytest
import pytest_asyncio


# Now import the repository
from winter.repository.base import repository
from winter.repository.crud_repository import CrudRepository


class Address(pdc.BaseModel):
    latitude: float
    longitude: float


class User(pdc.BaseModel):
    id: int
    name: str
    age: int
    address: Address | None = None


# Define the table schemas
Base: Any = declarative_base()


@for_model(Address)
class AddressTable(Base):
    __tablename__ = "Addresses"
    id = Column(Integer, primary_key=True)
    latitude = Column(Float)
    longitude = Column(Float)


@for_model(User)
class UserTable(Base):
    __tablename__ = "Users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)
    address_id = Column(Integer, ForeignKey("Addresses.id"))
    address = relation(AddressTable, lazy="joined")


@repository(User)
class UserRepository(CrudRepository[User, int]):
    pass


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup() -> None:
    winter.backend.Backend.driver = SqlAlchemyDriver()
    winter.backend.Backend.configure_for_driver(
        WinterSettings(
            connection_options=ConnectionOptions(url="postgresql+asyncpg://postgres:secret@localhost/tests")
        )
    )
    engine = getattr(winter.backend.Backend.driver, "_engine")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture
async def clean() -> AsyncGenerator[None, None]:
    yield
    session: AsyncSession = winter.backend.Backend.get_connection()
    async with session.begin():
        await session.execute(delete(AddressTable))
        await session.execute(delete(UserTable))
        await session.commit()


@pytest.mark.asyncio
async def test_repository_can_insert(clean: Any) -> None:
    print(winter.backend.Backend.driver)
    repo = UserRepository()
    user = User(id=2, name="test", age=10)

    await repo.create(entity=user)
    session: AsyncSession = winter.backend.Backend.get_connection()
    async with session.begin():
        results = await session.execute(select(UserTable))
    assert len(results.all()) == 1
