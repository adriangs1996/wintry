from abc import ABC
import asyncio
from dataclasses import dataclass
from functools import wraps
from inspect import isclass
from typing import Any, Callable, NewType, Protocol, TypeVar, overload
import inspect
from wintry.ioc.container import SnowFactory, igloo

from wintry.ioc.container import IGlooContainer


class ExecutionError(Exception):
    pass


T = TypeVar("T")


TDecorated = (
    Callable[[type[T]], type[T]] | Callable[[Callable[..., Any]], Callable[..., Any]]
)

Undefined = NewType("Undefined", int)


class ProtocolInit(Protocol):
    pass


@dataclass
class ParameterInfo:
    name: str
    type: Any
    default: Any = Undefined


NameTupleAndParameterMapping = tuple[tuple[str, ...], dict[str, ParameterInfo]]


def _inspect_function_arguments(function: Callable) -> NameTupleAndParameterMapping:
    # Get a mapping of parameters name and a handy
    # Parameter information
    params = inspect.signature(function)
    parameters_name: tuple[str, ...] = tuple(params.parameters.keys())
    parameters = {}

    for name, parameter in params.parameters.items():
        parameters[name] = ParameterInfo(
            parameter.name,
            parameter.annotation,
            parameter.default
            if parameter.default is not inspect.Parameter.empty
            else Undefined,
        )

    return parameters_name, parameters


@overload
def inject(service: type[T]) -> type[T]:
    ...


@overload
def inject(service: Callable[..., Any]) -> Callable[..., Any]:
    ...


@overload
def inject(*, container: IGlooContainer = igloo) -> TDecorated:
    ...


def inject(service: Any = None, /, *, container: IGlooContainer = igloo) -> Any:
    def decorator(srvc: Any):
        if isclass(srvc):
            # If the service we wanna inject objects is a class, then
            # we must decorate the __init__ function

            # Just ignore if this is something like a protocol or an ABC
            # IDK why you could @inject such an interface, but I'm not
            # here to judge
            setattr(srvc, "__init__", decorate(getattr(srvc, "__init__"), container))
            return srvc

        else:
            return decorate(srvc, container)

    if service is None:
        return decorator

    return decorator(service)


def resolve(
    parameters_name: tuple[str, ...],
    parameters: dict[str, ParameterInfo],
    igloo: IGlooContainer,
):
    resolved_kwargs = {}
    for name in parameters_name:
        # This might seems counterintuitive at first. I mean, why in
        # the world am I ignoring default parameters ? Think about it,
        # The main reason of using the DI Container is not to pass parameters, or
        # better yet, to choose which parameters I want to pass to my constructor,
        # and let him handle the rest. This is actually pretty big, because it would
        # allow me to merge FastAPI Depends() API with the builtin DI API. This
        # means that we can, if correctly implemented, bypass the restriction of
        # using Depends() at Router lvl and not be able to access the results
        # at endpoints implementations, or worse, having to duplicate the Depends
        # where we need the result. This is a really big deal for the entire point
        # of the framework, and is actually why I switch to a hand made Container
        # implementation.

        # A big NOTE: We ignore only parameters with a Default, NOT KEYWORD ARGS,
        # it might be subtle, but actually the difference matters a lot. the @controller
        # decorator already transforms the __init__ function into a KEYWORD_ONLY
        # function, so careful there.
        if parameters[name].type in igloo and parameters[name].default is Undefined:
            resolved_kwargs[name] = igloo[parameters[name].type]
            continue

        if parameters[name].default is not Undefined:
            resolved_kwargs[name] = parameters[name].default

    return resolved_kwargs


def decorate(func: Callable[..., Any], igloo: IGlooContainer):
    if func in (ABC.__init__, ProtocolInit.__init__):
        return func

    parameters_name, parameters = _inspect_function_arguments(func)

    # This is very standard DI Container Stuff

    def _resolve_kwargs(args, kwargs) -> dict:
        # attach named arguments
        passed_kwargs = {**kwargs}

        # resolve positional arguments
        if args:
            for key, value in enumerate(args):
                passed_kwargs[parameters_name[key]] = value

        # prioritise passed kwargs and args resolving
        if len(passed_kwargs) == len(parameters_name):
            return passed_kwargs

        resolved_kwargs = resolve(parameters_name, parameters, igloo)

        all_kwargs = {**resolved_kwargs, **passed_kwargs}

        if len(all_kwargs) < len(parameters_name):
            missing_parameters = [arg for arg in parameters_name if arg not in all_kwargs]
            raise ExecutionError(
                "Cannot execute function without required parameters. "
                + f"Did you forget to bind the following parameters: `{'`, `'.join(missing_parameters)}` for {str(func)}?"
            )

        return all_kwargs

    @wraps(func)
    def _decorated(*args, **kwargs):
        # all arguments were passed
        if len(args) == len(parameters_name):
            return func(*args, **kwargs)

        # all arguments were keywords an were passed
        if parameters_name == tuple(kwargs.keys()):
            return func(**kwargs)

        # We may have mixing parameters
        all_kwargs = _resolve_kwargs(args, kwargs)
        return func(**all_kwargs)

    @wraps(func)
    async def _async_decorated(*args, **kwargs):
        # all arguments were passed
        if len(args) == len(parameters_name):
            return await func(*args)

        if parameters_name == tuple(kwargs.keys()):
            return await func(**kwargs)

        all_kwargs = _resolve_kwargs(args, kwargs)
        return await func(**all_kwargs)

    if asyncio.iscoroutinefunction(func):
        return _async_decorated

    return _decorated


@overload
def provider(cls: type[T], /) -> type[T]:
    ...


@overload
def provider(cls: Callable[..., T], /) -> Callable[..., T]:
    ...


@overload
def provider(
    cls: None, /
) -> Callable[[type[T] | Callable[..., T]], type[T] | Callable[..., T]]:
    ...

I = TypeVar("I")

@overload
def provider(
    *,
    of: type[I] | None = None,
    singleton: bool = True,
    container: IGlooContainer = igloo,
) -> Callable[[type[T] | Callable[..., T]], type[T]]:
    ...


def provider(
    cls: Any = None,
    /,
    *,
    of: type | None = None,
    singleton: bool = True,
    container: IGlooContainer = igloo,
):
    def decorator(_cls: Any):
        if isclass(_cls):
            _cls = dataclass(
                eq=False,
                order=False,
                frozen=False,
                match_args=False,
                init=True,
                kw_only=False,
                repr=False,
                unsafe_hash=False,
            )(_cls)
        _cls = inject(container=container)(_cls)

        if of is None:
            key = _cls
        else:
            key = of

        if singleton:
            container[key] = _cls
        else:
            container[key] = SnowFactory(_cls)

        return _cls

    if cls is None:
        return decorator

    else:
        return decorator(cls)
