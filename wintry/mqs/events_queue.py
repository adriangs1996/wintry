from typing import TypeVar
from pyee.cls import evented, on
from wintry.mqs.keys import new_event


_T = TypeVar("_T")


@evented
class EventQueue(list):
    @on(new_event)
    def append(self, __object: _T) -> None:
        return super().append(__object)
