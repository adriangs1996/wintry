from winter.query.nodes import (
    AndNode,
    Create,
    EqualToNode,
    Find,
    LowerThanNode,
    OrNode,
)
from winter.query.parsing import ParsingError, QueryParser, QueryTokenizer, TokenType
import pytest


def test_tokenizer_recognizes_find_form():
    query = "find_by_id"
    tokens = QueryTokenizer.tokenize(query)
    tokens_types = [token.token_type for token in tokens]

    assert tokens_types == [
        TokenType.query_target,
        TokenType.by,
        TokenType.fieldName,
        TokenType.end_token,
    ]


def test_tokenizer_recognizes_create_form():
    query = "create"
    tokens = QueryTokenizer.tokenize(query)
    tokens_types = [token.token_type for token in tokens]

    assert tokens_types == [TokenType.query_target, TokenType.end_token]


def test_tokenizer_recognizes_delete_form():
    query = "delete_by_username_and_password"
    tokens = QueryTokenizer.tokenize(query)
    tokens_types = [token.token_type for token in tokens]

    assert tokens_types == [
        TokenType.query_target,
        TokenType.by,
        TokenType.fieldName,
        TokenType.logical_operator,
        TokenType.fieldName,
        TokenType.end_token,
    ]


def test_tokenizer_recognizes_update_form():
    query = "update_by_username_and_password"
    tokens = QueryTokenizer.tokenize(query)
    tokens_types = [token.token_type for token in tokens]

    assert tokens_types == [
        TokenType.query_target,
        TokenType.by,
        TokenType.fieldName,
        TokenType.logical_operator,
        TokenType.fieldName,
        TokenType.end_token,
    ]


def test_tokenizer_recognizes_get_form():
    query = "get_by_username_and_password"
    tokens = QueryTokenizer.tokenize(query)
    tokens_types = [token.token_type for token in tokens]

    assert tokens_types == [
        TokenType.query_target,
        TokenType.by,
        TokenType.fieldName,
        TokenType.logical_operator,
        TokenType.fieldName,
        TokenType.end_token,
    ]


def test_tokenizer_distinguish_between_operators_and_fieldNames():
    query = "Find_by_username_And_age_LowerThan"
    tokens = QueryTokenizer.tokenize(query)
    tokens_types = [token.token_type for token in tokens]

    assert tokens_types == [
        TokenType.query_target,
        TokenType.by,
        TokenType.fieldName,
        TokenType.logical_operator,
        TokenType.fieldName,
        TokenType.operator,
        TokenType.end_token,
    ]


def test_tokenizer_recognizes_nested_fields_access():
    query = "find_by_user__name_and_age"
    tokens = QueryTokenizer.tokenize(query)
    tokens_types = [token.token_type for token in tokens]

    assert tokens_types == [
        TokenType.query_target,
        TokenType.by,
        TokenType.nested_field,
        TokenType.logical_operator,
        TokenType.fieldName,
        TokenType.end_token,
    ]

def test_tokenizer_recognizes_deeply_nested_fields():
    query = "find_by_user__address__location__latitude_and_age_or_user__name"
    tokens = QueryTokenizer.tokenize(query)
    tokens_types = [token.token_type for token in tokens]

    assert tokens_types == [
        TokenType.query_target,
        TokenType.by,
        TokenType.nested_field,
        TokenType.logical_operator,
        TokenType.fieldName,
        TokenType.logical_operator,
        TokenType.nested_field,
        TokenType.end_token,
    ]


def test_parser_handles_find_queries():
    query = "find_by_id"
    parser = QueryParser()
    ast1 = parser.parse(query)

    assert ast1 == Find(AndNode(EqualToNode("id"), None))


def test_parser_handles_single_find():
    query = "find"
    parser = QueryParser()
    ast1 = parser.parse(query)

    assert ast1 == Find()


def test_parser_handles_create():
    query = "create"
    parser = QueryParser()
    ast = parser.parse(query)

    assert ast == Create()


def test_parser_throw_error_on_create_with_arguments():
    query = "create_by_id"
    parser = QueryParser()

    with pytest.raises(ParsingError):
        parser.parse(query)


def test_parser_handles_find_queries_with_logical_operators_and_filters():
    query = "find_by_id_and_age_lowerThan_or_username"
    parser = QueryParser()
    ast = parser.parse(query)

    assert ast == Find(
        AndNode(
            EqualToNode("id"),
            OrNode(
                LowerThanNode("age"),
                AndNode(
                    EqualToNode("username"),
                    None,
                ),
            ),
        )
    )
