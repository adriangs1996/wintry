import importlib
import logging
from typing import Any, Callable, Coroutine, Sequence, Union, Type, TypeVar

import uvicorn

# Import things directly from fastapi so they are
# accessible from wintry
from fastapi import Body, Depends, FastAPI, Header, Query
from fastapi.datastructures import Default
from fastapi.middleware import Middleware
from fastapi.params import Depends as DependsParam
from fastapi.routing import APIRoute
from fastapi.utils import generate_unique_id
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute

# Import the services defined by the framework
import wintry.services
from wintry.controllers import __controllers__
from wintry.errors import (
    ForbiddenError,
    InternalServerError,
    InvalidRequestError,
    NotFoundError,
    forbidden_exception_handler,
    internal_server_exception_handler,
    invalid_request_exception_handler,
    not_found_exception_handler,
)
from wintry.middlewares import IoCContainerMiddleware
from wintry.settings import BackendOptions, EngineType, WinterSettings
from wintry.transporters.service_container import ServiceContainer
from wintry.utils.loaders import autodiscover_modules
from wintry.ioc import inject
from wintry.utils.keys import __winter_backend_identifier_key__

__version__ = "0.1.2"


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


class InvalidEngineOption(Exception):
    pass


def _config_logger():
    FORMAT: str = "%(levelprefix)s %(asctime)s | %(message)s"
    # create logger
    logger = logging.getLogger("logger")
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = uvicorn.logging.DefaultFormatter(
        FORMAT, datefmt="%Y-%m-%d %H:%M:%S"
    )  # type:ignore

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    return logger


class App(FastAPI):
    def __init__(
        self,
        settings: WinterSettings,
        *,
        debug: bool = False,
        routes: list[BaseRoute] | None = None,
        title: str = "Wintry API",
        description: str = "",
        version: str = "0.1.0",
        openapi_url: str | None = "/openapi.json",
        openapi_tags: list[dict[str, Any]] | None = None,
        servers: list[dict[str, Union[str, Any]]] | None = None,
        dependencies: Sequence[DependsParam] | None = None,
        default_response_class: type[Response] = Default(JSONResponse),
        docs_url: str | None = "/docs",
        redoc_url: str | None = "/redoc",
        swagger_ui_oauth2_redirect_url: str | None = "/docs/oauth2-redirect",
        swagger_ui_init_oauth: dict[str, Any] | None = None,
        middleware: Sequence[Middleware] | None = None,
        exception_handlers: dict[
            Union[int, type[Exception]],
            Callable[[Request, Any], Coroutine[Any, Any, Response]],
        ]
        | None = None,
        on_startup: Sequence[Callable[[], Any]] | None = None,
        on_shutdown: Sequence[Callable[[], Any]] | None = None,
        terms_of_service: str | None = None,
        contact: dict[str, Union[str, Any]] | None = None,
        license_info: dict[str, Union[str, Any]] | None = None,
        openapi_prefix: str = "",
        root_path: str = "",
        root_path_in_servers: bool = True,
        responses: dict[Union[int, str], dict[str, Any]] | None = None,
        callbacks: list[BaseRoute] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        swagger_ui_parameters: dict[str, Any] | None = None,
        generate_unique_id_function: Callable[[APIRoute], str] = Default(
            generate_unique_id
        ),
        **extra: Any,
    ) -> None:
        super().__init__(
            debug=debug,
            routes=routes,
            callbacks=callbacks,
            contact=contact,
            default_response_class=default_response_class,
            dependencies=dependencies,
            deprecated=deprecated,
            description=description,
            docs_url=docs_url,
            exception_handlers=exception_handlers,
            extra=extra,
            generate_unique_id_function=generate_unique_id_function,
            include_in_schema=include_in_schema,
            license_info=license_info,
            middleware=middleware,
            on_shutdown=on_shutdown,
            on_startup=on_startup,
            openapi_prefix=openapi_prefix,
            openapi_tags=openapi_tags,
            openapi_url=openapi_url,
            redoc_url=redoc_url,
            responses=responses,
            root_path=root_path,
            root_path_in_servers=root_path_in_servers,
            servers=servers,
            swagger_ui_init_oauth=swagger_ui_init_oauth,
            swagger_ui_oauth2_redirect_url=swagger_ui_oauth2_redirect_url,
            swagger_ui_parameters=swagger_ui_parameters,
            terms_of_service=terms_of_service,
            title=title,
            version=version,
        )
        # Provide settings for the whole app. This would be accessible from
        # dependency injection.
        self.settings = settings

        self.service_container = ServiceContainer(settings)

        self.bootstrap()

        for transporter in settings.transporters:
            driver = importlib.import_module(transporter.driver)
            service_class = getattr(driver, transporter.service)
            self.service_container.add_service(service_class)

        if settings.middlewares:
            for mid in settings.middlewares:
                # Try to import the middleware module
                module = importlib.import_module(mid.module)
                # try to get the middleware object
                middleware_factory = getattr(module, mid.name)
                # register the middleware
                self.add_middleware(middleware_factory, **mid.args)

        self.add_middleware(IoCContainerMiddleware)

        for controller in __controllers__:
            self.include_router(controller, prefix=settings.server_prefix)

        if settings.include_error_handling:

            self.add_exception_handler(NotFoundError, not_found_exception_handler)
            self.add_exception_handler(
                InternalServerError, internal_server_exception_handler
            )
            self.add_exception_handler(ForbiddenError, forbidden_exception_handler)
            self.add_exception_handler(
                InvalidRequestError, invalid_request_exception_handler
            )

        @self.on_startup
        @inject
        async def wintry_startup(logger: logging.Logger):
            if self.settings.transporters:
                self.service_container.start_services()

        @self.on_shutdown
        @inject
        async def wintry_shutdown(logger: logging.Logger):
            if self.settings.transporters:
                await self.service_container.close()
            logger.info("Server is shuting down")

    def bootstrap(self):
        """
        Launch general configurations for the server.
        :func:`Winter.setup()` is based on the configurations
        provided in a settings.json, the default values of
        the `WinterSettings` or a custom instance passed
        to this method. It will launch services based on configuration
        flags, like autodiscovery and DI Configuration
        """
        settings = self.settings

        # Configure the builtin logger
        logger = _config_logger()

        # Load all the modules so DI and mappings works
        if settings.auto_discovery_enabled:
            logger.info("Loading project modules.")
            autodiscover_modules(settings)
            logger.info("Project modules loaded.")

    def on_startup(self, fn: Callable[..., Any]):
        return self.on_event("startup")(fn)

    def on_shutdown(self, fn: Callable[..., Any]):
        return self.on_event("shutdown")(fn)


T = TypeVar("T")
P = TypeVar("P")


class AppBuilder(object):
    @staticmethod
    def add_service(interface: Type[T], provider: Type[P]) -> "Type[AppBuilder]":

        return AppBuilder
