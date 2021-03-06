from functools import singledispatchmethod
from typing import Any, Dict, Type, cast
from wintry.backend import QueryDriver
from wintry.models import Model
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
from dataclass_wizard import fromdict
from wintry.utils.keys import __winter_model_collection_name__


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


def get_field_from_args(expected_name: str, kwargs: dict[str, Any]):
    """Resolve a field name from kwargs. The thing is that we use _ as
    separator for parsing, but in python, default naming convention
    is snake_case, so we must do some field preprocessing for supporting this
    """
    # normal case: field name is exactly contained in kwargs
    if expected_name in kwargs:
        return expected_name, kwargs.get(expected_name)

    # ok, field name is not exactly in kwargs, but we might
    # have a compressed version. For example, we want to match
    # issystem with is_system and composed fields as
    # user__address__streetname with user__address__street_name.

    # The examples reveals that simply compressing args is not enough.
    # We need to maintain the __, so we first replace __ with a dummy ($),
    # then compress, and finally replace the dummy with __ again
    def compress(arg: str):
        arg_with_dummy = arg.replace("__", "$")
        arg_compressed_with_dummy = arg_with_dummy.replace("_", "")
        return arg_compressed_with_dummy.replace("$", "__")

    args = zip(
        tuple(map(compress, kwargs.keys())), tuple(kwargs.values()), tuple(kwargs.keys())
    )
    for field, value, original_field_name in args:
        if expected_name == field:
            return original_field_name, value

    raise ExecutionError(f"{expected_name} was not suplied as argument")


def create_expression(node: FilterNode, op: Any, **kwargs: Any) -> Any:
    field_name = node.field
    if "." in field_name:
        value_query = "__".join(field_name.split("."))
    else:
        value_query = field_name
    field_name, value = get_field_from_args(value_query, kwargs)
    field_name = field_name.replace("__", ".")
    if value is None:
        raise ExecutionError(f"{field_name} was not suplied as argument")

    return op(field_name, value)


class DriverMappingError(Exception):
    pass


def get_tablename(cls: type) -> str:
    return getattr(cls, __winter_model_collection_name__, cls.__name__.lower() + "s")


def map_to_table(cls: type[Model], instance: dict):
    if instance is None:
        return None

    return cls.build(instance)


class ExecutionError(Exception):
    pass


