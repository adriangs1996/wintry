from functools import singledispatchmethod
from typing import Any, List, Optional, Type, TypeVar
from winter.backend import QueryDriver
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncResult
import sqlalchemy.orm as orm
from winter.query.nodes import AndNode, Delete, EqualToNode, Find, Get, OpNode, OrNode, RootNode, Update
from pydantic import BaseModel
from winter.settings import WinterSettings
from sqlalchemy import select, update, delete, inspect
from sqlalchemy.sql import Select, Update as UpdateStatement, Delete as DeleteStatement
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.orm import Mapper, RelationshipProperty


class ExecutionError(Exception):
    pass


T = TypeVar("T")


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


class PostgresqlDriver(QueryDriver):
    def init(self, settings: WinterSettings):  # type: ignore
        if settings.connection_options.url is not None:
            engine = create_async_engine(url=settings.connection_options.url, future=True)
        else:
            host = settings.connection_options.host
            port = settings.connection_options.port
            username = settings.connection_options.user
            password = settings.connection_options.password
            db_name = settings.connection_options.database_name
            url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{db_name}"
            engine = create_async_engine(url=url, future=True)

        session = orm.sessionmaker(bind=engine, expire_on_commit=False, autocommit=False, class_=AsyncSession)

        self._sessionmaker: orm.sessionmaker = session

        self._session: Optional[AsyncSession] = None

    def get_connection(self) -> Any:
        if self._session is not None:
            return self._session
        else:
            return self._sessionmaker()

    async def init_async(self, *args, **kwargs):  # type: ignore
        pass

    def run(self, query_expression: RootNode, table_name: str, **kwargs):  # type: ignore
        return super().run(query_expression, table_name, **kwargs)

    @singledispatchmethod
    async def visit(self, node: OpNode, schema: Type[Any], **kwargs):  # type: ignore
        raise NotImplementedError

    @visit.register
    async def _(self, node: Find, schema: Type[T], **kwargs: Any) -> List[T]:
        stmt: Select = select(schema)

        if node.filters is not None:
            conditions = await self.visit(node.filters, schema, stmt, **kwargs)
            stmt = stmt.where(conditions)

        if self._session is not None:
            result: AsyncResult = await self._session.execute(stmt)
            return result.scalars().all()
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    fresh_result: AsyncResult = await _session.execute(stmt)
                    return fresh_result.scalars().all()

    @visit.register
    async def _(self, node: Get, schema: Type[T], **kwargs: Any) -> T | None:
        stmt: Select = select(schema)

        if node.filters is not None:
            conditions = await self.visit(node.filters, schema, stmt, **kwargs)
            stmt = stmt.where(conditions)

        if self._session is not None:
            result: AsyncResult = await self._session.execute(stmt)
            return await result.scalar_one_or_none()
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    fresh_result: AsyncResult = await _session.execute(stmt)
                    return await fresh_result.scalar_one_or_none()

    @visit.register
    async def _(self, node: Update, schema: Type[T], *, entity: BaseModel) -> None:
        _id = getattr(entity, "id", None)
        if _id is None:
            raise ExecutionError("Entity must have id field")

        stmt: UpdateStatement = update(schema)
        stmt = (
            stmt.filter_by(id=_id)
            .values(**entity.dict(exclude={"id"}, exclude_unset=True))
            .execution_options(synchronize_session=False)
        )

        if self._session is not None:
            await self._session.execute(stmt)
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    await _session.execute(stmt)

    @visit.register
    async def _(self, node: Delete, schema: Type[T], **kwargs: Any) -> None:
        stmt: DeleteStatement = delete(schema)
        stmt = stmt.execution_options(synchronize_session=False)

        if node.filters is not None:
            conditions = await self.visit(node, schema, stmt, **kwargs)
            stmt = stmt.where(conditions)  # type: ignore

        if self._session is not None:
            await self._session.execute(stmt)
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    await _session.execute(stmt)

    @visit.register
    async def _(
        self, node: AndNode, schema: Type[T], stmt: Select | UpdateStatement, **kwargs: Any
    ) -> BinaryExpression:
        left = await self.visit(node.left, schema, stmt, **kwargs)

        if node.right is not None:
            right = await self.visit(node.right, schema, stmt, **kwargs)
            return (left) & (right)
        else:
            return left

    @visit.register
    async def _(
        self, node: OrNode, schema: Type[T], stmt: Select | UpdateStatement, **kwargs: Any
    ) -> BinaryExpression:
        left = await self.visit(node.left, schema, stmt, **kwargs)

        if node.right is not None:
            right = await self.visit(node.right, schema, stmt, **kwargs)
            return (left) | (right)
        else:
            return left

    @visit.register
    async def _(
        self, node: EqualToNode, schema: Type[T], stmt: Select | UpdateStatement, **kwargs: Any
    ) -> BinaryExpression:
        field_path = get_field_name(node.field)
        value = get_value_from_args(field_path, **kwargs)

        self._stmt = stmt

        if isinstance(field_path, list):
            assert isinstance(self._stmt, Select)
            # This is a related field
            schema_to_inspect = schema
            while field_path:
                field = field_path.pop(0)
                # is this the last one ??
                if field_path is None:
                    return getattr(schema_to_inspect, field) == value
                else:
                    mapper: Mapper = inspect(schema)
                    relationships: List[RelationshipProperty] = list(mapper.relationships)
                    schema_to_inspect = next(filter(lambda p: p.key == field, relationships)).entity
                    self._stmt = self._stmt.join(schema_to_inspect)
            raise ExecutionError("WTF This should not end here")
        else:
            return getattr(schema, field_path) == value
