from typing import Any, Callable, TypeVar

T = TypeVar("T")


class DependencyInjectionError(Exception):
    pass


class SnowFactory:
    def __init__(self, cls: Callable) -> None:
        self.cls = cls

    def __call__(self) -> Any:
        return self.cls()


class IGlooContainer:
    # An igloo is a container for wintry objects, so
    # bear with me on the name. This is a Dependency Injection
    # solution for the Wintry Framework. Users should not need
    # to use the Igloo directly, but I might give some options
    # for extension and configuration.

    # This container should be first of all, FAST. I mean, really fast.
    # Containers are by definition like python dicts, so, lets use
    # them

    def __init__(self) -> None:
        # So we can have factory services for on demand injection
        self.factories: dict[type, SnowFactory] = dict()
        # We can have singletons
        self.singletons: dict[type, Any] = dict()

    def __setitem__(self, key: type, value: Any):
        if isinstance(value, SnowFactory):
            self.factories[key] = value
        else:
            self.singletons[key] = value

    def __getitem__(self, key: type):
        if key in self.singletons:
            return self.singletons[key]

        if key in self.factories:
            return self.factories[key]()

        return None
