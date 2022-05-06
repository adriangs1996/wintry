from dataclasses import is_dataclass, asdict
from typing import Any
from wintry.drivers.mongo import MongoDbDriver, MongoSession, get_tablename
from wintry.utils.keys import __winter_track_target__
from wintry import BACKENDS


class MongoSessionTracker:
    """
    Tracks changes on objects returned by a repository
    and updates then after command
    """

    def __init__(self, owner: type, backend_name: str) -> None:
        self.owner = owner
        self._modified = list()
        self._backend_name = backend_name

    def add(self, instance: Any):
        if (target := getattr(instance, __winter_track_target__, None)) is not None:
            if target not in self._modified:
                assert is_dataclass(target)
                self._modified.append(target)

    async def flush(self, session: MongoSession):
        backend = BACKENDS[self._backend_name]
        assert isinstance(backend.driver, MongoDbDriver)

        db = backend.get_connection()
        collection = db[get_tablename(self.owner)]

        for modified_instance in self._modified:
            if (_id := getattr(modified_instance, "id", None)) is not None:
                values = asdict(modified_instance)
                values.pop("id", None)
                await collection.update_one({"id": _id}, {"$set": values}, session=session)

        self._modified = list()

    def clean(self):
        self._modified = list()
