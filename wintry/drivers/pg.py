from functools import singledispatchmethod
from operator import eq, gt, lt, ne
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, overload
from wintry.backend import QueryDriver
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.engine.result import Result
import sqlalchemy.orm as orm
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
from sqlalchemy import select, update, delete, inspect, insert
from sqlalchemy.sql import (
    Select,
    Update as UpdateStatement,
    Delete as DeleteStatement,
    Insert as InsertStatement,
)
from sqlalchemy.orm import Mapper, RelationshipProperty
from dataclass_wizard import asdict
from dataclasses import is_dataclass


class ExecutionError(Exception):
    pass


T = TypeVar("T")
Operator = Callable[[Any, Any], Any]


@overload
def _apply(stmt: Select, state: Dict[str, Any]) -> Select:
    ...


@overload
def _apply(stmt: DeleteStatement, state: Dict[str, Any]) -> DeleteStatement:  # type: ignore
    ...


def _apply(
    stmt: Select | DeleteStatement, state: Dict[str, Any]
) -> Select | DeleteStatement:
    new_stmt = stmt
    if (conditions := state.get("where", None)) is not None:
        new_stmt = new_stmt.where(conditions)

    if (joins := state.get("joins", None)) is not None and isinstance(new_stmt, Select):
        for table in joins:
            new_stmt = new_stmt.join(table)

    assert new_stmt is not None
    return new_stmt


