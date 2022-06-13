from dataclasses import Field, dataclass
from typing import Any, Optional


class OpNode:
    pass


@dataclass
class RootNode(OpNode):
    filters: "BinaryNode | None" = None

    def __eq__(self, __o: "RootNode") -> bool:
        return __o.filters == self.filters


@dataclass
class FilterNode(OpNode):
    field: str
    value: Any | None = None

    def __eq__(self, __o: "FilterNode") -> bool:
        return __o.field == self.field and self.value == __o.value

    def __and__(self, node: Optional["BinaryNode"]) -> "AndNode":
        return AndNode(self, node)

    def __or__(self, node: Optional["BinaryNode"]) -> "OrNode":
        return OrNode(self, node)


@dataclass
class BinaryNode(OpNode):
    left: FilterNode
    right: "BinaryNode | None" = None

    def __eq__(self, __o: "BinaryNode") -> bool:
        return self.left == __o.left and self.right == __o.right

    def __and__(self, o: "FilterNode"):
        if self.right is None:
            return AndNode(self.left, AndNode(o, None))
        else:
            return AndNode(self.left, self.right & o)
    
    def __or__(self, __t: FilterNode):
        if self.right is None:
            return OrNode(self.left, AndNode(__t, None))
        else:
            return OrNode(self.left, self.right | __t)


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
