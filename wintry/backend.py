import abc
from typing import Any, Type
from wintry.query.nodes import RootNode
from wintry.query.parsing import QueryParser
from functools import partial

from wintry.settings import EngineType


class BackendException(Exception):
    pass


class QueryDriver(abc.ABC):
    driver_class: EngineType = EngineType.NoEngine

    @abc.abstractmethod
    def run(
        self,
        query_expression: RootNode,
        table_name: str | Type[Any],
        session: Any = None,
        **kwargs: Any
    ) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    async def run_async(
        self,
        query_expression: RootNode,
        table_name: str | Type[Any],
        session: Any = None,
        **kwargs: Any
    ) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    def get_query_repr(
        self, query_expression: RootNode, table_name: str | Type[Any], **kwargs: Any
    ) -> Any:
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

    @abc.abstractmethod
    async def get_started_session(self) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    async def commit_transaction(self, session: Any) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def abort_transaction(self, session: Any) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def close_session(self, session: Any) -> None:
        raise NotImplementedError


class Backend:
    driver: QueryDriver | None = None

    def __init__(self, driver: QueryDriver) -> None:
        self.driver = driver

    def get_connection(self) -> Any:
        assert self.driver is not None
        return self.driver.get_connection()

    def configure_for_driver(self, *args: Any, **kwargs: Any) -> None:
        assert self.driver is not None
        self.driver.init(*args, **kwargs)

    async def configure_for_driver_async(self, *args: Any, **kwargs: Any) -> None:
        assert self.driver is not None
        await self.driver.init_async(*args, **kwargs)

    def run(
        self, query: str, table_name: str | Type[Any], dry_run: bool = False
    ) -> partial[Any]:
        if self.driver is None:
            raise BackendException("Driver is not configured.")

        parser = QueryParser()
        root_node = parser.parse(query)
        return partial(self.driver.run, root_node, table_name)

    def run_async(
        self, query: str, table_name: str | Type[Any], dry_run: bool = False
    ) -> partial[Any]:
        if self.driver is None:
            raise BackendException("Driver is not configured.")

        parser = QueryParser()
        root_node = parser.parse(query)
        if dry_run:
            return partial(self.driver.get_query_repr, root_node, table_name)
        else:
            return partial(self.driver.run_async, root_node, table_name)
