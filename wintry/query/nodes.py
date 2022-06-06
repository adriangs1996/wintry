from dataclasses import Field
from typing import Any, Optional


class OpNode:
    pass


class RootNode(OpNode):
    def __init__(self, filters: Optional["BinaryNode"] = None) -> None:
        self.filters = filters

    def __eq__(self, __o: "RootNode") -> bool:
        return __o.filters == self.filters


class FilterNode(OpNode):
    def __init__(self, field: str, value: Any = None) -> None:
        self.field = field
        self.value = value

    def __eq__(self, __o: "FilterNode") -> bool:
        return __o.field == self.field and self.value == __o.value

    def __and__(self, node: Optional["BinaryNode"]) -> "AndNode":
        return AndNode(self, node)

    def __or__(self, node: Optional["BinaryNode"]) -> "OrNode":
        return OrNode(self, node)


class BinaryNode(OpNode):
    def __init__(self, left: FilterNode, right: Optional["BinaryNode"]) -> None:
        self.left = left
        self.right = right

    def __eq__(self, __o: "BinaryNode") -> bool:
        return self.left == __o.left and self.right == __o.right


class Create(RootNode):
    def __init__(self) -> None:
        super().__init__(None)


class RemoveOne(RootNode):
    pass


class Update(RootNode):
    pass


class Find(RootNode):
    def __init__(
        self, filters: Optional["BinaryNode"] = None, projection: list[str] = []
    ) -> None:
        super().__init__(filters)
        self.projection = projection


class Get(RootNode):
    def __init__(
        self, filters: Optional["BinaryNode"] = None, projection: list[Field] = []
    ) -> None:
        super().__init__(filters)
        self.projection = projection


class Delete(RootNode):
    pass


class AndNode(BinaryNode):
    pass


class OrNode(BinaryNode):
    pass


class EqualToNode(FilterNode):
    pass


class NotEqualNode(FilterNode):
    pass


class LowerThanNode(FilterNode):
    pass


class NotLowerThanNode(FilterNode):
    pass


class GreaterThanNode(FilterNode):
    pass


class NotGreaterThanNode(FilterNode):
    pass


class InNode(FilterNode):
    pass


class NotInNode(FilterNode):
    pass
