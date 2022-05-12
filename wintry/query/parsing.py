from enum import Enum
from typing import Dict, List
import re
from .nodes import (
    AndNode,
    BinaryNode,
    Create,
    Delete,
    EqualToNode,
    FilterNode,
    Get,
    GreaterThanNode,
    InNode,
    LowerThanNode,
    NotEqualNode,
    NotGreaterThanNode,
    NotInNode,
    NotLowerThanNode,
    OrNode,
    RootNode,
    Find,
    Update,
)


class UnknownTokenError(Exception):
    pass


class ParsingError(Exception):
    pass


# Define the grammar


class TokenType(Enum):
    separator = 0
    by = 1
    operator = 2
    fieldName = 3
    query_target = 4
    logical_operator = 5
    modifier = 6
    end_token = 7
    nested_field = 8


TOKEN_MATCHER: Dict[TokenType, re.Pattern] = {
    TokenType.by: re.compile(r"by", flags=re.RegexFlag.IGNORECASE),
    TokenType.query_target: re.compile(
        r"(find|get|delete|update|removeOne|create)", flags=re.RegexFlag.IGNORECASE
    ),
    TokenType.operator: re.compile(
        r"(EqualTo|NotEqualTo|LowerThan|NotLowerThan|In|NotIn|GreaterThan|NotGreaterThan)",
        flags=re.RegexFlag.IGNORECASE,
    ),
    TokenType.logical_operator: re.compile(r"(and|or)", flags=re.RegexFlag.IGNORECASE),
    TokenType.modifier: re.compile(r"(skip|limit)", flags=re.RegexFlag.IGNORECASE),
    TokenType.nested_field: re.compile(r"[a-zA-Z]+(__[a-zA-Z]+)+"),
    TokenType.fieldName: re.compile(r"[a-zA-Z]+"),
    TokenType.separator: re.compile(r"_"),
    TokenType.end_token: re.compile(r"\$"),
}


class Token:
    def __init__(self, token_type: TokenType, lexema: str) -> None:
        self.token_type = token_type
        self.lexema = lexema


class QueryTokenizer:
    @staticmethod
    def tokenize(query: str) -> List[Token]:
        scan_target = query
        result: List[Token] = []

        while scan_target:
            matched_suffix = ""
            tt = None
            for token_type, pattern in TOKEN_MATCHER.items():
                if (m := pattern.match(scan_target)) is not None:
                    # Ignore spaces
                    msuffix = m.group()
                    if token_type == TokenType.separator:
                        matched_suffix = msuffix
                        tt = token_type
                        break
                    if len(msuffix) > len(matched_suffix):
                        matched_suffix = msuffix
                        tt = token_type

            if not matched_suffix:
                raise UnknownTokenError(scan_target)

            if tt != TokenType.separator:
                result.append(Token(tt, matched_suffix))  # type: ignore
            scan_target = scan_target[len(matched_suffix) :]

        return result + [Token(TokenType.end_token, "$")]


class QueryParser:
    def __init__(self) -> None:
        self.tokens: List[Token] = []

    def consume(self, token_type: TokenType):
        if not self.tokens:
            raise ParsingError()

        token = self.tokens.pop(0)

        if not token.token_type == token_type:
            raise ParsingError()

        return token

    def lookahead(self) -> TokenType | None:
        if not self.tokens:
            return None

        return self.tokens[0].token_type

    def parse_query_target(self) -> RootNode:
        token = self.consume(TokenType.query_target)

        if token.lexema.lower() == "create":
            return Create()

        if token.lexema.lower() == "update":
            return Update()

        if self.lookahead() == TokenType.end_token:
            query_body = None
        else:
            self.consume(TokenType.by)
            query_body = self.parse_filters_list()

        match token.lexema.lower():
            case "find":
                return Find(query_body)
            case "get":
                return Get(query_body)
            case "delete":
                return Delete(query_body)

        raise ParsingError()

    def parse_filters_list(self) -> BinaryNode:
        left = self.parse_criteria()

        if not (self.lookahead() is None or self.lookahead() == TokenType.end_token):
            join_operator = self.consume(TokenType.logical_operator)
            right = self.parse_filters_list()

            match join_operator.lexema.lower():
                case "and":
                    return AndNode(left, right)
                case "or":
                    return OrNode(left, right)

            raise ParsingError()

        else:
            return AndNode(left, None)

    def parse_criteria(self) -> FilterNode:
        if self.lookahead() == TokenType.fieldName:
            field_name_token = self.consume(TokenType.fieldName)
            field = field_name_token.lexema
        else:
            field_name_token = self.consume(TokenType.nested_field)
            field = ".".join(field_name_token.lexema.split("__"))

        if self.lookahead() == TokenType.operator:
            operator_token = self.consume(TokenType.operator)

            match operator_token.lexema.lower():
                case "equalto":
                    return EqualToNode(field)
                case "notequalto":
                    return NotEqualNode(field)
                case "lowerthan":
                    return LowerThanNode(field)
                case "notlowerthan":
                    return NotLowerThanNode(field)
                case "in":
                    return InNode(field)
                case "notin":
                    return NotInNode(field)
                case "greaterthan":
                    return GreaterThanNode(field)
                case "notgreaterthan":
                    return NotGreaterThanNode(field)
            raise ParsingError()
        else:
            return EqualToNode(field)

    def parse(self, query: str) -> RootNode:
        self.tokens = QueryTokenizer.tokenize(query)
        result = self.parse_query_target()
        self.consume(TokenType.end_token)
        return result
