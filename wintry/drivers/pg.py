from dataclasses import fields
from functools import singledispatchmethod
from operator import eq, gt, lt, ne
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    overload,
    Sequence,
    Iterable,
    Iterator,
    Generator,
    Mapping,
    Union,
)

import sqlalchemy.orm as orm
from sqlalchemy import delete, insert, inspect, select, update, Table
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncConnection
from sqlalchemy.orm import Mapper, RelationshipProperty
from sqlalchemy.sql import Delete as DeleteStatement
from sqlalchemy.sql import Insert as InsertStatement
from sqlalchemy.sql import Select
from sqlalchemy.sql import Update as UpdateStatement
from sqlalchemy.sql.expression import TextClause, text
from wintry.backend import QueryDriver
from wintry.models import Model, ModelRegistry
from wintry.query.nodes import (
    AndNode,
    Create,
    Delete,
    EqualToNode,
    FilterNode,
    Find,
    Get,
    GreaterThanNode,
    LowerThanNode,
    NotEqualNode,
    NotGreaterThanNode,
    OpNode,
    OrNode,
    RootNode,
    Update,
)
from wintry.settings import BackendOptions, EngineType
from wintry.utils.model_binding import SQLSelectQuery, load_model, tree_walk_dfs
from wintry.utils.type_helpers import resolve_generic_type_or_die
from wintry.utils.virtual_db_schema import (
    compute_model_insert_values,
    compute_model_related_data_for_insert,
    get_model_sql_table,
    mark_obj_used_by_sql,
    serialize_for_update,
)


class ExecutionError(Exception):
    pass


T = TypeVar("T", bound=Model)
Operator = Callable[[Any, Any], Any]


def get_field_name(field_name: str) -> str | List[str]:
    if "." in field_name:
        return field_name.split(".")
    else:
        return field_name


def get_value_from_args(field_path: str | List[str], **kwargs: Any) -> Any:
    if isinstance(field_path, list):
        field = "__".join(field_path)
        value = kwargs.get(field, None)
    else:
        field = field_path
        value = kwargs.get(field_path, None)

    if value is None:
        raise ExecutionError(f"{field} was not suplied as argument")

    return value


def _operate(
    node: FilterNode, schema: type[Model], op: Operator, **kwargs: Any
) -> Dict[str, Any]:
    table = get_model_sql_table(schema)
    field_path = get_field_name(node.field)
    value = node.value or get_value_from_args(field_path, **kwargs)

    if isinstance(field_path, list):
        # This is a related field
        schema_to_inspect = table
        current_type = schema
        while field_path:
            field = field_path.pop(0)
            # is this the last one ??
            if field_path == []:
                return {"where": op(getattr(schema_to_inspect.c, field), value)}  # type: ignore
            for f in fields(current_type):
                if f.name == field:
                    if isinstance(f.type, str):
                        current_type = eval(
                            f.type, globals() | ModelRegistry.models.copy()
                        )
                    else:
                        current_type = f.type
                    current_type = resolve_generic_type_or_die(current_type)
                    schema_to_inspect = get_model_sql_table(current_type)
        raise ExecutionError("WTF This should not end here")
    else:
        return {"where": op(getattr(table.c, field_path), value)}


