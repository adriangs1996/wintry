from dataclasses import dataclass
from wintry.ioc import provider, inject


def test_simple_ioc_provides_singletons_by_default():
    @provider
    class Provider:
        pass

    @inject
    class Consumer:
        def __init__(self, provider: Provider) -> None:
            self.provider = provider

    assert Consumer().provider == Consumer().provider  # type: ignore


def test_provider_also_injects():
    @provider
    class Provider:
        pass

    @provider
    class Consumer:
        def __init__(self, provider: Provider) -> None:
            self.provider = provider

    assert Consumer().provider == Consumer().provider  # type: ignore


def test_a_function_can_be_a_provider():
    class Interface:
        pass

    @provider(of=Interface) #type: ignore
    def Provider():
        return Interface()

    @inject
    class Consumer:
        def __init__(self, provider: Interface) -> None:
            self.provider = provider

    assert Consumer().provider == Consumer().provider  # type: ignore


def test_a_function_can_be_injected():
    @provider
    @dataclass
    class Interface:
        x: int = 20

    @inject
    def injected(i: Interface):
        return i.x

    assert injected() == 20  # type: ignore


def test_an_injected_function_can_be_overwritten_by_arguments():
    @provider
    @dataclass
    class Interface:
        x: int = 20

    @inject
    def injected(i: Interface):
        return i.x

    assert injected(Interface(x=10)) == 10


def test_an_injected_class_can_be_overwritten_by_arguments():
    @provider
    @dataclass
    class Interface:
        x: int = 20

    @inject
    class Consumer:
        def __init__(self, i: Interface) -> None:
            self.x = i.x

    assert Consumer().x == 20  # type: ignore
    assert Consumer(Interface(10)).x == 10


def test_nested_injection():
    @provider
    class ServiceA:
        pass

    @provider
    class ServiceB:
        def __init__(self, a: ServiceA) -> None:
            self.a = a

    @inject
    class ServiceC:
        def __init__(self, b: ServiceB, a: ServiceA) -> None:
            self.b = b
            self.a = a

    c = ServiceC()  # type: ignore
    assert c.a == c.b.a


def test_scoped_injection():
    @provider(singleton=False)
    class Provider:
        pass

    @inject
    class Consumer:
        def __init__(self, provider: Provider) -> None:
            self.provider = provider

    assert Consumer().provider != Consumer().provider  # type: ignore
