import abc
from winter.query.nodes import RootNode
from winter.query.parsing import QueryParser
from functools import partial, partialmethod


class QueryDriver(abc.ABC):
    @abc.abstractmethod
    def run(self, query_expression: RootNode, table_name: str, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    async def run_async(self, query_expression: RootNode, table_name: str, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def get_query_repr(self, query_expression: RootNode, table_name: str, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def init(self, *args, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def init_async(self, *args, **kwargs):
        raise NotImplementedError


class Backend:
    driver: QueryDriver

    @classmethod
    def configure_for_driver(cls, driver: QueryDriver):
        assert isinstance(driver, QueryDriver)
        driver.init()
        cls.driver = driver

    @classmethod
    async def configure_for_driver_async(cls, driver: QueryDriver):
        assert isinstance(driver, QueryDriver)
        await driver.init_async()
        cls.driver = driver

    @classmethod
    @classmethod
    def run(cls, query: str, table_name: str, dry_run: bool = False):
        parser = QueryParser()
        root_node = parser.parse(query)
        return partial(cls.driver.run, root_node, table_name)

    @classmethod
    def run_async(cls, query: str, table_name: str, dry_run: bool = False):
        parser = QueryParser()
        root_node = parser.parse(query)
        if dry_run:
            return partial(cls.driver.get_query_repr, root_node, table_name)
        else:
            return partial(cls.driver.run_async, root_node, table_name)
