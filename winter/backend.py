import abc
from typing import Any, Callable, Type
from winter.query.nodes import RootNode
from winter.query.parsing import QueryParser
from functools import partial
import winter.settings
import importlib


class BackendException(Exception):
    pass


class QueryDriver(abc.ABC):
    @abc.abstractmethod
    def run(self, query_expression: RootNode, table_name: str | Type[Any], **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    async def run_async(self, query_expression: RootNode, table_name: str | Type[Any], **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_query_repr(self, query_expression: RootNode, table_name: str | Type[Any], **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def init(self, *args, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def init_async(self, *args, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_connection(self) -> Any:
        raise NotImplementedError


class Backend:
    driver: QueryDriver | None = None

    @classmethod
    def get_connection(cls) -> Any:
        assert cls.driver is not None
        return cls.driver.get_connection()

    @classmethod
    def configure_for_driver(cls, *args, **kwargs):
        driver.init(*args, **kwargs)

    @classmethod
    async def configure_for_driver_async(cls, *args, **kwargs):
        await driver.init_async()

    @classmethod
    @classmethod
    def run(cls, query: str, table_name: str | Type[Any], dry_run: bool = False):
        if cls.driver is None:
            raise BackendException("Driver is not configured.")

        parser = QueryParser()
        root_node = parser.parse(query)
        return partial(cls.driver.run, root_node, table_name)

    @classmethod
    def run_async(cls, query: str, table_name: str | Type[Any], dry_run: bool = False):
        if cls.driver is None:
            raise BackendException("Driver is not configured.")

        parser = QueryParser()
        root_node = parser.parse(query)
        if dry_run:
            return partial(cls.driver.get_query_repr, root_node, table_name)
        else:
            return partial(cls.driver.run_async, root_node, table_name)


# Bootstrapping process
if Backend.driver is None:
    backend_settings = winter.settings.WinterSettings()
    try:
        driver_module = importlib.import_module(backend_settings.backend)
    except ModuleNotFoundError:
        raise BackendException(
            "Driver module was not found: provide a valid absolute path to driver."
        )

    try:
        driver_factory: Callable[
            [winter.settings.WinterSettings], QueryDriver
        ] = getattr(driver_module, "factory")
    except AttributeError:
        raise BackendException(
            "Driver module must provide a factory function (settings: WinterSettings) -> QueryDriver"
        )
    try:
        driver = driver_factory(backend_settings)
    except Exception as e:
        raise BackendException("Error initializing instance of driver")

    Backend.driver = driver
