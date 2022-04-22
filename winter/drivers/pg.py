from functools import singledispatchmethod
from operator import and_, or_
from turtle import st
from typing import Any, Optional, Type
from winter.backend import QueryDriver
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncResult
import sqlalchemy.orm as orm
from winter.query.nodes import Delete, Find, Get, OpNode, RootNode, Update
from pydantic import BaseModel
from winter.settings import WinterSettings
from sqlalchemy import select, update, delete, or_, and_, Column
from sqlalchemy.sql import Select, Update as UpdateStatement, Delete as DeleteStatement


class ExecutionError(Exception):
    pass


class PostgresqlDriver(QueryDriver):
    def init(self, settings: WinterSettings):
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

    async def init_async(self, *args, **kwargs):
        pass

    def run(self, query_expression: RootNode, table_name: str, **kwargs):
        return super().run(query_expression, table_name, **kwargs)

    @singledispatchmethod
    async def visit(self, node: OpNode, schema: Type[BaseModel], **kwargs):
        raise NotImplementedError

    @visit.register
    async def _(self, node: Find, schema: Type[BaseModel], **kwargs):
        stmt: Select = select(schema)

        if node.filters is not None:
            stmt = await self.visit(node.filters, stmt, **kwargs)

        if self._session is not None:
            result: AsyncResult = await self._session.execute(stmt)
            return result.scalars().all()
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    result: AsyncResult = await _session.execute(stmt)
                    return result.scalars().all()

    @visit.register
    async def _(self, node: Get, schema: Type[BaseModel], **kwargs):
        stmt: Select = select(schema)

        if node.filters is not None:
            stmt = await self.visit(node.filters, stmt, **kwargs)

        if self._session is not None:
            result: AsyncResult = await self._session.execute(stmt)
            return result.scalar_one_or_none()
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    result: AsyncResult = await _session.execute(stmt)
                    return result.scalar_one_or_none()

    @visit.register
    async def _(self, node: Update, schema: Type[BaseModel], *, entity: BaseModel):
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
    async def _(self, node: Delete, schema: Type[BaseModel], **kwargs):
        stmt: DeleteStatement = delete(schema)
        stmt = stmt.execution_options(synchronize_session=False)

        if node.filters is not None:
            stmt = await self.visit(node, stmt, **kwargs)

        if self._session is not None:
            await self._session.execute(stmt)
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    await _session.execute(stmt)
