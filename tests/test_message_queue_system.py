from pydantic import  Field
import pytest
from wintry.mqs import (
    MessageQueue,
    Event,
    Command,
    command_handler,
    event_handler,
)


class SumCommand(Command):
    numbers: list[int] = Field(default_factory=list)


class SumWithBias(Command):
    bias: int
    numbers: list[int] = Field(default_factory=list)


class SumWithTwoEvents(Command):
    numbers: list[int] = Field(default_factory=list)


class Summed(Event):
    result: int


class FinishedSum(Event):
    bias: int


class DoneSum(Event):
    result: int


class SleepCalled(Event):
    seconds: int


class TestMessageQueue(MessageQueue):

    # Normaly, message queues does not store
    # results, but this comes in handy in testing
    # scenarios
    result: int = 0

    @command_handler
    def sum(self, command: SumCommand):
        result = sum(command.numbers)
        self.register(Summed(result=result))

    @command_handler
    async def sum_with_two_events(self, command: SumWithTwoEvents):
        result = sum(command.numbers)
        self.register(DoneSum(result=result))

    @command_handler
    async def sum_with_bias(self, command: SumWithBias):
        result = sum(command.numbers)
        self.register(Summed(result=result))
        self.register(FinishedSum(bias=command.bias))

    @event_handler
    def summed(self, event: Summed):
        self.result = event.result

    @event_handler
    async def finished_sum(self, event: FinishedSum):
        self.result += event.bias

    # Multiple handlers for same event
    @event_handler
    def store_result_after_sum(self, event: DoneSum):
        self.result = event.result

    @event_handler
    async def add_bias_to_result_after_sum(self, event: DoneSum):
        self.result += event.result


@pytest.mark.asyncio
async def test_mqs_can_handle_defined_command():
    mq = TestMessageQueue()
    command = SumCommand(numbers=[1, 2, 3, 4, 5])
    await mq.handle(command)
    assert mq.result == 15


@pytest.mark.asyncio
async def test_mqs_cand_handle_multiple_events_on_one_command():
    mq = TestMessageQueue()
    command = SumWithBias(numbers=[1, 2, 3, 4, 5], bias=10)
    await mq.handle(command)
    assert mq.result == 25


@pytest.mark.asyncio
async def test_mqs_fires_multiple_handlers_for_same_event():
    mq = TestMessageQueue()
    command = SumWithTwoEvents(numbers=[1, 2, 3, 4, 5])
    await mq.handle(command)
    assert mq.result == 30
