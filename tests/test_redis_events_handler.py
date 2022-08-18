import asyncio
from dataclasses import dataclass
import json
from typing import ClassVar
import pytest
import pytest_asyncio
import aioredis

from wintry.controllers import microservice, on
from wintry.settings import (
    ConnectionOptions,
    TransporterSettings,
    TransporterType,
    WinterSettings,
)
from wintry.transporters.redis import RedisMicroservice
from wintry.transporters.service_container import ServiceContainer


@dataclass
class ChanelPayload(object):
    result: int


@microservice(TransporterType.redis)
class RedisService(object):
    result: ClassVar[int] = 0

    @on("channel")
    async def handle_channel(self, data: ChanelPayload):
        RedisService.result = data.result


@pytest_asyncio.fixture(scope="module", autouse=True)
async def container():
    service_container = ServiceContainer(
        WinterSettings(
            transporters=[
                TransporterSettings(
                    transporter=TransporterType.redis,
                    driver="wintry.transporters.redis",
                    service="RedisMicroservice",
                    connection_options=ConnectionOptions(url="redis://localhost"),
                )
            ]
        )
    )

    service_container.add_service(RedisMicroservice)
    service_container.start_services()
    yield service_container
    await service_container.close()


@pytest.fixture(scope="module")
def redis():
    redis = aioredis.from_url("redis://localhost")
    return redis


@pytest.mark.asyncio
@pytest.mark.skip
async def test_redis_microservice_handle_event(redis: aioredis.Redis, container):
    await redis.publish("channel", json.dumps({"result": 1}))
    await asyncio.sleep(1)

    assert RedisService.result == 1


def test_on_decorator_can_only_be_called_on_methods_with_one_argument():

    with pytest.raises(AssertionError):

        @microservice(TransporterType.redis)
        class DummyService(object):
            @on("dump")  # type: ignore
            def method(self, arg1: str, arg2: str):
                ...
