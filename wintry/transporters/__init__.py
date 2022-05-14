import abc
from typing import Protocol

from wintry.settings import TransporterType, WinterSettings


class Microservice(Protocol):
    transporter: TransporterType

    def __init__(self, settings: WinterSettings) -> None:
        ...

    @abc.abstractmethod
    def init(self) -> None:
        ...

    @abc.abstractmethod
    async def run():
        ...
