from typing import Any, Callable, TypeVar
from fastapi.params import Depends

T = TypeVar("T")


class DependencyInjectionError(Exception):
    pass


class SnowFactory:
    """This is just a way of differentiating Factories from singleton objects.
    This is a proxy object which forward the obj instantiation."""

    def __init__(self, cls: Callable, **dependencies: Depends) -> None:
        self.cls = cls
        self.fastapi_dependencies = dependencies

    def __call__(self) -> Any:
        return self.cls(**self.fastapi_dependencies)


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

        # Singletons types only get called once, so we need
        # a caching mechanism here
        self.cache: dict[type, Any] = dict()

    def __setitem__(self, key: type, value: Any):
        if isinstance(value, SnowFactory):
            self.factories[key] = value
        else:
            self.singletons[key] = value
            if key in self.cache:
                del self.cache[key]

    def __getitem__(self, key: type):
        if key in self.cache:
            # if it is present on cache, then it is a singleton.
            # Return that instance
            return self.cache[key]

        if key in self.singletons:
            # if there exists in singletons but not in cache
            # then this isntance has never been called. Construct
            # it and cache it. It will not be instantiated again
            type_ = self.singletons[key]
            instance = type_()
            self.cache[key] = instance
            return instance

        if key in self.factories:
            return self.factories[key]()

        raise DependencyInjectionError(f"{key} is not registered!")

    def clear(self):
        self.cache.clear()
        self.singletons.clear()
        self.factories.clear()

    def __contains__(self, key: type):
        return key in self.factories or key in self.singletons


# Global Container for the entire application
igloo = IGlooContainer()
