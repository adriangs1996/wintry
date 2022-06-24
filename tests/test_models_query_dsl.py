from typing import Any
from wintry.models import Model
import pytest
from wintry.orm.aql import Filter

from wintry.query.nodes import (
    AndNode,
    EqualToNode,
    FilterNode,
    GreaterThanNode,
    LowerThanNode,
    OrNode,
)


class QueryDslEntity(Model, mapped=False):
    field1: str
    field2: int


class QueryDslRelatedEntity(Model, mapped=False):
    f1: QueryDslEntity
    f2: int


def test_aql_can_generate_eq():
    query: Any = QueryDslEntity.field1 == "Hello"
    assert query == EqualToNode("field1", "Hello")


def test_aql_can_generate_lt():
    query: Any = QueryDslEntity.field2 < 10
    assert query == LowerThanNode("field2", value=10)


def test_aql_can_generate_gt():
    query: Any = QueryDslEntity.field2 > 10
    assert query == GreaterThanNode("field2", value=10)


def test_aql_handles_nested_fields_access():
    query: Any = QueryDslRelatedEntity.f1.field1 == "Hello"
    assert query == EqualToNode("f1.field1", "Hello")


def test_aql_can_join_logical_queries():
    query: Any = (QueryDslEntity.field1 == "Hello") | (QueryDslEntity.field2 < 20)
    assert query == OrNode(EqualToNode("field1", "Hello"), LowerThanNode("field2", 20))


def test_aql_can_join_logical_queries_and():
    query: Any = (QueryDslEntity.field1 == "Hello") & (QueryDslEntity.field2 < 20)
    assert query == AndNode(EqualToNode("field1", "Hello"), LowerThanNode("field2", 20))


def test_aql_can_handle_multiple_logical_queries():
    query: Any = (QueryDslEntity.field1 == "Hello") & (QueryDslEntity.field2 < 20) | (
        QueryDslEntity.field2 > 5
    )

    assert query == OrNode(
        AndNode(
            EqualToNode("field1", "Hello"),
            LowerThanNode("field2", 20),
        ),
        GreaterThanNode("field2", 5),
    )
