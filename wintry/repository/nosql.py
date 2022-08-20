import dataclasses
import uuid
from datetime import date, datetime
from enum import Enum, IntEnum
from logging import Logger
from typing import (
    Dict,
    List,
    Any,
    Type,
    Union,
    Optional,
    TypeVar,
    Callable,
    ClassVar,
)

from bson import ObjectId
from odmantic.bson import ObjectId as ODManticObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine
from wrapt import ObjectProxy, CallableObjectProxy

__mappings_builtins__ = (
    int,
    str,
    IntEnum,
    Enum,
    float,
    bool,
    bytes,
    date,
    datetime,
    dict,
    set,
    uuid.UUID,
    ObjectId,
    ODManticObjectId,
)

from odmantic.model import Model

from odmantic.query import QueryExpression


def _is_private_attr(attr: str):
    return attr.startswith("_")


class DetachedFromSessionException(Exception):
    pass


class State(int, Enum):
    new = 0
    dirty = 1
    deleted = 2


class ProxyList(ObjectProxy):
    def __init__(self, wrapped, session, parent):
        super(ProxyList, self).__init__(wrapped)
        self._self_session = session
        self._self_parent = parent

    def __getattr__(self, item):
        value = super(ProxyList, self).__getattr__(item)
        if item in ("append", "extend", "remove", "pop"):
            self._self_track()
        return value

    def __getitem__(self, item):
        value = super(ProxyList, self).__getitem__(item)
        if type(value) in __mappings_builtins__:
            return value
        return ModelSessionProxy(value, self._self_session, self._self_parent)

    def __setitem__(self, key, value):
        super(ProxyList, self).__setitem__(key, value)
        self._self_track()

    def _self_track(self):
        if self._self_session is not None and self._self_parent is not None:
            self._self_session.to_dirty(self._self_parent)

    def __copy__(self):
        """Dummy method to please the abstract definition"""

    def __deepcopy__(self, memo):
        """Dummy method to please the abstract definition"""

    def __reduce__(self):
        """Dummy method to please the abstract definition"""

    def __reduce_ex__(self, protocol):
        """Dummy method to please the abstract definition"""


class ModelSessionProxy(ObjectProxy):
    def __init__(self, proxied_instance: Any, session: "NosqlAsyncSession", parent: Any):
        super(ModelSessionProxy, self).__init__(proxied_instance)
        self._self_session = session
        self._self_parent = parent

    def __setattr__(self, key, value):
        super(ModelSessionProxy, self).__setattr__(key, value)
        if not key.startswith("_self_"):
            self._self_session.to_dirty(self._self_parent)

    def __getattr__(self, item: str):
        attr = super(ModelSessionProxy, self).__getattr__(item)

        if type(attr) in __mappings_builtins__ or isinstance(attr, Callable):
            return attr

        if isinstance(attr, list):
            proxy_attr = ProxyList(attr, self._self_session, self._self_parent)
        else:
            proxy_attr = ModelSessionProxy(attr, self._self_session, self._self_parent)

        return proxy_attr

    def __copy__(self):
        """Dummy method to please the abstract definition"""

    def __deepcopy__(self, memo):
        """Dummy method to please the abstract definition"""

    def __reduce__(self):
        """Dummy method to please the abstract definition"""

    def __reduce_ex__(self, protocol):
        """Dummy method to please the abstract definition"""


T = TypeVar("T", bound=Model)


class MotorContextNotInitialized(Exception):
    ...


class MotorContext(object):
    """
    This holds a class reference to a mongo client instance.
    Is meant to be initialized once, on the Event Loop that will
    be running the application, so no Detached Sessions Errors
    occurs
    """

    _client: ClassVar[Optional[AsyncIOMotorClient]] = None

    @classmethod
    def config(cls, url: str):
        if cls._client is None:
            cls._client = AsyncIOMotorClient(url)

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        if cls._client is None:
            raise MotorContextNotInitialized()
        return cls._client


class NosqlAsyncSession(AIOEngine):
    def __init__(
        self, motor_client: AsyncIOMotorClient = None, database: str = "test", orm=True
    ):
        super().__init__(motor_client, database)
        self.new: Dict[ObjectId, Model] = {}
        self.deleted: Dict[ObjectId, Model] = {}
        self.dirty: Dict[ObjectId, Model] = {}
        self.transient: Dict[ObjectId, Model] = {}
        self.orm = True

    def begin(self):
        self.new.clear()
        self.deleted.clear()
        self.dirty.clear()

    async def _commit_new(self):
        if self.new:
            await self.save_all(list(self.new.values()))

    async def _commit_dirty(self):
        if self.dirty:
            await self.save_all(list(self.dirty.values()))

    async def _commit_deleted(self):
        for instance in self.deleted.values():
            await self.delete(instance)

    async def commit(self):
        await self._commit_new()
        await self._commit_dirty()
        await self._commit_deleted()
        self.begin()

    async def rollback(self):
        self.new.clear()
        self.dirty.clear()
        self.deleted.clear()

    def add(self, model: Model):
        self.new[model.id] = model
        self.transient[model.id] = model

    def remove(self, model: Model):
        if model.id not in self.transient:
            raise DetachedFromSessionException()

        if model.id in self.new:
            self.new.pop(model.id)
            return

        if model.id in self.dirty:
            self.dirty.pop(model.id)

        self.deleted[model.id] = model

    def to_dirty(self, pk: ObjectId):
        if pk in self.dirty:
            return

        if pk not in self.transient:
            raise DetachedFromSessionException()

        if pk not in self.new:
            model = self.transient[pk]
            self.dirty[pk] = model

    def _to_deleted(self, pk: ObjectId):
        if pk not in self.transient:
            raise DetachedFromSessionException()

        if pk in self.new:
            self.new.pop(pk)

        if pk in self.dirty:
            self.dirty.pop(pk)

        model = self.transient[pk]
        self.deleted[pk] = model

    def _register(self, model: Model):
        self.transient[model.id] = model

    async def find_one(
        self,
        model: Type[T],
        *queries: Union[QueryExpression, Dict, bool],
        sort: Optional[Any] = None,
    ) -> Optional[T]:

        # This might seem odd, but actually is quite important.
        # find_one is just a shortcut for find()[0]. As this calls
        # (as implemented by AIOEngine) self.find, we must ensure
        # that result does not get registered twice and that the
        # registry does not accidentally map a proxy object instead
        # of the original one. So we save the old orm value, set it
        # to false in the call to super, and finally revert it back
        # to function as the flag for configuring the OrmProxy or not.
        old_orm = self.orm

        # Set the orm flag to False, so the call to super returns pure
        # objects
        self.orm = False

        result = await super(NosqlAsyncSession, self).find_one(model, *queries, sort=sort)

        # Restore the orm flag
        self.orm = old_orm

        if not self.orm:
            return result

        if result is not None:
            proxy = ModelSessionProxy(result, self, result.id)
            self._register(result)
            return proxy
        return None

    async def find(
        self,
        model: Type[T],
        *queries: Union[QueryExpression, Dict, bool],
        sort: Optional[Any] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> List[T]:

        # Same as above, overriden method should account for the orm flag
        # presence, otherwise they could end up with proxies registered in the
        # identity map instead of the pure objects the imap is expecting
        old_orm = self.orm
        self.orm = False
        results = await super(NosqlAsyncSession, self).find(
            model, *queries, sort=sort, skip=skip, limit=limit
        )
        self.orm = old_orm
        if not self.orm:
            return results

        proxies = []
        for result in results:
            proxy = ModelSessionProxy(result, self, result.id)
            self._register(result)
            proxies.append(proxy)
        return proxies
