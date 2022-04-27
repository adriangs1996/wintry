

from typing import Any


class Duck:
    def __init__(self, **kwargs: str | int) -> None:
        self.__dict__.update(kwargs)

    def __getattribute__(self, __name: str) -> str | int:
        try:
            return self.__dict__[__name]
        except KeyError:
            raise AttributeError(__name + " is not found")


class Donald(Duck):
    pass

print(Donald().y)