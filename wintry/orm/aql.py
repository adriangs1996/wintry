"""
Abstract Query Language (AQL) is an API for constructing an AST
for the Repository Query Compiler. This is meant to be used inside
managed method of repositories
"""

from wintry.models import Model
from wintry.query.nodes import BinaryNode, FilterNode
from wintry.utils.decorators import alias


class FilteredClause:
    def __init__(
        self, action: "QueryAction", model: type[Model], condition: BinaryNode | None
    ) -> None:
        self.model = model
        self.condition = condition
        assert type(action) in (Find, Delete, Update)
        self.action = action


class QueryAction:
    def __init__(self, model: type[Model]):
        self.model = model

    def by(self, condition: BinaryNode | FilterNode) -> FilteredClause:
        if isinstance(condition, BinaryNode):
            return FilteredClause(self, self.model, condition)
        else:
            return FilteredClause(self, self.model, condition & None)


class Find(QueryAction):
    ...


class Delete(QueryAction):
    ...


class Update(QueryAction):
    ...


class Create(QueryAction):
    ...


@alias(Find)
def find(model: type[Model]) -> Find:
    ...


@alias(Delete)
def delete(model: type[Model]) -> Delete:
    ...


@alias(Update)
def update(model: type[Model]) -> Update:
    ...


@alias(Create)
def create(model: type[Model]) -> Create:
    ...
