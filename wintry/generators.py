from typing import Any
from uuid import UUID, uuid4

class Increment:
    class NumberSequence:
        def __init__(self):
            self.counter = 0

        def __call__(self) -> Any:
            while True:
                yield self.counter
                self.counter += 1

    def __init__(self) -> None:
        self.generator = Increment.NumberSequence()()

    def __call__(self) -> int:
        return next(self.generator)


class RandomUUID:
    def __call__(self) -> UUID:
        return uuid4()

class UniqueString:
    def __call__(self) -> Any:
        return uuid4().hex


AutoIncrement = Increment()
AutoUUID = RandomUUID()
AutoString = UniqueString()