from dataclasses import Field, dataclass
from typing import Any, Optional


class OpNode:
    pass


@dataclass
class RootNode(OpNode):
    filters: "BinaryNode | FilterNode | None" = None

    def __eq__(self, __o: "RootNode") -> bool:
        return __o.filters == self.filters


@dataclass
class FilterNode(OpNode):
    field: str
    value: Any | None = None

    def __eq__(self, __o: "FilterNode") -> bool:
        return __o.field == self.field and self.value == __o.value

    def __and__(self, node: "FilterNode") -> "AndNode":
        return AndNode(self, node)

    def __or__(self, node: "FilterNode") -> "OrNode":
        return OrNode(self, node)


@dataclass
class BinaryNode(OpNode):
    left: "BinaryNode | FilterNode"
    right: "FilterNode | None" = None

    def __eq__(self, __o: "BinaryNode") -> bool:
        return self.left == __o.left and self.right == __o.right

    def __and__(self, o: FilterNode):
        return AndNode(self, o)

    def __or__(self, __t: FilterNode):
        return OrNode(self, __t)


class Create(RootNode):
    def __init__(self) -> None:
        super().__init__(None)


class RemoveOne(RootNode):
    pass


class Update(RootNode):
    pass


class Find(RootNode):
    def __init__(
        self, filters: BinaryNode | FilterNode | None = None, projection: list[str] = []
    ) -> None:
        super().__init__(filters)
        self.projection = projection


class Get(RootNode):
    def __init__(
        self, filters: BinaryNode | FilterNode | None = None, projection: list[Field] = []
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
