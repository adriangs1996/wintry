"""
A message dispatcher is a piece of software that knows how to route
Messages (Commands, Queries and Notifications) to handlers. Wintry borrows
some ideas from MediatR in .NET world, and applies the pythonic way of
registering stuff.

Long story short:
    - Command: An Object that triggers an Action with only one handler and that
    do not returns a value.

    - Query: An Object that triggers an Action with only one handler and that returns
    a value.

    -Notification: An object that Triggers an Action with multiple handlers that do not
    returns a value

That being said, this modules is most useful when using CQRS architecture.

One important thing to note, is that action are run in-process, and as so, any
exception will interrupt the main flow. In order to provide asynchronous processing
I will provide integrations with other technologies as Celery or maybe with FastAPI
background tasks.
"""
from dataclasses import dataclass
from inspect import iscoroutinefunction
from typing import TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel
from starlette.concurrency import run_in_threadpool

from wintry import inject
from wintry.ioc.container import igloo

T = TypeVar("T")


class HandlerNotFoundException(Exception):
    ...


class ICommand(BaseModel):
    class Config(object):
        orm_mode = True


class IEvent(BaseModel):
    class Config(object):
        orm_mode = True


class IQuery(GenericModel):
    class Config(object):
        orm_mode = True


class ICommandHandler(object):
    def __init_subclass__(cls, container=igloo):
        cls = dataclass(cls)
        cls = inject(container=container)(cls)
        return cls

    async def handle(self, command: ICommand) -> None:
        ...


class IEventHandler(object):
    def __init_subclass__(cls, container=igloo):
        cls = dataclass(cls)
        cls = inject(container=container)(cls)
        return cls

    async def handle(self, command: IEvent) -> None:
        ...


class IQueryHandler(object):
    def __init_subclass__(cls, container=igloo):
        cls = dataclass(cls)
        cls = inject(container=container)(cls)
        return cls

    async def handle(self, command: IQuery[T]) -> T:
        ...


def command_handler(command: type[ICommand]):
    """
    Decorator to register a Handler for a Command
    Args:
        command:

    Returns:

    """

    def handler_wrapper(handler: type[ICommandHandler]):
        COMMANDS_HANDLERS[command] = handler
        return handler

    return handler_wrapper


def event_handler(event: type[IEvent]):
    def handler_wrapper(handler: type[IEventHandler]):
        if event in EVENTS_HANDLERS:
            EVENTS_HANDLERS[event].append(handler)
        else:
            EVENTS_HANDLERS[event] = [handler]

        return handler

    return handler_wrapper


def query_handler(qry: type[IQuery]):
    """
    Decorator to register a Handler for a Query
    Args:
        qry:

    Returns:

    """

    def handler_wrapper(handler: type[IQueryHandler]):
        QUERY_HANDLERS[qry] = handler
        return handler

    return handler_wrapper


class Mediator(object):
    """
    A mediator is an object that routes and dispatches your messages.
    The Mediator API is async friendly, but you can register non-async
    handlers and it will know what to do (essentially, it will run your
    code in a thread-pool)
    """

    @staticmethod
    async def send(command: ICommand) -> None:
        """Dispatch a command to its Handler.

        Args:
            command: An object that has a registered Handler

        Returns: None

        """
        handler_type = COMMANDS_HANDLERS.get(type(command), None)
        if handler_type is not None:
            handler = handler_type()
            if iscoroutinefunction(handler.handle):
                await handler.handle(command)
            else:
                await run_in_threadpool(handler.handle, command)

        raise HandlerNotFoundException("No handler registered for this command")

    @staticmethod
    async def publish(event: IEvent) -> None:
        """
        Publish an event to be handled by its Handlers

        Args:
            event: An object that represents a notification and has MULTIPLE Handlers

        Returns: None

        """

        for handler_type in EVENTS_HANDLERS.get(type(event), []):
            handler = handler_type()
            if iscoroutinefunction(handler.handle):
                await handler.handle(event)
            else:
                await run_in_threadpool(handler.handle, event)

    @staticmethod
    async def query(qry: IQuery[T]) -> T:
        """
        Dispatch a command to its Handler and returns the result

        Args:
            qry: A object that represents a Query that has ONE Handler

        Returns: An instance of the type of the query

        """
        handler_type = QUERY_HANDLERS.get(type(qry), None)
        if handler_type is not None:
            handler = handler_type()
            if iscoroutinefunction(handler.handle):
                return await handler.handle(qry)
            else:
                return await run_in_threadpool(handler.handle, qry)

        raise HandlerNotFoundException("Not registered handler for this query")


EVENTS_HANDLERS: dict[type[IEvent], list[type[IEventHandler]]] = {}
COMMANDS_HANDLERS: dict[type[ICommand], type[ICommandHandler]] = {}
QUERY_HANDLERS: dict[type[IQuery], type[IQueryHandler]] = {}