class SqlAlchemyDriver(QueryDriver):
    driver_class: EngineType = EngineType.Sql

    def init(self, settings: BackendOptions):  # type: ignore
        if settings.connection_options.url is not None:
            self._engine = create_async_engine(
                url=settings.connection_options.url, future=True
            )
        else:
            host = settings.connection_options.host
            port = settings.connection_options.port
            username = settings.connection_options.user
            password = settings.connection_options.password
            db_name = settings.connection_options.database_name
            connector = settings.connection_options.connector
            url = f"{connector}://{username}:{password}@{host}:{port}/{db_name}"
            self._engine = create_async_engine(url=url, future=True, echo=True)

        session = orm.sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autocommit=False,
            class_=AsyncSession,
        )

        self._sessionmaker: orm.sessionmaker = session

        self._connection: AsyncConnection | None = None

    async def get_connection(self) -> AsyncConnection:
        if self._connection is not None:
            return self._connection
        else:
            return await self._engine.connect()

    async def get_started_session(self) -> AsyncConnection:
        connection: AsyncConnection = await self._engine.connect()
        connection.begin()
        return connection

    async def commit_transaction(self, session: AsyncConnection) -> None:
        await session.commit()

    async def abort_transaction(self, session: AsyncConnection) -> None:
        await session.rollback()

    async def close_session(self, session: AsyncConnection) -> None:
        await session.close()

    async def init_async(self, *args, **kwargs):  # type: ignore
        pass

    def run(self, query_expression: RootNode, table_name: str, session: Any = None, **kwargs):  # type: ignore
        return super().run(query_expression, table_name, session=session, **kwargs)

    async def run_async(
        self,
        query_expression: RootNode,
        table_name: str | Type[Model],
        session: AsyncConnection | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self.visit(query_expression, table_name, session=session, **kwargs)

    async def get_query_repr(
        self, query_expression: RootNode, table_name: str | Type[Model], **kwargs: Any
    ) -> str:
        return await self.query(query_expression, table_name, **kwargs)

    @singledispatchmethod
    async def query(
        self,
        node: OpNode,
        schema: Type[Model],
        session: AsyncConnection | None = None,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError

    @query.register
    async def _(
        self,
        node: Find,
        schema: Type[Model],
        session: AsyncConnection | None = None,
        **kwargs: Any,
    ) -> str:
        sql = SQLSelectQuery()
        tree_walk_dfs(schema, sql, {})
        stmt = sql.render()

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            filters = state.get("where", None)
            if filters is not None:
                stmt = stmt.where(filters)

        return str(stmt)

    @query.register
    async def _(
        self,
        node: Get,
        schema: Type[Model],
        session: AsyncConnection | None = None,
        **kwargs: Any,
    ) -> str:
        sql = SQLSelectQuery()
        tree_walk_dfs(schema, sql, {})
        stmt = sql.render()

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            filters = state.get("where", None)
            if filters is not None:
                stmt = stmt.where(filters)

        return str(stmt)

    @query.register
    async def _(
        self,
        node: Delete,
        schema: Type[Model],
        session: AsyncConnection | None = None,
        **kwargs: Any,
    ) -> str:
        table = get_model_sql_table(schema)
        stmt: DeleteStatement = delete(table)

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            filters = state.get("where", None)
            if filters is not None:
                stmt = stmt.where(filters)  # type: ignore

        return str(stmt)

    @query.register
    async def _(
        self,
        node: Update,
        schema: Type[Model],
        *,
        entity: Model,
        session: AsyncConnection | None = None,
    ) -> str:
        table = get_model_sql_table(schema)
        pks = entity.ids()
        if not pks:
            raise ExecutionError("Entity must have an id field")
        data = serialize_for_update(entity)

        stmt: UpdateStatement = update(table)
        stmt = stmt.filter_by(**pks).values(data)
        return str(stmt)

    @query.register
    async def _(
        self,
        node: Create,
        schema: Type[Model],
        *,
        entity: Model,
        session: AsyncConnection | None = None,
    ) -> str:
        table = get_model_sql_table(schema)
        stmt: InsertStatement = insert(table)
        data = compute_model_insert_values(entity)
        stmt = stmt.values(**data)  # type: ignore

        return str(stmt)

    @singledispatchmethod
    async def visit(self, node: OpNode, schema: Type[Model], session: AsyncConnection | None = None, **kwargs: Any):  # type: ignore
        raise NotImplementedError

    @visit.register
    async def _(
        self, node: Find, schema: Type[Model], session: Any = None, **kwargs: Any
    ) -> List[Model]:

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            filters = state.get("where", None)
        else:
            filters = None

        if session is not None:
            return await load_model(schema, session, filters)
        else:
            async with self._engine.connect() as conn:
                return await load_model(schema, conn, filters)

    @visit.register
    async def _(
        self,
        node: Get,
        schema: Type[Model],
        session: AsyncConnection | None = None,
        **kwargs: Any,
    ) -> Model | None:

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            filters = state.get("where", None)
        else:
            filters = None

        if session is not None:
            results = await load_model(schema, session, filters)
            return results[0] if results else None
        else:
            async with self._engine.connect() as conn:
                results = await load_model(schema, conn, filters)
                return results[0] if results else None

    @visit.register
    async def _(
        self,
        node: Update,
        schema: Type[Model],
        *,
        entity: Model,
        session: AsyncConnection | None = None,
    ) -> None:
        table = get_model_sql_table(schema)
        pks = entity.ids()
        if not pks:
            raise ExecutionError("Entity must have id field")

        data = serialize_for_update(entity)

        stmt: UpdateStatement = update(table)
        stmt = stmt.filter_by(**pks).values(data)

        if session is not None:
            await session.execute(stmt)
        else:
            async with self._engine.connect() as conn:
                await conn.execute(stmt)
                await conn.commit()

    @visit.register
    async def _(
        self,
        node: Create,
        schema: Type[Model],
        *,
        entity: Model,
        session: AsyncConnection | None = None,
    ):
        for t, data in compute_model_related_data_for_insert(entity):
            stmt: InsertStatement = insert(t).values(**data)  # type: ignore

            if session is not None:
                await session.execute(stmt)
            else:
                async with self._engine.connect() as conn:
                    await conn.execute(stmt)
                    await conn.commit()

        mark_obj_used_by_sql(entity)
        return entity

    @visit.register
    async def _(
        self,
        node: Delete,
        schema: Type[Model],
        session: AsyncConnection | None = None,
        **kwargs: Any,
    ) -> None:
        table = get_model_sql_table(schema)
        stmt: DeleteStatement = delete(table)

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            filters = state.get("where", None)
            if filters is not None:
                stmt = stmt.where(filters)  # type: ignore

        if session is not None:
            await session.execute(stmt)
        else:
            async with self._engine.connect() as conn:
                await conn.execute(stmt)
                await conn.commit()

    @visit.register
    async def _(
        self, node: AndNode, schema: Type[Model], **kwargs: Any
    ) -> Dict[str, Any]:
        state = {}
        left = await self.visit(node.left, schema, **kwargs)

        if node.right is not None:
            right = await self.visit(node.right, schema, **kwargs)
            state["where"] = left["where"] & right["where"]
            return state
        else:
            return left

    @visit.register
    async def _(self, node: OrNode, schema: Type[Model], **kwargs: Any) -> Dict[str, Any]:
        state = {}
        left = await self.visit(node.left, schema, **kwargs)

        if node.right is not None:
            right = await self.visit(node.right, schema, **kwargs)
            state["where"] = left["where"] | right["where"]
            return state
        else:
            return left

    @visit.register
    async def _(
        self, node: EqualToNode, schema: Type[Model], **kwargs: Any
    ) -> Dict[str, Any]:
        return _operate(node, schema, eq, **kwargs)

    @visit.register
    async def _(
        self, node: NotEqualNode, schema: Type[Model], **kwargs: Any
    ) -> Dict[str, Any]:
        return _operate(node, schema, ne, **kwargs)

    @visit.register
    async def _(
        self, node: GreaterThanNode, schema: Type[Model], **kwargs: Any
    ) -> Dict[str, Any]:
        return _operate(node, schema, gt, **kwargs)

    @visit.register
    async def _(
        self, node: LowerThanNode, schema: Type[Model], **kwargs: Any
    ) -> Dict[str, Any]:
        return _operate(node, schema, lt, **kwargs)


def factory(settings: BackendOptions) -> SqlAlchemyDriver:
    return SqlAlchemyDriver()
