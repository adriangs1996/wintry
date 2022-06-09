from typing import Any
from wintry.drivers.mongo import MongoDbDriver, MongoSession, get_tablename
from wintry.models import Model
from wintry.orm.aql import execute, update
from wintry.settings import EngineType
from wintry.utils.keys import __winter_track_target__
from wintry import BACKENDS
from weakref import WeakValueDictionary
from sqlalchemy.ext.asyncio import AsyncConnection


class TrackerError(Exception):
    pass


def get_instance_key(instance: Model):
    return (type(instance),) + tuple(instance.ids().values())


class Tracker:
    """
    Tracks changes on objects returned by a repository
    and updates then after command
    """

    def __init__(self, owner: type[Model], backend_name: str) -> None:
        self.owner = owner
        self._modified: set[tuple[Any, ...]] = set()
        self._backend_name = backend_name
        self._identity_map: WeakValueDictionary[
            tuple[Any, ...], Model
        ] = WeakValueDictionary()

    def track(self, instance: Model):
        key = get_instance_key(instance)
        self._identity_map[key] = instance

    def add(self, instance: Model):
        if (target := getattr(instance, __winter_track_target__, None)) is not None:
            key = get_instance_key(target)
            if key not in self._modified:
                self._modified.add(key)

    def get_tracked_instance(self, instance: Model) -> Model:
        key = get_instance_key(instance)
        result = self._identity_map.get(key)
        assert result is not None
        return result

    @property
    def dirty(self):
        for key in self._modified:
            modified_instance = self._identity_map.get(key)
            assert modified_instance is not None
            yield modified_instance

    async def flush(self, session):
        for modified_instance in self.dirty:
            pks = modified_instance.ids()
            if not pks:
                raise TrackerError(f"{modified_instance} has not defined an id property")
            await execute(
                update(entity=modified_instance), self._backend_name, session=session
            )

        self._modified.clear()

    def clean(self):
        self._modified.clear()
        self._identity_map.clear()

    def __contains__(self, instance: Model):
        key = get_instance_key(instance)
        return key in self._identity_map
