from functools import singledispatchmethod
from typing import Any, Dict, Optional, Type, cast
from winter.backend import QueryDriver
from winter.query.nodes import (
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
from pydantic import BaseModel

from winter.settings import WinterSettings


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

    # This is specific to MongoDb, special handling of _id
    if field_name == "id":
        field_name = "_id"

    return op(field_name, value)


class ExecutionError(Exception):
    pass


class MongoDbDriver(QueryDriver):
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

    def init(self, settings: WinterSettings) -> None:  # type: ignore
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

    async def get_query_repr(
        self, query_expression: RootNode, table_name: str | Type[Any], **kwargs: Any
    ) -> str:
        return await self.query(query_expression, table_name, **kwargs)

    async def run(
        self, query_expression: RootNode, table_name: str | Type[Any], session: Any = None, **kwargs: Any
    ) -> Any:
        return super().run(query_expression, table_name, session=session, **kwargs)

    async def run_async(
        self, query_expression: RootNode, table_name: str | Type[Any], session: Any = None, **kwargs: Any
    ) -> Any:
        return await self.visit(query_expression, table_name, session=session, **kwargs)

    @singledispatchmethod
    async def query(self, node: OpNode, table_name: str | Type[Any], **kwargs: Any) -> str:
        return await self.visit(node, table_name, **kwargs)

    @query.register
    async def _(self, node: Find, table_name: str, **kwargs: Any) -> str:
        if node.filters is not None:
            filters = await self.query(node.filters, table_name, **kwargs) or ""
        else:
            filters = {}  # type: ignore
        return f"db.{table_name}.find({filters}).to_list()"

    @query.register
    async def _(self, node: Delete, table_name: str, **kwargs: Any) -> str:
        if node.filters is not None:
            filters = await self.query(node.filters, table_name, **kwargs) or ""
        else:
            filters = {}  # type: ignore
        return f"db.{table_name}.delete_many({filters})"

    @query.register
    async def _(self, node: Get, table_name: str, **kwargs: Any) -> str:
        filters = await self.query(node.filters, table_name, **kwargs) or ""
        return f"db.{table_name}.find_one({filters})"

    @query.register
    async def _(self, node: Create, table_name: str, **kwargs: Any) -> str:
        entity = kwargs.get("entity", None)
        if entity is None:
            raise ExecutionError("Entity parameter required for create operation")

        if isinstance(entity, BaseModel):
            entity = entity.dict(exclude_unset=True, by_alias=True)

        return f"db.{table_name}.insert_one({entity})"

    @query.register
    async def _(self, node: Update, table_name: str, *, entity: BaseModel) -> str:
        _id = getattr(entity, "id", None)
        if _id is None:
            raise ExecutionError("Entity must have id field")

        return f"db.{table_name}.update_one({{'_id': {_id}}}, {entity.dict(exclude={'id'})})"

    @singledispatchmethod
    async def visit(self, node: OpNode, table_name: str, session: Any = None, **kwargs: Any) -> Any:
        raise NotImplementedError

    @visit.register
    async def _(self, node: Create, table_name: str, session: Any = None, **kwargs: Any) -> Any:
        entity = kwargs.get("entity", None)
        if entity is None:
            raise ExecutionError("Entity parameter required for create operation")

        if isinstance(entity, BaseModel):
            entity = entity.dict(exclude_unset=True, by_alias=True)
        elif not isinstance(entity, dict):
            entity = vars(entity)

        collection = self.db[table_name]
        return await collection.insert_one(entity, session=session) #type: ignore

    @visit.register
    async def _(self, node: Update, table_name: str, *, entity: BaseModel, session: Any = None) -> Any:
        _id = getattr(entity, "id", None)
        if _id is None:
            raise ExecutionError("Entity must have id field")

        collection = self.db[table_name]
        return await collection.update_one(  # type: ignore
            {"_id": _id}, {"$set": entity.dict(exclude_unset=True, exclude={"id"})}, session=session
        )

    @visit.register
    async def _(self, node: Find, table_name: str, session: Any = None, **kwargs: Any) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table_name, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[table_name]

        return await collection.find(filters, session=session).to_list(None)

    @visit.register
    async def _(self, node: Delete, table_name: str, session: Any = None, **kwargs: Any) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table_name, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[table_name]

        return await collection.delete_many(filters, session=session) #type: ignore

    @visit.register
    async def _(self, node: Get, table_name: str, session: Any = None, **kwargs: Any) -> Any:
        if node.filters is not None:
            filters = await self.visit(node.filters, table_name, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[table_name]

        return await collection.find_one(filters, session=session) #type: ignore

    @visit.register
    async def _(self, node: AndNode, table_name: str, **kwargs: Any) -> Any:
        conditions = await self.visit(node.left, table_name, **kwargs)

        # conditions should be a list of tuples name, value where
        # name => FieldName (str)
        # value => comparison condition (dict)
        and_list = [conditions]
        where = {"$and": and_list}

        if node.right is not None:
            right_condition = await self.visit(node.right, table_name, **kwargs)
            if isinstance(node.right, AndNode):
                where["$and"].extend(right_condition["$and"])
            else:
                where["$and"].append(right_condition)

        return where

    @visit.register
    async def _(self, node: OrNode, table_name: str, **kwargs: Any) -> Any:
        or_condition = await self.visit(node.left, table_name, **kwargs)

        # or_condition should be a list of tuples name, value where
        # name => FieldName (str)
        # value => comparison condition (dict)
        or_list = [or_condition]

        where = {"$or": or_list}

        if node.right is not None:
            right_condition = await self.visit(node.right, table_name, **kwargs)
            if isinstance(node.right, OrNode):
                where["$or"].extend(right_condition["$or"])
            else:
                where["$or"].append(right_condition)

        return where

    @visit.register
    async def _(self, node: EqualToNode, table_name: str, **kwargs: Any) -> Any:
        return create_expression(node, Eq, **kwargs)

    @visit.register
    async def _(self, node: NotEqualNode, table_name: str, **kwargs: Any) -> Any:
        return create_expression(node, Ne, **kwargs)

    @visit.register
    async def _(self, node: LowerThanNode, table_name: str, **kwargs: Any) -> Any:
        return create_expression(node, Lt, **kwargs)

    @visit.register
    async def _(self, node: NotLowerThanNode, table_name: str, **kwargs: Any) -> Any:
        return create_expression(node, Notlt, **kwargs)

    @visit.register
    async def _(self, node: GreaterThanNode, table_name: str, **kwargs: Any) -> Any:
        return create_expression(node, Gt, **kwargs)

    @visit.register
    async def _(self, node: NotGreaterThanNode, table_name: str, **kwargs: Any) -> Any:
        return create_expression(node, Notlt, **kwargs)

    @visit.register
    async def _(self, node: InNode, table_name: str, **kwargs: Any) -> Any:
        return create_expression(node, In, **kwargs)

    @visit.register
    async def _(self, node: NotInNode, table_name: str, **kwargs: Any) -> Any:
        return create_expression(node, Nin, **kwargs)


def factory(settings: WinterSettings) -> MongoDbDriver:
    return MongoDbDriver()
