from functools import update_wrapper
from inspect import iscoroutine, iscoroutinefunction, signature
from typing import Any, Callable, Coroutine, TypeVar, overload
from pydantic import BaseModel


class EventRegistrationError(Exception):
    pass


class CommandRegistrationError(Exception):
    pass


class Command(BaseModel):
    pass


class Event(BaseModel):
    pass


_TQueue = TypeVar("_TQueue", bound="MessageQueue")
_TCommand = TypeVar("_TCommand", bound=Command)
_TEvent = TypeVar("_TEvent", bound=Event)
EventHandler = (
    Callable[[_TQueue, _TEvent], None]
    | Callable[[_TQueue, _TEvent], Coroutine[None, None, None]]
)
CommandHandler = (
    Callable[[_TQueue, _TCommand], None]
    | Callable[[_TQueue, _TCommand], Coroutine[None, None, None]]
)
Message = Command | Event


__event_handlers__: dict[type[Event], list[EventHandler]] = {}
__command_handlers__: dict[type[Command], list[CommandHandler]] = {}


class MessageQueue:
    def __init__(self) -> None:
        self._message_queue: list[Message] = []

    async def handle(self, cmd: Message):
        self._message_queue = [cmd]
        messages_queue = self._message_queue
        while messages_queue:
            msg = messages_queue.pop(0)
            if isinstance(msg, Event):
                try:
                    await self.handle_event(msg)
                except:
                    pass
            else:
                try:
                    await self.handle_command(msg)
                except Exception as e:
                    messages_queue.clear()
                    raise e

            await self.collect_new_messages(messages_queue)

    async def collect_new_messages(self, messages: list[Message]):
        pass

    def register(self, message: Message):
        self._message_queue.append(message)

    async def handle_event(self, event: Event):
        handlers = __event_handlers__.get(type(event), [])
        for handler in handlers:
            try:
                if iscoroutinefunction(handler):
                    await handler(self, event)  # type: ignore
                else:
                    handler(self, event)
            except:
                pass

    async def handle_command(self, cmd: Command):
        handlers = __command_handlers__.get(type(cmd), [])
        for handler in handlers:
            result = handler(self, cmd)
            if iscoroutine(result):
                await result


@overload
def event_handler(
    fn: None, _type: type[_TEvent] | None = None
) -> Callable[
    [Callable[[_TQueue, _TEvent], None]], Callable[[_TQueue, _TEvent], None]
] | Callable[
    [Callable[[_TQueue, _TEvent], Coroutine[_TQueue, _TQueue, None]]],
    Callable[[_TQueue, _TEvent], Coroutine[Any, Any, None]],
]:
    ...


@overload
def event_handler(
    fn: Callable[[_TQueue, _TEvent], None], _type: type[_TEvent] | None = None
) -> Callable[[_TQueue, _TEvent], None]:
    ...


@overload
def event_handler(
    fn: Callable[[_TQueue, _TEvent], Coroutine[Any, Any, None]],
    _type: type[_TEvent] | None = None,
) -> Callable[[_TQueue, _TEvent], Coroutine[Any, Any, None]]:
    ...


