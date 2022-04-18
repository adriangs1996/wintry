from functools import singledispatchmethod
from platform import node
from typing import Optional
from winter.backend import QueryDriver
from winter.query.nodes import (
    AndNode,
    Create,
    Delete,
    EqualToNode,
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
from pydantic import BaseModel


def Eq(field, value):
    return {field: {"$eq": value}}


def Lt(field, value):
    return {field: {"$lt": value}}


def Gt(field, value):
    return {field: {"$gt": value}}


def Lte(field, value):
    return {field: {"$lte": value}}


def Gte(field, value):
    return {field: {"$gte": value}}


def In(field, value):
    return {field: {"$in": value}}


def Nin(field, value):
    return {field: {"$nin": value}}


def Ne(field, value):
    return {field: {"$ne": value}}


def NotGt(field, value):
    return {field: {"$not": {"$gt": value}}}


def Notlt(field, value):
    return {field: {"$not": {"$lt": value}}}


def create_expression(node, op, **kwargs):
    field_name = node.field
    value = kwargs.get(field_name, None)
    if value is None:
        raise ExecutionError(f"{field_name} was not suplied as argument")

    # This is specific to MongoDb, special handling of _id
    if field_name == "id":
        field_name = "_id"

    return op(field_name, value)


class ExecutionError(Exception):
    pass


class MongoDbDriver(QueryDriver):
    def init(
        self,
        url: Optional[str] = None,
        host: str = "localhost",
        port: int = 27017,
        database_name: str = "tests",
    ):
        if url is not None:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(url)
        else:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(host, port)

        self.db = self.client[database_name]

    async def init_async(self, *args, **kwargs):
        pass

    async def get_query_repr(
        self, query_expression: RootNode, table_name: str, **kwargs
    ):
        return await self.query(query_expression, table_name, **kwargs)

    async def run(self, query_expression: RootNode, table_name: str, **kwargs):
        return super().run(query_expression, table_name, **kwargs)

    async def run_async(self, query_expression: RootNode, table_name: str, **kwargs):
        return await self.visit(query_expression, table_name, **kwargs)

    @singledispatchmethod
    async def query(self, node: OpNode, table_name: str, **kwargs):
        return await self.visit(node, table_name, **kwargs)

    @query.register
    async def _(self, node: Find, table_name: str, **kwargs):
        if node.filters is not None:
            filters = await self.query(node.filters, table_name, **kwargs) or ""
        else:
            filters = {}
        return f"db.{table_name}.find({filters}).to_list()"

    @query.register
    async def _(self, node: Delete, table_name: str, **kwargs):
        if node.filters is not None:
            filters = await self.query(node.filters, table_name, **kwargs) or ""
        else:
            filters = {}
        return f"db.{table_name}.delete_many({filters})"

    @query.register
    async def _(self, node: Get, table_name: str, **kwargs):
        filters = await self.query(node.filters, table_name, **kwargs) or ""
        return f"db.{table_name}.find_one({filters})"

    @query.register
    async def _(self, node: Create, table_name: str, **kwargs):
        entity = kwargs.get("entity", None)
        if entity is None:
            raise ExecutionError("Entity parameter required for create operation")

        if isinstance(entity, BaseModel):
            entity = entity.dict(exclude_unset=True, by_alias=True)

        return f"db.{table_name}.insert_one({entity})"

    @query.register
    async def _(self, node: Update, table_name: str, *, entity: BaseModel):
        _id = getattr(entity, "id", None)
        if _id is None:
            raise ExecutionError("Entity must have id field")

        return f"db.{table_name}.update_one({{'_id': {_id}}}, {entity.dict(exclude={'id'})})"

    @singledispatchmethod
    async def visit(self, node: OpNode, table_name: str, **kwargs):
        raise NotImplementedError

    @visit.register
    async def _(self, node: Create, table_name: str, **kwargs):
        entity = kwargs.get("entity", None)
        if entity is None:
            raise ExecutionError("Entity parameter required for create operation")

        collection = self.db[table_name]
        return await collection.insert_one(entity)

    @visit.register
    async def _(self, node: Update, table_name: str, **kwargs):
        _id = kwargs.pop("_id", None) or kwargs.pop("id", None)
        if _id is None:
            raise ExecutionError("Must supply id to update")

        collection = self.db[table_name]
        return await collection.update_one({"_id": _id}, kwargs)

    @visit.register
    async def _(self, node: Find, table_name: str, **kwargs):
        if node.filters is not None:
            filters = await self.visit(node.filters, table_name, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[table_name]

        return await collection.find(filters).to_list(None)

    @visit.register
    async def _(self, node: Delete, table_name: str, **kwargs):
        if node.filters is not None:
            filters = await self.visit(node.filters, table_name, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[table_name]

        return await collection.delete_many(filters)

    @visit.register
    async def _(self, node: Get, table_name: str, **kwargs):
        if node.filters is not None:
            filters = await self.visit(node.filters, table_name, **kwargs) or {}
        else:
            filters = {}
        collection = self.db[table_name]

        return await collection.find_one(filters)

    @visit.register
    async def _(self, node: AndNode, table_name: str, **kwargs):
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
    async def _(self, node: OrNode, table_name: str, **kwargs):
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
    async def _(self, node: EqualToNode, table_name: str, **kwargs):
        return create_expression(node, Eq, **kwargs)

    @visit.register
    async def _(self, node: NotEqualNode, table_name: str, **kwargs):
        return create_expression(node, Ne, **kwargs)

    @visit.register
    async def _(self, node: LowerThanNode, table_name: str, **kwargs):
        return create_expression(node, Lt, **kwargs)

    @visit.register
    async def _(self, node: NotLowerThanNode, table_name: str, **kwargs):
        return create_expression(node, Notlt, **kwargs)

    @visit.register
    async def _(self, node: GreaterThanNode, table_name: str, **kwargs):
        return create_expression(node, Gt, **kwargs)

    @visit.register
    async def _(self, node: NotGreaterThanNode, table_name: str, **kwargs):
        return create_expression(node, Notlt, **kwargs)

    @visit.register
    async def _(self, node: InNode, table_name: str, **kwargs):
        return create_expression(node, In, **kwargs)

    @visit.register
    async def _(self, node: NotInNode, table_name: str, **kwargs):
        return create_expression(node, Nin, **kwargs)
