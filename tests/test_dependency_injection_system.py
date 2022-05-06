from abc import ABC, abstractmethod
from wintry.dependency_injection import service, provider, __mappings__, Factory
import inject
import pytest


def start_injector():
    def binder_config(binder: inject.Binder):
        for interface, implementation in __mappings__.items():
            if isinstance(implementation, Factory):
                binder.bind_to_provider(interface, implementation)
            else:
                binder.bind(interface, implementation())

    inject.clear_and_configure(binder_config, bind_in_runtime=False)


class Interface(ABC):
    @abstractmethod
    def do_something(self) -> int:
        ...


@provider(interface=Interface)
class Implementer(Interface):
    def do_something(self) -> int:
        return 10


@provider
class NestedService:
    def __init__(self, i: Interface) -> None:
        self.i = i


@service
class Consumer:
    def __init__(self, implementer: Interface, nest: NestedService) -> None:
        self.i = implementer
        self.nested = nest


@pytest.fixture(scope="module", autouse=True)
def setup():
    start_injector()


def test_correctly_instantiate_interface():
    c = Consumer()  # type: ignore
    assert c.i.do_something() == 10
    assert c.nested.i.do_something() == 10