def event_handler(
    fn: Callable[[_TQueue, _TEvent], None]
    | Callable[[_TQueue, _TEvent], Coroutine[Any, Any, None]]
    | None = None,
    /,
    _type: type[_TEvent] | None = None,
) -> Callable[[_TQueue, _TEvent], None] | Callable[
    [Callable[[_TQueue, _TEvent], None]], Callable[[_TQueue, _TEvent], None]
] | Callable[[_TQueue, _TEvent], Coroutine[Any, Any, None]] | Callable[
    [Callable[[_TQueue, _TEvent], Coroutine[Any, Any, None]]],
    Callable[[_TQueue, _TEvent], Coroutine[None, None, None]],
]:
    def wrapper(
        func: Callable[[_TQueue, _TEvent], None]
        | Callable[[_TQueue, _TEvent], Coroutine[None, None, None]]
    ) -> Callable[[_TQueue, _TEvent], None] | Callable[
        [_TQueue, _TEvent], Coroutine[None, None, None]
    ]:
        if _type is None:
            sig = signature(func)
            parameters = sig.parameters
            _self = parameters.get("self", None)
            if _self is None:
                raise EventRegistrationError(
                    f"event_handler should be called on a MessageQueue instance method"
                )

            param = list(parameters.values())[1:]
            if len(param) != 1:
                raise EventRegistrationError(
                    "event_handler should be called on an instance method that only receives the event as parameter"
                )

            t = param[0].annotation

            if not issubclass(t, Event):
                raise EventRegistrationError(
                    f"Argument {param[0]} must be annotated with a subclass of Event"
                )
        else:
            t = _type

        try:
            __event_handlers__[t].append(func)  # type: ignore
        except:
            __event_handlers__[t] = [func]  # type: ignore

        update_wrapper(wrapper, func)
        return func

    if fn is None:
        return wrapper  # type: ignore
    else:
        return wrapper(fn)


@overload
def command_handler(
    fn: None, _type: type[_TCommand] | None = None
) -> Callable[
    [Callable[[_TQueue, _TCommand], None]], Callable[[_TQueue, _TCommand], None]
] | Callable[
    [Callable[[_TQueue, _TCommand], Coroutine[_TQueue, _TQueue, None]]],
    Callable[[_TQueue, _TCommand], Coroutine[Any, Any, None]],
]:
    ...


@overload
def command_handler(
    fn: Callable[[_TQueue, _TCommand], None], _type: type[_TCommand] | None = None
) -> Callable[[_TQueue, _TCommand], None]:
    ...


@overload
def command_handler(
    fn: Callable[[_TQueue, _TCommand], Coroutine[Any, Any, None]],
    _type: type[_TCommand] | None = None,
) -> Callable[[_TQueue, _TCommand], Coroutine[Any, Any, None]]:
    ...


def command_handler(
    fn: Callable[[_TQueue, _TCommand], None]
    | Callable[[_TQueue, _TCommand], Coroutine[Any, Any, None]]
    | None = None,
    /,
    _type: type[_TCommand] | None = None,
) -> Callable[[_TQueue, _TCommand], None] | Callable[
    [Callable[[_TQueue, _TCommand], None]], Callable[[_TQueue, _TCommand], None]
] | Callable[[_TQueue, _TCommand], Coroutine[Any, Any, None]] | Callable[
    [Callable[[_TQueue, _TCommand], Coroutine[Any, Any, None]]],
    Callable[[_TQueue, _TCommand], Coroutine[None, None, None]],
]:
    def wrapper(
        func: Callable[[_TQueue, _TCommand], None]
        | Callable[[_TQueue, _TCommand], Coroutine[None, None, None]]
    ) -> Callable[[_TQueue, _TCommand], None] | Callable[
        [_TQueue, _TCommand], Coroutine[None, None, None]
    ]:
        if _type is None:
            sig = signature(func)
            parameters = sig.parameters
            _self = parameters.get("self", None)
            if _self is None:
                raise CommandRegistrationError(
                    f"event_handler should be called on a MessageQueue instance method"
                )

            param = list(parameters.values())[1:]
            if len(param) != 1:
                raise CommandRegistrationError(
                    "event_handler should be called on an instance method that only receives the event as parameter"
                )

            t = param[0].annotation

            if not issubclass(t, Command):
                raise CommandRegistrationError(
                    f"Argument {param[0]} must be annotated with a subclass of Event"
                )
        else:
            t = _type

        try:
            __command_handlers__[t].append(func)  # type: ignore
        except:
            __command_handlers__[t] = [func]  # type: ignore

        update_wrapper(wrapper, func)
        return func

    if fn is None:
        return wrapper  # type: ignore
    else:
        return wrapper(fn)
