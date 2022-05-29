import json
from typing import Protocol
from wintry.ioc import provider
import aioredis


class Publisher(Protocol):
    async def send(self, channel: str, data: dict):
        ...


@provider(of=Publisher)
class RedisPublisher(Publisher):
    def __init__(self) -> None:
        self.client = aioredis.from_url("redis://localhost")

    async def send(self, channel: str, data: dict):
        await self.client.publish(channel, json.dumps(data))
