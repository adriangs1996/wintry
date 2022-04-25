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
    def run(self, query_expression: RootNode, table_name: str | Type[Any], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    async def run_async(self, query_expression: RootNode, table_name: str | Type[Any], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    def get_query_repr(self, query_expression: RootNode, table_name: str | Type[Any], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    def init(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def init_async(self, *args: Any, **kwargs: Any) -> None:
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
    def configure_for_driver(cls, *args: Any, **kwargs: Any) -> None:
        assert cls.driver is not None
        cls.driver.init(*args, **kwargs)

    @classmethod
    async def configure_for_driver_async(cls, *args: Any, **kwargs: Any) -> None:
        assert cls.driver is not None
        await cls.driver.init_async(*args, **kwargs)

    @classmethod
    @classmethod
    def run(cls, query: str, table_name: str | Type[Any], dry_run: bool = False) -> partial[Any]:
        if cls.driver is None:
            raise BackendException("Driver is not configured.")

        parser = QueryParser()
        root_node = parser.parse(query)
        return partial(cls.driver.run, root_node, table_name)

    @classmethod
    def run_async(cls, query: str, table_name: str | Type[Any], dry_run: bool = False) -> partial[Any]:
        if cls.driver is None:
            raise BackendException("Driver is not configured.")

        parser = QueryParser()
        root_node = parser.parse(query)
        if dry_run:
            return partial(cls.driver.get_query_repr, root_node, table_name)
        else:
            return partial(cls.driver.run_async, root_node, table_name)
