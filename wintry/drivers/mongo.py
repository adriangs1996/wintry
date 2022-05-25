from functools import singledispatchmethod
from typing import Any, Dict, Type, cast
from wintry.backend import QueryDriver
from wintry.query.nodes import (
    AndNode,
    Create,
    Delete,
    EqualToNode,
    FilterNode,
    Find,
    Get,
    GreaterThanNode,
    InNode,
    LowerThanNode,
    NotEqualNode,
    NotGreaterThanNode,
    NotInNode,
    NotLowerThanNode,
    OpNode,
    OrNode,
    RootNode,
    Update,
)
import motor.motor_asyncio
from motor.core import AgnosticClientSession, AgnosticClient
from wintry.settings import BackendOptions, EngineType
from dataclasses import is_dataclass, asdict
from dataclass_wizard import fromdict


class MongoSession(AgnosticClientSession):
    """
    This is a stub class for the benefit of the type-checker, do not
    instantiate it directly. Instead call :func:`typing.cast()` with
    `MongoSession` as first argument when calling :func:`motor.motor_asyncio.MotorClient.start_session()`.
    """

    async def commit_transaction(self) -> None:
        """
        Commit a multi-statement transaction
        """
        ...

    async def abort_transaction(self) -> None:
        """
        Abort a multi-statement transaction.
        """
        ...

    async def end_session(self) -> None:
        """
        Finish this session. If a transaction has started, abort it.

        It is an error to use the session after the session has ended.
        """
        ...


class Client(AgnosticClient):
    """
    This is a stub class for the benefit of the type-checker, do not
    instantiate it directly. Instead call :func:`typing.cast()` with
    `Client` as first argument when instantiating an AsyncioMotorClient.
    """

    async def start_session(self) -> AgnosticClientSession:
        ...


