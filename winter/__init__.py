from typing import Any
from winter.backend import QueryDriver, Backend
from winter.drivers.mongo import MongoSession
from winter.settings import WinterSettings
import importlib
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase


class DriverNotFoundError(Exception):
    pass


class FactoryNotFoundError(Exception):
    pass


class InvalidDriverInterface(Exception):
    pass


class DriverNotSetError(Exception):
    pass


def init_backend(settings: WinterSettings = WinterSettings()) -> None:
    """
    Initialize the winter engine with the provided driver in the config.
    Defaults to `winter.drivers.mongo`.
    """
    # try to get driver
    try:
        driver_module = importlib.import_module(settings.backend)
    except ModuleNotFoundError:
        raise DriverNotFoundError("Provide the absolute path to driver module: Ej: winter.drivers.module")

    try:
        factory = getattr(driver_module, "factory")
    except AttributeError:
        raise FactoryNotFoundError(
            "Driver module must contain a factory function: (WinterSettings) -> QueryDriver"
        )

    driver = factory(settings)

    if not isinstance(driver, QueryDriver):
        raise InvalidDriverInterface("Driver should implement QueryDriver interface")

    # set the backend driver
    Backend.driver = driver
    # init the driver
    driver.init(settings)


def get_connection() -> AsyncIOMotorDatabase | AsyncSession:
    return Backend.get_connection()


async def get_session() -> AsyncSession | MongoSession:
    if Backend.driver is None:
        raise DriverNotSetError()

    return await Backend.driver.get_started_session()


async def commit(session: Any) -> None:
    if Backend.driver is None:
        raise DriverNotSetError()

    await Backend.driver.commit_transaction(session)


async def rollback(session: Any) -> None:
    if Backend.driver is None:
        raise DriverNotSetError()

    await Backend.driver.abort_transaction(session)


async def close_session(session: Any) -> None:
    if Backend.driver is None:
        raise DriverNotSetError()

    await Backend.driver.close_session(session)
