import uuid
from datetime import date, datetime
from enum import Enum
from typing import (
    Dict,
    List,
    Iterable,
    Any,
    Type,
    Union,
    Optional,
    TYPE_CHECKING,
    ClassVar,
)

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine
from odmantic.engine import AIOCursor
from pydantic.utils import lenient_issubclass

if TYPE_CHECKING:
    from pydantic.typing import (
        AbstractSetIntStr,
        DictStrAny,
        MappingIntStrAny,
        ReprArgs,
    )

__mappings_builtins__ = (
    int,
    str,
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
)

from odmantic.model import _BaseODMModel, ModelMetaclass, EmbeddedModelMetaclass

from odmantic.query import QueryExpression
from pydantic import BaseModel


def _is_private_attr(attr: str):
    return attr.startswith("_")


class DetachedFromSessionException(Exception):
    pass


class State(int, Enum):
    new = 0
    dirty = 1
    deleted = 2


class Model(_BaseODMModel, metaclass=ModelMetaclass):
    """Class that can be extended to create an ODMantic Model.

    Each model will be bound to a MongoDB collection. You can customize the collection
    name by setting the `__collection__` class variable in the model classes.
    """

    if TYPE_CHECKING:
        __collection__: ClassVar[str] = ""
        __primary_field__: ClassVar[str] = ""
        __wintry_session__: ClassVar["NosqlAsyncSession"] = None
        __wintry_embedded_parent__: ClassVar[Any] = None

        id: Union[ObjectId, Any]

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "__wintry_session__" or name == "__wintry_embedded_parent__":
            object.__setattr__(self, name, value)
            return

        if name == self.__primary_field__:
            raise NotImplementedError(
                "Reassigning a new primary key is not supported yet"
            )
        super().__setattr__(name, value)

        # record the change
        session: "NosqlAsyncSession | None" = getattr(self, "__wintry_session__", None)
        if session is not None:
            session.to_dirty(self.id)

    def update(
        self,
        patch_object: Union[BaseModel, Dict[str, Any]],
        *,
        include: Union[None, "AbstractSetIntStr", "MappingIntStrAny"] = None,
        exclude: Union[None, "AbstractSetIntStr", "MappingIntStrAny"] = None,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> None:
        is_primary_field_in_patch = (
            isinstance(patch_object, BaseModel)
            and self.__primary_field__ in patch_object.__fields__
        ) or (isinstance(patch_object, dict) and self.__primary_field__ in patch_object)
        if is_primary_field_in_patch:
            if (
                include is None
                and (exclude is None or self.__primary_field__ not in exclude)
            ) or (
                include is not None
                and self.__primary_field__ in include
                and (exclude is None or self.__primary_field__ not in exclude)
            ):
                raise ValueError(
                    "Updating the primary key is not supported. "
                    "See the copy method if you want to modify the primary field."
                )
        return super().update(
            patch_object,
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

    def dict(  # type: ignore # Missing deprecated/ unsupported parameters
        self,
        *,
        include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,  # type: ignore
        exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,  # type: ignore
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        by_alias: bool = False,
    ) -> "DictStrAny":
        exclude = exclude or set() | {"__wintry_session__", "__wintry_embedded_parent__"}
        return super(Model, self).dict(
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            by_alias=by_alias,
        )


class EmbeddedModel(_BaseODMModel, metaclass=EmbeddedModelMetaclass):
    """Class that can be extended to create an ODMantic Embedded Model.

    An embedded document cannot be persisted directly to the database but should be
    integrated in a regular ODMantic Model.
    """

    if TYPE_CHECKING:
        __wintry_session__: ClassVar["NosqlAsyncSession"] = None
        __wintry_embedded_parent__: ClassVar[Any] = None

    def dict(  # type: ignore # Missing deprecated/ unsupported parameters
        self,
        *,
        include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,  # type: ignore
        exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,  # type: ignore
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        by_alias: bool = False,
    ) -> "DictStrAny":
        exclude = exclude or set() | {"__wintry_session__", "__wintry_embedded_parent__"}
        return super(EmbeddedModel, self).dict(
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            by_alias=by_alias,
        )

    def __setattr__(self, key, value):
        if key == "__wintry_session__" or key == "__wintry_embedded_parent__":
            object.__setattr__(self, key, value)
            return

        super(EmbeddedModel, self).__setattr__(key, value)
        # record the change
        session: "NosqlAsyncSession | None" = getattr(self, "__wintry_session__", None)
        if session is not None:
            parent = getattr(self, "__wintry_embedded_parent__", None)
            if parent is not None:
                session.to_dirty(parent)


class ProxyList(list[Model | EmbeddedModel]):
    def instrument(self, session: "NosqlAsyncSession", parent: Any):
        self.parent = parent
        self.session = session

    def track(self):
        if self.session is not None and self.parent is not None:
            self.session.to_dirty(self.parent)

    def append(self, __object: Model | EmbeddedModel) -> None:
        """

        Args:
            __object (Model, EmbeddedModel):
        """
        super(ProxyList, self).append(__object)
        self.track()

    def extend(self, __iterable: Iterable[Model | EmbeddedModel]) -> None:
        super().extend(__iterable)
        self.track()

    def pop(self, __index: int = ...) -> Model | EmbeddedModel | None:
        super(ProxyList, self).pop(__index)
        self.track()

    def remove(self, __value: EmbeddedModel | Model) -> None:
        super(ProxyList, self).remove(__value)


class NosqlAsyncSession(AIOEngine):
    def __init__(self, motor_client: AsyncIOMotorClient = None, database: str = "test"):
        super().__init__(motor_client, database)
        self.new: Dict[ObjectId, Model] = {}
        self.deleted: Dict[ObjectId, Model] = {}
        self.dirty: Dict[ObjectId, Model] = {}
        self.transient: Dict[ObjectId, Model] = {}

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

    def _instrument(
        self,
        model: Any | List[Any],
        parent: Any,
    ):
        if model is None or type(model) in __mappings_builtins__:
            return model

        if not isinstance(model, list):
            for k, v in vars(model).items():
                if not _is_private_attr(k) and type(v) not in __mappings_builtins__:
                    if isinstance(v, list):
                        # If this is a list, we must convert it to a proxylist
                        # to allow for append and remove synchronization
                        proxy_list = ProxyList(self._instrument(val, parent) for val in v)
                        proxy_list.instrument(self, parent)
                        setattr(model, k, proxy_list)
                    else:
                        setattr(model, k, self._instrument(v, parent))

            # Augment instance with special variables so tracking is possible
            # Set track target (this allow to child objects to reference the root entity)
            setattr(model, "__wintry_session__", self)
            setattr(model, "__wintry_embedded_parent__", parent)
            return model
        else:
            return list(self._instrument(m, parent) for m in model)

    def _register(self, model: Model):
        self.transient[model.id] = model
        self._instrument(model, model.id)

    async def find_one(
        self,
        model: Type[Model],
        *queries: Union[QueryExpression, Dict, bool],
        sort: Optional[Any] = None,
    ) -> Optional[Model]:
        """Search for a Model instance matching the query filter provided

        Args:
            model: model to perform the operation on
            *queries: query filter to apply
            sort: sort expression

        Raises:
            DocumentParsingError: unable to parse the resulting document

        Returns:
            the fetched instance if found otherwise None

        <!---
        #noqa: DAR401 TypeError
        #noqa: DAR402 DocumentParsingError
        -->
        """
        if not lenient_issubclass(model, Model):
            raise TypeError("Can only call find_one with a Model class")
        results = await self.find(model, *queries, sort=sort, limit=1)
        if len(results) == 0:
            result = None
        else:
            result = results[0]

        if result is not None:
            self._register(result)
        return result

    async def find(
        self,
        model: Type[Model],
        *queries: Union[QueryExpression, Dict, bool],
        sort: Optional[Any] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> List[Model]:
        """Search for Model instances matching the query filter provided

        Args:
            model: model to perform the operation on
            *queries: query filter to apply
            sort: sort expression
            skip: number of document to skip
            limit: maximum number of instance fetched

        Raises:
            DocumentParsingError: unable to parse one of the resulting documents

        Returns:
            [odmantic.engine.AIOCursor][] of the query

        <!---
        #noqa: DAR401 ValueError
        #noqa: DAR401 TypeError
        #noqa: DAR402 DocumentParsingError
        -->
        """
        if not lenient_issubclass(model, Model):
            raise TypeError("Can only call find with a Model class")
        sort_expression = self._validate_sort_argument(sort)
        if limit is not None and limit <= 0:
            raise ValueError("limit has to be a strict positive value or None")
        if skip < 0:
            raise ValueError("skip has to be a positive integer")
        query = AIOEngine._build_query(*queries)
        collection = self.get_collection(model)
        pipeline: List[Dict] = [{"$match": query}]
        if sort_expression is not None:
            pipeline.append({"$sort": sort_expression})
        if skip > 0:
            pipeline.append({"$skip": skip})
        if limit is not None and limit > 0:
            pipeline.append({"$limit": limit})
        pipeline.extend(AIOEngine._cascade_find_pipeline(model))
        motor_cursor = collection.aggregate(pipeline)
        cursor = AIOCursor(model, motor_cursor)

        results = await cursor
        for m in results:
            self._register(m)
        return results
