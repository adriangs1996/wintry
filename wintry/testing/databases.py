import asyncio
from typing import Callable, ClassVar, TypeVar
import mongomock
from mongomock import collection as mongomock_collection
from mongomock.mongo_client import MongoClient


class WrappableClass:
    ASYNC_METHODS: ClassVar[list[str]] = []


# Take a callable and transform it into
# an async function. This is really useful
# to migrate an existing sync code base
def async_decorator(f: Callable):
    async def decorator(*args, **kwargs):
        return f(*args, **kwargs)

    return decorator


TWrappable = TypeVar("TWrappable", bound=WrappableClass)

# Wrapp all methods in cls prepopulated property
def wrapp_methods(cls: type[TWrappable]) -> type[TWrappable]:
    for method_name in cls.ASYNC_METHODS:
        method = getattr(cls, method_name, None)
        if method is not None:
            setattr(cls, method_name, async_decorator(method))

    return cls


class AsyncMongoCursor(mongomock_collection.Cursor):
    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self)
        except StopIteration:
            raise StopAsyncIteration()


@wrapp_methods
class AsyncMongoCollection(WrappableClass, mongomock.Collection):
    ASYNC_METHODS = [
        "find_one",
        "find_one_and_delete",
        "find_one_and_replace",
        "find_one_and_update",
        "find_and_modify",
        "save",
        "delete_one",
        "delete_many",
        "count",
        "insert_one",
        "insert_many",
        "update_one",
        "update_many",
        "replace_one",
        "count_documents",
        "estimated_document_count",
        "drop",
        "create_index",
        "ensure_index",
        "map_reduce",
    ]

    # overwrite find as it returns a cursors
    def find(self, *args, **kwargs) -> AsyncMongoCursor:
        cursor = super().find(*args, **kwargs)

        # Ok, this is going to feel like a bit of magic, and it is.
        # This effectively overwrites the methods on cursor,
        # with the methods defined in AsyncMongoCursor.
        cursor.__class__ = AsyncMongoCursor

        return cursor  # type: ignore


class AsyncMongoMockDatabase(mongomock.Database):
    ASYNC_METHODS = ["list_collection_names"]

    def get_collection(self, *args, **kwargs) -> AsyncMongoCollection:
        collection = super().get_collection(*args, **kwargs)
        collection.__class__ = AsyncMongoCollection
        return collection  # type: ignore


class MongoSession:
    # The mongo session requires some specific functionalities
    # from the wintry perspective. For example, we require
    # that the session contains information about the client
    #  who started it
    def __init__(self, client: "AsyncMongoMockClient") -> None:
        self.client = client

    async def __aenter__(self):
        await asyncio.sleep(0)

    async def __aexit__(self, exc_type, exc, tb):
        await asyncio.sleep(0)


class AsyncMongoMockClient(MongoClient):
    def get_database(self, *args, **kwargs) -> AsyncMongoMockDatabase:
        db = super().get_database(*args, **kwargs)
        db.__class__ = AsyncMongoMockDatabase
        return db  # type: ignore

    async def start_session(self, **kwargs):
        await asyncio.sleep(0)
        return MongoSession(self)
