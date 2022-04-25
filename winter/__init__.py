from winter.backend import QueryDriver, Backend
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


def init_backend(settings: WinterSettings = WinterSettings()) -> None:
    """
    Initialize the winter engine with the priveded driver in the config.
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
