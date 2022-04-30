from dataclasses import dataclass, field
import pytest


@dataclass
class SumCommand:
    numbers: list[int] = field(default_factory=list)


@dataclass
class SumWithBias:
    bias: int
    numbers: list[int] = field(default_factory=list)


@dataclass
class Summed:
    result: int


@dataclass
class FinishedSum:
    bias: int


class TestMessageQueue(MessageQueue):

    # Normaly, message queues does not store
    # results, but this comes in handy in testing
    # scenarios
    result: int = 0

    @command_handler
    async def sum(self, command: SumCommand):
        result = sum(command.numbers)
        self.emit_event(Summed(result))

    @command_handler
    async def sum_with_bias(self, command: SumWithBias):
        result = sum(command.numbers)
        self.emit_event(Summed(result))
        self.emit_event(FinishedSum(command.bias))

    @event_handler
    async def summed(self, event: Summed):
        self.result = event.result

    @event_handler
    async def finished_sum(self, event: FinishedSum):
        self.result += event.bias


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