def Eq(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$eq": value}}


def Lt(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$lt": value}}


def Gt(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$gt": value}}


def Lte(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$lte": value}}


def Gte(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$gte": value}}


def In(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$in": value}}


def Nin(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$nin": value}}


def Ne(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$ne": value}}


def NotGt(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$not": {"$gt": value}}}


def Notlt(field: str, value: Any) -> Dict[str, Dict[str, Any]]:
    return {field: {"$not": {"$lt": value}}}


def create_expression(node: FilterNode, op: Any, **kwargs: Any) -> Any:
    field_name = node.field
    if "." in field_name:
        value_query = "__".join(field_name.split("."))
    else:
        value_query = field_name
    value = kwargs.get(value_query, None)
    if value is None:
        raise ExecutionError(f"{field_name} was not suplied as argument")

    return op(field_name, value)


class DriverMappingError(Exception):
    pass


def get_tablename(cls: type) -> str:
    return getattr(cls, "__tablename__", cls.__name__.lower() + "s")


def map_to_table(cls: type, instance: dict):
    if not is_dataclass(cls):
        raise DriverMappingError(f"{cls} is not a dataclass")

    if instance is None:
        return None

    return fromdict(cls, instance)


class ExecutionError(Exception):
    pass


class MongoDbDriver(QueryDriver):
    driver_class: EngineType = EngineType.NoSql

    def get_connection(self) -> Any:
        return self.db

    async def get_started_session(self) -> MongoSession:
        session = cast(MongoSession, await self.client.start_session())
        session.start_transaction()
        return session

    async def commit_transaction(self, session: MongoSession) -> None:
        if session.in_transaction:
            await session.commit_transaction()

    async def abort_transaction(self, session: MongoSession) -> None:
        if session.in_transaction:
            await session.abort_transaction()

    async def close_session(self, session: MongoSession) -> None:
        if not session.has_ended:
            await session.end_session()

    def init(self, settings: BackendOptions) -> None:  # type: ignore
        if settings.connection_options.url is not None:
            self.client = cast(
                Client, motor.motor_asyncio.AsyncIOMotorClient(settings.connection_options.url)
            )
        else:
            host = settings.connection_options.host
            port = settings.connection_options.port
            self.client = cast(Client, motor.motor_asyncio.AsyncIOMotorClient(host, port))

        database_name = settings.connection_options.database_name
        self.db = self.client[database_name]

    async def init_async(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def get_query_repr(self, query_expression: RootNode, table: type, **kwargs: Any) -> str:
        return await self.query(query_expression, table, **kwargs)

    async def run(self, query_expression: RootNode, table: type, session: Any = None, **kwargs: Any) -> Any:
        return super().run(query_expression, table, session=session, **kwargs)

    async def run_async(
        self, query_expression: RootNode, table: type, session: Any = None, **kwargs: Any
    ) -> Any:
        return await self.visit(query_expression, table, session=session, **kwargs)

    @singledispatchmethod
    async def query(self, node: OpNode, table: type, session: Any = None, **kwargs: Any) -> str:
        return await self.visit(node, table, **kwargs)

    @query.register
    async def _(self, node: Find, table: type, session: Any = None, **kwargs: Any) -> str:
        if node.filters is not None:
            filters = await self.query(node.filters, table, **kwargs) or ""
        else:
            filters = {}  # type: ignore
        return f"db.{get_tablename(table)}.find({filters}).to_list()"

    @query.register
    async def _(self, node: Delete, table: type, session: Any = None, **kwargs: Any) -> str:
        if node.filters is not None:
            filters = await self.query(node.filters, table, **kwargs) or ""
        else:
            filters = {}  # type: ignore
        return f"db.{get_tablename(table)}.delete_many({filters})"

    @query.register
    async def _(self, node: Get, table: type, session: Any = None, **kwargs: Any) -> str:
        filters = await self.query(node.filters, table, **kwargs) or ""
        return f"db.{get_tablename(table)}.find_one({filters})"

    @query.register
    async def _(self, node: Create, table: type, session: Any = None, **kwargs: Any) -> str:
        entity = kwargs.get("entity", None)
        if entity is None:
            raise ExecutionError("Entity parameter required for create operation")

        if is_dataclass(entity):
            entity = asdict(entity)

        return f"db.{get_tablename(table)}.insert_one({entity})"

    @query.register
    async def _(self, node: Update, table: type, *, entity: Any, session: Any = None) -> str:
        _id = getattr(entity, "id", None)
        if _id is None:
            raise ExecutionError("Entity must have id field")

        if is_dataclass(entity):
            entity = asdict(entity)

        return f"db.{get_tablename(table)}.update_one({{'id': {_id}}}, {entity})"

    @singledispatchmethod
    async def visit(self, node: OpNode, table: type, session: Any = None, **kwargs: Any) -> Any:
        raise NotImplementedError

    @visit.register
    async def _(self, node: Create, table: type, session: Any = None, **kwargs: Any) -> Any:
        entity = kwargs.get("entity", None)
        if entity is None:
            raise ExecutionError("Entity parameter required for create operation")

        if is_dataclass(entity):
            entity = asdict(entity)

        collection = self.db[get_tablename(table)]
        await collection.insert_one(entity, session=session)  # type: ignore
        return map_to_table(table, entity)

    @visit.register
    async def _(self, node: Update, table: type, *, entity: Any, session: Any = None) -> Any:
        _id = getattr(entity, "id", None)
        if _id is None:
            raise ExecutionError("Entity must have id field")

        if is_dataclass(entity):
            entity = asdict(entity)

        collection = self.db[get_tablename(table)]
        await collection.update_one({"id": _id}, {"$set": entity}, session=session)  # type: ignore

    @visit.register
    async def _(self, node: Find, table: type, session: Any = None, **kwargs: Any) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[get_tablename(table)]

        documents = await collection.find(filters, session=session).to_list(None)
        return [map_to_table(table, doc) for doc in documents]

    @visit.register
    async def _(self, node: Delete, table: type, session: Any = None, **kwargs: Any) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[get_tablename(table)]

        await collection.delete_many(filters, session=session)  # type: ignore

    @visit.register
    async def _(self, node: Get, table: type, session: Any = None, **kwargs: Any) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[get_tablename(table)]

        documents = await collection.find_one(filters, session=session)  # type: ignore
        return map_to_table(table, documents)

    @visit.register
    async def _(self, node: AndNode, table: type, **kwargs: Any) -> Any:
        conditions = await self.visit(node.left, table, **kwargs)

        # conditions should be a list of tuples name, value where
        # name => FieldName (str)
        # value => comparison condition (dict)
        and_list = [conditions]
        where = {"$and": and_list}

        if node.right is not None:
            right_condition = await self.visit(node.right, table, **kwargs)
            if isinstance(node.right, AndNode):
                where["$and"].extend(right_condition["$and"])
            else:
                where["$and"].append(right_condition)

        return where

    @visit.register
    async def _(self, node: OrNode, table: type, **kwargs: Any) -> Any:
        or_condition = await self.visit(node.left, table, **kwargs)

        # or_condition should be a list of tuples name, value where
        # name => FieldName (str)
        # value => comparison condition (dict)
        or_list = [or_condition]

        where = {"$or": or_list}

        if node.right is not None:
            right_condition = await self.visit(node.right, table, **kwargs)
            if isinstance(node.right, OrNode):
                where["$or"].extend(right_condition["$or"])
            else:
                where["$or"].append(right_condition)

        return where

    @visit.register
    async def _(self, node: EqualToNode, table: type, **kwargs: Any) -> Any:
        return create_expression(node, Eq, **kwargs)

    @visit.register
    async def _(self, node: NotEqualNode, table: type, **kwargs: Any) -> Any:
        return create_expression(node, Ne, **kwargs)

    @visit.register
    async def _(self, node: LowerThanNode, table: type, **kwargs: Any) -> Any:
        return create_expression(node, Lt, **kwargs)

    @visit.register
    async def _(self, node: NotLowerThanNode, table: type, **kwargs: Any) -> Any:
        return create_expression(node, Notlt, **kwargs)

    @visit.register
    async def _(self, node: GreaterThanNode, table: type, **kwargs: Any) -> Any:
        return create_expression(node, Gt, **kwargs)

    @visit.register
    async def _(self, node: NotGreaterThanNode, table: type, **kwargs: Any) -> Any:
        return create_expression(node, Notlt, **kwargs)

    @visit.register
    async def _(self, node: InNode, table: type, **kwargs: Any) -> Any:
        return create_expression(node, In, **kwargs)

    @visit.register
    async def _(self, node: NotInNode, table: type, **kwargs: Any) -> Any:
        return create_expression(node, Nin, **kwargs)


def factory(settings: BackendOptions) -> MongoDbDriver:
    return MongoDbDriver()
