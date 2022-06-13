"""
Abstract Query Language (AQL) is an API for constructing an AST
for the Repository Query Compiler. This is meant to be used inside
managed method of repositories
"""

from typing import Any, Protocol
from wintry import BACKENDS
from wintry.models import Model
from wintry.query.nodes import BinaryNode, FilterNode, RootNode
from wintry.utils.decorators import alias
from wintry.query.nodes import Find as FindNode
from wintry.query.nodes import Delete as DeleteNode
from wintry.query.nodes import Update as UpdateNode
from wintry.query.nodes import Create as CreateNode
from wintry.query.nodes import Get as GetNode

Condition = tuple[BinaryNode | FilterNode, dict[str, Any]]
Filter = tuple[BinaryNode | None, dict[str, Any]]


class ClauseProtocol(Protocol):
    def compile(self) -> RootNode:
        raise NotImplementedError()


class FilteredClause(ClauseProtocol):
    def __init__(
        self, action: "QueryAction", model: type[Model], condition: Filter | None
    ) -> None:
        self.model = model
        self.condition = condition
        assert type(action) in (Find, Delete, Get)
        self.action = action

    @property
    def bindings(self) -> dict[str, Any]:
        if self.condition is not None:
            return self.condition[1]
        return {}

    def compile(self):
        root_node = self.action.compile()
        if self.condition is not None:
            root_node.filters = self.condition[0]

        return root_node

class FilteredGet(FilteredClause):
    pass

class FilteredDelete(FilteredClause):
    pass

class FilteredFind(FilteredClause):
    pass


class QueryAction(ClauseProtocol):
    def __init__(self, model: type[Model], **kwargs: Any):
        self.model = model
        self.bindings = kwargs or {}

    def by(self, condition: Any) -> FilteredClause:
        return FilteredClause(self, self.model, (condition, self.bindings))

    def compile(self):
        return super().compile()


class Find(QueryAction):
    def compile(self):
        return FindNode()

    def by(self, condition: Any) -> FilteredFind:
        return FilteredFind(self, self.model, (condition, self.bindings))


class Delete(QueryAction):
    def compile(self):
        return DeleteNode()

    def by(self, condition: Any) -> FilteredDelete:
        return FilteredDelete(self, self.model, (condition, self.bindings))


class Update(QueryAction):
    def compile(self):
        return UpdateNode()


class Create(QueryAction):
    def compile(self):
        return CreateNode()


class Get(QueryAction):
    def compile(self):
        return GetNode()

    def by(self, condition: Any) -> FilteredGet:
        return FilteredGet(self, self.model, (condition, self.bindings))


@alias(Get)
def get(model: type[Model]) -> Get:
    ...


@alias(Find)
def find(model: type[Model]) -> Find:
    ...


@alias(Delete)
def delete(model: type[Model]) -> Delete:
    ...


def update(*, entity: Model) -> Update:
    return Update(type(entity), entity=entity)


def create(*, entity: Model) -> Create:
    return Create(type(entity), entity=entity)


async def execute(
    statement: FilteredClause | QueryAction,
    backend_identifier: str = "default",
    session: Any = None,
) -> Any:
    node = statement.compile()
    backend = BACKENDS[backend_identifier]
    assert backend.driver is not None

    return await backend.driver.run_async(
        node, statement.model, session=session, **statement.bindings
    )
