from typing import Any
from winter.backend import QueryDriver, Backend
from winter.drivers.mongo import MongoSession
from winter.settings import BackendOptions, WinterSettings
import importlib
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase


BACKENDS: dict[str, Backend] = {}


class DriverNotFoundError(Exception):
    pass


class FactoryNotFoundError(Exception):
    pass


class InvalidDriverInterface(Exception):
    pass


class DriverNotSetError(Exception):
    pass


def init_backend(settings: BackendOptions) -> None:
    """
    Initialize the winter engine with the provided driver in the config.
    Defaults to `winter.drivers.mongo`.
    """
    # try to get driver
    try:
        driver_module = importlib.import_module(settings.driver)
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
    backend = Backend(driver)
    # init the driver
    driver.init(settings)

    BACKENDS[settings.name] = backend


def init_backends(settings: WinterSettings = WinterSettings()) -> None:
    for backend in settings.backends:
        init_backend(backend)


def get_connection(backend_name: str = "default") -> AsyncIOMotorDatabase | AsyncSession:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    return backend.get_connection()


async def get_session(backend_name: str = "default") -> AsyncSession | MongoSession:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    return await backend.driver.get_started_session()


async def commit(session: Any, backend_name: str = "default") -> None:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    await backend.driver.commit_transaction(session)


async def rollback(session: Any, backend_name: str = "default") -> None:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    await backend.driver.abort_transaction(session)


async def close_session(session: Any, backend_name: str = "default") -> None:
    backend = BACKENDS.get(backend_name, None)
    if backend is None:
        raise DriverNotFoundError(f"{backend_name} has not been configured as a backend")

    if backend.driver is None:
        raise DriverNotSetError()

    await backend.driver.close_session(session)
