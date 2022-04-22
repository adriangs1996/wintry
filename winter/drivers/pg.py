from functools import singledispatchmethod
from typing import Any, Optional
from winter.backend import QueryDriver
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncResult
import sqlalchemy.orm as orm
from winter.query.nodes import Find, Get, OpNode, RootNode
from pydantic import BaseModel
from winter.settings import WinterSettings
from sqlalchemy import select, update, delete
from sqlalchemy.sql import Select


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
    async def visit(self, node: OpNode, schema: BaseModel, **kwargs):
        raise NotImplementedError

    @visit.register
    async def _(self, node: Find, schema: BaseModel, **kwargs):
        if node.filters is not None:
            modifiers: dict[str, Any] = await self.visit(node.filters, schema, **kwargs)
        else:
            modifiers = {}
        stmt: Select = select(schema)

        if (where := modifiers.get("where", None)) is not None:
            stmt = stmt.where(where)

        if (joins := modifiers.get("joins", None)) is not None:
            for jointable in joins:
                stmt = stmt.join(jointable)

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
    async def _(self, node: Get, schema: BaseModel, **kwargs):
        if node.filters is not None:
            modifiers: dict[str, Any] = await self.visit(node.filters, schema, **kwargs)
        else:
            modifiers = {}

        stmt: Select = select(schema)

        if (condition := modifiers.get("where", None)) is not None:
            stmt = stmt.where(condition)

        if (joins := modifiers.get("joins", None)) is not None:
            for jointable in joins:
                stmt = stmt.join(jointable)

        if self._session is not None:
            result: AsyncResult = await self._session.execute(stmt)
            return result.scalars().all()
        else:
            async with self._sessionmaker() as session:
                _session: AsyncSession = session
                async with _session.begin():
                    result: AsyncResult = await _session.execute(stmt)
                    return result.scalar_one_or_none()