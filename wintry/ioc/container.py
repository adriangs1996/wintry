from asyncio import iscoroutinefunction
from contextlib import contextmanager, asynccontextmanager
from contextvars import ContextVar, Token
from typing import Any, Callable, TypeVar
from fastapi.params import Depends
from starlette.concurrency import run_in_threadpool

T = TypeVar("T")

# This would be used to define scoped dependencies. Scoped dependencies are
# singletons for an event lifecycle (like a web request) so the container
# is in charge of initializing and disposing it
_context_bounded_dependencies: ContextVar[dict[type, Any]] = ContextVar(
    "scoped_dependencies", default={}
)
_in_scope: ContextVar[bool] = ContextVar("igloo_in_scope", default=False)


class DependencyInjectionError(Exception):
    pass


class SnowFactory(object):
    """This is just a way of differentiating Factories from singleton objects.
    This is a proxy object which forward the obj instantiation."""

    def __init__(self, cls: Callable, **dependencies: Depends) -> None:
        self.cls = cls
        self.fastapi_dependencies = dependencies

    def __call__(self) -> Any:
        return self.cls(**self.fastapi_dependencies)


class IGlooContainer(object):
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

        # This are request Scoped dependencies. These is needed to
        # provide a way of handling the dependency lifecycle beyond
        # the call moment. We define the lifecycle of these dependencies
        # inside a context manager, and allows implementations to
        # bound the dependencies to a particular event (for example,
        # when a web server start handling a request).
        # We maintain request dependencies inside a separate dict
        # so we can inject them inside the singleton part while inside
        # the context manager and remove them when the context manager
        # exits
        self.request_dependencies: dict[type, Any] = dict()

    @asynccontextmanager
    async def scoped(self):
        # Prepare the scoped context for dependency injection
        # It is important that this method gets called once for
        # each async context, so it might be a good candidate
        # for a middleware
        token_context = _context_bounded_dependencies.set({})
        token_flag = _in_scope.set(True)
        try:
            yield
        finally:
            # Try to clean the context objects
            context = _context_bounded_dependencies.get()
            for dep in context.values():
                if hasattr(dep, "dispose"):
                    dispose_method = getattr(dep, "dispose")
                    if iscoroutinefunction(dispose_method):
                        await dispose_method()
                    else:
                        await run_in_threadpool(dispose_method)
            _context_bounded_dependencies.reset(token_context)
            _in_scope.reset(token_flag)

    def add_scoped(self, interface: type, implementer: Any):
        factory = SnowFactory(implementer)
        self.request_dependencies[interface] = factory

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
            # then this instance has never been called. Construct
            # it and cache it. It will not be instantiated again
            type_ = self.singletons[key]
            instance = type_()
            self.cache[key] = instance
            return instance

        # If container is running inside a scoped context, then
        # scoped dependencies are prioritized over transient ones
        if _in_scope.get():
            context = _context_bounded_dependencies.get()
            # treat context as a scoped cache
            if key in context:
                return context[key]

            if key in self.request_dependencies:
                constructor = self.request_dependencies[key]
                instance = constructor()
                context[key] = instance
                return instance

        if key in self.factories:
            return self.factories[key]()

        raise DependencyInjectionError(f"{key} is not registered!")

    def clear(self):
        self.cache.clear()
        self.singletons.clear()
        self.factories.clear()

    def __contains__(self, key: type):
        return (
            key in self.factories
            or key in self.singletons
            or key in self.request_dependencies
        )


# Global Container for the entire application
igloo = IGlooContainer()
