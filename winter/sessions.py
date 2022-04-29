from dataclasses import is_dataclass
from dataclass_wizard import asdict
from typing import Any
from winter.drivers.mongo import MongoDbDriver, MongoSession, get_tablename
from winter.backend import Backend


class MongoSessionTracker:
    """
    Tracks changes on objects returned by a repository
    and updates then after command
    """

    def __init__(self, owner: type) -> None:
        self.owner = owner
        self._modified = list()

    def add(self, instance: Any):
        assert is_dataclass(instance)
        if instance not in self._modified:
            self._modified.append(instance)

    async def flush(self, session: MongoSession):
        assert Backend.driver is not None
        assert isinstance(Backend.driver, MongoDbDriver)

        db = Backend.get_connection()
        collection = db[get_tablename(self.owner)]

        for modified_instance in self._modified:
            if (_id := getattr(modified_instance, "id", None)) is not None:
                values = asdict(modified_instance, exclude=["id"])
                await collection.update_one({"id": _id}, {"$set": values}, session=session)

        self._modified = list()

    def clean(self):
        self._modified = list()
