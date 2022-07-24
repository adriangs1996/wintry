from typing import (
    Optional,
    TypeVar,
    Union,
    Mapping,
    Any,
    Sequence,
    overload,
    Type,
    Literal,
)

from sqlalchemy.engine import Result, ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import util
from sqlalchemy.sql import Select
from sqlmodel.sql.base import Executable as _Executable, Executable
from sqlmodel.sql.expression import SelectOfScalar

from wintry import BackendOptions
from wintry.db_contexts import DbContext

_ExecuteParams = TypeVar("_ExecuteParams")
_ExecuteOptions = TypeVar("_ExecuteOptions")
_TSelectParam = TypeVar("_TSelectParam")


class AsyncSession(_AsyncSession):
    @overload
    async def exec(
        self,
        statement: Select[_TSelectParam],
        *,
        params: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
        execution_options: Mapping[str, Any] = util.EMPTY_DICT,
        bind_arguments: Optional[Mapping[str, Any]] = None,
        _parent_execute_state: Optional[Any] = None,
        _add_event: Optional[Any] = None,
        **kw: Any,
    ) -> Result[_TSelectParam]:
        ...

    @overload
    async def exec(
        self,
        statement: SelectOfScalar[_TSelectParam],
        *,
        params: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
        execution_options: Mapping[str, Any] = util.EMPTY_DICT,
        bind_arguments: Optional[Mapping[str, Any]] = None,
        _parent_execute_state: Optional[Any] = None,
        _add_event: Optional[Any] = None,
        **kw: Any,
    ) -> ScalarResult[_TSelectParam]:
        ...

    async def exec(
        self,
        statement: Union[
            Select[_TSelectParam],
            SelectOfScalar[_TSelectParam],
            Executable[_TSelectParam],
        ],
        *,
        params: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
        execution_options: Mapping[str, Any] = util.EMPTY_DICT,
        bind_arguments: Optional[Mapping[str, Any]] = None,
        _parent_execute_state: Optional[Any] = None,
        _add_event: Optional[Any] = None,
        **kw: Any,
    ) -> Union[Result[_TSelectParam], ScalarResult[_TSelectParam]]:
        results = await super().execute(
            statement,
            params=params,
            execution_options=execution_options,
            bind_arguments=bind_arguments,
            _parent_execute_state=_parent_execute_state,
            _add_event=_add_event,
            **kw,
        )
        if isinstance(statement, SelectOfScalar):
            return results.scalars()  # type: ignore
        return results  # type: ignore

    async def execute(
        self,
        statement: _Executable,
        params: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
        execution_options: Optional[Mapping[str, Any]] = util.EMPTY_DICT,
        bind_arguments: Optional[Mapping[str, Any]] = None,
        _parent_execute_state: Optional[Any] = None,
        _add_event: Optional[Any] = None,
        **kw: Any,
    ) -> Result[Any]:
        """
        🚨 You probably want to use `session.exec()` instead of `session.execute()`.

        This is the original SQLAlchemy `session.execute()` method that returns objects
        of type `Row`, and that you have to call `scalars()` to get the model objects.

        For example:

        ```Python
        heroes = session.execute(select(Hero)).scalars().all()
        ```

        instead you could use `exec()`:

        ```Python
        heroes = session.exec(select(Hero)).all()
        ```
        """
        return await super().execute(  # type: ignore
            statement,
            params=params,
            execution_options=execution_options,
            bind_arguments=bind_arguments,
            _parent_execute_state=_parent_execute_state,
            _add_event=_add_event,
            **kw,
        )

    async def get(
        self,
        entity: Type[_TSelectParam],
        ident: Any,
        options: Optional[Sequence[Any]] = None,
        populate_existing: bool = False,
        with_for_update: Optional[Union[Literal[True], Mapping[str, Any]]] = None,
        identity_token: Optional[Any] = None,
    ) -> Optional[_TSelectParam]:
        return await super().get(
            entity,
            ident,
            options=options,
            populate_existing=populate_existing,
            with_for_update=with_for_update,
            identity_token=identity_token,
        )


class SQLContext(DbContext):
    def __init__(self, settings: BackendOptions):
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

        session = sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autocommit=False,
            class_=AsyncSession,
        )

        self._sessionmaker: sessionmaker = session
        self._session: AsyncSession | None = None

    @property
    async def session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return self._sessionmaker()

    async def save_changes(self):
        if self._session is not None:
            await self._session.commit()