class MongoDbDriver(QueryDriver):
    driver_class: EngineType = EngineType.NoSql

    async def get_connection(self) -> Any:
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
                Client,
                motor.motor_asyncio.AsyncIOMotorClient(settings.connection_options.url),
            )
        else:
            host = settings.connection_options.host
            port = settings.connection_options.port
            self.client = cast(Client, motor.motor_asyncio.AsyncIOMotorClient(host, port))

        database_name = settings.connection_options.database_name
        self.db = self.client[database_name]

    async def init_async(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def get_query_repr(
        self, query_expression: RootNode, table: type[Model], **kwargs: Any
    ) -> str:
        return await self.query(query_expression, table, **kwargs)

    async def run(
        self,
        query_expression: RootNode,
        table: type[Model],
        session: Any = None,
        **kwargs: Any,
    ) -> Any:
        return super().run(query_expression, table, session=session, **kwargs)

    async def run_async(
        self,
        query_expression: RootNode,
        table: type[Model],
        session: Any = None,
        **kwargs: Any,
    ) -> Any:
        return await self.visit(query_expression, table, session=session, **kwargs)

    @singledispatchmethod
    async def query(
        self, node: OpNode, table: type[Model], session: Any = None, **kwargs: Any
    ) -> str:
        return await self.visit(node, table, **kwargs)

    @query.register
    async def _(
        self, node: Find, table: type[Model], session: Any = None, **kwargs: Any
    ) -> str:
        if node.filters is not None:
            filters = await self.query(node.filters, table, **kwargs) or ""
        else:
            filters = {}  # type: ignore
        return f"db.{get_tablename(table)}.find({filters}).to_list()"

    @query.register
    async def _(
        self, node: Delete, table: type[Model], session: Any = None, **kwargs: Any
    ) -> str:
        if node.filters is not None:
            filters = await self.query(node.filters, table, **kwargs) or ""
        else:
            filters = {}  # type: ignore
        return f"db.{get_tablename(table)}.delete_many({filters})"

    @query.register
    async def _(
        self, node: Get, table: type[Model], session: Any = None, **kwargs: Any
    ) -> str:
        filters = await self.query(node.filters, table, **kwargs) or ""
        return f"db.{get_tablename(table)}.find_one({filters})"

    @query.register
    async def _(
        self, node: Create, table: type[Model], *, entity: Model, session: Any = None
    ) -> str:

        data = entity.to_dict()

        return f"db.{get_tablename(table)}.insert_one({data})"

    @query.register
    async def _(
        self, node: Update, table: type[Model], *, entity: Model, session: Any = None
    ) -> str:
        pks = entity.ids()
        if not pks:
            raise ExecutionError(f"There is not id configured for {entity}")

        data = entity.to_dict()

        return f"db.{get_tablename(table)}.update_one({pks}, {data})"

    @singledispatchmethod
    async def visit(
        self, node: OpNode, table: type[Model], session: Any = None, **kwargs: Any
    ) -> Any:
        raise NotImplementedError

    @visit.register
    async def _(
        self, node: Create, table: type[Model], *, entity: Model, session: Any = None
    ) -> Any:
        if entity is None:
            raise ExecutionError("Entity parameter required for create operation")

        data = entity.to_dict()

        collection = self.db[get_tablename(table)]
        await collection.insert_one(data, session=session)  # type: ignore
        return entity

    @visit.register
    async def _(
        self, node: Update, table: type[Model], *, entity: Model, session: Any = None
    ) -> Any:
        pks = entity.ids()
        if not pks:
            raise Exception(f"There is not id configured for {entity}")
        data = entity.to_dict()

        collection = self.db[get_tablename(table)]
        await collection.update_one(pks, {"$set": data}, session=session)  # type: ignore

    @visit.register
    async def _(
        self, node: Find, table: type[Model], session: Any = None, **kwargs: Any
    ) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[get_tablename(table)]

        documents = await collection.find(filters, session=session).to_list(None)
        return [map_to_table(table, doc) for doc in documents]

    @visit.register
    async def _(
        self, node: Delete, table: type[Model], session: Any = None, **kwargs: Any
    ) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[get_tablename(table)]

        await collection.delete_many(filters, session=session)  # type: ignore

    @visit.register
    async def _(
        self, node: Get, table: type[Model], session: Any = None, **kwargs: Any
    ) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[get_tablename(table)]

        documents = await collection.find_one(filters, session=session)  # type: ignore
        return map_to_table(table, documents)

    @visit.register
    async def _(self, node: AndNode, table: type[Model], **kwargs: Any) -> Any:
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
    async def _(self, node: OrNode, table: type[Model], **kwargs: Any) -> Any:
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
    async def _(self, node: EqualToNode, table: type[Model], **kwargs: Any) -> Any:
        return create_expression(node, Eq, **kwargs)

    @visit.register
    async def _(self, node: NotEqualNode, table: type[Model], **kwargs: Any) -> Any:
        return create_expression(node, Ne, **kwargs)

    @visit.register
    async def _(self, node: LowerThanNode, table: type[Model], **kwargs: Any) -> Any:
        return create_expression(node, Lt, **kwargs)

    @visit.register
    async def _(self, node: NotLowerThanNode, table: type[Model], **kwargs: Any) -> Any:
        return create_expression(node, Notlt, **kwargs)

    @visit.register
    async def _(self, node: GreaterThanNode, table: type[Model], **kwargs: Any) -> Any:
        return create_expression(node, Gt, **kwargs)

    @visit.register
    async def _(self, node: NotGreaterThanNode, table: type[Model], **kwargs: Any) -> Any:
        return create_expression(node, Notlt, **kwargs)

    @visit.register
    async def _(self, node: InNode, table: type[Model], **kwargs: Any) -> Any:
        return create_expression(node, In, **kwargs)

    @visit.register
    async def _(self, node: NotInNode, table: type[Model], **kwargs: Any) -> Any:
        return create_expression(node, Nin, **kwargs)


def factory(settings: BackendOptions) -> MongoDbDriver:
    return MongoDbDriver()
