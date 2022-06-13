from wintry.query.nodes import (
    AndNode,
    Create,
    EqualToNode,
    Find,
    LowerThanNode,
    OrNode,
)
from wintry.query.parsing import ParsingError, QueryParser, QueryTokenizer, TokenType
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


def test_tokenizer_correctly_handles_long_words_with_keywords_inside():
    # orderid has "or" at the begining, but it is a long word, so
    # we must try to match the whole word, instead just the first part
    query = "find_by_orderid"
    tokens = QueryTokenizer.tokenize(query)
    token_types = [token.token_type for token in tokens]

    assert token_types == [
        TokenType.query_target,
        TokenType.by,
        TokenType.fieldName,
        TokenType.end_token,
    ]


def test_parser_handles_find_queries():
    query = "find_by_id"
    parser = QueryParser()
    ast1 = parser.parse(query)

    assert ast1 == Find(EqualToNode("id"))


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

    assert ast == Find(EqualToNode("id") & LowerThanNode("age") | EqualToNode("username"))
    assert ast == Find(
        OrNode(
            AndNode(
                EqualToNode("id"),
                LowerThanNode("age"),
            ),
            EqualToNode("username"),
        )
    )


def test_parser_gets_dot_separated_nested_fields():
    query = "find_by_id_and_user__age_lowerThan_or_user__username"
    parser = QueryParser()
    ast = parser.parse(query)

    assert ast == Find(
        OrNode(
            AndNode(
                EqualToNode("id"),
                LowerThanNode("user.age"),
            ),
            EqualToNode("user.username"),
        )
    )

    assert ast == Find(
        EqualToNode("id") & LowerThanNode("user.age") | EqualToNode("user.username")
    )
