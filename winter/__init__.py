from winter.backend import QueryDriver, Backend
from winter.settings import WinterSettings
import importlib


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
        print(driver_module)
        print(driver_module.factory)
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