def _resolve_joins(schema_to_inspect: Type[Any], field: str, joins: List[Any]) -> Any:
    mapper: Mapper = inspect(schema_to_inspect)
    relationships: List[RelationshipProperty] = list(mapper.relationships)
    schema_to_inspect = next(
        filter(lambda p: p.key == field, relationships)
    ).entity.mapped_table
    joins.append(schema_to_inspect)
    return schema_to_inspect


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
    node: FilterNode, schema: Type[Any], op: Operator, **kwargs: Any
) -> Dict[str, Any]:
    field_path = get_field_name(node.field)
    value = get_value_from_args(field_path, **kwargs)
    joins: List[Any] = []

    if isinstance(field_path, list):
        # This is a related field
        schema_to_inspect = schema
        while field_path:
            field = field_path.pop(0)
            # is this the last one ??
            if field_path == []:
                return {"where": op(getattr(schema_to_inspect.c, field), value), "joins": joins}  # type: ignore
            else:
                schema_to_inspect = _resolve_joins(schema_to_inspect, field, joins)
        raise ExecutionError("WTF This should not end here")
    else:
        return {"where": op(getattr(schema, field_path), value), "joins": joins}


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
            self._engine = create_async_engine(url=url, future=True)

        session = orm.sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autocommit=False,
            class_=AsyncSession,
        )

        self._sessionmaker: orm.sessionmaker = session

        self._session: Optional[AsyncSession] = None

    def get_connection(self) -> Any:
        if self._session is not None:
            return self._session
        else:
            return self._sessionmaker()

    async def get_started_session(self) -> AsyncSession:
        session: AsyncSession = self._sessionmaker()
        session.begin()
        return session

    async def commit_transaction(self, session: AsyncSession) -> None:
        if session.in_transaction():
            await session.commit()

    async def abort_transaction(self, session: AsyncSession) -> None:
        if session.in_transaction():
            await session.rollback()

    async def close_session(self, session: AsyncSession) -> None:
        if session.in_transaction():
            await session.close()

    async def init_async(self, *args, **kwargs):  # type: ignore
        pass

    def run(self, query_expression: RootNode, table_name: str, session: Any = None, **kwargs):  # type: ignore
        return super().run(query_expression, table_name, session=session, **kwargs)

    async def run_async(
        self,
        query_expression: RootNode,
        table_name: str | Type[Any],
        session: Any = None,
        **kwargs: Any,
    ) -> Any:
        return await self.visit(query_expression, table_name, session=session, **kwargs)

    async def get_query_repr(
        self, query_expression: RootNode, table_name: str | Type[Any], **kwargs: Any
    ) -> str:
        return await self.query(query_expression, table_name, **kwargs)

    @singledispatchmethod
    async def query(
        self, node: OpNode, schema: Type[Any], session: Any = None, **kwargs: Any
    ) -> str:
        raise NotImplementedError

    @query.register
    async def _(
        self, node: Find, schema: Type[Any], session: Any = None, **kwargs: Any
    ) -> str:
        stmt: Select = select(schema)

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            stmt = _apply(stmt, state)

        return str(stmt)

    @query.register
    async def _(
        self, node: Get, schema: Type[Any], session: Any = None, **kwargs: Any
    ) -> str:
        stmt: Select = select(schema)

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            stmt = _apply(stmt, state)

        return str(stmt)

    @query.register
    async def _(
        self, node: Delete, schema: Type[Any], session: Any = None, **kwargs: Any
    ) -> str:
        stmt: DeleteStatement = delete(schema)
        stmt = stmt.execution_options(synchronize_session=False)

        if node.filters is not None:
            state = await self.visit(node, schema, **kwargs)
            stmt = _apply(stmt, state)

        return str(stmt)

    @query.register
    async def _(
        self, node: Update, schema: Type[Any], *, entity: Any, session: Any = None
    ) -> str:
        if not is_dataclass(entity):
            raise ExecutionError("Entity must be a dataclass")

        _id = getattr(entity, "id", None)
        if _id is None:
            raise ExecutionError("Entity must have an id field")

        stmt: UpdateStatement = update(schema)
        stmt = (
            stmt.filter_by(id=_id)
            .values(**asdict(entity, exclude=["id"]))
            .execution_options(synchronize_session=False)
        )
        return str(stmt)

    @query.register
    async def _(
        self, node: Create, schema: Type[Any], *, entity: Any, session: Any = None
    ) -> str:
        if not is_dataclass(entity):
            raise ExecutionError("Entity must be a dataclass")

        stmt: InsertStatement = insert(schema)
        stmt = stmt.values(**asdict(entity))  # type: ignore

        return str(stmt)

    @singledispatchmethod
    async def visit(self, node: OpNode, schema: Type[Any], session: Any = None, **kwargs: Any):  # type: ignore
        raise NotImplementedError

    @visit.register
    async def _(
        self, node: Find, schema: Type[T], session: Any = None, **kwargs: Any
    ) -> List[T]:
        stmt: Select = select(schema)

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            stmt = _apply(stmt, state)

        if session is not None:
            result: Result = await session.execute(stmt)
            return result.scalars().unique().all()
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    fresh_result: Result = await _session.execute(stmt)
                    return fresh_result.scalars().unique().all()

    @visit.register
    async def _(
        self, node: Get, schema: Type[T], session: Any = None, **kwargs: Any
    ) -> T | None:
        stmt: Select = select(schema)

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            stmt = _apply(stmt, state)

        if session is not None:
            result: Result = await session.execute(stmt)
            return result.unique().scalar_one_or_none()
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    fresh_result: Result = await _session.execute(stmt)
                    return fresh_result.unique().scalar_one_or_none()

    @visit.register
    async def _(
        self, node: Update, schema: Type[Any], *, entity: Any, session: Any = None
    ) -> None:
        if not is_dataclass(entity):
            raise ExecutionError("Entity must be a dataclass")

        _id = getattr(entity, "id", None)
        if _id is None:
            raise ExecutionError("Entity must have id field")

        stmt: UpdateStatement = update(schema)
        stmt = (
            stmt.filter_by(id=_id)
            .values(**asdict(entity, exclude=["id"], skip_defaults=True))
            .execution_options(synchronize_session=False)
        )

        if session is not None:
            await session.execute(stmt)
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    await _session.execute(stmt)

    @visit.register
    async def _(
        self,
        node: Create,
        schema: Type[Any],
        *,
        entity: Any,
        session: AsyncSession | None = None,
    ) -> None:
        if not is_dataclass(entity):
            raise ExecutionError("Entity must be a dataclass")

        if session is not None:
            session.add(entity)
        else:
            async with self._sessionmaker() as __session:
                _session: AsyncSession = __session
                async with _session.begin():
                    _session.add(entity)

        return entity

    @visit.register
    async def _(
        self, node: Delete, schema: Type[Any], session: Any = None, **kwargs: Any
    ) -> None:
        stmt: DeleteStatement = delete(schema)
        stmt = stmt.execution_options(synchronize_session=False)

        if node.filters is not None:
            state = await self.visit(node.filters, schema, **kwargs)
            stmt = _apply(stmt, state)

        if session is not None:
            await session.execute(stmt)
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    await _session.execute(stmt)

    @visit.register
    async def _(self, node: AndNode, schema: Type[Any], **kwargs: Any) -> Dict[str, Any]:
        state = {}
        left = await self.visit(node.left, schema, **kwargs)

        if node.right is not None:
            right = await self.visit(node.right, schema, **kwargs)
            state["where"] = left["where"] & right["where"]
            state["joins"] = left["joins"] + right["joins"]
            return state
        else:
            return left

    @visit.register
    async def _(self, node: OrNode, schema: Type[Any], **kwargs: Any) -> Dict[str, Any]:
        state = {}
        left = await self.visit(node.left, schema, **kwargs)

        if node.right is not None:
            right = await self.visit(node.right, schema, **kwargs)
            state["where"] = left["where"] | right["where"]
            state["joins"] = left["joins"] + right["joins"]
            return state
        else:
            return left

    @visit.register
    async def _(
        self, node: EqualToNode, schema: Type[Any], **kwargs: Any
    ) -> Dict[str, Any]:
        return _operate(node, schema, eq, **kwargs)

    @visit.register
    async def _(
        self, node: NotEqualNode, schema: Type[Any], **kwargs: Any
    ) -> Dict[str, Any]:
        return _operate(node, schema, ne, **kwargs)

    @visit.register
    async def _(
        self, node: GreaterThanNode, schema: Type[Any], **kwargs: Any
    ) -> Dict[str, Any]:
        return _operate(node, schema, gt, **kwargs)

    @visit.register
    async def _(
        self, node: LowerThanNode, schema: Type[Any], **kwargs: Any
    ) -> Dict[str, Any]:
        return _operate(node, schema, lt, **kwargs)


def factory(settings: BackendOptions) -> SqlAlchemyDriver:
    return SqlAlchemyDriver()
