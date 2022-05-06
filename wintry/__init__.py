from enum import Enum
from typing import Any
from wintry.backend import QueryDriver, Backend
from wintry.dependency_injection import Factory
from wintry.settings import BackendOptions, WinterSettings
import importlib
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
import inject
from wintry.utils.loaders import autodiscover_modules
from fastapi import FastAPI
from wintry.controllers import __controllers__
from wintry.errors import (
    InvalidRequestError,
    ForbiddenError,
    NotFoundError,
    InternalServerError,
    not_found_exception_handler,
    forbidden_exception_handler,
    internal_server_exception_handler,
    invalid_request_exception_handler,
)
import uvicorn

# Import the services defined by the framework
import wintry.services


BACKENDS: dict[str, Backend] = {}


class ServerTypes(Enum):
    API = 0
    RPC = 1


class NotConfiguredFactoryForServerType(Exception):
    pass


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
        raise DriverNotFoundError(
            "Provide the absolute path to driver module: Ej: winter.drivers.module"
        )

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


def _config_logger():
    FORMAT: str = "%(levelprefix)s %(asctime)s | %(message)s"
    # create logger
    logger = logging.getLogger("logger")
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = uvicorn.logging.DefaultFormatter(FORMAT, datefmt="%Y-%m-%d %H:%M:%S")  # type: ignore

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)


class Winter:
    @staticmethod
    def setup(settings: WinterSettings = WinterSettings()):
        """
        Launch general configurations for the server.
        :func:`Winter.setup()` is based on the configurations
        provided in a settings.json, the default values of
        the `WinterSettings` or a custom instance passed
        to this method. It will launch services based on configuration
        flags, like autodiscovery and DI Configuration
        """
        # Configure the builtin logger
        _config_logger()

        # Load all the modules so DI and mappings works
        if settings.auto_discovery_enabled:
            autodiscover_modules(settings)

        # Configure the DI Container
        from wintry.dependency_injection import __mappings__

        def config(binder: inject.Binder):
            for dependency, factory in __mappings__.items():
                if isinstance(factory, Factory):
                    binder.bind_to_provider(dependency, factory)
                else:
                    binder.bind(dependency, factory())

        inject.configure_once(config)

        # Initialize the backends
        if settings.backends:
            init_backends(settings)

    @staticmethod
    def factory(settings=WinterSettings(), server_type: ServerTypes = ServerTypes.API):
        match server_type:
            case ServerTypes.API:
                return Winter._get_api_instance(settings)
            case _:
                raise NotConfiguredFactoryForServerType

    @staticmethod
    def serve(
        server_type=ServerTypes.API, with_settings: WinterSettings = WinterSettings()
    ):
        match server_type:
            case ServerTypes.API:
                uvicorn.run(
                    with_settings.app_path,
                    reload=with_settings.hot_reload,
                    host=with_settings.host,
                    port=with_settings.port,
                )
            case _:
                raise NotConfiguredFactoryForServerType

    @staticmethod
    def _get_api_instance(settings: WinterSettings):
        api = FastAPI(
            docs_url=f"{settings.server_prefix}/swag",
            redoc_url=f"{settings.server_prefix}/docs",
            openapi_url=f"{settings.server_prefix}/openapi.json",
            title=settings.server_title,
            version=settings.server_version,
            contact={"name": "NextX Team"},
        )

        if settings.middlewares:
            for middleware in settings.middlewares:
                # Try to import the middleware module
                module = importlib.import_module(middleware.module)
                # try to get the middleware object
                middleware_factory = getattr(module, middleware.name)
                # register the middleware
                api.add_middleware(middleware_factory, **middleware.args)

        for controller in __controllers__:
            api.include_router(controller, prefix=settings.server_prefix)

        if settings.include_error_handling:

            api.add_exception_handler(NotFoundError, not_found_exception_handler)
            api.add_exception_handler(
                InternalServerError, internal_server_exception_handler
            )
            api.add_exception_handler(ForbiddenError, forbidden_exception_handler)
            api.add_exception_handler(
                InvalidRequestError, invalid_request_exception_handler
            )

        return api


__all__ = ["get_connection", "init_backends"]
