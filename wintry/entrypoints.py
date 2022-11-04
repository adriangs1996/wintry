# Import the services defined by the framework
import logging
from typing import Any, Sequence, Coroutine, Callable, Optional, List, Union

from wintry.errors import (
    NotFoundError,
    not_found_exception_handler,
    internal_server_exception_handler,
    InternalServerError,
    ForbiddenError,
    forbidden_exception_handler,
    invalid_request_exception_handler,
    InvalidRequestError,
)
from wintry.middlewares import IoCContainerMiddleware
from wintry.controllers import __controllers__
from wintry.utils.loaders import autodiscover_modules
from fastapi import FastAPI
import uvicorn.logging


from fastapi.datastructures import Default
from fastapi.middleware import Middleware as Middleware
from fastapi.params import Depends as DependsParam
from fastapi.routing import APIRoute
from fastapi.utils import generate_unique_id
from starlette.requests import Request as Request
from starlette.responses import JSONResponse as JSONResponse, Response as Response
from starlette.routing import BaseRoute


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
        *,
        server_prefix: str = "",
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
        self.add_middleware(IoCContainerMiddleware)

        for controller in __controllers__:
            self.include_router(controller, prefix=server_prefix)

        _config_logger()

    def on_startup(self, fn: Callable[..., Any]):
        return self.on_event("startup")(fn)

    def on_shutdown(self, fn: Callable[..., Any]):
        return self.on_event("shutdown")(fn)


class AppBuilder(object):
    @staticmethod
    def autodiscover(app_path: str, modules: Optional[List[str]] = None):
        modules = modules or []
        autodiscover_modules(modules, app_path)
        return AppBuilder

    @staticmethod
    def use_default_exception_handlers(app: App):
        app.add_exception_handler(NotFoundError, not_found_exception_handler)
        app.add_exception_handler(InternalServerError, internal_server_exception_handler)
        app.add_exception_handler(ForbiddenError, forbidden_exception_handler)
        app.add_exception_handler(InvalidRequestError, invalid_request_exception_handler)
        return AppBuilder
